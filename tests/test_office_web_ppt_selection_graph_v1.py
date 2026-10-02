"""Offline exact-item owner download for selection PowerPoint decks."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.test_office_web_ppt_graph_readback_v1 import (
    FakeClient, Response, pptx,
)
from tools.office_web_ppt_selection_graph_v1 import (
    SelectionPptGraphOwnerReadback,
)


class SelectionClient(FakeClient):
    def get(self, url, *, headers, params=None):
        response = super().get(url, headers=headers, params=params)
        if (not url.endswith(('/me', '/permissions', '/content')) and
                response.status_code == 200):
            metadata = response.json()
            metadata['name'] = 'EL-PPT-Selection-Test.pptx'
            return Response(200, value=metadata)
        return response


class PptSelectionGraphTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ppt-selection-graph-')
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name) / 'readback'
        self.out.mkdir(mode=0o700)
        self.arguments = {
            'owner_user_id': 'owner1234',
            'drive_id': 'drive1234',
            'item_id': 'item1234',
            'expected_name': 'EL-PPT-Selection-Test.pptx',
            'out_dir': self.out,
        }

    def capture(self, first, second):
        client = SelectionClient(first, second)
        with patch.dict(os.environ, {
                'MS_GRAPH_OWNER_TOKEN': 'fake-owner-token'}):
            return SelectionPptGraphOwnerReadback(
                client_factory=lambda: client).capture(**self.arguments)

    def test_exact_selection_name_and_two_identical_downloads(self):
        body = pptx('selection')
        receipt = self.capture(body, body)
        self.assertEqual(receipt['first_sha256'],
                         receipt['second_sha256'])
        self.assertEqual(receipt['byte_count'], len(body))
        self.assertEqual((self.out / 'first.private.pptx').read_bytes(),
                         body)

    def test_changed_download_or_train_name_fails(self):
        with self.assertRaisesRegex(ValueError,
                                    'selection_downloads_or_metadata_changed'):
            self.capture(pptx('first'), pptx('second'))
        self.arguments['expected_name'] = 'EL-PPT-Train-Test.pptx'
        with self.assertRaisesRegex(ValueError,
                                    'exact_ppt_selection_item_required'):
            self.capture(pptx('a'), pptx('a'))


if __name__ == '__main__':
    unittest.main()
