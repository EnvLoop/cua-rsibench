"""Generic admission checks; no provider and no native UI is used."""
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from tools import office_owned_folder_runtime_v2 as rt
from tools.office_owned_folder_paid_sampler_v2 import GenericOfficePaidSampler,validate_admission
from cursibench.native_surface_guard_policy_v1 import POLICY_SHA
from cursibench.scale_vision_proxy import MODEL

@unittest.skipUnless(os.environ.get('ENVLOOP_PPT_TRAIN_PACKAGE'),'actual TRAIN package path not configured')
class PaidAdmissionTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.root.chmod(0o700);source=Path(os.environ['ENVLOOP_PPT_TRAIN_PACKAGE']);task=json.loads((source/'task.private.json').read_bytes())
  for name in ['source.pptx','task.private.json','source-snapshot.private.json','source-provenance.private.json','source-country.private.zip']:
   if (source/name).exists():rt.write_new(self.root/name,(source/name).read_bytes())
  rt.descriptor(cell_id='powerpoint-web',split=task['split'],task_id=task['task_id'],instruction=task['actor_task'],baseline=self.root/'source.pptx',task_spec=self.root/'task.private.json',out=self.root/'package.private.json');self.package=rt.Package(self.root/'package.private.json',package_root=self.root)
  self.binding={'account_principal_sha256':'a'*64,'folder_scope_sha256':'b'*64,'native_evidence_root':str(self.root)}
  before={'path':'source.pptx','sha256':rt.sha((self.root/'source.pptx').read_bytes())}
  self.admission={'schema':'office-owned-folder-paid-sampler-admission-v2','mode':'development_train','cell_id':'powerpoint-web','task_id':task['task_id'],'package_sha256':self.package.binding_sha256,
   'native_policy_sha256':POLICY_SHA,'source_sha256s':rt.source_hashes(),'account_principal_sha256':'a'*64,'folder_scope_sha256':'b'*64,'runtime_binding_sha256':rt.sha(rt.canonical(self.binding)),
   'single_account':True,'graph_used':False,'max_actions':90,'max_wall_seconds':720,'native_window_sha256':'c'*64,'viewport':[1000,700],'native_before_ref':before,'native_before_sha256':before['sha256'],
   'owner_slot':'shared-base','source_reviewed':True,'checkpoint_path':None,'checkpoint_sha256':rt.sha(MODEL.encode()),'seed':23,'max_output_tokens':512,'selection_or_final_eligible':False,'official_final_credit':0}
 def tearDown(self):self.temp.cleanup()
 def test_actual_generic_ppt_identity_admits_train_without_formal_credit(self):
  self.assertEqual(validate_admission(self.admission,package=self.package,runtime_binding=self.binding)['official_final_credit'],0)
 def test_fake_final_authority_refuses_before_process_factory(self):
  self.admission['mode']='formal_final';path=self.root/'admission.private.json';rt.write_new(path,rt.canonical(self.admission));calls=[]
  with self.assertRaises(ValueError):GenericOfficePaidSampler(admission_path=path,package=self.package,runtime_binding=self.binding,output_root=self.root/'sampler',repo_root=self.root,authority=object(),delegate_factory=lambda **kwargs:calls.append(kwargs))
  self.assertEqual(calls,[]);self.assertFalse((self.root/'sampler').exists())
 def test_checkpoint_native_before_or_uniform_caps_tamper_rejected(self):
  for field,value in [('checkpoint_sha256','f'*64),('native_before_sha256','f'*64),('max_actions',91),('max_wall_seconds',721),('folder_scope_sha256','f'*64)]:
   edited={**self.admission,field:value}
   with self.assertRaises(ValueError):validate_admission(edited,package=self.package,runtime_binding=self.binding)
 def test_generic_excel_package_identity_uses_same_admission_rule(self):
  # Admission identity validation is independent of PPT-only legacy prefixes.
  # SEC saved-artifact scoring has separate actual-corpus qualification.
  self.package.actor=rt.ActorTask('sec-native-train-generic',self.package.binding_sha256,'excel-web','train','Visible workbook task only','d'*64)
  self.admission.update(cell_id='excel-web',task_id=self.package.actor.task_id)
  self.assertEqual(validate_admission(self.admission,package=self.package,runtime_binding=self.binding)['cell_id'],'excel-web')

if __name__=='__main__':unittest.main()
