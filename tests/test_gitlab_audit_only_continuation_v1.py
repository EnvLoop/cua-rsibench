"""Offline one-use/reset/capture/source seams; no Docker or private task reads."""
import asyncio,copy,json,os,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from gitlab_world import v066_audit_only_continuation_v1 as c
from gitlab_world import factory,gui_controls,verify

class ContinuationTests(unittest.TestCase):
 def test_reset_cleanup_gap_and_full_denominator_math(self):
  self.assertEqual(c.generations(0),[2,3,4]);self.assertEqual(c.generations(4),[14,15,16])
  self.assertEqual(c.expected_entry_generation(5),17);self.assertEqual(c.generations(5),[18,19,20])
  self.assertEqual(c.generations(99),[300,301,302]);self.assertEqual(c.expected_entry_generation(99),299)
  self.assertEqual(len({g for i in range(100) for g in c.generations(i)}),300)
  self.assertNotIn(17,{g for i in range(100) for g in c.generations(i)})
 def test_new_journal_cannot_replay_skip_or_reclassify_terminal(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/c.NAMESPACE).mkdir();rows=[]
   c.append(root,rows,{'kind':'intent','task_index':5})
   before=(root/c.NAMESPACE/'journal.private.jsonl').read_bytes()
   for index in [4,5,6]:
    with self.assertRaises(ValueError):c.append(root,rows,{'kind':'intent','task_index':index})
   self.assertEqual((root/c.NAMESPACE/'journal.private.jsonl').read_bytes(),before)
   c.append(root,rows,{'kind':'terminal','task_index':5,'passed':False})
   with self.assertRaises(ValueError):c.append(root,rows,{'kind':'intent','task_index':6})
 def test_exact_terminal_boolean_and_hash_chain_required(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/c.NAMESPACE).mkdir();rows=[];c.append(root,rows,{'kind':'intent','task_index':5})
   with self.assertRaises(ValueError):c.append(root,rows,{'kind':'terminal','task_index':5,'passed':1})
   bad=copy.deepcopy(rows);bad[0]['task_index']=6
   with self.assertRaises(ValueError):c.journal_state(bad)
 def test_no_live_without_explicit_execute(self):
  with patch.object(c,'checked_permit',side_effect=AssertionError('No authority or app call')):
   with self.assertRaises(ValueError):c.run(authority=Path('/absent'),permit=Path('/absent'))
 def test_capture_pins_tree_diff_and_blobs_to_snapshot_commit(self):
  with tempfile.TemporaryDirectory() as d:
   folder=Path(d);folder.chmod(0o700);calls=[];before={'business_sha256':'b'*64,'git':{'7':{'refs':{'refs/heads/main':'1'*40}}}};after={'business_sha256':'a'*64,'git':{'7':{'refs':{'refs/heads/main':'2'*40}}}}
   def git(pid,*args):calls.append((pid,*args));return b'raw-private-proof'
   with patch.object(verify,'_context',return_value=({}, {'project_id':7})),patch.object(verify,'_git',side_effect=git),patch.object(verify,'git_blob',side_effect=AssertionError('Unpinned mutable main read forbidden')):
    proof=c.capture_git({'task':'opaque'},before,after,folder)
   self.assertEqual(proof['after_main_sha'],'2'*40);self.assertEqual(len(proof['main_blob_refs']),6)
   shows=[a for a in calls if a[1]=='show'];self.assertEqual(len(shows),6)
   self.assertTrue(all(a[2].startswith('2'*40+':') for a in shows))
   self.assertEqual(calls[0],(7,'diff','--name-only','1'*40,'2'*40))
 def test_readonly_hook_does_not_mutate_frozen_module_globals(self):
  original_attempt=gui_controls.attempt;original_live=c.original.lane.live_one;called=[]
  async def fake_attempt(_browser,_task,_variant,_label,folder):
   path=folder/'label';path.mkdir(mode=0o700);c.source.write_new(path/'after-persisted-state.json',{'saved':'native'});return {'saved':True}
  async def fake_live(plan,sha,index,run,baseline):
   return await gui_controls.attempt(None,{'task':'opaque'},None,'label',run)
  with tempfile.TemporaryDirectory() as d:
   with patch.object(gui_controls,'attempt',fake_attempt),patch.object(c.original.lane,'live_one',fake_live),patch.object(c,'capture_git',side_effect=lambda *a:called.append(a)):
    namespace_attempt=gui_controls.attempt;namespace_live=c.original.lane.live_one
    result=asyncio.run(c.live_one({},'s',5,Path(d),{}))
    self.assertIs(gui_controls.attempt,namespace_attempt);self.assertIs(c.original.lane.live_one,namespace_live)
   self.assertEqual(result,{'saved':True});self.assertEqual(len(called),1)
  self.assertIs(gui_controls.attempt,original_attempt);self.assertIs(c.original.lane.live_one,original_live)

