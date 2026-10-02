import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from native_desktop_factory.native_visible_diagnostic_v29 import run

class DiagnosticTests(unittest.TestCase):
 def module(self):
  module=SimpleNamespace(owner_module=lambda:None,owned_window=lambda *a:None,match_rule=lambda *a:None,collection_queries=lambda *a:None,ancestors=lambda *a:None,native_record=lambda *a:None)
  return module
 def test_completed_nested_match_rule_does_not_hide_failed_collection_stage(self):
  class NativeError(Exception):domain='atspi-error';code=2
  module=self.module()
  def query(*args):module.match_rule(None,[]);raise NativeError('private raw Collection error')
  module.collection_queries=query;module.run=lambda **kwargs:module.collection_queries(None,None)
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'private.json';result=run(filename='owned.xlsx',viewport=[1280,800],loader=lambda:module,error_path=path)
   self.assertEqual(result['failure']['stage'],'collection_queries');self.assertEqual(result['trace'][1]['status'],'completed');self.assertNotIn('private raw Collection error',str(result));self.assertEqual(path.stat().st_mode&0o777,0o600)
   raw=json.loads(path.read_bytes());self.assertEqual(raw['errors'][0]['raw_error_string'],'private raw Collection error');self.assertFalse(raw['actor_access_authorized'])
 def test_first_failed_nested_stage_is_not_overwritten_by_outer_error(self):
  module=self.module()
  def ancestry(*args):raise RuntimeError('private actual ancestry failure')
  module.ancestors=ancestry;module.native_record=lambda *args:module.ancestors(None,None);module.run=lambda **kwargs:module.native_record(None,None,None)
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'private.json';result=run(filename='owned.xlsx',viewport=[1280,800],loader=lambda:module,error_path=path)
   self.assertEqual(result['failure']['stage'],'ancestors');self.assertEqual(len(json.loads(path.read_bytes())['errors']),2);self.assertNotIn('private actual ancestry failure',str(result))
 def test_existing_private_error_file_is_never_overwritten(self):
  module=self.module();module.run=lambda **kwargs:None
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'private.json';path.write_bytes(b'old raw errors')
   with self.assertRaises(FileExistsError):run(filename='owned.xlsx',viewport=[1280,800],loader=lambda:module,error_path=path)
   self.assertEqual(path.read_bytes(),b'old raw errors')

if __name__=='__main__':unittest.main()
