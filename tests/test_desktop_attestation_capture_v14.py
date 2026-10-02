import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from tools import capture_desktop_guest_attestation_v14 as capture


class CaptureTests(unittest.TestCase):
    def test_disabled_probe_precedes_private_reads_or_provider_import(self):
        with patch.object(capture, 'validate', side_effect=AssertionError('Private read')):
            with self.assertRaisesRegex(ValueError, 'disabled'):capture.run(Path('/absent'), Path('/absent'))

    def test_nonzero_exit_raw_stdout_stderr_are_retained_before_comparison(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = SimpleNamespace(exit_code=1, stdout='', stderr='Probe traceback fixture.')
            value = capture.capture_result(root, run, manifest_reader=lambda: b'partial-manifest-fixture')
            stored = json.loads((root / 'command-result.private.json').read_bytes())
            self.assertEqual((stored['exit_code'], stored['stdout'], stored['stderr']), (1, '', run.stderr))
            self.assertIn('manifest_ref', value)

    def test_invalid_json_output_survives_and_manifest_failure_is_distinct(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            def absent():raise FileNotFoundError()
            capture.capture_result(root, SimpleNamespace(exit_code=0, stdout='not-json', stderr=''), manifest_reader=absent)
            self.assertEqual(json.loads((root / 'command-result.private.json').read_bytes())['stdout'], 'not-json')
            self.assertEqual(json.loads((root / 'capture-index.private.json').read_bytes())['manifest_capture_error_type'], 'FileNotFoundError')

    def test_each_attestation_field_is_compared_without_relaxation(self):
        reference = {'static_content_sha256': 'a', 'static_content_counts': {'regular_file': 1},
                     'kernel_identity': {'release': 'fixed'}, 'static_content_excluded_paths': ['fixed']}
        observed = {'content_tree_sha256': 'a', 'counts': {'regular_file': 1},
                    'kernel': {'release': 'fixed'}, 'excluded_paths': ['fixed']}
        self.assertEqual(capture.compare(observed, reference), [])
        for key in observed:
            changed = {**observed, key: None}
            self.assertEqual(capture.compare(changed, reference), [key])

    def test_sdk_nonzero_command_exception_preserves_its_output(self):
        class Exit(Exception):
            exit_code = 7; stdout = 'partial output'; stderr = 'fixture error'
        with TemporaryDirectory() as tmp:
            sandbox = SimpleNamespace(commands=SimpleNamespace(run=lambda *args, **kwargs: (_ for _ in ()).throw(Exit())),
                                      files=SimpleNamespace(read=lambda *args, **kwargs: b'partial fixture'))
            result = capture.run_command_capture(sandbox, Path(tmp))
            self.assertEqual((result['exit_code'], result['stdout'], result['stderr']), (7, 'partial output', 'fixture error'))


if __name__ == '__main__':unittest.main()