class SupervisionAndPermitTests(unittest.TestCase):
 def fixture(self,root):
  folder=root/c.NAMESPACE/'supervision';folder.mkdir(parents=True,mode=0o700);folder.chmod(0o700)
  for name in ['005-stdout.private.log','005-stderr.private.log']:
   p=folder/name;p.write_bytes(b'');p.chmod(0o600)
  intent={'kind':'intent','task_index':5,'task_id':'task','package_sha256':'a'*64,'expected_entry_generation':17,'supervisor_pid':101,'permit_sha256':'p'*64,'authority_sha256':'b'*64,'entry_sha256':'c'*64}
  child={'child_pid':102,'exit_code':0,'child_terminated':True,'process_group_terminated':True,'group_survivor_observed_after_child_wait':False,'timed_out':False,'termination_unconfirmed':False,'stdout_sha256':c.source.sha(b''),'stderr_sha256':c.source.sha(b'')}
  marker={'schema':'envloop-gitlab-v6-audit-only-child-started-v1','task_index':5,'child_pid':102,'parent_pid':101,'pending_intent_sha256':'c'*64,'permit_sha256':'p'*64,'authority_sha256':'b'*64,'old_intent_replay_authorized':False}
  c.source.write_new(folder/'005-child-started.private.json',marker)
  result={'schema':'envloop-gitlab-v6-audit-only-supervised-private-v1','index':5,'passed':True,'child':child};sha=c.source.write_new(folder/'005-result.private.json',result)
  rows=[intent,{'kind':'terminal','task_index':5,'supervisor_result_sha256':sha}];plan={'task_roster':[{}]*5+[{'task_id':'task','package_sha256':'a'*64}]}
  return folder,rows,plan,marker
 def test_completed_child_marker_logs_group_and_task_bound(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);folder,rows,plan,marker=self.fixture(root)
   self.assertTrue(c._future_supervision(root,5,rows,'b'*64,plan)['passed'])
   for mutation in ['marker','log','package','generation']:
    with self.subTest(mutation=mutation):
     if mutation=='marker':bad={**marker,'permit_sha256':'z'*64};(folder/'005-child-started.private.json').write_bytes(json.dumps(bad,sort_keys=True).encode())
     elif mutation=='log':(folder/'005-stdout.private.log').write_bytes(b'altered')
     elif mutation=='package':rows[0]['package_sha256']='z'*64
     else:rows[0]['expected_entry_generation']=16
     with self.assertRaises(ValueError):c._future_supervision(root,5,rows,'b'*64,plan)
     (folder/'005-child-started.private.json').write_bytes(json.dumps(marker,sort_keys=True).encode());(folder/'005-stdout.private.log').write_bytes(b'');rows[0]['package_sha256']='a'*64;rows[0]['expected_entry_generation']=17
 def test_permit_requires_exact_range_generation_schema_and_authority(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);authority=root/'authority';c.source.write_new(authority,{'closed':'authority'})
   binding={'authority_path':str(authority),'authority_sha256':c.source.sha(authority.read_bytes()),'source_sha256s':{},'original_cohort_plan_sha256':'a'*64,'first_index':5,'maximum_control_count':2,'journal_head_sha256':'0'*64,'entry_generation':17,'old_intent_replay_authorized':False,'model_calls':0,'official_final_admitted':0}
   review=root/'review';c.source.write_new(review,{**binding,'schema':'envloop-gitlab-v6-audit-only-root-review-v1','note':'Source-only fake guard'})
   permit=root/'permit';base={**binding,'schema':c.PERMIT_SCHEMA,'root_review_path':str(review),'root_review_sha256':c.source.sha(review.read_bytes()),'execution_authorized':True}
   c.source.write_new(permit,base)
   with patch.object(c,'checked_authority',return_value=({}, {}, {}, 'a'*64, {})),patch.object(c,'source_hashes',return_value={}):
    c.checked_permit(authority,permit)
    for change in [{'first_index':4},{'first_index':100},{'maximum_control_count':96},{'entry_generation':16},{'authority_path':'different'},{'old_intent_replay_authorized':True},{'execution_authorized':False},{'schema':'legacy'}]:
     permit.write_bytes(json.dumps({**base,**change}).encode())
     with self.assertRaises(ValueError):c.checked_permit(authority,permit)
 def test_capture_hook_failure_cannot_become_success(self):
  async def fake_attempt(_browser,_task,_variant,_label,folder):
   sub=folder/'case';sub.mkdir(mode=0o700);c.source.write_new(sub/'after-persisted-state.json',{});return {'score':1}
  async def fake_live(_plan,_sha,_index,root,_baseline):return await gui_controls.attempt(None,{},None,'case',root)
  with tempfile.TemporaryDirectory() as d,patch.object(gui_controls,'attempt',fake_attempt),patch.object(c.original.lane,'live_one',fake_live),patch.object(c,'capture_git',side_effect=ValueError('missing proof')):
   with self.assertRaises(ValueError):asyncio.run(c.live_one({},'s',5,Path(d),{}))
 def test_formal_oracle_cannot_use_historical_projection(self):
  with self.assertRaises(c.saved_git.SavedGitEvidenceError):c.saved_git.audit_formal_saved_task({}, {}, {},captured_git=None,read_ref=lambda r:b'')

if __name__=='__main__':unittest.main()
