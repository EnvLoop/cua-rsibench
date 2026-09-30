"""Offline no-replay, reset math and physical-scheduling evidence guards."""
import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from gitlab_world import v066_post_reset_continuation_v2 as c
from gitlab_world import v066_case6_saved_reconciliation_v1 as r


class ContinuationGuards(unittest.TestCase):
 def test_only_untouched7_to99_with_same300_reset_math(self):
  self.assertEqual(c.expected_entry_generation(7),23)
  self.assertEqual(c.generations(7),[24,25,26]);self.assertEqual(c.generations(99),[300,301,302])
  self.assertEqual(len({g for i in range(7,100) for g in c.generations(i)}),279)
 def test_consumed_case6_replay_skip_and_failed_new_intent_are_refused(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/c.NAMESPACE).mkdir();rows=[]
   for index in (5,6,8,99):
    with self.assertRaises(ValueError):c.append(root,rows,{'kind':'intent','task_index':index})
   self.assertFalse((root/c.NAMESPACE/'journal.private.jsonl').exists())
   c.append(root,rows,{'kind':'intent','task_index':7});raw=(root/c.NAMESPACE/'journal.private.jsonl').read_bytes()
   for index in (6,7,8):
    with self.assertRaises(ValueError):c.append(root,rows,{'kind':'intent','task_index':index})
   self.assertEqual((root/c.NAMESPACE/'journal.private.jsonl').read_bytes(),raw)
   c.append(root,rows,{'kind':'terminal','task_index':7,'passed':False})
   with self.assertRaises(ValueError):c.append(root,rows,{'kind':'intent','task_index':8})
 def test_terminal_boolean_and_hash_cannot_be_reclassified(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/c.NAMESPACE).mkdir();rows=[];c.append(root,rows,{'kind':'intent','task_index':7})
   with self.assertRaises(ValueError):c.append(root,rows,{'kind':'terminal','task_index':7,'passed':1})
   rows[0]['task_index']=8
   with self.assertRaises(ValueError):c.journal_state(rows)
 def test_execute_false_cannot_touch_authority_or_runtime(self):
  with patch.object(c,'checked_permit',side_effect=AssertionError('No saved or live boundary')):
   with self.assertRaises(ValueError):c.run(authority=Path('missing'),permit=Path('missing'))
 def test_permit7_range_generation_and_root_review_are_bound(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);authority=root/'authority';c.source.write_new(authority,{'audit':'saved'})
   binding={'authority_path':str(authority),'authority_sha256':c.source.sha(authority.read_bytes()),'source_sha256s':{},
    'original_cohort_plan_sha256':'a'*64,'first_index':7,'maximum_control_count':93,'journal_head_sha256':'0'*64,
    'entry_generation':23,'old_intent_replay_authorized':False,'model_calls':0,'official_final_admitted':0}
   review=root/'review';c.source.write_new(review,{**binding,'schema':'envloop-gitlab-v6-post-reset-root-review-v2','note':'Explicit offline source review fixture'})
   permit=root/'permit';base={**binding,'schema':c.PERMIT_SCHEMA,'root_review_path':str(review),
    'root_review_sha256':c.source.sha(review.read_bytes()),'execution_authorized':True};c.source.write_new(permit,base)
   with patch.object(c,'checked_authority',return_value=({}, {}, {}, 'a'*64, {})),patch.object(c,'source_hashes',return_value={}):
    c.checked_permit(authority,permit)
    for changes in [{'first_index':6},{'first_index':100},{'maximum_control_count':94},{'entry_generation':22},
                    {'schema':'legacy'},{'old_intent_replay_authorized':True},{'model_calls':1}]:
     permit.write_bytes(json.dumps({**base,**changes}).encode())
     with self.assertRaises(ValueError):c.checked_permit(authority,permit)
 def test_v1_namespace_and_frozen_runtime_are_not_modified(self):
  self.assertNotEqual(c.NAMESPACE,c.legacy.NAMESPACE)
  self.assertEqual(c.legacy.NAMESPACE,'audit-only-continuation-controls-v1')
  self.assertIs(c.scoped,c.legacy.scoped);self.assertIs(c.verify,c.legacy.verify)
  self.assertNotEqual(c.JOURNAL_SCHEMA,c.legacy.JOURNAL_SCHEMA)


