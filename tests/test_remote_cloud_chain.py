import io
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import remote_cloud_worker as worker
import run_cloud_chain_remote as launcher


def archive(entries):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:gz') as tar:
        for name, content in entries.items():
            entry = tarfile.TarInfo(name)
            entry.size = len(content)
            tar.addfile(entry, io.BytesIO(content))
    return stream.getvalue()


def payload():
    script = b'# frozen launcher fixture\n'
    manifest = {'operational_version': worker.VERSION, 'runtime': {},
                'model': {'kind': 'base', 'name': 'Qwen/Qwen3.5-4B'}, 'task_names': ['a', 'b', 'c'],
                'files': {'tools/run_cloud_chain.py': {'sha256': worker.sha(script), 'bytes': len(script), 'mode': 0o600}}}
    manifest_bytes = json.dumps(manifest).encode()
    return archive({'manifest.json': manifest_bytes, 'blobs/' + worker.sha(script): script}), worker.sha(manifest_bytes)


class ArchiveTests(unittest.TestCase):
    def test_deduplicated_inputs_reconstruct_exact_bytes(self):
        data, digest = payload()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = worker.unpack_payload(data, root, digest)
            worker.verify_materialized(root, manifest)
            (root / 'tools/run_cloud_chain.py').write_text('changed')
            with self.assertRaisesRegex(ValueError, 'changed'):
                worker.verify_materialized(root, manifest)

    def test_corrupt_payload_missing_blobs_and_traversal_are_rejected(self):
        data, digest = payload()
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, 'manifest hash'):
                worker.unpack_payload(data, Path(temporary), 'wrong')
            contents = worker.read_archive(data)
            del contents[next(name for name in contents if name.startswith('blobs/'))]
            with self.assertRaisesRegex(ValueError, 'blob set'):
                worker.unpack_payload(archive(contents), Path(temporary), digest)
        with self.assertRaisesRegex(ValueError, 'unsafe archive path'):
            worker.read_archive(archive({'../escape': b'no'}))

    def test_links_are_rejected(self):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w:gz') as tar:
            member = tarfile.TarInfo('link')
            member.type, member.linkname = tarfile.SYMTYPE, '/tmp/target'
            tar.addfile(member)
        with self.assertRaisesRegex(ValueError, 'link'):
            worker.read_archive(stream.getvalue())

    def test_archive_download_checks_every_file_and_rejects_corruption(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'evidence').mkdir()
            (root / 'evidence/result.json').write_text('{"proxy_destroyed": true}')
            receipt = worker.archive_evidence(root, root / 'evidence.tar.gz', [])
            data = (root / 'evidence.tar.gz').read_bytes()
            _, index = launcher.verified_evidence(data, receipt)
            self.assertEqual(set(index['files']), {'result.json'})
            with self.assertRaisesRegex(ValueError, 'archive hash'):
                launcher.verified_evidence(data + b'changed', receipt)
            contents = worker.read_archive(data)
            contents['evidence/result.json'] = b'{}'
            corrupt = archive(contents)
            with self.assertRaisesRegex(ValueError, 'file mismatch'):
                launcher.verified_evidence(corrupt, dict(receipt, archive_bytes=len(corrupt), archive_sha256=worker.sha(corrupt)))

    def test_credentials_and_raw_provider_envelopes_are_withheld(self):
        with self.assertRaisesRegex(ValueError, 'credential'):
            worker.assert_no_credentials(b'example secret-value', ['secret-value'])
        with self.assertRaisesRegex(ValueError, 'credential'):
            worker.assert_no_credentials(b'Bearer abcdefghijklmnopqrstuvwxyz123456', [])
        with self.assertRaisesRegex(ValueError, 'provider envelope'):
            worker.assert_no_credentials(b'prefix {"object":"response","output":[]}', [])


