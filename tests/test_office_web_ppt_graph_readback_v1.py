"""Offline Graph metadata/redirect tests; no Microsoft request is sent."""

from __future__ import annotations

import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tools.office_web_ppt_graph_readback_v1 import GraphOwnerReadback


def pptx(tag: str) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr('[Content_Types].xml', '<Types/>')
        archive.writestr('ppt/presentation.xml', '<p/>')
        archive.writestr('ppt/_rels/presentation.xml.rels', '<r/>')
        archive.writestr('ppt/slides/slide1.xml', f'<s>{tag}</s>')
    return stream.getvalue()


class Response:
    def __init__(self, code, *, value=None, headers=None):
        self.status_code = code
        self.value = value
        self.headers = headers or {}

    def json(self):
        return self.value


class Stream:
    def __init__(self, body):
        self.status_code = 200
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def iter_bytes(self):
        yield self.body


class FakeClient:
    def __init__(self, first: bytes, second: bytes,
                 *, wrong_meta=False, wrong_redirect=False,
                 permission_present=False):
        self.bodies = [first, second]
        self.initial_size = len(first)
        self.wrong_meta = wrong_meta
        self.wrong_redirect = wrong_redirect
        self.permission_present = permission_present
        self.content_calls = 0
        self.download_headers = []
        self.closed = False

    def get(self, url, *, headers, params=None):
        if url.endswith('/me'):
            return Response(200, value={'id': 'owner1234'})
        if url.endswith('/permissions'):
            return Response(200, value={'value': ([{'id': 'old-share'}] if
                                                   self.permission_present else [])})
        if url.endswith('/content'):
            self.content_calls += 1
            redirect = ('http://localhost/private' if self.wrong_redirect
                        else 'https://download.example.test/file')
            return Response(302, headers={'Location': redirect})
        metadata = {
            'id': 'item1234', 'name': 'EL-PPT-Train-Test.pptx',
            'file': {'mimeType':
                     'application/vnd.openxmlformats-officedocument.presentationml.presentation'},
            'parentReference': {'driveId': 'drive1234'},
            'eTag': 'etag-1', 'size': self.initial_size,
        }
        if self.wrong_meta:
            metadata['parentReference']['driveId'] = 'another-drive'
        return Response(200, value=metadata)

    def stream(self, method, url, *, headers):
        self.download_headers.append(headers)
        return Stream(self.bodies.pop(0))

    def close(self):
        self.closed = True


class GraphReadbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='office-graph-test-')
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name) / 'readback'
        self.out.mkdir(mode=0o700)
        self.kwargs = {'owner_user_id': 'owner1234',
                       'drive_id': 'drive1234', 'item_id': 'item1234',
                       'expected_name': 'EL-PPT-Train-Test.pptx',
                       'out_dir': self.out}

    def run_capture(self, fake: FakeClient):
        with patch.dict(os.environ, {'MS_GRAPH_OWNER_TOKEN': 'test-only-token'}):
            return GraphOwnerReadback(client_factory=lambda: fake).capture(
                **self.kwargs)

    def test_two_exact_owner_downloads_are_private_and_equal(self):
        body = pptx('baseline')
        fake = FakeClient(body, body)
        receipt = self.run_capture(fake)
        self.assertEqual(receipt['first_sha256'], receipt['second_sha256'])
        self.assertEqual(receipt['byte_count'], len(body))
        self.assertEqual(fake.download_headers, [{}, {}])
        self.assertTrue(fake.closed)
        self.assertEqual((self.out / 'first.private.pptx').read_bytes(), body)
        self.assertEqual((self.out / 'readback.private.json').stat().st_mode & 0o077, 0)

    def test_content_change_or_drive_change_fails_without_receipt(self):
        with self.assertRaisesRegex(ValueError, 'two_downloads_or_metadata_changed'):
            self.run_capture(FakeClient(pptx('a'), pptx('b')))
        self.assertFalse((self.out / 'readback.private.json').exists())
        with self.assertRaisesRegex(ValueError, 'item_identity_or_size_changed'):
            self.run_capture(FakeClient(pptx('a'), pptx('a'), wrong_meta=True))

    def test_http_or_local_redirect_is_rejected_before_download(self):
        fake = FakeClient(pptx('a'), pptx('a'), wrong_redirect=True)
        with self.assertRaisesRegex(ValueError, 'graph_download_redirect_invalid'):
            self.run_capture(fake)
        self.assertEqual(fake.download_headers, [])

    def test_missing_owner_token_fails_before_client_creation(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, 'graph_owner_token_missing'):
                GraphOwnerReadback(client_factory=lambda: self.fail(
                    'client must not be constructed')).capture(**self.kwargs)

    def test_revocation_requires_empty_owner_permission_set(self):
        safe = FakeClient(pptx('a'), pptx('a'))
        with patch.dict(os.environ, {'MS_GRAPH_OWNER_TOKEN': 'test-only-token'}):
            receipt = GraphOwnerReadback(client_factory=lambda: safe).permissions_empty(
                owner_user_id='owner1234', drive_id='drive1234',
                item_id='item1234')
        self.assertEqual(receipt['permissions_count'], 0)
        stale = FakeClient(pptx('a'), pptx('a'), permission_present=True)
        with patch.dict(os.environ, {'MS_GRAPH_OWNER_TOKEN': 'test-only-token'}):
            with self.assertRaisesRegex(ValueError, 'permission_still_present'):
                GraphOwnerReadback(client_factory=lambda: stale).permissions_empty(
                    owner_user_id='owner1234', drive_id='drive1234',
                    item_id='item1234')


if __name__ == '__main__':
    unittest.main()