class PhysicalSchedulingGuards(unittest.TestCase):
 def fixture(self,root):
  original=root/'original';p=original/'work/gitlab-overlay-memory-maintenance-root-20260930.private/plan.private.json'
  p.parent.mkdir(parents=True)
  paths={role:{kind:'/vm/'+role+'/'+kind for kind in ['lower','upper','work','merged']} for role in ['config','logs','data']}
  plan={'original_container_id':'container-id','metadata_sha256s':{'old':'m'*64},'core_source_sha256s':{'core':'s'*64},
    'original_seed_volume_identities':{'config':'seed-id'},'overlay_recipe':paths}
  c.source.write_new(p,plan)
  epoch=root/'epoch';epoch.mkdir();c.source.write_new(epoch/'runtime.env',{'fake':'not a real environment'})
  env_sha=r.sha_private(epoch/'runtime.env')
  stats={path:{'inode':10+i,'size':20,'mode':448,'uid':0,'gid':0,'mtime_ns':30} for i,path in enumerate(x for d in paths.values() for x in d.values())}
  doc={'schema':r.PHYSICAL_SCHEMA,'status':'unused_original31_gracefully_stopped_no_profile_change',
   'root_authorized':True,'no_active_lease_or_workers_verified':True,'spectator_running_before':True,
   'spectator_running_after':False,'spectator_id_unchanged':True,'successor_running_after':True,
   'no_wait_config_monitoring_or_task_data_change':True,'graceful_stop_exit_code':0,
   'spectator_container_id_sha256':c.source.sha(b'container-id'),'source_freeze_sha256':'f'*64,
   'metadata_sha256s_before':plan['metadata_sha256s'],'metadata_sha256s_after':plan['metadata_sha256s'],
   'core_source_sha256s_before':plan['core_source_sha256s'],'core_source_sha256s_after':plan['core_source_sha256s'],
   'frozen_bound_metadata_sha256s_before':{'frozen':'b'*64},'frozen_bound_metadata_sha256s_after':{'frozen':'b'*64},
   'seed_volume_identities_before':plan['original_seed_volume_identities'],'seed_volume_identities_after':plan['original_seed_volume_identities'],
   'successor_runtime_env_sha256_before':env_sha,'successor_runtime_env_sha256_after':env_sha,
   'vm_path_stat_before':stats,'vm_path_stat_after':copy.deepcopy(stats),'raw_evidence_refs':[],
   'model_calls':0,'provider_calls':0,'official_final_admitted':0,'control_credit':0}
  for i in range(4):
   path=root/f'raw-{i}';path.write_bytes(b'retained synthetic raw evidence');path.chmod(0o600)
   doc['raw_evidence_refs'].append({'path':path.name,'sha256':c.source.sha(path.read_bytes())})
  receipt=root/'stop-receipt';c.source.write_new(receipt,doc)
  value={'evaluator_root':str(original),'epoch_root':str(epoch),'_freeze_sha256':'f'*64,'bound_metadata_sha256s':{'frozen':'b'*64}}
  return receipt,doc,value,paths
 def test_fixed_seed_identity_and_truthful_mutable_log_metadata(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);receipt,doc,value,paths=self.fixture(root)
   doc['vm_path_stat_after'][paths['logs']['upper']]['mtime_ns']=99
   doc['vm_path_stat_after'][paths['logs']['merged']]['size']=24
   receipt.write_bytes(json.dumps(doc).encode())
   self.assertEqual(r.validate_physical_receipt(receipt,value=value)['control_credit'],0)
 def test_seed_replacement_missing_worker_proof_and_runtime_change_refused(self):
  for mutation in ['seed_inode','seed_mtime','upper_inode','metadata','runtime','worker','raw_evidence','credit']:
   with tempfile.TemporaryDirectory() as d:
    root=Path(d);receipt,doc,value,paths=self.fixture(root)
    if mutation=='seed_inode':doc['vm_path_stat_after'][paths['data']['lower']]['inode']+=1
    elif mutation=='seed_mtime':doc['vm_path_stat_after'][paths['data']['lower']]['mtime_ns']+=1
    elif mutation=='upper_inode':doc['vm_path_stat_after'][paths['data']['upper']]['inode']+=1
    elif mutation=='metadata':doc['metadata_sha256s_after']={'changed':'x'*64}
    elif mutation=='runtime':doc['successor_runtime_env_sha256_after']='x'*64
    elif mutation=='worker':doc['no_active_lease_or_workers_verified']=False
    elif mutation=='raw_evidence':(root/'raw-0').write_bytes(b'changed')
    else:doc['control_credit']=1
    receipt.write_bytes(json.dumps(doc).encode())
    with self.assertRaises(ValueError):r.validate_physical_receipt(receipt,value=value)


if __name__=='__main__':unittest.main()
