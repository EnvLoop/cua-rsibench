"""Evaluator exact-item Graph readback for Excel selection `.xlsx` copies."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
from urllib.parse import quote

from tools.office_web_excel_graph_readback_v1 import ExcelGraphOwnerReadback
from tools.office_web_ppt_graph_readback_v1 import (
    _IDENTIFIER, _require, _sha, _write_new, MAX_PPTX_BYTES,
)


class SelectionExcelGraphOwnerReadback(ExcelGraphOwnerReadback):
    def capture(self, *, owner_user_id: str, drive_id: str,
                item_id: str, expected_name: str,
                out_dir: Path) -> dict:
        self.preflight()
        _require(all(type(value) is str and _IDENTIFIER.fullmatch(value)
                     for value in (owner_user_id, drive_id, item_id)) and
                 type(expected_name) is str and
                 re.fullmatch(
                     r'EL-Excel-Selection-[A-Za-z0-9._-]{1,100}\.xlsx',
                     expected_name) is not None and
                 isinstance(out_dir, Path) and out_dir.is_dir() and
                 not out_dir.is_symlink() and
                 out_dir.stat().st_mode & 0o077 == 0,
                 'graph_exact_excel_selection_item_required')
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
                     'graph_excel_selection_token_not_owner')
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
                 first == second and 0 < len(first) <= MAX_PPTX_BYTES,
                 'graph_excel_selection_downloads_or_metadata_changed')
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
