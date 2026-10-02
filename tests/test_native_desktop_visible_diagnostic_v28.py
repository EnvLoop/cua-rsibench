from types import SimpleNamespace
import unittest
from native_desktop_factory.native_visible_diagnostic_v28 import run

class DiagnosticTests(unittest.TestCase):
 def module(self,error):
  module=SimpleNamespace(owner_module=lambda:None,owned_window=lambda *a:None,match_rule=lambda *a:None,collection_queries=lambda *a:None,ancestors=lambda *a:None,native_record=lambda *a:None)
  def query(*args):raise error
  module.collection_queries=query
  module.run=lambda **kwargs:module.collection_queries(None,None)
  return module
 def test_native_error_stage_domain_code_retained_without_message_text(self):
  class NativeError(Exception):domain='atspi-error';code=2
  value=run(filename='owned.xlsx',viewport=[1280,800],loader=lambda:self.module(NativeError('private native detail')))
  self.assertEqual(value['failure']['stage'],'collection_queries');self.assertEqual(value['failure']['error_domain'],'atspi-error');self.assertEqual(value['failure']['error_code'],2);self.assertNotIn('private native detail',str(value));self.assertFalse(value['native_qualification_passed']);self.assertFalse(value['guard_or_query_relaxed'])
 def test_pinned_source_is_importable_without_native_call(self):
  from native_desktop_factory.native_visible_diagnostic_v28 import load
  self.assertTrue(callable(load().collection_queries))

if __name__=='__main__':unittest.main()
