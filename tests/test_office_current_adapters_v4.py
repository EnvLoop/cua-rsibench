"""Real v22 authority/session gates with synthetic native/provider surfaces."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from tools.office_current_authority_v4 import Authority
from tools.office_current_paid_v4 import TeacherSampler
from tools.office_current_protocol_v4 import epoch_context
from tools import office_owned_folder_runtime_v2 as office
from cursibench import full_study_runtime_v2 as runtime
from tests import test_full_study_campaign_dispatch_v1 as fixture
from tests import v22_policy_runtime_fixture as v2

class CurrentAuthorityTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.FullStudyDispatchTests();self.f.setUp();self.addCleanup(self.f.tearDown);
  with epoch_context():self.study=v2.study(self.f.frozen())
 def test_nonreal_study_or_final_gate_refuses_before_package_body_or_delegate(self):
  for authority in (object(),{'qualified':True,'campaigns':24}):
   with self.assertRaises(ValueError):Authority(authority=authority,cell_id='powerpoint-web',owner_slot='shared-base')
 def test_real_base_and_checkpoint_reservation_scope_with_current_office_environment(self):
  for cell in ('powerpoint-web','excel-web'):
   session=runtime.SharedBaseSession(self.study,cell)
   # Fake matrix fixture checkpoint is deliberately not a real Qwen base;
   # refusal is the authentic checkpoint gate, before any package/provider.
   with self.assertRaisesRegex(ValueError,'Exact base/checkpoint'):
    Authority(authority=self.study,cell_id=cell,owner_slot='shared-base',session=session)
 def test_teacher_authority_uses_real_campaign_and_no_tinker_requirement(self):
  cell='powerpoint-web';v2.base_receipt(self.study,cell)
  session=self.study.open_campaign(self.study.repo_root/'work/current-teacher',cell_id=cell,researcher_id='astra',now=lambda:self.f.clock[0])
  authority=Authority(authority=self.study,cell_id=cell,owner_slot='astra',session=session,teacher=True)
  self.assertEqual(authority.split,'train');self.assertEqual(authority.checkpoint_path,None)
  before=session.budget.snapshot();self.assertEqual(before['pending_attempts'],0)
 def test_missing_current_qualification_refuses_before_metadata_or_provider(self):
  cell='powerpoint-web';v2.base_receipt(self.study,cell)
  session=self.study.open_campaign(self.study.repo_root/'work/current-qual',cell_id=cell,researcher_id='astra',now=lambda:self.f.clock[0])
  authority=Authority(authority=self.study,cell_id=cell,owner_slot='astra',session=session,teacher=True)
  path=self.study.repo_root/'work/unqualified.private.json';office.write_new(path,office.canonical({'accepted':False}))
  with self.assertRaises(ValueError):authority.qualify(path,office.sha(office.private(path)))

class ProspectiveGateTests(CurrentAuthorityTests):
 def test_old_source_epoch_is_not_retroactively_admitted(self):
  old=v2.study(self.f.frozen())
  with self.assertRaisesRegex(ValueError,'Fresh pre-result'):Authority(authority=old,cell_id='powerpoint-web',owner_slot='shared-base')
 def test_final_worker_refuses_before_profile_or_hidden_package_when_no_all24_gate(self):
  from tools.office_current_workers_v4 import TrustedFinalWorker
  for gate in (self.study,{'freezes':24},object()):
   with self.assertRaisesRegex(ValueError,'all24'):TrustedFinalWorker(gate=gate,cell_id='powerpoint-web',worker_options={},quote='10000')
 def test_current_neutral_namespace_keeps_source_review_and_execution_disabled(self):
  from tools.office_current_neutral_v4 import module
  value=module();self.assertEqual(value.NativeOperationSpool.__name__,'CurrentOperationSpool');self.assertIn('tools/office_current_cua_pump_v4.mjs',value.V4_FILES)
  with self.assertRaises(ValueError):value.run(config_path=self.study.repo_root/'work/missing-config.private.json',permit_path=None,enable_native=False)
