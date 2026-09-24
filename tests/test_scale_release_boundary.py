import tempfile
import unittest
from pathlib import Path

from tools.scale_release_boundary import scan_public_tree, sha256


class ScaleReleaseBoundaryTests(unittest.TestCase):
    def test_allows_explicit_sanitized_text_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'report.md'
            path.write_text('One application, measured scores and a source reference.\n')
            result = scan_public_tree(temporary)
            self.assertEqual(result['status'], 'text-and-inventory-pass')
            self.assertFalse(result['screenshot_content_reviewed'])

    def test_rejects_account_and_provider_values_without_echoing_them(self):
        for value in ('bench-account' + '@example.test', 'e2b_' + 'x' * 30,
                      'https://' + '1drv.ms' + '/u/s!sensitive-link'):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as temporary:
                (Path(temporary) / 'summary.json').write_text('{"value":' + repr(value).replace("'", '"') + '}')
                with self.assertRaises(ValueError) as caught:
                    scan_public_tree(temporary, markers=('bench-account' + '@example.test',))
                self.assertNotIn(value, str(caught.exception))

    def test_requires_reviewed_binary_and_rejects_raw_auth_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            image = Path(temporary) / 'figure.png'
            image.write_bytes(b'not a reviewed screenshot')
            with self.assertRaisesRegex(ValueError, 'unreviewed binary'):
                scan_public_tree(temporary)
            approved = scan_public_tree(temporary, approved_binary_hashes=[sha256(image.read_bytes())])
            self.assertTrue(approved['files']['figure.png']['reviewed_binary'])
            (Path(temporary) / 'storage_state.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'authentication or raw-state'):
                scan_public_tree(temporary, approved_binary_hashes=[sha256(image.read_bytes())])

    def test_symlink_cannot_escape_public_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'safe.txt').write_text('safe')
            (root / 'link.txt').symlink_to(root / 'safe.txt')
            with self.assertRaisesRegex(ValueError, 'symlink'):
                scan_public_tree(root)

    def test_javascript_modules_and_gitignore_are_scanned_as_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'builder.mjs').write_text('export const rows = 2;\n')
            (root / '.gitignore').write_text('output/\n')
            result = scan_public_tree(root)
            self.assertEqual(set(result['files']), {'builder.mjs', '.gitignore'})
            self.assertFalse(any(row['reviewed_binary'] for row in result['files'].values()))
            (root / 'builder.mjs').write_text('export const key = "e2b_' + 'x' * 30 + '";\n')
            with self.assertRaisesRegex(ValueError, 'provider credential'):
                scan_public_tree(root)


if __name__ == '__main__':
    unittest.main()
