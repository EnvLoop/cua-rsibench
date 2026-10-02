"""Build staging cannot copy evaluator secrets, ignored work or shell state."""
import unittest
from tools.build_enterprise_runtime_image_v1 import public_source

class ContextTests(unittest.TestCase):
    def test_ignored_evaluator_and_credential_files_fail_closed(self):
        for name in ['work/fixture.json','tools/work/fixture.json','runtime/stage.private/credentials.json',
            'tools/credentials.private.json','tools/log.private.bin','.bashrc','.env',
            'runtime/.env.local','../private.json','/Users/example/.bashrc','.git/config',
            'src/__pycache__/api.pyc']:
            with self.subTest(name=name):self.assertFalse(public_source(name))
    def test_needed_enterprise_public_sources_remain_available(self):
        for name in ['pyproject.toml','src/cursibench/scale_action_contract.py',
            'magento_catalog_factory/native_surface_workers_v2.py','gitlab_world/runtime.py',
            'enterprise_fallback/odoo18/compose.yaml','tests/test_magento_quote_navigation_v2.py',
            'runtime/enterprise/runner.Dockerfile','ppt_wdi_factory/plan.py','sec_excel_factory/verify_train_transfer_four.py']:
            with self.subTest(name=name):self.assertTrue(public_source(name))

if __name__=='__main__':unittest.main()
