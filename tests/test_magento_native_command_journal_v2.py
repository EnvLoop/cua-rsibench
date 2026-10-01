import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from magento_catalog_factory.native_command_journal_v2 import CommandJournal, exact_absence, expected_stopped_service


class ExactAbsenceTests(unittest.TestCase):
    def test_lowercase_actual_result_is_absent_and_raw_journal_is_unchanged(self):
        name = 'envloop-magento-original-control'
        stderr = 'error: no such object: ' + name + '\n'
        calls = []
        def runner(args, **kwargs):
            calls.append(args)
            return SimpleNamespace(returncode=1, stdout='[]\n', stderr=stderr)
        with TemporaryDirectory() as temp:
            root = Path(temp)
            root.chmod(0o700)
            journal = CommandJournal(root, runner=runner)
            self.assertIsNone(journal.run('owned_app_absent', ('inspect', name), mutating=False, allow_absent=True))
            rows = [json.loads(line) for line in journal.path.read_text().splitlines()]
            self.assertTrue(rows[-1]['absent'])
            self.assertEqual(rows[-1]['stderr_sha256'], hashlib.sha256(stderr.encode()).hexdigest())
            self.assertEqual(len(calls), 1)

    def test_transport_errors_wrong_names_and_nonempty_output_stay_terminal(self):
        args = ('inspect', 'envloop-magento-original-control')
        cases = [
            ('[]', 'error: no such object: envloop-magento-other'),
            ('[]', 'context not found'),
            ('[]', 'cannot connect to daemon: not found'),
            ('[{}]', 'error: no such object: envloop-magento-original-control'),
            ('', 'error: no such object: envloop-magento-original-control'),
        ]
        for stdout, stderr in cases:
            self.assertFalse(exact_absence(args, SimpleNamespace(returncode=1, stdout=stdout, stderr=stderr)))

    def test_only_exact_owned_network_missing_response_is_accepted(self):
        args = ('network', 'inspect', 'envloop-magento-v066-teacher-network')
        result = SimpleNamespace(returncode=1, stdout='[]', stderr='Error response from daemon: network envloop-magento-v066-teacher-network not found')
        self.assertTrue(exact_absence(args, result))
        self.assertFalse(exact_absence(('rm', args[-1]), result))

    def test_only_exact_owned_cron_stopped_reply_is_known_nonzero_success(self):
        args = ('exec', 'envloop-magento-original-v066-teacher-app-a', 'supervisorctl', 'status', 'cron')
        result = SimpleNamespace(returncode=3, stdout='cron                             STOPPED   Not started\n', stderr='')
        self.assertTrue(expected_stopped_service(args, result))
        self.assertFalse(expected_stopped_service(args[:-1] + ('mysql',), result))
        self.assertFalse(expected_stopped_service(('exec', 'other-container', *args[2:]), result))
        self.assertFalse(expected_stopped_service(args, SimpleNamespace(returncode=3, stdout='cron FATAL failed\n', stderr='')))
        with TemporaryDirectory() as temp:
            root = Path(temp)
            root.chmod(0o700)
            journal = CommandJournal(root, runner=lambda *a, **kw: result)
            self.assertEqual(journal.run('owned_cron_status', args, mutating=False), result.stdout)
            rows = [json.loads(line) for line in journal.path.read_text().splitlines()]
            self.assertEqual(rows[-1]['returncode'], 3)
            self.assertEqual(rows[-1]['stdout_sha256'], hashlib.sha256(result.stdout.encode()).hexdigest())
            self.assertTrue(rows[-1]['expected_stopped_service'])
            self.assertEqual((root / 'process-diagnostics/owned_cron_status.stdout.private.bin').read_bytes(), result.stdout.encode())


if __name__ == '__main__':
    unittest.main()