class DurableWorkerTests(unittest.TestCase):
    def test_completed_or_lost_completion_ack_never_replays_evaluation(self):
        data, manifest_sha = payload()
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            source = home / 'payload.tar.gz'
            source.write_bytes(data)
            root = home / 'job'
            def dispatch(command, **kwargs):
                self.assertEqual(command[1], 'tools/run_cloud_chain.py')
                self.assertIn('--job-timeout', command)
                self.assertEqual(command[command.index('--job-timeout') + 1], '2700')
                self.assertNotIn('OPENAI_API_KEY', kwargs['env'])
                evidence = root / 'evidence'
                evidence.mkdir()
                (evidence / 'result.json').write_text('{"proxy_destroyed":true,"harbor_exit":0}')
                return SimpleNamespace(pid=12345, wait=lambda **_: 0, poll=lambda: 0)
            with patch.object(worker, 'verify_runtime', return_value={'platform': 'linux'}), patch.object(worker.subprocess, 'Popen', side_effect=dispatch) as popen:
                args = (root, source, worker.sha(data), manifest_sha, worker.sha(Path(worker.__file__).read_bytes()), time.time() + 3600)
                self.assertEqual(worker.run(*args)['state'], 'complete')
                self.assertEqual(worker.run(*args)['state'], 'already_complete')
                (home / 'control/completion.json').unlink()
                self.assertEqual(worker.run(*args)['state'], 'prior_dispatch_uncertain_no_replay')
                self.assertEqual(popen.call_count, 1)

    def test_short_remaining_lease_aborts_before_model_dispatch(self):
        data, manifest_sha = payload()
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            source = home / 'payload.tar.gz'
            source.write_bytes(data)
            with patch.object(worker, 'verify_runtime', return_value={}), patch.object(worker.subprocess, 'Popen') as popen:
                result = worker.run(home / 'job', source, worker.sha(data), manifest_sha,
                                    worker.sha(Path(worker.__file__).read_bytes()), time.time() + 2900)
                self.assertEqual(result['state'], 'failed')
                self.assertFalse(result['evaluation_dispatched'])
                popen.assert_not_called()


