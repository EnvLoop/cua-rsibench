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

    def permissions_empty(self, *, owner_user_id: str,
                          drive_id: str, item_id: str) -> dict:
        """Verify the prior one-file actor grant was removed by the owner."""
        self.preflight()
        _require(all(type(value) is str and _IDENTIFIER.fullmatch(value)
                     for value in (owner_user_id, drive_id, item_id)),
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
                     response.json().get('value') == [],
                     'graph_actor_permission_still_present')
        finally:
            client.close()
        return {'schema': 'cua-office-ppt-owner-revocation-readback-v1',
                'owner_user_id_sha256': _sha(owner_user_id),
                'drive_id_sha256': _sha(drive_id),
                'item_id_sha256': _sha(item_id),
                'permissions_count': 0}
