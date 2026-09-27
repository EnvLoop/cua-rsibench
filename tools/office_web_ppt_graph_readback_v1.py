"""Evaluator-owned, read-only Graph download of one exact PowerPoint item.

The actor never receives this client or its delegated owner token. Metadata
and two independent `/content` downloads must agree before bytes can enter a
saved-state verifier. Graph's preauthenticated redirect is fetched without an
Authorization header. This module cannot create, edit, or share a drive item.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
from urllib.parse import quote, urlsplit


MAX_PPTX_BYTES = 50_000_000
_IDENTIFIER = re.compile(r'[A-Za-z0-9!._:-]{4,180}\Z')


class GraphReadbackError(ValueError):
    pass


def _require(value: bool, code: str) -> None:
    if not value:
        raise GraphReadbackError(code)


def _sha(raw: bytes | str) -> str:
    return hashlib.sha256(raw if isinstance(raw, bytes) else raw.encode()).hexdigest()


def _write_new(path: Path, raw: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def _redirect_url(value: object) -> str:
    _require(type(value) is str and len(value) <= 8192,
             'graph_download_redirect_invalid')
    parsed = urlsplit(value)
    host = parsed.hostname
    _require(parsed.scheme == 'https' and host is not None and
             parsed.username is None and parsed.password is None and
             parsed.port in (None, 443) and not parsed.fragment and
             host != 'localhost' and '.' in host,
             'graph_download_redirect_invalid')
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise GraphReadbackError('graph_download_redirect_ip_forbidden')
    return value


class GraphOwnerReadback:
    """Uses a delegated owner token supplied only through the host environment."""

    def __init__(self, *, client_factory=None):
        self.client_factory = client_factory

    def preflight(self) -> None:
        _require(bool(os.environ.get('MS_GRAPH_OWNER_TOKEN')),
                 'graph_owner_token_missing_before_reservation')

    def _client(self):
        if self.client_factory is not None:
            return self.client_factory()
        import httpx
        return httpx.Client(timeout=httpx.Timeout(30, connect=10),
                            follow_redirects=False)

    @staticmethod
    def _metadata(client, base: str, headers: dict, *,
                  owner_user_id: str, drive_id: str, item_id: str,
                  expected_name: str) -> dict:
        response = client.get(base, headers=headers,
                              params={'$select':
                                      'id,name,eTag,cTag,size,parentReference,file'})
        _require(response.status_code == 200,
                 'graph_item_metadata_unavailable')
        value = response.json()
        _require(type(value) is dict and value.get('id') == item_id and
                 value.get('name') == expected_name and
                 type(value.get('file')) is dict and
                 value['file'].get('mimeType') ==
                 'application/vnd.openxmlformats-officedocument.presentationml.presentation' and
                 type(value.get('parentReference')) is dict and
                 value['parentReference'].get('driveId') == drive_id and
                 type(value.get('eTag')) is str and value['eTag'] and
                 type(value.get('size')) is int and
                 0 < value['size'] <= MAX_PPTX_BYTES,
                 'graph_item_identity_or_size_changed')
        return value

    @staticmethod
    def _content(client, url: str, headers: dict) -> bytes:
        response = client.get(url + '/content', headers=headers)
        _require(response.status_code == 302,
                 'graph_content_did_not_return_preauthed_redirect')
        redirect = _redirect_url(response.headers.get('Location'))
        # A Graph download URL is preauthenticated. Never forward the owner
        # bearer token to a redirected host.
        with client.stream('GET', redirect, headers={}) as downloaded:
            _require(downloaded.status_code == 200,
                     'graph_preauthed_download_failed')
            chunks = []
            size = 0
            for chunk in downloaded.iter_bytes():
                size += len(chunk)
                _require(size <= MAX_PPTX_BYTES,
                         'graph_download_exceeds_pptx_limit')
                chunks.append(chunk)
        data = b''.join(chunks)
        _require(bool(data), 'graph_download_empty')
        return data

    def capture(self, *, owner_user_id: str, drive_id: str,
                item_id: str, expected_name: str,
                out_dir: Path) -> dict:
        self.preflight()
        _require(all(type(value) is str and _IDENTIFIER.fullmatch(value)
                     for value in (owner_user_id, drive_id, item_id)) and
                 type(expected_name) is str and
                 re.fullmatch(r'EL-PPT-Train-[A-Za-z0-9._-]+\.pptx',
                              expected_name) is not None and
                 isinstance(out_dir, Path) and out_dir.is_dir() and
                 not out_dir.is_symlink() and
                 out_dir.stat().st_mode & 0o077 == 0,
                 'graph_exact_train_item_binding_required')
        token = os.environ['MS_GRAPH_OWNER_TOKEN']
        headers = {'Authorization': 'Bearer ' + token}
        base = ('https://graph.microsoft.com/v1.0/drives/' +
                quote(drive_id, safe='') + '/items/' + quote(item_id, safe=''))
        client = self._client()
        try:
            me = client.get('https://graph.microsoft.com/v1.0/me',
                            headers=headers, params={'$select': 'id'})
            _require(me.status_code == 200 and
                     type(me.json()) is dict and
                     me.json().get('id') == owner_user_id,
                     'graph_token_not_owner')
            first_meta = self._metadata(
                client, base, headers, owner_user_id=owner_user_id,
                drive_id=drive_id, item_id=item_id,
                expected_name=expected_name)
            first = self._content(client, base, headers)
            middle_meta = self._metadata(
                client, base, headers, owner_user_id=owner_user_id,
                drive_id=drive_id, item_id=item_id,
                expected_name=expected_name)
            second = self._content(client, base, headers)
            last_meta = self._metadata(
                client, base, headers, owner_user_id=owner_user_id,
                drive_id=drive_id, item_id=item_id,
                expected_name=expected_name)
        finally:
            client.close()
        _require(first_meta['eTag'] == middle_meta['eTag'] ==
                 last_meta['eTag'] and
                 first_meta['size'] == middle_meta['size'] ==
                 last_meta['size'] == len(first) == len(second) and
                 first == second,
                 'graph_two_downloads_or_metadata_changed')
        first_path = out_dir / 'first.private.pptx'
        second_path = out_dir / 'second.private.pptx'
        _write_new(first_path, first)
        _write_new(second_path, second)
        receipt = {
            'schema': 'cua-office-ppt-owner-double-download-v1',
            'owner_user_id_sha256': _sha(owner_user_id),
            'drive_id_sha256': _sha(drive_id),
            'item_id_sha256': _sha(item_id),
            'name_sha256': _sha(expected_name),
            'etag_sha256': _sha(first_meta['eTag']),
            'first_sha256': _sha(first),
            'second_sha256': _sha(second),
            'byte_count': len(first),
        }
        _write_new(out_dir / 'readback.private.json',
                   (json.dumps(receipt, sort_keys=True,
                               separators=(',', ':')) + '\n').encode())
        return receipt

    @staticmethod
    def _revoked_permissions(value: object, *, owner_user_id: str,
                             actor_email: str,
                             prior_permission_id: str) -> dict:
        """Preserve owner/inherited entries while rejecting actor or broad grants.

        Graph lists *effective* permissions. An empty collection is therefore
        not a valid general post-revocation requirement. Unknown direct grants
        and specific-user sharing links fail closed because they could retain
        actor access without exposing an invitation email.
        """
        _require(type(value) is list and len(value) <= 1000 and
                 type(actor_email) is str and actor_email and
                 type(prior_permission_id) is str and prior_permission_id,
                 'graph_permission_response_invalid')
        owner_count = inherited_count = existing_access_link_count = 0
        for permission in value:
            _require(type(permission) is dict and
                     type(permission.get('id')) is str and
                     permission['id'],
                     'graph_permission_response_invalid')
            roles = permission.get('roles')
            _require(type(roles) is list and
                     all(type(role) is str for role in roles),
                     'graph_permission_response_invalid')
            _require(permission['id'] != prior_permission_id,
                     'graph_prior_actor_permission_still_present')
            link = permission.get('link')
            if link is not None:
                _require(type(link) is dict and
                         link.get('scope') == 'existingAccess',
                         'graph_broad_or_unidentified_link_present')
                existing_access_link_count += 1
            emails = []
            invitation = permission.get('invitation')
            if invitation is not None:
                _require(type(invitation) is dict and
                         type(invitation.get('email')) is str,
                         'graph_permission_response_invalid')
                emails.append(invitation['email'])
            owner_identity = False
            for name in ('grantedToV2', 'grantedTo'):
                identity = permission.get(name)
                if identity is None:
                    continue
                _require(type(identity) is dict,
                         'graph_permission_response_invalid')
                user = identity.get('user')
                if user is not None:
                    _require(type(user) is dict,
                             'graph_permission_response_invalid')
                    owner_identity |= user.get('id') == owner_user_id
                    if type(user.get('email')) is str:
                        emails.append(user['email'])
            for name in ('grantedToIdentitiesV2', 'grantedToIdentities'):
                identities = permission.get(name)
                if identities is None:
                    continue
                _require(type(identities) is list,
                         'graph_permission_response_invalid')
                for identity in identities:
                    _require(type(identity) is dict and
                             type(identity.get('user')) is dict,
                             'graph_permission_response_invalid')
                    user = identity['user']
                    owner_identity |= user.get('id') == owner_user_id
                    if type(user.get('email')) is str:
                        emails.append(user['email'])
            _require(all(email.casefold() != actor_email.casefold()
                         for email in emails),
                     'graph_actor_identity_still_granted')
            inherited = permission.get('inheritedFrom') is not None
            if inherited:
                _require(type(permission['inheritedFrom']) is dict,
                         'graph_permission_response_invalid')
                inherited_count += 1
                continue
            if link is not None:
                # existingAccess does not grant a new principal access.
                continue
            _require(owner_identity or 'owner' in roles,
                     'graph_unknown_direct_grant_after_revocation')
            owner_count += 1
        return {'remaining_permission_count': len(value),
                'owner_permission_count': owner_count,
                'inherited_permission_count': inherited_count,
                'existing_access_link_count': existing_access_link_count}

    def verify_actor_revoked(self, *, owner_user_id: str,
                             drive_id: str, item_id: str,
                             actor_email: str,
                             prior_permission_id: str) -> dict:
        """Verify the exact actor grant is gone without requiring an empty list."""
        self.preflight()
        _require(all(type(value) is str and _IDENTIFIER.fullmatch(value)
                     for value in (owner_user_id, drive_id, item_id)) and
                 type(actor_email) is str and
                 type(prior_permission_id) is str,
                 'graph_permission_item_binding_invalid')
        token = os.environ['MS_GRAPH_OWNER_TOKEN']
        headers = {'Authorization': 'Bearer ' + token}
        base = ('https://graph.microsoft.com/v1.0/drives/' +
                quote(drive_id, safe='') + '/items/' + quote(item_id, safe=''))
        client = self._client()
        try:
            me = client.get('https://graph.microsoft.com/v1.0/me',
                            headers=headers, params={'$select': 'id'})
            _require(me.status_code == 200 and
                     type(me.json()) is dict and
                     me.json().get('id') == owner_user_id,
                     'graph_token_not_owner')
            response = client.get(base + '/permissions', headers=headers)
            _require(response.status_code == 200 and
                     type(response.json()) is dict and
                     response.json().get('@odata.nextLink') is None,
                     'graph_permission_response_invalid_or_paginated')
            audit = self._revoked_permissions(
                response.json().get('value'),
                owner_user_id=owner_user_id,
                actor_email=actor_email,
                prior_permission_id=prior_permission_id)
        finally:
            client.close()
        return {'schema': 'cua-office-ppt-owner-revocation-readback-v1',
                'owner_user_id_sha256': _sha(owner_user_id),
                'drive_id_sha256': _sha(drive_id),
                'item_id_sha256': _sha(item_id),
                'actor_email_sha256': _sha(actor_email.casefold()),
                'prior_permission_id_sha256': _sha(prior_permission_id),
                'actor_grants_remaining': 0,
                'broad_links_remaining': 0,
                **audit}
