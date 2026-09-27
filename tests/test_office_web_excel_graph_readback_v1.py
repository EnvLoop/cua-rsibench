"""Offline Excel Graph download/revocation tests; no Microsoft request."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.test_office_web_ppt_graph_readback_v1 import FakeClient
from tools.office_web_excel_graph_readback_v1 import (
    ExcelGraphOwnerReadback, MIME,
)


class ExcelClient(FakeClient):
    def get(self, url, *, headers, params=None):
        response = super().get(url, headers=headers, params=params)
        if isinstance(response.value, dict) and 'file' in response.value:
            response.value['name'] = 'EL-Excel-Train-Test.xlsx'
            response.value['file']['mimeType'] = MIME
        return response


class ExcelGraphTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='excel-graph-test-')
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name) / 'readback'
        self.out.mkdir(mode=0o700)
        self.kwargs = {'owner_user_id': 'owner1234',
                       'drive_id': 'drive1234', 'item_id': 'item1234',
                       'expected_name': 'EL-Excel-Train-Test.xlsx',
                       'out_dir': self.out}

    def test_exact_xlsx_double_download_and_owner_readback(self):
        fake = ExcelClient(b'xlsx-payload', b'xlsx-payload')
        with patch.dict(os.environ, {'MS_GRAPH_OWNER_TOKEN': 'test-token'}):
            receipt = ExcelGraphOwnerReadback(
                client_factory=lambda: fake).capture(**self.kwargs)
        self.assertEqual(receipt['schema'],
                         'cua-office-excel-owner-double-download-v1')
        self.assertEqual(receipt['first_sha256'], receipt['second_sha256'])
        self.assertEqual(fake.download_headers, [{}, {}])
        self.assertEqual((self.out / 'first.private.xlsx').read_bytes(),
                         b'xlsx-payload')

    def test_changed_download_or_permission_is_rejected(self):
        fake = ExcelClient(b'one', b'two')
        with patch.dict(os.environ, {'MS_GRAPH_OWNER_TOKEN': 'test-token'}):
            with self.assertRaisesRegex(ValueError, 'two_downloads_or_metadata_changed'):
                ExcelGraphOwnerReadback(client_factory=lambda: fake).capture(
                    **self.kwargs)
        stale = ExcelClient(b'x', b'x', permission_present=True)
        with patch.dict(os.environ, {'MS_GRAPH_OWNER_TOKEN': 'test-token'}):
            with self.assertRaisesRegex(ValueError, 'prior_actor_permission_still_present'):
                ExcelGraphOwnerReadback(
                    client_factory=lambda: stale).verify_actor_revoked(
                        owner_user_id='owner1234', drive_id='drive1234',
                        item_id='item1234', actor_email='actor@example.test',
                        prior_permission_id='old-share')

    def test_owner_and_inherited_permissions_can_remain(self):
        fake = ExcelClient(b'x', b'x')
        with patch.dict(os.environ, {'MS_GRAPH_OWNER_TOKEN': 'test-token'}):
            result = ExcelGraphOwnerReadback(
                client_factory=lambda: fake).verify_actor_revoked(
                    owner_user_id='owner1234', drive_id='drive1234',
                    item_id='item1234', actor_email='actor@example.test',
                    prior_permission_id='old-share')
        self.assertEqual(result['schema'],
                         'cua-office-excel-owner-revocation-readback-v1')
        self.assertEqual(result['remaining_permission_count'], 2)
        self.assertEqual(result['actor_grants_remaining'], 0)


if __name__ == '__main__':
    unittest.main()
