"""No-guest tests: actual diagnostic stages survive the frozen rejection."""
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from native_desktop_factory import native_accessibility_diagnostic_v23b as diagnostic

class DiagnosticTests(unittest.TestCase):
 def test_raw_x11_process_facts_retained_without_accepting_class_or_uid(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);proc=root/'proc'/'42';proc.mkdir(parents=True);exe=root/'soffice.bin';exe.write_bytes(b'native fixture executable');(proc/'exe').symlink_to(exe)
   (proc/'status').write_text('Name:\tsoffice.bin\nUid:\t1000\t1000\t1000\t1000\n')
   outputs={'getactivewindow':'5678\n','getwindowpid':'42\n','getwindowname':'private owned document title\n','WM_CLASS':'WM_CLASS(STRING) = "libreoffice", "libreoffice-calc"\n'}
   calls=[]
   def runner(args,**kwargs):calls.append(args);return SimpleNamespace(returncode=0,stdout=outputs[args[-1] if args[0]=='xprop' else args[1]],stderr='')
   value=diagnostic.diagnostic_x11(runner=runner,proc_root=root/'proc',probe_uid=0)
   self.assertEqual(value['native_pid'],42);self.assertEqual(value['native_uid'],1000);self.assertFalse(value['uid_matches_probe']);self.assertIn('libreoffice-calc',value['wm_class_raw']);self.assertEqual(value['process_exe_basename'],'soffice.bin')
   self.assertEqual(len(calls),4);self.assertTrue(value['process_observed']);self.assertNotIn('private owned document title',str(value));self.assertEqual(len(value['window_title_sha256']),64)
 def test_partial_native_query_preserves_successful_stages(self):
  count=0
  def runner(args,**kwargs):
   nonlocal count;count+=1
   return SimpleNamespace(returncode=0 if count==1 else 1,stdout='5678\n' if count==1 else '',stderr='' if count==1 else 'No PID property')
  value=diagnostic.diagnostic_x11(runner=runner,probe_uid=1000)
  self.assertEqual(value['window_id'],'5678');self.assertEqual(value['status'],'partial_or_unavailable');self.assertEqual(value['queries'][1]['stderr'],'No PID property');self.assertFalse(value['process_observed'])
 def test_frozen_guard_failure_keeps_diagnostics_and_never_relaxes_guard(self):
  class Frozen:
   def probe(self,**kwargs):raise ValueError('native_application_account_not_owned')
  result=diagnostic.run(filename='owned.xlsx',viewport=[1280,800],x11_reader=lambda:{'native_uid':1000,'probe_uid':0,'wm_class_raw':'observed native class'},frozen_loader=lambda:Frozen())
  self.assertFalse(result['guard_relaxed']);self.assertEqual(result['native_mutations'],0);self.assertEqual(result['frozen_probe_result']['error_code'],'native_application_account_not_owned');self.assertEqual(result['x11_details']['native_uid'],1000)
 def test_original_probe_source_is_still_exactly_frozen(self):
  self.assertEqual(diagnostic.sha(Path(diagnostic.__file__).with_name(diagnostic.FROZEN_SOURCE).read_bytes()),diagnostic.FROZEN_SHA)
  self.assertTrue(callable(diagnostic.load_frozen().probe))

if __name__=='__main__':unittest.main()
