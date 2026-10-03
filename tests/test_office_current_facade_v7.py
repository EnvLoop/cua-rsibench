"""Uniform source-only readiness successor; no browser/provider execution."""
import json
from pathlib import Path
import subprocess
import unittest
from tools import office_current_facade_v7 as current
from tools import office_current_facade_v6 as previous

ROOT=Path(__file__).resolve().parents[1]

class ReadinessFacadeTests(unittest.TestCase):
    def test_all59_parent_bytes_and_complete_js_binding_preserved(self):
        old=previous.current_sources(ROOT);new=current.current_sources(ROOT)
        self.assertEqual(len(old),59);self.assertEqual(len(new),64)
        self.assertEqual({k:new[k] for k in old},old)
        raw=subprocess.check_output(['node','--input-type=module','-e',
            "import {officeV7SourceHashes} from './tools/office_current_cua_pump_v7.mjs';console.log(JSON.stringify(await officeV7SourceHashes()));"],cwd=ROOT,text=True)
        self.assertEqual(json.loads(raw),current.supplemental_sources(ROOT))
        self.assertEqual(len(current.supplemental_sources(ROOT)),12)

    def test_every_role_uses_one_source_map_and_original_actor_code(self):
        modules=current.parent.checked_modules();worker=modules['tools/office_current_execution_v4.py'].TaskWorker
        code=worker.run.__code__;originals={name:(getattr(m,'current_sources',None),getattr(m,'office',None)) for name,m in modules.items()}
        with current.source_epoch() as active:
            for module in active.values():
                if hasattr(module,'current_sources'):self.assertEqual(module.current_sources(ROOT),current.current_sources(ROOT))
                if hasattr(module,'TaskWorker'):self.assertIs(module.TaskWorker,worker)
            self.assertIs(worker.run.__code__,code)
            self.assertEqual(current.neutral_module().source_hashes(ROOT),current.current_sources(ROOT))
        self.assertIs(worker.run.__code__,code)
        for name,module in modules.items():self.assertEqual((getattr(module,'current_sources',None),getattr(module,'office',None)),originals[name])

    def test_old_binding_and_wrong_transport_refuse(self):
        for value in [dict(source_epoch=previous.SOURCE_EPOCH,baseline_upload_transport=current.BASELINE_UPLOAD_TRANSPORT,native_picker_app_id=current.NATIVE_PICKER_APP_ID),
                      dict(source_epoch=current.SOURCE_EPOCH,baseline_upload_transport='filechooser',native_picker_app_id=current.NATIVE_PICKER_APP_ID)]:
            with self.assertRaises(ValueError):current._transport(value)
        registration=current.counterpart_registry(ROOT)
        self.assertEqual(registration['mandatory_execution_entrypoint'],'tools.office_current_worker_cli_v7')
        self.assertFalse(registration['native_qualified'])

if __name__=='__main__':unittest.main()
