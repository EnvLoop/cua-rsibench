"""Saved-only review validation and production read-only actual20 replay."""
from contextlib import ExitStack,contextmanager
from datetime import datetime,timezone
from hashlib import sha256
import copy,json,os,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image
from io import BytesIO
from enterprise_fallback.odoo18 import native_reference_split_finalizer_v1 as target


def write(path,value,raw=False):
 path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
 b=value if raw else target.canonical(value)
 path.write_bytes(b);path.chmod(0o600)
 return {'path':str(path.resolve()),'sha256':sha256(b).hexdigest()}


def picture():
 b=BytesIO();Image.new('RGB',(16,16),'white').save(b,'PNG');return b.getvalue()


@contextmanager
def fixture(root,count=20):
 split='selection' if count==20 else 'official_hidden';worker=root/split;private=worker/'private';run=private/'v066_native_surface_controls_v12'/'fresh-run'
 run.mkdir(mode=0o700,parents=True);stage=root/'stage';stage.mkdir(mode=0o700);qa=stage/'qa';qa.mkdir(mode=0o700)
 plan={'split':split,'task_count':count,'tasks':[],'fresh_run_directory_name':run.name,'native_worker_binding':{'binding_sha256':'a'*64},
  'native_adapter_binding_sha256':'b'*64,'run_nonce_sha256':'c'*64}
 outer={'native_core_plan':plan,'reference_binding':{'reference_binding_sha256':'d'*64}};world={'split':split,'cases':{f:[] for f in ('purchase','inventory','sales','crm')}}
 audits=[];qa_rows=[];review_rows=[];image=picture();stamp='2026-10-01T06:47:03+00:00'
 for i in range(count):
  family=list(world['cases'])[i//(count//4)];task=f'task-{i:03d}';case={'id':task,'family':family,'prompt':'Visible synthetic instruction','source_note':'Synthetic original source '+task}
  asset=case['source_note'].encode();package=target.digest(json.dumps(case,sort_keys=True).encode()+b'\n'+asset)
  metadata={'task_id':task,'family':family,'package_sha256':package,'source_asset_sha256':target.digest(asset),'visible_instruction_sha256':target.digest(case['prompt'].encode())}
  plan['tasks'].append(metadata);world['cases'][family].append(case)
  attempt=run/f'attempt-{i:03d}';attempt.mkdir(mode=0o700)
  frame=write(attempt/'frame.png',image,True)
  receipt={**{k:metadata[k] for k in ('task_id','family','package_sha256')},'plan_sha256':None,'run_nonce_sha256':'c'*64,'model_attempts':0,'official_final_tasks_admitted':0,
   'finished_at_utc':'2026-10-01T06:00:00+00:00','refs':{'source_frame':{'path':'frame.png','sha256':frame['sha256']}}}
  audit={'independent_baseline_reward':0.0,'independent_positive_reward':1.0,'independent_wrong_object_reward':0.0,
   'native_guard_action_count':1,'source_visual_review_pending':True,'source_visual_review_verified':False}
  write(attempt/'attempt.private.json',receipt);audit_ref=write(attempt/'independent-audit.private.json',audit)
  folder=qa/str(i);folder.mkdir(mode=0o700);asset_ref=write(folder/'asset.txt',asset,True);copy_ref=write(folder/'copy.png',image,True);pair_ref=write(folder/'pair.png',image,True)
  qa_rows.append({**{k:metadata[k] for k in ('family','task_id','package_sha256','source_asset_sha256')},'index':i+1,'ordinal':i,
   'original_native_frame':frame,'exact_source_asset_copy':asset_ref,'unchanged_native_frame_copy':copy_ref,'side_by_side_qa':pair_ref,'native_crop_origin':[0,0]})
  review_rows.append({**{k:metadata[k] for k in ('family','task_id','package_sha256','source_asset_sha256')},'index':i+1,'ordinal':i,
   'source_frame_sha256':frame['sha256'],'attempt_sha256':None,'audit_sha256':audit_ref['sha256'],'qa_pair_sha256':pair_ref['sha256'],
   'reviewer_independent_of_actor':True,'source_attachment_readable':True,'source_matches_package':True,'reviewed_at_utc':stamp,'review_notes':'Independent source inspection fixture'})
  audits.append({'task_id':task,'family':family,'attempt_sha256':None,'audit_sha256':audit_ref['sha256'],'audit':audit})
 core_sha=target.digest(target.canonical(plan));outer_ref=write(stage/'plan.private.json',outer)
 for i in range(count):
  path=run/f'attempt-{i:03d}'/'attempt.private.json';v=json.loads(path.read_bytes());v['plan_sha256']=core_sha;ref=write(path,v)
  review_rows[i]['attempt_sha256']=audits[i]['attempt_sha256']=ref['sha256']
 result={'schema':'native-batch-fixture','status':'full_native_surface_gui_control_semantics_verified_source_visual_review_pending','split':split,
  'fresh_native_gui_controls':count,'expected_case_count':count,'source_visual_review_pending':True,'model_attempts':0,'official_final_tasks_admitted':0,'old_positive_credit':0,
  'plan_sha256':core_sha,'native_worker_binding_sha256':'a'*64,'native_adapter_binding_sha256':'b'*64,'run_nonce_sha256':'c'*64,
  'task_roster_sha256':target.digest(target.canonical(plan['tasks'])),'audits':audits}
 result_ref=write(run/'result.private.json',result)
 write(run/'batch-intent.private.json',{'plan_sha256':core_sha,'expected_case_count':count,'native_worker_binding_sha256':'a'*64,'run_nonce_sha256':'c'*64,
  'old_positive_credit':0,'automatic_replay_authorized':False,'model_attempts':0,'official_final_tasks_admitted':0,'fresh_train_control_sha256':'e'*64})
 write(private/'partition_cases.json',world)
 qa_value={'schema':'odoo-saved-native-source-visual-qa-manifest-v1','split':split,'case_count':count,'rows':qa_rows,'native_core_plan_sha256':core_sha,
  'native_binding_sha256':'a'*64,'reference_binding_sha256':'d'*64,'actual_result_ref':result_ref,'outer_plan_ref':outer_ref,'generated_at_utc':'2026-10-01T06:10:00+00:00'}
 qa_ref=write(qa/'manifest.private.json',qa_value)
 review={'schema':target.REVIEW_SCHEMA,'status':target.REVIEW_STATUS,'split':split,'expected_case_count':count,'outer_plan_sha256':outer_ref['sha256'],
  'native_core_plan_sha256':core_sha,'native_worker_binding_sha256':'a'*64,'native_adapter_binding_sha256':'b'*64,'reference_binding_sha256':'d'*64,'run_nonce_sha256':'c'*64,
  'require_exact_task_roster_order':True,'no_formal_registration_by_review_alone':True,'reviewer_approval':True,'rows':review_rows,'actual_result_ref':result_ref,'qa_manifest_ref':qa_ref}
 review_path=stage/'review.private.json';review_ref=write(review_path,review)
 original={str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()}
 replay=SimpleNamespace(_case_row=lambda *args:{},audit_case=lambda **kw:json.loads((kw['attempt']/'independent-audit.private.json').read_bytes()))
 with ExitStack() as stack:
  stack.enter_context(patch.object(target.qualification,'validate_plan',lambda _:None))
  stack.enter_context(patch.object(target.qualification,'_facade',return_value=replay))
  stack.enter_context(patch.object(target.qualification.core,'BATCH_SCHEMA','native-batch-fixture'))
  stack.enter_context(patch.object(target.partition_factory,'source_asset',lambda case,world:case['source_note'].encode()))
  yield SimpleNamespace(root=root,stage=stage,run=run,worker=worker,review=review,review_path=review_path,original=original,
   args={'plan_path':Path(outer_ref['path']),'worker_dir':worker,'run_dir':run,'source_review_path':review_path,'source_review_sha256':review_ref['sha256']})


class FinalizerTests(unittest.TestCase):
 def test_complete_twenty_and_hundred_support_additive_receipt_preserve_originals(self):
  for count in (20,100):
   with self.subTest(count=count),tempfile.TemporaryDirectory() as tmp,fixture(Path(tmp).resolve(),count) as f:
    output=f.stage/'derived.private.json';v=target.finalize(output_path=output,**f.args)
    self.assertEqual(v['qualified_control_case_count'],count);self.assertFalse(v['formal_registration_performed'])
    for path,raw in f.original.items():self.assertEqual(Path(path).read_bytes(),raw)
    with self.assertRaisesRegex(ValueError,'fresh_private'):target.finalize(output_path=output,**f.args)
 def test_missing_corrupt_partial_old_reordered_unknown_and_self_authored_reviews_reject(self):
  changes=[lambda v:v['rows'].pop(),lambda v:v['rows'].reverse(),lambda v:v.update(reviewer_approval=False),lambda v:v.update(schema='old-review'),
   lambda v:v.update(unknown=True),lambda v:v['rows'][0].update(source_attachment_readable=None),lambda v:v['rows'][0].update(reviewed_at_utc='2026-09-30T00:00:00+00:00'),
   lambda v:v['rows'][0].update(source_frame_sha256='0'*64),lambda v:v['rows'][0].update(package_sha256='0'*64),lambda v:v['rows'][0].update(audit_sha256='0'*64)]
  for change in changes:
   with tempfile.TemporaryDirectory() as tmp,fixture(Path(tmp).resolve()) as f:
    value=copy.deepcopy(f.review);change(value);ref=write(f.review_path,value);args={**f.args,'source_review_sha256':ref['sha256']}
    with self.assertRaises(ValueError):target.derive(**args)
  with tempfile.TemporaryDirectory() as tmp,fixture(Path(tmp).resolve()) as f:
   f.review_path.unlink()
   with self.assertRaises(ValueError):target.derive(**f.args)
  with tempfile.TemporaryDirectory() as tmp,fixture(Path(tmp).resolve()) as f:
   with self.assertRaisesRegex(ValueError,'hash_changed'):target.derive(**{**f.args,'source_review_sha256':'0'*64})
 def test_wrong_saved_score_source_copy_failed_result_and_outside_output_refuse(self):
  for kind in ('saved','source','failed'):
   with self.subTest(kind=kind),tempfile.TemporaryDirectory() as tmp,fixture(Path(tmp).resolve()) as f:
    if kind=='saved':write(f.run/'attempt-000/independent-audit.private.json',{'changed':True})
    elif kind=='source':(f.stage/'qa/0/asset.txt').write_bytes(b'changed')
    else:write(f.run/'failed.private.json',{'failed':True})
    with self.assertRaises(ValueError):target.derive(**f.args)
  with tempfile.TemporaryDirectory() as tmp,fixture(Path(tmp).resolve()) as f:
   with self.assertRaisesRegex(ValueError,'fresh_private'):target.finalize(output_path=f.run/'forbidden-rewrite.json',**f.args)


class ActualSavedReplay(unittest.TestCase):
 def test_production_read_only_actual_root_review_twenty_cases(self):
  stage=Path('/Users/xiaoyong/Documents/Codex/2026-09-22/magento-observer-fix/work/odoo-native-reference-v1-root-20261001.private')
  review=stage/'root-full20-source-visual-review.private.json'
  if not review.exists():self.skipTest('private actual20 proof is unavailable')
  worker=Path('/Users/xiaoyong/Documents/Codex/2026-09-25/odoo-four-workflows/enterprise_fallback/odoo18/partition_workers/selection')
  run=worker/'private/v066_native_surface_controls_v12/native-v12-2bb7c47798fa4713cf207c274f56d469'
  before=(run/'result.private.json').read_bytes()
  value=target.derive(plan_path=stage/'selection-plan.private.json',worker_dir=worker,run_dir=run,
   source_review_path=review,source_review_sha256='4539fd602b5c8ebf4f43c0cecabb963473a1d7adc246f53eb73a2c556ec6af09')
  self.assertEqual(value['qualified_control_case_count'],20);self.assertEqual(value['original_pending_result_sha256'],sha256(before).hexdigest())
  self.assertEqual(value['original_pending_result_sha256'],'758dcece7184deac295b6fd590bd641cb8752158875cfe334b4234aae3152721')
  self.assertEqual((run/'result.private.json').read_bytes(),before);self.assertFalse(value['formal_registration_performed'])
  self.assertEqual(value['native_calls'],0)

if __name__=='__main__':unittest.main()