class LocalLifecycleTests(unittest.TestCase):
    def prepared(self, folder):
        out = Path(folder)
        data = b'payload'
        code = b'worker'
        (out / 'payload.tar.gz').write_bytes(data)
        (out / 'worker.py').write_bytes(code)
        plan = {'job_id': 'job-one', 'payload_sha256': worker.sha(data),
                'worker_sha256': worker.sha(code), 'manifest_sha256': 'manifest-hash'}
        (out / 'plan.json').write_text(json.dumps(plan))
        return out, plan

    def test_upload_retries_are_bounded_exact_byte_operations(self):
        files = Mock()
        files.read.side_effect = [b'bad', b'exact']
        with patch.object(launcher.time, 'sleep'):
            launcher.bounded_upload(SimpleNamespace(files=files), '/tmp/input', b'exact')
        self.assertEqual(files.write.call_count, 2)
        files.read.side_effect = TimeoutError()
        with patch.object(launcher.time, 'sleep'), self.assertRaises(TimeoutError):
            launcher.bounded_upload(SimpleNamespace(files=files), '/tmp/input', b'exact')
        self.assertEqual(files.write.call_count, 5)

    def test_lost_dispatch_ack_reuses_sandbox_without_upload_or_lease_extension(self):
        with tempfile.TemporaryDirectory() as temporary:
            out, _ = self.prepared(temporary)
            stored = {}
            files = SimpleNamespace(write=lambda name, data, **_: stored.__setitem__(name, data),
                                    read=lambda name, **_: stored[name])
            commands = Mock()
            commands.run.side_effect = [TimeoutError(), SimpleNamespace(exit_code=0)]
            sandbox = SimpleNamespace(sandbox_id='one-sandbox', files=files, commands=commands)
            with patch.dict(os.environ, {'E2B_API_KEY': 'test-e2b', 'TINKER_API_KEY': 'test-tinker', 'OPENAI_API_KEY': 'not-uploaded'}), patch('e2b.Sandbox.create', return_value=sandbox) as create, patch('e2b.Sandbox.connect', return_value=sandbox) as connect:
                self.assertFalse(launcher.launch(out, 'template')['acknowledged'])
                self.assertTrue(launcher.launch(out, 'template')['acknowledged'])
                self.assertEqual(create.call_count, 1)
                connect.assert_called_once_with('one-sandbox')
                self.assertEqual(create.call_args.kwargs['timeout'], 3600)
                self.assertEqual(set(create.call_args.kwargs['envs']), {'E2B_API_KEY', 'TINKER_API_KEY'})
                self.assertEqual(len(stored), 2)
                self.assertEqual(commands.run.call_args_list[0], commands.run.call_args_list[1])

    def test_ambiguous_creation_is_never_repeated(self):
        with tempfile.TemporaryDirectory() as temporary:
            out, _ = self.prepared(temporary)
            with patch.dict(os.environ, {'E2B_API_KEY': 'test', 'TINKER_API_KEY': 'test'}), patch('e2b.Sandbox.create', side_effect=TimeoutError()) as create:
                with self.assertRaises(TimeoutError):
                    launcher.launch(out, 'template')
                with self.assertRaisesRegex(ValueError, 'no receipt'):
                    launcher.launch(out, 'template')
                self.assertEqual(create.call_count, 1)

    def test_collection_resumes_verified_partial_files_and_only_then_destroys_host(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            out = home / 'local'
            out.mkdir()
            _, plan = self.prepared(out)
            remote = home / 'remote'
            (remote / 'evidence').mkdir(parents=True)
            (remote / 'evidence/result.json').write_text('{"harbor_exit":0}')
            receipt = worker.archive_evidence(remote, remote / 'archive.tar.gz', [])
            receipt.update(complete=True, payload_sha256=plan['payload_sha256'],
                           manifest_sha256=plan['manifest_sha256'])
            data = (remote / 'archive.tar.gz').read_bytes()
            state = {'sandbox_id': 'one-sandbox', 'lease_deadline_upper_bound': time.time() + 600}
            (out / 'lifecycle.json').write_text(json.dumps(state))
            (out / 'evaluation.partial').mkdir()
            (out / 'evaluation.partial/result.json').write_text('{"harbor_exit":0}')
            files = Mock()
            files.read.side_effect = lambda path, **_: json.dumps(receipt) if path.endswith('completion.json') else data
            sandbox = SimpleNamespace(files=files, kill=Mock())
            with patch('e2b.Sandbox.connect', return_value=sandbox) as connect, patch('e2b.Sandbox.create') as create:
                result = launcher.collect(out)
                self.assertEqual(result['state'], 'collected')
                self.assertTrue(result['orchestrator_destroyed'])
                self.assertEqual((out / 'evaluation/result.json').read_bytes(), (remote / 'evidence/result.json').read_bytes())
                self.assertEqual(launcher.collect(out)['state'], 'collected')
                self.assertEqual(connect.call_count, 1)
                sandbox.kill.assert_called_once()
                create.assert_not_called()

    def test_corrupt_download_does_not_mark_collected_or_destroy_remote_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            out, plan = self.prepared(temporary)
            (out / 'lifecycle.json').write_text(json.dumps({'sandbox_id': 'one', 'lease_deadline_upper_bound': time.time() + 600}))
            receipt = dict(complete=True, payload_sha256=plan['payload_sha256'], manifest_sha256=plan['manifest_sha256'],
                           archive_sha256='expected', archive_bytes=4)
            sandbox = SimpleNamespace(files=Mock(), kill=Mock())
            sandbox.files.read.side_effect = lambda path, **_: json.dumps(receipt) if path.endswith('completion.json') else b'bad'
            with patch('e2b.Sandbox.connect', return_value=sandbox), patch.object(launcher.time, 'sleep'), self.assertRaisesRegex(ValueError, 'archive hash'):
                launcher.collect(out)
            sandbox.kill.assert_not_called()
            self.assertFalse(json.loads((out / 'lifecycle.json').read_text()).get('collected', False))


if __name__ == '__main__':
    unittest.main()
