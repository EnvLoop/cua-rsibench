"""Cross-source formal admission metadata only; no native/provider operation.

Package metadata is a synthetic test double of the actual Package type. This
verifies authority/policy interchange, not package scoring or qualification.
"""
import copy
from pathlib import Path
import unittest
from cursibench import full_study_runtime_v2 as runtime
from tools import office_owned_folder_runtime_v2 as office
from tools.office_owned_folder_paid_sampler_v2 import validate_admission,SCHEMA
from cursibench.native_surface_guard_policy_v1 import POLICY_SHA
from cursibench.scale_vision_proxy import MODEL
from tests import test_full_study_campaign_dispatch_v1 as fixture
from tests import v22_policy_runtime_fixture as v2


class OfficePolicyCounterpartTests(unittest.TestCase):
    def test_actual_office_formal_validator_reads_exact_amended_mapping_from_real_study(self):
        f=fixture.FullStudyDispatchTests();f.setUp();self.addCleanup(f.tearDown)
        study=v2.study(f.frozen())
        for cell in ('powerpoint-web','excel-web'):
            with self.subTest(cell=cell):
                base=v2.base_receipt(study,cell)
                session=study.open_campaign(study.repo_root/'work'/cell,cell_id=cell,researcher_id='astra',now=lambda:f.clock[0])
                task=study.task_views(cell)['selection'][0]
                package=object.__new__(office.Package)
                package.binding_sha256=task['package_sha256']
                package.actor=office.ActorTask(task['task_id'],task['package_sha256'],cell,'selection','Synthetic visible task','d'*64)
                root=study.repo_root/'work'/('office-metadata-'+cell);root.mkdir(mode=0o700)
                before=root/'before.bin';runtime.campaign._private_write_new(before,b'synthetic native-before bytes')
                binding={'account_principal_sha256':'a'*64,'folder_scope_sha256':'b'*64,'native_evidence_root':str(root)}
                training,_=study.student_training_configuration();views=study.task_views(cell)
                value={'schema':SCHEMA,'mode':'formal_selection','cell_id':cell,'task_id':task['task_id'],'package_sha256':task['package_sha256'],
                    'native_policy_sha256':POLICY_SHA,'source_sha256s':office.source_hashes(),'account_principal_sha256':'a'*64,'folder_scope_sha256':'b'*64,
                    'runtime_binding_sha256':office.sha(office.canonical(binding)),'single_account':True,'graph_used':False,
                    'max_actions':90,'max_wall_seconds':720,'native_window_sha256':'c'*64,'viewport':[1000,700],
                    'native_before_ref':{'path':before.name,'sha256':office.sha(before.read_bytes())},'native_before_sha256':office.sha(before.read_bytes()),
                    'owner_slot':'shared-base','source_reviewed':True,'checkpoint_path':None,'checkpoint_sha256':office.sha(MODEL.encode()),
                    'seed':training['seed'],'max_output_tokens':training['sample_max_tokens'],'policy_manifest_sha256':study.manifest_sha256,
                    'selection_attempt':'actual-selection-fixture','selection_identities_sha256':office.sha(office.canonical(list(views['selection'])))}
                result=validate_admission(value,package=package,runtime_binding=binding,authority=study,session=session)
                self.assertEqual(result['cell_id'],cell)
                self.assertEqual(study.policy_manifest['native_environment_by_cell'][cell],'owned_local_browser_cloud_account')
                self.assertEqual(study.amendment['native_environment_by_cell'][cell],'owned_local_browser_cloud_account')
                self.assertEqual(study.amendment['environment_policy_sha256'],runtime.environment.binding_sha256())
                original=study.policy_manifest['native_environment_by_cell'][cell]
                study.policy_manifest['native_environment_by_cell'][cell]='e2b'
                with self.assertRaises(ValueError):validate_admission(value,package=package,runtime_binding=binding,authority=study,session=session)
                study.policy_manifest['native_environment_by_cell'][cell]=original
