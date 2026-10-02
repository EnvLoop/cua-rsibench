"""Evaluator-only Graph double download of one exact Excel training item.

The actor cannot call this client. It reuses the PowerPoint Graph transport and
identity-bound permission audit while pinning Excel's MIME/name and `.xlsx`
bytes. Neither workbook contents nor bearer token enter model observations.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
from urllib.parse import quote

from tools.office_web_ppt_graph_readback_v1 import (
    GraphOwnerReadback, _IDENTIFIER, _require, _sha, _write_new,
    MAX_PPTX_BYTES,
)


MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


class ExcelGraphOwnerReadback(GraphOwnerReadback):
    @staticmethod
    def _metadata(client, base: str, headers: dict, *,
                  owner_user_id: str, drive_id: str, item_id: str,
                  expected_name: str) -> dict:
        response = client.get(base, headers=headers,
                              params={'$select':
                                      'id,name,eTag,cTag,size,parentReference,file'})
        _require(response.status_code == 200,
                 'graph_excel_item_metadata_unavailable')
        value = response.json()
        _require(type(value) is dict and value.get('id') == item_id and
                 value.get('name') == expected_name and
                 type(value.get('file')) is dict and
                 value['file'].get('mimeType') == MIME and
                 type(value.get('parentReference')) is dict and
                 value['parentReference'].get('driveId') == drive_id and
                 type(value.get('eTag')) is str and value['eTag'] and
                 type(value.get('size')) is int and
                 0 < value['size'] <= MAX_PPTX_BYTES,
                 'graph_excel_item_identity_or_size_changed')
        return value

    def capture(self, *, owner_user_id: str, drive_id: str,
                item_id: str, expected_name: str,
                out_dir: Path) -> dict:
        self.preflight()
        _require(all(type(value) is str and _IDENTIFIER.fullmatch(value)
                     for value in (owner_user_id, drive_id, item_id)) and
                 type(expected_name) is str and
                 re.fullmatch(r'EL-Excel-Train-[A-Za-z0-9._-]{1,100}\.xlsx',
                              expected_name) is not None and
                 isinstance(out_dir, Path) and out_dir.is_dir() and
                 not out_dir.is_symlink() and
                 out_dir.stat().st_mode & 0o077 == 0,
                 'graph_exact_excel_train_item_binding_required')
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
                     'graph_excel_token_not_owner')
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
                 'graph_excel_two_downloads_or_metadata_changed')
        first_path = out_dir / 'first.private.xlsx'
        second_path = out_dir / 'second.private.xlsx'
        _write_new(first_path, first)
        _write_new(second_path, second)
        receipt = {
            'schema': 'cua-office-excel-owner-double-download-v1',
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

    def verify_actor_revoked(self, **kwargs) -> dict:
        result = super().verify_actor_revoked(**kwargs)
        return {**result,
                'schema': 'cua-office-excel-owner-revocation-readback-v1'}
