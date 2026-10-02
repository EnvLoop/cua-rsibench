"""Pinned offline asset/bootstrap checks; no guest/provider/template calls."""
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from native_desktop_factory import native_atspi_bootstrap_v25 as bootstrap

ASSET=Path(__file__).resolve().parents[1]/'native_desktop_factory/native_runtime_assets/Atspi-2.0.typelib'
class BootstrapTests(unittest.TestCase):
 def test_official_typelib_asset_matches_exact_package_pin(self):
  raw=ASSET.read_bytes();self.assertEqual(len(raw),54164);self.assertEqual(bootstrap.sha(raw),bootstrap.TYPELIB_SHA)
 def fixture(self,root):
  paths=['/usr/lib/x86_64-linux-gnu/libatspi.so.0.0.1','/usr/libexec/at-spi-bus-launcher','/usr/libexec/at-spi2-registryd','/usr/lib/os-release'];expected={}
  for name in paths:
   path=root/name.lstrip('/');path.parent.mkdir(parents=True,exist_ok=True);raw=('synthetic existing '+name).encode();path.write_bytes(raw);expected[name]=bootstrap.sha(raw)
  return expected
 def test_exclusive_offline_one_file_bootstrap_preserves_all_existing_dependency_bytes(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);expected=self.fixture(root);before={n:(root/n.lstrip('/')).read_bytes() for n in expected};prefix=root/'setup'
   with patch.object(bootstrap,'REQUIRED',expected):
    result=bootstrap.apply(typelib=ASSET,prefix=prefix,root=root)
    self.assertFalse(result['task_files_modified']);self.assertFalse(result['gui_configuration_changed']);self.assertEqual((prefix/'Atspi-2.0.typelib').read_bytes(),ASSET.read_bytes())
    with self.assertRaisesRegex(ValueError,'Exclusive'):bootstrap.apply(typelib=ASSET,prefix=prefix,root=root)
   self.assertEqual(before,{n:(root/n.lstrip('/')).read_bytes() for n in expected})
 def test_changed_native_dependency_or_existing_profile_rejects_before_write(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);expected=self.fixture(root);prefix=root/'setup';path=root/'home/user/.config/libreoffice/4/user';path.mkdir(parents=True)
   with patch.object(bootstrap,'REQUIRED',expected):
    with self.assertRaisesRegex(ValueError,'fresh guest'):bootstrap.apply(typelib=ASSET,prefix=prefix,root=root)
    self.assertFalse(prefix.exists())
   (root/next(iter(expected)).lstrip('/')).write_bytes(b'changed native library')
   with patch.object(bootstrap,'REQUIRED',expected):
    with self.assertRaisesRegex(ValueError,'content changed'):bootstrap.prerequisite(typelib=ASSET,root=root)
 def test_namespace_child_environment_is_scoped_no_native_qualification(self):
  with tempfile.TemporaryDirectory() as tmp:
   prefix=Path(tmp);(prefix/'Atspi-2.0.typelib').write_bytes(ASSET.read_bytes());seen=[]
   def runner(args,**kwargs):seen.append(kwargs['env']['GI_TYPELIB_PATH']);return SimpleNamespace(returncode=0,stderr='',stdout='{"namespace_available":true,"desktop_count":1}')
   result=bootstrap.namespace(prefix=prefix,runner=runner);self.assertEqual(seen,[str(prefix)]);self.assertFalse(result['native_tree_qualified']);self.assertFalse(result['actual_focus_qualified'])

if __name__=='__main__':unittest.main()
