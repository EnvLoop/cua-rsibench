"""Saved-only V3 provenance and source-review validation on 20/100 fixtures."""
from contextlib import ExitStack,contextmanager
from datetime import datetime,timezone
from hashlib import sha256
import copy,json,os,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image
from io import BytesIO
from enterprise_fallback.odoo18 import native_reference_split_finalizer_v3 as target


def write(path,value,raw=False):
 path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
 b=value if raw else target.canonical(value)
 path.write_bytes(b);path.chmod(0o600)
 return {'path':str(path.resolve()),'sha256':sha256(b).hexdigest()}


def picture():
 b=BytesIO();Image.new('RGB',(16,16),'white').save(b,'PNG');return b.getvalue()


@contextmanager
def fixture(root,count=20):
 split='selection' if count==20 else 'official_hidden';worker=root/split;private=worker/'private';run=private/'v066_native_surface_controls_v13'/'fresh-run'
 run.mkdir(mode=0o700,parents=True);stage=root/'stage';stage.mkdir(mode=0o700);qa=stage/'qa';qa.mkdir(mode=0o700)
 plan={'split':split,'task_count':count,'tasks':[],'fresh_run_directory_name':run.name,'native_worker_binding':{'binding_sha256':'a'*64},
  'native_adapter_binding_sha256':'b'*64,'run_nonce_sha256':'c'*64,'run_nonce_hex':'a'*32}
 outer={'native_core_plan':plan,'reference_binding':{'reference_binding_sha256':'d'*64,'max_scroll_actions_per_candidate':8}};world={'split':split,'cases':{f:[] for f in ('purchase','inventory','sales','crm')}}
 audits=[];qa_rows=[];review_rows=[];image=picture();stamp='2026-10-01T06:47:03+00:00'
 for i in range(count):
  family=list(world['cases'])[i//(count//4)];task=f'task-{i:03d}';case={'id':task,'family':family,'prompt':'Visible synthetic instruction','source_note':'Synthetic original source '+task}
  asset=case['source_note'].encode();package=target.digest(json.dumps(case,sort_keys=True).encode()+b'\n'+asset)
  metadata={'task_id':task,'family':family,'package_sha256':package,'source_asset_sha256':target.digest(asset),'visible_instruction_sha256':target.digest(case['prompt'].encode())}
  plan['tasks'].append(metadata);world['cases'][family].append(case)
  attempt=run/f'attempt-{i:03d}';attempt.mkdir(mode=0o700)
  frame=write(attempt/'frame.png',image,True)
  frame_ref={'path':'frame.png','sha256':frame['sha256']}
  action={'type':'click','step':0,'frame_id':f'frame-{i}','target':{'x':5,'y':5}}
  write(attempt/'actions/step-000-intent.private.json',{'step':0,'frame_id':action['frame_id'],'phase':'positive',
   'normalized_action':action,'dispatch_state':'intent_durable_before_gui_action','optional_native_facet_resolution':None,
   'native_candidate_viewport_resolution':{'status':'current_candidate_inside_viewport','candidate_bounds':{'x':1,'y':1,'width':8,'height':8},
    'viewport':[16,16],'scroll_selected_before_intent':False,'candidate_resolved_after_observation':True}})
  trace_ref=write(attempt/'trace.private.json',{'actions':[{'frame':frame_ref}]})
  receipt={**{k:metadata[k] for k in ('task_id','family','package_sha256')},'plan_sha256':None,'run_nonce_sha256':'c'*64,'model_attempts':0,'official_final_tasks_admitted':0,
   'finished_at_utc':'2026-10-01T06:00:00+00:00','refs':{'source_frame':frame_ref,'gui_trace':{'path':'trace.private.json','sha256':trace_ref['sha256']}}}
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
 write(stage/(plan['run_nonce_hex']+'-core-plan.private.json'),plan)
 write(stage/(plan['run_nonce_hex']+'-reference-intent.private.json'),{
  'schema':'odoo-native-reference-dispatch-intent-v3','plan_sha256':outer_ref['sha256'],'native_core_plan_sha256':core_sha,
  'reference_binding':outer['reference_binding'],'same_episode_replay_authorized':False,'native_actor_epoch':'v13','native_scorer_reset_unchanged':True})
 write(stage/(plan['run_nonce_hex']+'-reference-result.private.json'),{
  'schema':'odoo-native-reference-run-result-v3','reference_binding_sha256':'d'*64,
  'native_core_result':{key:value for key,value in result.items() if key!='audits'},'formal_registration_performed':False,'old_reference_control_credit':0})
 write(run/'batch-intent.private.json',{'plan_sha256':core_sha,'expected_case_count':count,'native_worker_binding_sha256':'a'*64,'run_nonce_sha256':'c'*64,
  'old_positive_credit':0,'automatic_replay_authorized':False,'model_attempts':0,'official_final_tasks_admitted':0,'fresh_train_control_sha256':'e'*64})
 write(private/'partition_cases.json',world)
 qa_value={'schema':'odoo-saved-native-source-visual-qa-manifest-v3','split':split,'case_count':count,'rows':qa_rows,'native_core_plan_sha256':core_sha,
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
   outer=outer,result=result,
   args={'plan_path':Path(outer_ref['path']),'worker_dir':worker,'run_dir':run,'source_review_path':review_path,'source_review_sha256':review_ref['sha256']})


class FinalizerTests(unittest.TestCase):
 def test_complete_twenty_and_hundred_support_additive_receipt_preserve_originals(self):
  for count in (20,100):
   with self.subTest(count=count),tempfile.TemporaryDirectory() as tmp,fixture(Path(tmp).resolve(),count) as f:
    output=f.stage/'derived.private.json';v=target.finalize(output_path=output,**f.args)
    self.assertEqual(v['qualified_control_case_count'],count);self.assertFalse(v['formal_registration_performed'])
    derived=json.loads(output.read_bytes())
    self.assertTrue(derived['v3_reference_run_provenance_verified'])
    self.assertEqual(derived['native_train_control_prerequisite_sha256'],'e'*64)
    self.assertFalse(derived['native_train_prerequisite_is_v3_reference_train_credit'])
    self.assertEqual(derived['v3_reference_train_control_credit'],0)
    self.assertTrue(all(row['v3_reference_action_provenance_verified'] for row in derived['rows']))
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

 def test_native_only_old_absent_and_corrupt_reference_provenance_refuse(self):
  for suffix in ('core-plan','reference-intent','reference-result'):
   for kind in ('absent','corrupt'):
    with self.subTest(suffix=suffix,kind=kind),tempfile.TemporaryDirectory() as tmp,fixture(Path(tmp).resolve()) as f:
     path=f.stage/(f.outer['native_core_plan']['run_nonce_hex']+'-'+suffix+'.private.json')
     if kind=='absent':path.unlink()
     else:path.write_bytes(b'{broken')
     with self.assertRaises(ValueError):target.derive(**f.args)
  changes=[('reference-intent',lambda v:v.update(schema='odoo-native-reference-dispatch-intent-v2')),
   ('reference-intent',lambda v:v.update(plan_sha256='0'*64)),
   ('reference-intent',lambda v:v.update(native_core_plan_sha256='0'*64)),
   ('reference-intent',lambda v:v['reference_binding'].update(reference_binding_sha256='0'*64)),
   ('reference-intent',lambda v:v.update(same_episode_replay_authorized=True)),
   ('reference-result',lambda v:v.update(schema='odoo-native-reference-run-result-v2')),
   ('reference-result',lambda v:v.update(reference_binding_sha256='0'*64)),
   ('reference-result',lambda v:v['native_core_result'].update(fresh_native_gui_controls=1)),
   ('reference-result',lambda v:v.update(old_reference_control_credit=1)),
   ('reference-result',lambda v:v.update(formal_registration_performed=True)),
   ('core-plan',lambda v:v.update(run_nonce_sha256='0'*64))]
  for suffix,change in changes:
   with self.subTest(suffix=suffix),tempfile.TemporaryDirectory() as tmp,fixture(Path(tmp).resolve()) as f:
    path=f.stage/(f.outer['native_core_plan']['run_nonce_hex']+'-'+suffix+'.private.json')
    value=json.loads(path.read_bytes());change(value);write(path,value)
    with self.assertRaises(ValueError):target.derive(**f.args)

 def test_old_or_inconsistent_locator_action_resolution_refuse(self):
  changes=[lambda v:v.pop('native_candidate_viewport_resolution'),lambda v:v.pop('optional_native_facet_resolution'),
   lambda v:v.update(native_candidate_viewport_resolution=None),
   lambda v:v['native_candidate_viewport_resolution'].update(candidate_resolved_after_observation=False),
   lambda v:v['native_candidate_viewport_resolution'].update(viewport=[16,17]),
   lambda v:v['native_candidate_viewport_resolution'].update(scroll_selected_before_intent=True),
   lambda v:v['native_candidate_viewport_resolution']['candidate_bounds'].update(y=-1),
   lambda v:v['normalized_action'].update(target={'x':6,'y':5})]
  for change in changes:
   with tempfile.TemporaryDirectory() as tmp,fixture(Path(tmp).resolve()) as f:
    path=f.run/'attempt-000/actions/step-000-intent.private.json';value=json.loads(path.read_bytes());change(value);write(path,value)
    with self.assertRaises(ValueError):target.derive(**f.args)

 def test_guarded_scroll_requires_fresh_frame_and_original_deferred_action(self):
  for kind in ('valid','reused-frame','missing-original','wrong-original','bound-exhausted','wrong-scroll-delta'):
   with self.subTest(kind=kind),tempfile.TemporaryDirectory() as tmp,fixture(Path(tmp).resolve()) as f:
    attempt=f.run/'attempt-000';receipt=json.loads((attempt/'attempt.private.json').read_bytes())
    first={'step':0,'frame_id':'scroll-frame','phase':'positive','dispatch_state':'intent_durable_before_gui_action',
     'normalized_action':{'type':'scroll','step':0,'frame_id':'scroll-frame','target':{'x':8,'y':8},'dx':0,'dy':480},
     'optional_native_facet_resolution':None,'native_candidate_viewport_resolution':{'status':'offviewport_candidate_guarded_scroll_selected',
      'candidate_bounds':{'x':1,'y':15,'width':8,'height':4},'viewport':[16,16],'scroll_selected_before_intent':True,
      'candidate_resolved_after_observation':True,'scroll_target_kind':'current_viewport_center_subject_to_native_ownership_hit_guard',
      'original_action_type':'click','original_action_deferred':True}}
    second={'step':1,'frame_id':'click-frame','phase':'positive','dispatch_state':'intent_durable_before_gui_action',
     'normalized_action':{'type':'click','step':1,'frame_id':'click-frame','target':{'x':5,'y':13}},
     'optional_native_facet_resolution':None,'native_candidate_viewport_resolution':{'status':'current_candidate_inside_viewport',
      'candidate_bounds':{'x':1,'y':11,'width':8,'height':4},'viewport':[16,16],'scroll_selected_before_intent':False,
      'candidate_resolved_after_observation':True}}
    if kind=='wrong-scroll-delta':first['normalized_action']['dy']=4
    if kind=='reused-frame':second['frame_id']=second['normalized_action']['frame_id']='scroll-frame'
    if kind=='wrong-original':second['normalized_action']['type']='double_click'
    write(attempt/'actions/step-000-intent.private.json',first)
    if kind!='missing-original':write(attempt/'actions/step-001-intent.private.json',second)
    count=1 if kind=='missing-original' else 2
    trace=write(attempt/'trace.private.json',{'actions':[{'frame':receipt['refs']['source_frame']} for _ in range(count)]})
    receipt['refs']['gui_trace']={'path':'trace.private.json','sha256':trace['sha256']}
    reference={**f.outer['reference_binding'],'max_scroll_actions_per_candidate':0 if kind=='bound-exhausted' else 8}
    args=(target.SavedReader(),attempt,receipt,{'native_guard_action_count':count},reference)
    if kind=='valid':
     value=target._v3_action_provenance(*args);self.assertEqual(value['reference_viewport_scroll_action_count'],1)
    else:
     with self.assertRaises(ValueError):target._v3_action_provenance(*args)


if __name__=="__main__":unittest.main()
