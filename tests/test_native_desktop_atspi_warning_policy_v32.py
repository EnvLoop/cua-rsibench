"""The saved actual V27 warning shape, plus strict rejection controls."""
import hashlib
from pathlib import Path
import unittest
from native_desktop_factory import native_atspi_warning_policy_v32 as policy

ROOT=Path(__file__).resolve().parents[1]
# Exact stderr from the actual saved V27 command. It contains only the trusted
# helper path and source line, with no task/document/window/account data.
ACTUAL_WARNING="/tmp/envloop-native-ownership-v24/native_visible_surface_probe_v27.py:41: DeprecationWarning: Atspi.Accessible.get_collection_iface is deprecated\n  collection=window.get_collection_iface();require(collection is not None,'Actual native Collection interface required')\n"
SOURCE='native_desktop_factory/native_visible_surface_probe_v27.py'
SOURCES={SOURCE:hashlib.sha256((ROOT/SOURCE).read_bytes()).hexdigest()}

class WarningTests(unittest.TestCase):
 def classify(self,value,**kwargs):return policy.classify(value,source_root=ROOT,source_sha256s=kwargs.get('sources',SOURCES))
 def test_saved_actual_warning_is_information_with_exact_hash_and_no_success_inference(self):
  result=self.classify(ACTUAL_WARNING);self.assertEqual(result['status'],'known_atspi_getter_deprecations');self.assertEqual(result['warning_blocks'],1);self.assertEqual(result['methods'],['get_collection_iface']);self.assertFalse(result['native_success_inferred']);self.assertEqual(result['stderr_sha256'],hashlib.sha256(ACTUAL_WARNING.encode()).hexdigest())
 def test_empty_stderr_is_separate_from_known_warning(self):self.assertEqual(self.classify('')['status'],'empty')
 def test_unknown_error_warning_getter_path_line_or_continuation_are_rejected(self):
  invalid=[ACTUAL_WARNING+'RuntimeError: unsafe\n',ACTUAL_WARNING.replace('DeprecationWarning','RuntimeWarning'),ACTUAL_WARNING.replace('get_collection_iface','get_text'),ACTUAL_WARNING.replace('envloop-native-ownership-v24','unowned'),ACTUAL_WARNING.replace(':41:',':42:'),ACTUAL_WARNING.replace('collection=window','task_value=window'),ACTUAL_WARNING.rstrip('\n')]
  for value in invalid:
   with self.subTest(value_hash=hashlib.sha256(value.encode()).hexdigest()),self.assertRaises(ValueError):self.classify(value)
 def test_changed_source_hash_is_not_trusted(self):
  with self.assertRaisesRegex(ValueError,'frozen manifest'):self.classify(ACTUAL_WARNING,sources={SOURCE:'a'*64})

if __name__=='__main__':unittest.main()
