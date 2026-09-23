"""Recovery retries preserve effects after lost replies and fail closed on doubt."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


io = module('restoration_io')
journal = module('restoration_journal')


class FakeFiles:
    def __init__(self):
        self.values = {}
        self.writes = 0
        self.reads = 0
        self.lose_write_reply = False
        self.read_failures = 0

    def write(self, path, text, **kwargs):
        self.writes += 1
        self.values[path] = text
        if self.lose_write_reply:
            raise ConnectionError('reply lost after commit')

    def read(self, path, **kwargs):
        self.reads += 1
        if self.read_failures:
            self.read_failures -= 1
            raise ConnectionError('transient read failure')
        return self.values[path]


class RestorationIOTests(unittest.TestCase):
    def test_exact_creation_intent_precedes_lost_ack_and_cannot_be_replaced(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'restoration'
            workspace = io.RestorationWorkspace(root)
            def lost_ack(**kwargs):
                saved = json.loads((root / 'creation-intent.json').read_text())
                self.assertEqual(saved['metadata'], kwargs['metadata'])
                self.assertEqual(saved['restoration_id'], kwargs['metadata']['restoration_id'])
                self.assertEqual(saved['timeout_seconds'], kwargs['timeout'])
                self.assertTrue(saved['template'])
                self.assertIsInstance(saved['created_at'], float)
                self.assertEqual([saved[k] for k in ('model_calls', 'program_runs', 'teacher_calls')], [0, 0, 0])
                self.assertFalse(saved['allow_internet_access'])
                self.assertFalse(saved['provider_credentials_injected'])
                self.assertEqual(kwargs['envs'], {})
                raise ConnectionError('create acknowledgement lost')
            with patch('e2b.Sandbox.create', side_effect=lost_ack) as create:
                with self.assertRaises(ConnectionError):
                    workspace.start({}, 'worker source')
                original = (root / 'creation-intent.json').read_bytes()
                with self.assertRaises(FileExistsError):
                    workspace.start({}, 'worker source')
                self.assertEqual((root / 'creation-intent.json').read_bytes(), original)
                self.assertEqual(create.call_count, 1)
                self.assertFalse((root / 'sandbox.json').exists())

    def test_lost_upload_reply_uses_hash_readback_without_duplicate_write(self):
        files = FakeFiles()
        files.lose_write_reply = True
        bounded = io.BoundedIO(SimpleNamespace(files=files), pause=lambda _: None)
        result = bounded.write_text('/workspace/factory.py', 'exact data', user='factory')
        self.assertEqual(result['sha256'], io.sha('exact data'))
        self.assertEqual(files.writes, 1)
        with self.assertRaises(ValueError):
            bounded.write_text('/workspace/factory.py', 'changed data', user='factory')

    def test_read_retries_are_bounded_across_identical_requests(self):
        files = FakeFiles()
        files.values['/file'] = 'exact data'
        files.read_failures = 2
        bounded = io.BoundedIO(SimpleNamespace(files=files), pause=lambda _: None)
        self.assertEqual(bounded.read_text('/file'), 'exact data')
        self.assertEqual(files.reads, 3)
        with self.assertRaises(io.RecoveryIOError):
            bounded.read_text('/file')
        self.assertEqual(files.reads, 3)

    def test_uncertain_upload_has_at_most_three_identical_writes_and_reads(self):
        files = FakeFiles()
        files.lose_write_reply = True
        files.read_failures = 99
        bounded = io.BoundedIO(SimpleNamespace(files=files), pause=lambda _: None)
        with self.assertRaises(io.RecoveryIOError):
            bounded.write_text('/workspace/data.jsonl', 'exact data', user='factory')
        self.assertEqual((files.writes, files.reads), (3, 3))

    def test_lost_command_reply_reads_the_existing_journal_result(self):
        files = FakeFiles()
        calls = []
        def execute(command, **kwargs):
            calls.append(command)
            files.values['/result.json'] = json.dumps({'initialized': True})
            raise ConnectionError('reply lost')
        sandbox = SimpleNamespace(files=files, commands=SimpleNamespace(run=execute))
        bounded = io.BoundedIO(sandbox, pause=lambda _: None)
        self.assertEqual(bounded.journal_command('same guarded command', '/result.json'), {'initialized': True})
        self.assertEqual(len(calls), 1)


class InitializationJournalTests(unittest.TestCase):
    def test_successful_initialization_is_not_replayed_after_reply_loss(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            counter = root / 'effects'
            worker = root / 'worker.py'
            worker.write_text('from pathlib import Path\ndef initialize():\n'
                f'    with Path({str(counter)!r}).open("a") as f: f.write("effect\\n")\n'
                '    return {"initialized": True, "program_uid": 1001}\n')
            digest = hashlib.sha256(worker.read_bytes()).hexdigest()
            first = journal.initialize_once(worker, root / 'journal', digest)
            second = journal.initialize_once(worker, root / 'journal', digest)
            self.assertEqual(first, second)
            self.assertEqual(counter.read_text().splitlines(), ['effect'])

    def test_uncertain_initialization_cannot_replay_its_partial_effect(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            counter = root / 'effects'
            worker = root / 'worker.py'
            worker.write_text('from pathlib import Path\ndef initialize():\n'
                f'    with Path({str(counter)!r}).open("a") as f: f.write("effect\\n")\n'
                '    raise RuntimeError("simulated interruption")\n')
            digest = hashlib.sha256(worker.read_bytes()).hexdigest()
            with self.assertRaises(RuntimeError):
                journal.initialize_once(worker, root / 'journal', digest)
            with self.assertRaisesRegex(RuntimeError, 'must not be replayed'):
                journal.initialize_once(worker, root / 'journal', digest)
            self.assertEqual(counter.read_text().splitlines(), ['effect'])

    def test_changed_initializer_is_rejected_without_effects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            worker = root / 'worker.py'
            worker.write_text('raise RuntimeError("must never execute")\n')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                journal.initialize_once(worker, root / 'journal', '0' * 64)
            self.assertFalse((root / 'journal').exists())


if __name__ == '__main__':
    unittest.main()
