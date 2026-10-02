import unittest
from unittest.mock import patch
from types import SimpleNamespace
from native_desktop_factory import native_accessibility_probe_v24 as probe

class OwnershipTests(unittest.TestCase):
 def first(self,klass='libreoffice-calc',uid=1000):return {'uid':uid,'probe_uid':1000,'pid':2042,'wm_class':f'WM_CLASS(STRING) = "libreoffice", "{klass}"'}
 def test_actual_observed_calc_type_and_same_uid_requires_attested_executable(self):
  with patch.object(probe.os,'readlink',return_value='/usr/lib/libreoffice/program/soffice.bin'),patch.object(probe.Path,'read_bytes',return_value=b'actual fixture executable'),patch.object(probe,'sha',return_value=probe.ATTESTED_EXE_SHA):
   self.assertTrue(probe.ownership(self.first(),'owned.xlsx'))
   self.assertFalse(probe.ownership(self.first(uid=0),'owned.xlsx'))
   self.assertFalse(probe.ownership(self.first('libreoffice-writer'),'owned.xlsx'))
   self.assertFalse(probe.ownership(self.first('libreoffice-writer'),'owned.docx'))
   self.assertFalse(probe.ownership(self.first('libreoffice-impress'),'owned.pptx'))
   self.assertFalse(probe.ownership({**self.first(),'wm_class':'arbitrary contains soffice'},'owned.xlsx'))
 def test_class_alone_does_not_accept_wrong_process_or_guest_image(self):
  with patch.object(probe.os,'readlink',return_value='/tmp/soffice.bin'):self.assertFalse(probe.ownership(self.first(),'owned.xlsx'))
  with patch.object(probe.os,'readlink',return_value='/usr/lib/libreoffice/program/soffice.bin'),patch.object(probe.Path,'read_bytes',return_value=b'wrong guest image'):
   self.assertFalse(probe.ownership(self.first(),'owned.xlsx'))
 def test_frozen_loader_changes_only_owner_predicate_and_schema(self):
  module=probe.load();self.assertEqual(module.SCHEMA,probe.SCHEMA);self.assertTrue(callable(module.native_api));self.assertEqual(probe.OBSERVED_NATIVE_CLASSES,['libreoffice-calc'])

if __name__=='__main__':unittest.main()
