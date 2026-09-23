import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from cursibench.factory_campaign import digest
from remote_cloud_worker import archive_evidence, sha, VERSION
from remote_evidence_audit import audit_remote


def archive(entries):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:gz') as target:
        for name, data in entries.items():
            row = tarfile.TarInfo(name)
            row.size = len(data)
            target.addfile(row, io.BytesIO(data))
    return stream.getvalue()


class EvidenceAdmissionTests(unittest.TestCase):
    def fixture(self, root, extra_path=None):
        def write(name, data):
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data))
        content = b'frozen task'
        worker = (Path(__file__).resolve().parents[1] / 'tools/remote_cloud_worker.py').read_bytes()
        checkpoint = digest(None)
        manifest = {'job_id': 'fixed-job', 'task_names': ['a'], 'admission_kind': 'test',
                    'operational_version': VERSION, 'worker_sha256': sha(worker),
                    'model': {'name': 'student', 'checkpoint_sha256': checkpoint},
                    'runtime': {'packages': {'example': '1'}, 'package_sources': {'code': {'sha256': 'fixed'}}},
                    'files': {'tasks/a/task.toml': {'sha256': sha(content), 'bytes': len(content)}}}
        if extra_path:
            manifest['files'][extra_path] = {'sha256': sha(content), 'bytes': len(content)}
        encoded = json.dumps(manifest).encode()
        payload = archive({'manifest.json': encoded, 'blobs/' + sha(content): content})
        (root / 'payload.tar.gz').write_bytes(payload)
        (root / 'worker.py').write_bytes(worker)
        plan = {'job_id': 'fixed-job', 'operational_version': VERSION, 'payload_sha256': sha(payload),
                'manifest_sha256': sha(encoded), 'worker_sha256': sha(worker)}
        write('plan.json', plan)
        write('manifest.json', manifest)
        write('evidence/result.json', {'training_checkpoint': None, 'training_model': 'student', 'proxy_destroyed': True})
        receipt = archive_evidence(root, root / 'evidence.tar.gz', [])
        (root / 'evidence').rename(root / 'evaluation')
        write('remote-completion.json', dict(receipt, complete=True, evaluation_dispatched=True,
            operational_version=VERSION, child_exit=0,
            payload_sha256=plan['payload_sha256'], manifest_sha256=plan['manifest_sha256'], started_at=1,
            runtime={'platform': 'linux', 'python': '3.12.14', 'packages': {'example': '1'}, 'package_source_hashes': {'code': 'fixed'}}))
        write('lifecycle.json', {'job_id': 'fixed-job', 'collected': True, 'orchestrator_destroyed': True,
                                'archive_sha256': receipt['archive_sha256']})
        final = {'task_package_hashes': {'a': digest({'task.toml': sha(content)})}, 'runtime_hashes': {}}
        return checkpoint, final

    def test_complete_archive_and_final_package_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkpoint, final = self.fixture(root)
            proof = audit_remote(root, ['a'], checkpoint, final, source_hashes={})
            self.assertTrue(proof['runtime_and_member_hashes_verified'])

    def test_tampered_extracted_evidence_and_wrong_checkpoint_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkpoint, final = self.fixture(root)
            with self.assertRaisesRegex(ValueError, 'checkpoint binding'):
                audit_remote(root, ['a'], 'another-checkpoint', final, source_hashes={})
            (root / 'evaluation/result.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'evidence changed'):
                audit_remote(root, ['a'], checkpoint, final, source_hashes={})

    def test_changed_tasks_runtime_and_missing_cleanup_rejected(self):
        for field in ('task', 'runtime', 'cleanup'):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                checkpoint, final = self.fixture(root)
                if field == 'task':
                    final['task_package_hashes']['a'] = 'changed'
                else:
                    path = root / ('remote-completion.json' if field == 'runtime' else 'lifecycle.json')
                    data = json.loads(path.read_text())
                    if field == 'runtime':
                        data['runtime']['packages']['example'] = '2'
                    else:
                        data['orchestrator_destroyed'] = False
                    path.write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    audit_remote(root, ['a'], checkpoint, final, source_hashes={})

    def test_untrusted_source_and_outside_inventory_paths_are_rejected(self):
        for extra in ('src/cursibench/untrusted.py', 'sitecustomize.py'):
            with self.subTest(extra=extra), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                checkpoint, final = self.fixture(root, extra)
                with self.assertRaises(ValueError):
                    audit_remote(root, ['a'], checkpoint, final, source_hashes={})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkpoint, final = self.fixture(root)
            with self.assertRaisesRegex(ValueError, 'source inventory'):
                audit_remote(root, ['a'], checkpoint, final, source_hashes={'tools/required.py': 'missing'})

    def test_self_consistent_replacement_worker_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkpoint, final = self.fixture(root)
            (root / 'worker.py').write_bytes(b'altered dispatcher')
            path = root / 'plan.json'
            plan = json.loads(path.read_text())
            plan['worker_sha256'] = sha(b'altered dispatcher')
            path.write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, 'trusted source'):
                audit_remote(root, ['a'], checkpoint, final, source_hashes={})

    def test_cap_kill_or_failed_child_cannot_be_admitted(self):
        for field, value in [('child_wall_cap_reached', True), ('forced_group_kill', True), ('child_exit', 137)]:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                checkpoint, final = self.fixture(root)
                path = root / 'remote-completion.json'
                data = json.loads(path.read_text())
                data[field] = value
                path.write_text(json.dumps(data))
                with self.assertRaisesRegex(ValueError, 'scored admission prohibited'):
                    audit_remote(root, ['a'], checkpoint, final, source_hashes={})


if __name__ == '__main__':
    unittest.main()
