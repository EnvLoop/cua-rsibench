"""Distribution privacy, tamper detection and reproducible archive checks."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from tools import build_non_tinker_source_bundle_v1 as bundle


class BundleTests(unittest.TestCase):
    def fixture(self,root):
        files={'src/cursibench/__init__.py':b'# Public implementation\n',
            'deployment/non-tinker-runner/.dockerignore':b'work\n.env\n'}
        for name,raw in files.items():
            p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
        return files

    def test_credential_and_private_state_never_enter_build_context(self):
        for name in ['work/secret.json','src/private/gold.json','tools/run.private.json',
                     'src/.env','../src/escape.py','/src/absolute.py']:
            with self.subTest(name=name):self.assertFalse(bundle.allowed(name))
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            p=root/'src/credential.py';p.write_bytes(b'key="'+b'sk-'+b'x'*40+b'"')
            with self.assertRaisesRegex(ValueError,'credential_value'):
                bundle.checked_file(root,'src/credential.py')

    def test_parent_symlink_cannot_smuggle_external_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);outside=root/'outside';outside.mkdir();(outside/'a.py').write_text('secret')
            (root/'src').mkdir();(root/'src/link').symlink_to(outside,target_is_directory=True)
            with self.assertRaisesRegex(ValueError,'symlink'):
                bundle.checked_file(root,'src/link/a.py')

    def test_public_task_and_provider_field_names_are_not_credentials(self):
        self.assertIsNone(bundle.SECRET.search(b'task-source-snapshot-bound-window-reference'))
        self.assertIsNone(bundle.SECRET.search(b'e2b_environment_class_attribution_source'))
        self.assertIsNotNone(bundle.SECRET.search(b'key="e2b_'+b'a'*40+b'"'))
        self.assertIsNone(bundle.SECRET.search(b'PRIVATE_MARKER="-----BEGIN PRIVATE KEY-----"'))
        self.assertIsNotNone(bundle.SECRET.search(b'-----BEGIN PRIVATE KEY-----\n'+b'A'*64+b'\n-----END PRIVATE KEY-----'))

    def test_tamper_and_unlisted_files_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'source';root.mkdir();files=self.fixture(root)
            with patch.object(bundle.subprocess,'check_output',return_value=('\0'.join(files)+'\0').encode()):
                out=Path(tmp)/'context';bundle.stage(root,out)
            bundle.verify(out)
            p=out/'src/cursibench/__init__.py';p.write_text('changed')
            with self.assertRaisesRegex(ValueError,'member_changed'):bundle.verify(out)
            p.write_bytes(files['src/cursibench/__init__.py'])
            (out/'surprise.txt').write_text('unlisted')
            with self.assertRaisesRegex(ValueError,'unlisted'):bundle.verify(out)

    def test_identical_contexts_produce_identical_archives(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'source';root.mkdir();files=self.fixture(root)
            out=Path(tmp)/'context'
            with patch.object(bundle.subprocess,'check_output',return_value=('\0'.join(files)+'\0').encode()):
                value=bundle.stage(root,out)
            a=bundle.archive(out,Path(tmp)/'one.tar.gz');b=bundle.archive(out,Path(tmp)/'two.tar.gz')
            self.assertEqual(a,b)
            self.assertFalse(value['training_provider_required_for_build'])
            self.assertFalse(value['benchmark_model_results_claimed'])


if __name__=='__main__':unittest.main()
