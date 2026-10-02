"""Documented LSB status3 and reader-independent rollback; no native calls."""
import json,os,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from gitlab_world import v066_neutral_telemetry_coldboot_v5 as v5
from tests.test_gitlab_neutral_telemetry_coldboot_v1 import identity
from tests import test_gitlab_neutral_telemetry_coldboot_v2 as v2_tests


def status_bytes(down=None,foreign=False):
 names=list(v5.profile.CRITICAL_SERVICES)+(['foreign-service'] if foreign else [])
 return ('\n'.join(('down' if name in (down or set()) else 'run')+': '+name+': (pid 1) 1s' for name in names)+'\n').encode()

class LsbTests(unittest.TestCase):
 def test_before0_all_running_after3_only_sidekiq_down(self):
  self.assertEqual(v5.status_semantics(0,status_bytes(),b'')['sidekiq'],'running')
  value=v5.status_semantics(3,status_bytes({'sidekiq'}),b'')
  self.assertEqual(value['sidekiq'],'disabled')
  for name in v5.profile.CRITICAL_SERVICES:
   if name!='sidekiq':self.assertEqual(value[name],'running')
 def test_unknown4_other_critical_down_foreign_error_and_nondown3_rejected(self):
  cases=[(4,status_bytes({'sidekiq'}),b''),(3,status_bytes({'postgresql'}),b''),(3,status_bytes({'sidekiq','redis'}),b''),
   (3,status_bytes({'sidekiq'},foreign=True),b''),(3,status_bytes({'sidekiq'}),b'context error'),(3,status_bytes(),b''),
   (1,status_bytes({'sidekiq'}),b''),(0,status_bytes({'sidekiq'}),b''),(True,status_bytes(),b'')]
  for code,stdout,stderr in cases:
   with self.subTest(code=code,stderr=stderr):
    with self.assertRaises(ValueError):v5.status_semantics(code,stdout,stderr)
 def test_real_reader_preserves_exit3_and_exact_stream(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);backend=v5.NativeBackend(v2_tests.SeamTests().doc(),root);raw=status_bytes({'sidekiq'})
   with v5.version_scope(),patch.object(subprocess,'run',return_value=subprocess.CompletedProcess([],3,raw,b'')):
    value=backend.service_status('owned','original-ordered-sidekiq-after')
   self.assertEqual(value['returncode'],3);self.assertTrue(value['semantic_status_valid'])
   self.assertEqual((root/'original-ordered-sidekiq-after.stdout.private.log').read_bytes(),raw)
 def test_actual_saved_v4_cli3_replay(self):
  # The actual private receipt is opt-in and is never copied into public fixtures.
  value=os.environ.get('ENVLOOP_V4_RAW_DIR')
  if not value:self.skipTest('Actual saved private raw directory not supplied')
  root=Path(value);before=json.loads((root/'original-ordered-sidekiq-before.private.json').read_bytes());after=json.loads((root/'original-ordered-sidekiq-after.private.json').read_bytes())
  self.assertEqual(before['returncode'],0);self.assertEqual(after['returncode'],3)
  for phase,row in [('before',before),('after',after)]:
   stdout=(root/('original-ordered-sidekiq-'+phase+'.stdout.private.log')).read_bytes();stderr=(root/('original-ordered-sidekiq-'+phase+'.stderr.private.log')).read_bytes()
   self.assertEqual(v5.source.sha(stdout),row['stdout_sha256']);self.assertEqual(v5.source.sha(stderr),row['stderr_sha256'])
   result=v5.status_semantics(row['returncode'],stdout,stderr)
   self.assertEqual(result['sidekiq'],'running' if phase=='before' else 'disabled')
 def test_pre_restore_reader_fault_does_not_suppress_one_known_stop_rollback(self):
  with tempfile.TemporaryDirectory() as folder:
   doc=v2_tests.SeamTests().doc()|{'original_container':'preserved33'};backend=v5.NativeBackend(doc,Path(folder));backend.original_sidekiq_stop_attempted=True;calls=[]
   before={'identity':identity()};good={'services':{name:'running' for name in v5.profile.CRITICAL_SERVICES}}
   with patch.object(v5.runtime,'proof',return_value=identity()|{'running':True}),\
    patch.object(backend,'service_status',side_effect=[ValueError('unknown status reader'),good]),patch.object(backend,'docker',side_effect=lambda *a,**k:calls.append(a) or ''),\
    patch.object(v5.legacy.NativeBackend,'resume_original',return_value={'same_identity':True}) as restore:
     result=backend.resume_original(before)
   self.assertTrue(result['same_identity']);restore.assert_called_once_with(backend,before)
   self.assertEqual(calls,[('exec','preserved33','gitlab-ctl','start','sidekiq')])
   self.assertTrue((Path(folder)/'original-restore-status-fault.private.json').exists())
 def test_post_restore_reader_fault_remains_failure_after_physical_restoration(self):
  with tempfile.TemporaryDirectory() as folder:
   doc=v2_tests.SeamTests().doc()|{'original_container':'preserved33'};backend=v5.NativeBackend(doc,Path(folder));before={'identity':identity()}
   with patch.object(v5.runtime,'proof',return_value=identity()|{'running':False}),\
    patch.object(v5.legacy.NativeBackend,'resume_original',return_value={'same_identity':True}) as restore,\
    patch.object(backend,'service_status',side_effect=ValueError('post-restore unknown status')),patch.object(backend,'protected',return_value={'exact':True}),\
    patch.object(backend,'seed_content',return_value={'exact':True}):
     with self.assertRaises(ValueError):backend.resume_original(before)
     restore.assert_called_once_with(backend,before)
   self.assertTrue((Path(folder)/'original-resumed-status-fault.private.json').exists())
   self.assertTrue((Path(folder)/'protected-exit.private.json').exists());self.assertTrue((Path(folder)/'seed-exit.private.json').exists())
 def test_identity_change_never_authorizes_blind_service_start(self):
  with tempfile.TemporaryDirectory() as folder:
   backend=v5.NativeBackend(v2_tests.SeamTests().doc()|{'original_container':'preserved33'},Path(folder));backend.original_sidekiq_stop_attempted=True
   with patch.object(v5.runtime,'proof',return_value=identity('b')|{'running':True}),patch.object(backend,'docker') as docker:
    with self.assertRaises(ValueError):backend.resume_original({'identity':identity()})
    docker.assert_not_called()
 def test_old_v4_bytes_and_decoder_are_frozen(self):
  before=v5.previous.status_semantics;self.assertEqual(v5.source.sha(Path(v5.previous.__file__).read_bytes()),v5.PINNED_V4)
  with v5.version_scope():self.assertIs(v5.previous.status_semantics,v5.status_semantics)
  self.assertIs(v5.previous.status_semantics,before)

if __name__=='__main__':unittest.main()
