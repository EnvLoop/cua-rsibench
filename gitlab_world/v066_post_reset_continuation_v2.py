"""Pre-model audit-only continuation of the unchanged v6 GitLab cohort.

The old terminal journal and native attempts remain immutable. This module
records a separate authority and one-use journal for untouched indices5..99.
Saved-Git proof is read-only recording; the frozen GUI/runtime/grader do not
change. Historical six-blob coverage is never called full-tree evidence.
"""
from __future__ import annotations
import argparse,asyncio,copy,fcntl,json,os,sys,time,types
from pathlib import Path
from . import factory,gui_controls,verify,reset
from . import v066_prospective_cohort_v6 as source
from . import v066_prospective_cohort_runtime_v6 as scoped
from . import v066_prospective_cohort_controller_v6 as original
from . import v066_supervised_final_one_v1 as supervisor
from . import v066_infra_requalification_v1 as process_audit
from . import v066_saved_git_oracle_v1 as saved_git

SCHEMA='envloop-gitlab-v6-post-reset-continuation-private-v2'
JOURNAL_SCHEMA='envloop-gitlab-v6-post-reset-continuation-journal-v2'
PERMIT_SCHEMA='envloop-gitlab-v6-post-reset-continuation-permit-v2'
NAMESPACE='post-reset-continuation-controls-v2'
from . import v066_audit_only_continuation_v1 as legacy
from . import v066_case6_saved_reconciliation_v1 as reconciliation

SOURCE_FILES=('gitlab_world/v066_post_reset_continuation_v2.py',
 'gitlab_world/v066_case6_saved_reconciliation_v1.py',
 'tests/test_gitlab_post_reset_continuation_v2.py',
 'docs/FULL_STUDY_GITLAB_V6_CASE6_SAVED_RECONCILIATION_2026-09-30.md',
 *legacy.SOURCE_FILES)



def require(ok,message):
 if not ok:raise ValueError(message)


def source_hashes():
 root=Path(__file__).resolve().parents[1]
 return {p:source.sha((root/p).read_bytes()) for p in SOURCE_FILES}


def generations(index):
 require(type(index) is int and 0<=index<100,'Control index out of cohort')
 first=2+3*index if index<5 else 18+3*(index-5)
 return list(range(first,first+3))


def _manifest(paths,root):
 return {str(path.relative_to(root)):source.sha(source.private(path)) for path in sorted(paths) if path.is_file()}


def preserved_manifest(root):
 paths=list((root/'controls').rglob('*'))
 paths += [root/name for name in ['bootstrap-receipt.private.json','cohort-plan.private.json','baseline-persisted-state.json',
  'world-private.json','native-acl.private.json','first-cold-readback.private.json','runtime.env','parent-archive-stop.private.json']]
 return _manifest(paths,root)


def _read_ref(root,ref):
 require(type(ref) is dict and set(ref)=={'path','sha256'},'Saved-Git ref shape changed')
 relative=Path(ref['path']);require(not relative.is_absolute() and '..' not in relative.parts,'Saved-Git path escaped attempt')
 path=root/relative
 for parent in [path,*path.parents]:
  if parent==root.parent:break
  require(not parent.is_symlink(),'Saved-Git ref crosses symlink')
 raw=source.private(path);require(source.sha(raw)==ref['sha256'],'Saved-Git bytes changed');return raw


def _corrected_auditor(value,plan,baseline,index):
 """Isolate the exact old reader; substitute only saved Git data and reset math."""
 path=Path(original.__file__);raw=path.read_bytes()
 require(source.sha(raw)==value['source_sha256s']['gitlab_world/v066_prospective_cohort_controller_v6.py'],'Frozen original reader changed')
 code=raw.decode();old="if generations!=list(range(2+3*index,5+3*index)):"
 require(code.count(old)==1,'Frozen reader generation seam changed')
 code=code.replace(old,"if generations!=expected_generations(index):",1)
 old="root=Path(value['epoch_root']);run=root/'controls';folder=run/'attempts'/f'{index:03d}';identity=plan['task_roster'][index]"
 require(code.count(old)==1,'Frozen reader control-root seam changed')
 code=code.replace(old,"root=Path(value['epoch_root']);run=corrected_run_root(root,index);folder=run/'attempts'/f'{index:03d}';identity=plan['task_roster'][index]",1)
 module=types.ModuleType('gitlab_world._saved_git_corrected_reader');module.__package__='gitlab_world';module.__file__=str(path)
 exec(compile(code,str(path),'exec'),module.__dict__)
 module.expected_generations=generations
 module.corrected_run_root=lambda root,i:root/'controls' if i<5 else root/NAMESPACE
 project,progress=verify._context(gui_controls._task(plan['task_roster'][index]['task_id']))
 folder=Path(value['epoch_root'])/('controls' if index<5 else NAMESPACE)/'attempts'/f'{index:03d}'
 coverage=[];phase_cursor=[0]
 def evaluated(task,before,after,**_flags):
  captured=None;captured_folder=None;captured_verdict=None
  phases=original.lane.CASES[task['template_group']]
  if phase_cursor[0]<3:
   label=phases[phase_cursor[0]][0];phase_cursor[0]+=1;candidate=folder/label
   require(json.loads(source.private(candidate/'after-persisted-state.json'))==after,'Saved reader phase order/state changed')
   captured_verdict=json.loads(source.private(candidate/'receipt.json'))['persisted_oracle']
   require(index<5 or (candidate/'git-sidecar.private.json').exists(),'Untouched continuation case missing full Git sidecar')
   if (candidate/'git-sidecar.private.json').exists():
    captured=json.loads(source.private(candidate/'git-sidecar.private.json'));captured_folder=candidate
  # An unrelated database perturbation is rejected by the unchanged database
  # predicates before Git is inspected; it does not borrow a positive proof.
  audited=saved_git.audit_saved_task(task,before,after,project=project,progress=progress,
   captured_git=captured,read_ref=None if captured_folder is None else lambda ref:_read_ref(captured_folder,ref),captured_verdict=captured_verdict,expected_verifier_sha256=value['source_sha256s']['gitlab_world/verify.py'])
  coverage.append(audited)
  return audited['verdict']
 proxy=types.SimpleNamespace(**verify.__dict__);proxy.evaluate_final_task=evaluated;module.verify=proxy
 return module,coverage


def audit_one(value,plan,plan_sha,baseline,index):
 reader,coverage=_corrected_auditor(value,plan,baseline,index)
 result=reader.audit_one(value=value,plan=plan,plan_sha=plan_sha,baseline=baseline,index=index)
 case_reviews=[r for r in coverage if r.get('captured_live_verdict_matches') is not None]
 require(len(case_reviews)==3 and all(r.get('captured_live_verdict_matches') is True for r in case_reviews),'All three raw case verdicts must independently match the retained live results')
 full=all(r.get('full_git_tree_verified') is True for r in case_reviews)
 require(index<5 or full,'Future raw case Git proof incomplete')
 return {**result,'saved_git_oracle_reviews':coverage,'historical_full_tree_evidence_retained':full,
  'historical_live_verdict_is_authority':False,'reader_only_correction':True}


def _supervision(root,index,rows,freeze_sha):
 folder=root/'controls/supervision';raw=source.private(folder/f'{index:03d}-result.private.json');result=json.loads(raw)
 intents=[r for r in rows if r['kind']=='intent' and r['task_index']==index]
 terms=[r for r in rows if r['kind']=='terminal' and r['task_index']==index]
 require(len(intents)==len(terms)==1 and source.sha(raw)==terms[0]['supervisor_result_sha256'],'Old result/journal binding changed')
 child=result['child'];marker=json.loads(source.private(folder/f'{index:03d}-child-started.private.json'))
 require(marker.get('source_freeze_sha256')==freeze_sha and marker.get('task_index')==index and marker.get('child_pid')==child.get('child_pid') and
  marker.get('parent_pid')==intents[0]['supervisor_pid'] and marker.get('pending_intent_sha256')==intents[0]['entry_sha256'] and
  marker.get('permit_sha256')==intents[0]['permit_sha256'] and marker.get('same_intent_replay_authorized') is False and
  child.get('process_group_terminated') is True and child.get('child_terminated') is True and child.get('timed_out') is False and
  child.get('group_survivor_observed_after_child_wait') is False and child.get('termination_unconfirmed') is False and
  child.get('stdout_sha256')==source.sha(source.private(folder/f'{index:03d}-stdout.private.log')) and
  child.get('stderr_sha256')==source.sha(source.private(folder/f'{index:03d}-stderr.private.log')),'Old supervised process/marker/log evidence changed')
 if index<4:require(result.get('passed') is True and child.get('exit_code')==0,'Old completed child was not successful')
 else:
  stderr=source.private(folder/'004-stderr.private.log')
  require(result.get('passed') is False and child.get('exit_code')==1 and
   b'audit_one' in stderr and b'Independent prospective persisted-state scorer disagrees' in stderr and
   result.get('cleanup',{}).get('exact_baseline') is True,'Fifth child is not the exact post-trio reader failure')
 return {'index':index,'original_exit_code':child['exit_code'],'original_passed':result['passed'],'result_sha256':source.sha(raw)}


def prepare(*,parent_authority,physical_receipt,authority,public_out):
 require(not authority.exists() and not public_out.exists(),'Fresh exclusive reconciliation authority outputs required')
 saved=reconciliation.audit_case6(parent_authority=parent_authority)
 parent,value,plan,plan_sha,baseline=legacy.checked_authority(parent_authority)
 root=Path(value['epoch_root']);freeze=Path(parent['original_freeze_path'])
 physical=reconciliation.validate_physical_receipt(physical_receipt,value={**value,'_freeze_sha256':source.sha(source.private(freeze))})
 entry_cow_path=authority.with_name(authority.stem+'.entry-cow-state.private.json')
 raw=source.private(root/'cow-reset-state.json');require(source.sha(raw)==saved['entry_cow_state_sha256'],'Entry cold snapshot changed during preparation')
 fd=os.open(entry_cow_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
 doc={'schema':SCHEMA,'status':'saved_phase_reconciliation_and_physical_scheduling_no_new_dispatch',
  'created_utc':source.now(),'parent_authority_path':str(parent_authority),
  'parent_authority_sha256':source.sha(source.private(parent_authority)),
  'physical_receipt_path':str(physical_receipt),'physical_receipt_sha256':source.sha(source.private(physical_receipt)),
  'original_freeze_path':str(freeze),'original_freeze_sha256':source.sha(source.private(freeze)),
  'original_cohort_plan_sha256':plan_sha,'epoch_root':str(root),'evaluator_root':value['evaluator_root'],
  'source_sha256s':source_hashes(),'saved_case6_reconciliation':saved,'physical_scheduling_review':physical,
  'entry_cow_state_path':str(entry_cow_path),'entry_cow_state_sha256':source.sha(raw),
  'preserved_artifact_sha256s':reconciliation.manifest(root),
  'original_terminal_index':6,'original_child_exit_code':1,'original_terminal_passed':False,
  'original_complete_prior_trios':6,'interrupted_case_saved_phases':3,
  'original_interrupted_trio_completion_present':False,'original_repeated_positive_reset_receipt_present':False,
  'cleanup_generation':23,'entry_cold_seed_binding':original.cold_seed_binding(value,baseline),
  'first_untouched_index':7,'remaining_control_count':93,'first_future_reset_generations':[24,25,26],
  'final_expected_generation':302,'expected_case_resets':300,'earlier_extra_cleanup_resets':1,
  'baseline_action_runtime_grader_data_unchanged':True,'new_fifo_projects':0,
  'old_intent_replay_authorized':False,'new_dispatch_authorized':False,'control_credit':0,
  'model_calls':0,'provider_calls':0,'official_final_admitted':0}
 digest=source.write_new(authority,doc)
 public={k:doc[k] for k in ['status','original_freeze_sha256','original_cohort_plan_sha256',
  'original_terminal_index','original_child_exit_code','original_terminal_passed','original_complete_prior_trios',
  'interrupted_case_saved_phases','original_interrupted_trio_completion_present',
  'original_repeated_positive_reset_receipt_present','cleanup_generation','first_untouched_index',
  'remaining_control_count','first_future_reset_generations','final_expected_generation',
  'expected_case_resets','earlier_extra_cleanup_resets','baseline_action_runtime_grader_data_unchanged',
  'new_fifo_projects','old_intent_replay_authorized','new_dispatch_authorized','control_credit',
  'model_calls','provider_calls','official_final_admitted','source_sha256s']}
 public.update(schema='envloop-gitlab-v6-case6-reconciliation-public-v1',private_authority_sha256=digest,
  saved_phase_scores=[1.0,0.0,1.0],all_three_saved_phases_full_git_verified=True,
  physical_scheduling_receipt_sha256=doc['physical_receipt_sha256'],
  protected_original_stop_flag_and_bootstrap_history_unchanged=True,
  logger_root_cause_established=False,physical_stop_is_logger_fix_guarantee=False)
 source.write_new(public_out,public,0o644);return public


def checked_authority(path):
 doc=json.loads(source.private(path))
 require(doc.get('schema')==SCHEMA and doc.get('source_sha256s')==source_hashes() and
  doc.get('new_dispatch_authorized') is False and doc.get('old_intent_replay_authorized') is False and
  doc.get('first_untouched_index')==7 and doc.get('remaining_control_count')==93 and
  doc.get('cleanup_generation')==23 and doc.get('original_child_exit_code')==1 and
  doc.get('original_terminal_passed') is False and doc.get('original_interrupted_trio_completion_present') is False,
  'Saved reconciliation source/authority boundary changed')
 parent_authority=Path(doc['parent_authority_path']);parent,value,plan,plan_sha,baseline=legacy.checked_authority(parent_authority)
 require(source.sha(source.private(parent_authority))==doc['parent_authority_sha256'] and
  plan_sha==doc['original_cohort_plan_sha256'] and value['epoch_root']==doc['epoch_root'] and
  value['evaluator_root']==doc['evaluator_root'],'Immutable parent/cohort/evaluator authority changed')
 root=Path(value['epoch_root'])
 require(reconciliation.manifest(root)==doc['preserved_artifact_sha256s'] and
  source.sha(source.private(Path(doc['entry_cow_state_path'])))==doc['entry_cow_state_sha256'] and
  reconciliation.audit_case6(parent_authority=parent_authority,entry_cow_state_path=Path(doc['entry_cow_state_path']))==doc['saved_case6_reconciliation'],
  'Original consumed continuations/saved phase/reset evidence changed')
 freeze=Path(doc['original_freeze_path']);physical=Path(doc['physical_receipt_path'])
 require(source.sha(source.private(freeze))==doc['original_freeze_sha256'] and
  source.sha(source.private(physical))==doc['physical_receipt_sha256'] and
  original.cold_seed_binding(value,baseline)==doc['entry_cold_seed_binding'],
  'Original freeze/physical stop/cold seed changed')
 reconciliation.validate_physical_receipt(physical,value={**value,'_freeze_sha256':doc['original_freeze_sha256']})
 return doc,value,plan,plan_sha,baseline


def journal_state(rows):
 next_index=7;pending=None;terminal=False;previous='0'*64
 for number,row in enumerate(rows):
  require(row.get('schema')==JOURNAL_SCHEMA and row.get('seq')==number+1 and row.get('previous_sha256')==previous and
   row.get('entry_sha256')==source.sha(factory.canonical({k:v for k,v in row.items() if k!='entry_sha256'})),'Continuation journal hash chain changed')
  require(type(row.get('task_index')) is int and 7<=row['task_index']<100,'Continuation index type/range invalid')
  if row['kind']=='intent':
   require(not terminal and pending is None and row['task_index']==next_index and next_index<100,'Consumed/failed continuation identity cannot replay or skip');pending=row
  elif row['kind']=='terminal':
   require(pending is not None and row['task_index']==pending['task_index'],'Continuation terminal lacks unique intent')
   require(type(row.get('passed')) is bool,'Continuation terminal pass must be an exact boolean')
   if row['passed'] is True:next_index+=1
   else:terminal=True
   pending=None
  else:raise ValueError('Unknown continuation journal event')
  previous=row['entry_sha256']
 return {'next_index':next_index,'pending':pending,'terminal_failure':terminal,'head_sha256':previous,'completed_new':next_index-7}


def read_journal(root):
 path=root/NAMESPACE/'journal.private.jsonl'
 if not path.exists():return []
 raw=source.private(path);require(not raw or raw.endswith(b'\n'),'Incomplete continuation journal tail')
 rows=[json.loads(line) for line in raw.splitlines()];journal_state(rows);return rows


def append(root,rows,payload):
 row={'schema':JOURNAL_SCHEMA,'seq':len(rows)+1,'previous_sha256':rows[-1]['entry_sha256'] if rows else '0'*64,**payload}
 row['entry_sha256']=source.sha(factory.canonical(row));journal_state([*rows,row])
 path=root/NAMESPACE/'journal.private.jsonl';fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
 with os.fdopen(fd,'wb') as stream:stream.write((json.dumps(row,sort_keys=True,separators=(',',':'))+'\n').encode());stream.flush();os.fsync(stream.fileno())
 rows.append(row);return row


def expected_entry_generation(index):return 17+3*(index-5)


def review(*,authority,review_out,permit,count,accepted=False,note=''):
 require(accepted is True and note.strip() and type(count) is int and 1<=count<=93,'Explicit source review and bounded untouched range required')
 doc,value,plan,plan_sha,baseline=checked_authority(authority);root=Path(value['epoch_root']);state=journal_state(read_journal(root))
 require(state['pending'] is None and not state['terminal_failure'] and state['next_index']+count<=100,'Continuation range is pending/terminal/consumed')
 cold=json.loads(source.private(root/'cow-reset-state.json'));generation=expected_entry_generation(state['next_index'])
 require(cold['clone_generation']==generation,'Continuation expected generation gap changed')
 binding={'authority_path':str(authority),'authority_sha256':source.sha(source.private(authority)),'source_sha256s':source_hashes(),
  'original_cohort_plan_sha256':plan_sha,'first_index':state['next_index'],'maximum_control_count':count,
  'journal_head_sha256':state['head_sha256'],'entry_generation':generation,'old_intent_replay_authorized':False,'model_calls':0,'official_final_admitted':0}
 review_doc={**binding,'schema':'envloop-gitlab-v6-post-reset-root-review-v2','note':note,'reviewed_utc':source.now()}
 sha=source.write_new(review_out,review_doc);permit_doc={**binding,'schema':PERMIT_SCHEMA,'root_review_path':str(review_out),'root_review_sha256':sha,'execution_authorized':True}
 digest=source.write_new(permit,permit_doc);return {'status':'untouched_range_permit_written_no_native_dispatch','permit_sha256':digest,'first_index':state['next_index'],'count':count}


def checked_permit(authority,permit):
 doc,value,plan,plan_sha,baseline=checked_authority(authority);p=json.loads(source.private(permit));raw=source.private(Path(p['root_review_path']));reviewed=json.loads(raw)
 require(type(p.get('first_index')) is int and 7<=p['first_index']<100 and type(p.get('maximum_control_count')) is int and 1<=p['maximum_control_count']<=100-p['first_index'] and p.get('entry_generation')==expected_entry_generation(p['first_index']) and reviewed.get('schema')=='envloop-gitlab-v6-post-reset-root-review-v2' and p.get('model_calls')==p.get('official_final_admitted')==0 and p.get('authority_path')==str(authority),'Continuation permit range/policy invalid')
 require(p.get('schema')==PERMIT_SCHEMA and p.get('execution_authorized') is True and p.get('authority_sha256')==source.sha(source.private(authority)) and
  p.get('source_sha256s')==source_hashes() and p.get('root_review_sha256')==source.sha(raw) and p.get('old_intent_replay_authorized') is False and
  p.get('original_cohort_plan_sha256')==plan_sha and reviewed.get('note','').strip() and
  all(reviewed.get(k)==p.get(k) for k in ['authority_path','authority_sha256','source_sha256s','original_cohort_plan_sha256','first_index','maximum_control_count','journal_head_sha256','entry_generation','old_intent_replay_authorized','model_calls','official_final_admitted']),
  'Exact audit-only permit source/range/head binding changed')
 return doc,value,plan,plan_sha,baseline,p


def capture_git(task,before,after,folder):
 """Future-dispatch only: preserve raw Git proof before the cold reset."""
 project,progress=verify._context(task);pid=int(progress['project_id'])
 old=before['git'][str(pid)]['refs']['refs/heads/main'];new=after['git'][str(pid)]['refs']['refs/heads/main']
 proof=folder/'git-proof';proof.mkdir(mode=0o700,exist_ok=False)
 def save(name,raw):
  require(type(raw) is bytes and len(raw)<=8_000_000,'Native Git proof exceeds bounded bytes')
  path=proof/name;fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
  with os.fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
  return {'path':'git-proof/'+name,'sha256':source.sha(raw)}
 sidecar={'schema':'envloop-gitlab-saved-git-sidecar-v1','project_id':pid,'before_main_sha':old,'after_main_sha':new,
  'before_business_sha256':before['business_sha256'],'after_business_sha256':after['business_sha256'],
  'diff_ref':save('diff.private.txt',verify._git(pid,'diff','--name-only',old,new)),
  'before_tree_ref':save('before-tree.private.bin',verify._git(pid,'ls-tree','-r','-z','--full-tree',old)),
  'after_tree_ref':save('after-tree.private.bin',verify._git(pid,'ls-tree','-r','-z','--full-tree',new)),
  'main_blob_refs':{}}
 for number,path in enumerate(sorted(saved_git.MONITORED_PATHS)):sidecar['main_blob_refs'][path]=save(f'blob-{number}.private.bin',verify._git(pid,'show',new+':'+path))
 # This exact source capability is reusable for formal model/final readback.
 source.write_new(folder/'git-sidecar.private.json',sidecar)
 return sidecar


async def live_one(plan,plan_sha,index,run,baseline):
 # Isolate only the read-only recording hook; no frozen module global changes.
 original_attempt=gui_controls.attempt
 async def attempted(browser,task,variant,label,folder):
  result=await original_attempt(browser,task,variant,label,folder)
  after=json.loads(source.private(folder/label/'after-persisted-state.json'))
  capture_git(task,baseline,after,folder/label)
  return result
 proxy=types.SimpleNamespace(**gui_controls.__dict__);proxy.attempt=attempted
 scope=dict(original.lane.live_one.__globals__);scope['gui_controls']=proxy
 live=types.FunctionType(original.lane.live_one.__code__,scope,original.lane.live_one.__name__,original.lane.live_one.__defaults__,original.lane.live_one.__closure__)
 live.__kwdefaults__=original.lane.live_one.__kwdefaults__
 return await live(plan,plan_sha,index,run,baseline)


def _future_supervision(root,index,rows,authority_sha,plan):
 folder=root/NAMESPACE/'supervision';raw=source.private(folder/f'{index:03d}-result.private.json');result=json.loads(raw)
 intents=[r for r in rows if r['kind']=='intent' and r['task_index']==index];terms=[r for r in rows if r['kind']=='terminal' and r['task_index']==index]
 require(len(intents)==len(terms)==1 and result.get('schema')=='envloop-gitlab-v6-audit-only-supervised-private-v1' and result.get('index')==index and result.get('passed') is True and source.sha(raw)==terms[0]['supervisor_result_sha256'],'Continuation result identity/hash changed')
 child=result['child'];marker=json.loads(source.private(folder/f'{index:03d}-child-started.private.json'))
 identity=plan['task_roster'][index]
 require(intents[0].get('task_id')==identity['task_id'] and intents[0].get('package_sha256')==identity['package_sha256'] and intents[0].get('expected_entry_generation')==expected_entry_generation(index),'Continuation intent task/package/generation changed')
 require(marker.get('schema')=='envloop-gitlab-v6-audit-only-child-started-v1' and marker.get('task_index')==index and
  marker.get('child_pid')==child.get('child_pid') and marker.get('parent_pid')==intents[0]['supervisor_pid'] and
  marker.get('pending_intent_sha256')==intents[0]['entry_sha256'] and marker.get('permit_sha256')==intents[0]['permit_sha256'] and
  marker.get('authority_sha256')==authority_sha==intents[0]['authority_sha256'] and marker.get('old_intent_replay_authorized') is False and
  child.get('exit_code')==0 and child.get('child_terminated') is True and child.get('process_group_terminated') is True and
  child.get('group_survivor_observed_after_child_wait') is False and child.get('timed_out') is False and child.get('termination_unconfirmed') is False and
  child.get('stdout_sha256')==source.sha(source.private(folder/f'{index:03d}-stdout.private.log')) and
  child.get('stderr_sha256')==source.sha(source.private(folder/f'{index:03d}-stderr.private.log')),'Continuation one-use child process/marker/log identity changed')
 return result


def audit_prefix(authority):
 doc,value,plan,plan_sha,baseline=checked_authority(authority);root=Path(value['epoch_root']);rows=read_journal(root);state=journal_state(rows);audits=[]
 with scoped.cohort_context(value):
  for index in range(7,state['next_index']):
   result=_future_supervision(root,index,rows,source.sha(source.private(authority)),plan)
   audited=audit_one(value,plan,plan_sha,baseline,index)
   require(result['independent_audit']==audited,'Completed continuation raw proof changed');audits.append(audited)
 return {'status':'terminal_no_replay' if state['terminal_failure'] else 'pending_no_replay' if state['pending'] else 'untouched_continuation_prefix_reopened',
  'complete_prior_native_trios_reopened':6,'interrupted_case6_saved_phases_reconciled':3,'new_complete_git_trios':len(audits),'next_index':state['next_index'],'pending_intent':state['pending'] is not None,
  'terminal_failure':state['terminal_failure'],'legacy_full_git_tree_evidence':False,'model_calls':0,'official_final_admitted':0}


def child(*,authority,permit,index,parent_pid):
 doc,value,plan,plan_sha,baseline,p=checked_permit(authority,permit);root=Path(value['epoch_root']);state=journal_state(read_journal(root));pending=state['pending']
 require(Path(__file__).resolve().parents[1]==Path(doc['evaluator_root']) and os.getppid()==parent_pid and pending is not None and
  pending['task_index']==index and pending.get('task_id')==plan['task_roster'][index]['task_id'] and pending.get('package_sha256')==plan['task_roster'][index]['package_sha256'] and pending.get('expected_entry_generation')==expected_entry_generation(index) and pending['supervisor_pid']==parent_pid and pending.get('permit_sha256')==source.sha(source.private(permit)) and pending.get('authority_sha256')==source.sha(source.private(authority)) and p['first_index']<=index<p['first_index']+p['maximum_control_count'],
  'Continuation child lacks one-use original evaluator parent intent')
 folder=root/NAMESPACE/'supervision'
 source.write_new(folder/f'{index:03d}-child-started.private.json',{'schema':'envloop-gitlab-v6-audit-only-child-started-v1','task_index':index,'child_pid':os.getpid(),
  'parent_pid':parent_pid,'pending_intent_sha256':pending['entry_sha256'],'permit_sha256':source.sha(source.private(permit)),
  'authority_sha256':source.sha(source.private(authority)),'created_utc':source.now(),'old_intent_replay_authorized':False})
 with scoped.cohort_context(value):
  require(verify.state_snapshot()==baseline and json.loads(source.private(root/'cow-reset-state.json'))['clone_generation']==expected_entry_generation(index),'Exact continuation entry SQL/Git/generation changed')
  result=asyncio.run(live_one(plan,plan_sha,index,root/NAMESPACE,baseline));audited=audit_one(value,plan,plan_sha,baseline,index)
 source.write_new(folder/f'{index:03d}-child-result.private.json',{'result':result,'audit':audited})
 return {'status':'new_complete_git_native_trio_verified','index':index,'model_calls':0,'official_final_admitted':0}


def run(*,authority,permit,max_tasks=1,execute=False):
 require(execute is True,'Explicit reviewed native continuation execution required')
 doc,value,plan,plan_sha,baseline,p=checked_permit(authority,permit);root=Path(value['epoch_root']);control=root/NAMESPACE
 require(Path(__file__).resolve().parents[1]==Path(doc['evaluator_root']) and type(max_tasks) is int and 1<=max_tasks<=p['maximum_control_count'],'Original evaluator/exact bounded range required')
 if not control.exists():
  control.mkdir(mode=0o700);(control/'attempts').mkdir(mode=0o700);(control/'supervision').mkdir(mode=0o700)
 audit_prefix(authority)
 lock=os.open(control/'.supervisor.lock',os.O_WRONLY|os.O_CREAT,0o600);fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 try:
  rows=read_journal(root);state=journal_state(rows)
  require(state['pending'] is None and not state['terminal_failure'] and state['next_index']==p['first_index'] and state['head_sha256']==p['journal_head_sha256'],'Continuation range/head already consumed or terminal')
  for index in range(p['first_index'],p['first_index']+max_tasks):
   require(json.loads(source.private(root/'cow-reset-state.json'))['clone_generation']==expected_entry_generation(index),'Continuation cold generation changed before intent')
   item=plan['task_roster'][index]
   append(root,rows,{'kind':'intent','task_index':index,'task_id':item['task_id'],'package_sha256':item['package_sha256'],
    'supervisor_pid':os.getpid(),'original_cohort_plan_sha256':plan_sha,'authority_sha256':source.sha(source.private(authority)),'permit_sha256':source.sha(source.private(permit)),
    'expected_entry_generation':expected_entry_generation(index),'created_utc':source.now(),'old_intent_replay_authorized':False})
   folder=control/'supervision';argv=[sys.executable,'-m','gitlab_world.v066_post_reset_continuation_v2','child','--authority',str(authority),'--permit',str(permit),'--index',str(index),'--supervisor-pid',str(os.getpid()),'--execute']
   child_result=process_audit._confirm_child_process_group(supervisor.supervise_child(argv,cwd=Path(doc['evaluator_root']),env=os.environ.copy(),stdout_path=folder/f'{index:03d}-stdout.private.log',stderr_path=folder/f'{index:03d}-stderr.private.log',timeout_seconds=7200,grace_seconds=30))
   passed=False;audited=None;cleanup=None
   try:
    require(child_result.get('exit_code')==0 and child_result.get('timed_out') is False and child_result.get('child_terminated') is True and
     child_result.get('process_group_terminated') is True and child_result.get('group_survivor_observed_after_child_wait') is False,'Continuation child failed or has an uncertain surviving group')
    with scoped.cohort_context(value):
     audited=audit_one(value,plan,plan_sha,baseline,index)
     require(verify.state_snapshot()==baseline and json.loads(source.private(root/'cow-reset-state.json'))['clone_generation']==generations(index)[-1],'Continuation child post-baseline/generation changed')
    passed=True
   except Exception as error:
    audited={'error_type':type(error).__name__}
    if child_result.get('process_group_terminated') is True:
     try:
      with scoped.cohort_context(value):
       forensic=scoped.capture_forensics(root/'startup-forensics'/('audit-continuation-terminal-'+str(index)+'-'+str(time.monotonic_ns())))
       reset.reset();restored=verify.state_snapshot();sha=source.write_new(folder/f'{index:03d}-cleanup-after-reset-persisted-state.private.json',restored)
       cleanup={'exact_baseline':restored==baseline,'restored_sql_git_sha256':sha,'forensics':forensic}
     except Exception as failure:cleanup={'exact_baseline':False,'error_type':type(failure).__name__}
   result={'schema':'envloop-gitlab-v6-audit-only-supervised-private-v1','index':index,'passed':passed,'child':child_result,'independent_audit':audited,'cleanup':cleanup,'model_calls':0,'official_final_admitted':0}
   sha=source.write_new(folder/f'{index:03d}-result.private.json',result)
   append(root,rows,{'kind':'terminal','task_index':index,'passed':passed,'supervisor_result_sha256':sha,'model_calls':0,'official_final_admitted':0})
   if not passed:break
  return audit_prefix(authority)
 finally:fcntl.flock(lock,fcntl.LOCK_UN);os.close(lock)


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['prepare','review','audit-prefix','run','child'])
 for opt in ['freeze','parent-authority','physical-receipt','authority','public-out','review-out','permit']:p.add_argument('--'+opt,type=Path)
 p.add_argument('--accept-root-review',action='store_true');p.add_argument('--note',default='');p.add_argument('--count',type=int,default=1)
 p.add_argument('--max-tasks',type=int,default=1);p.add_argument('--index',type=int);p.add_argument('--supervisor-pid',type=int);p.add_argument('--execute',action='store_true');a=p.parse_args()
 if a.mode=='prepare':result=prepare(parent_authority=a.parent_authority,physical_receipt=a.physical_receipt,authority=a.authority,public_out=a.public_out)
 elif a.mode=='review':result=review(authority=a.authority,review_out=a.review_out,permit=a.permit,count=a.count,accepted=a.accept_root_review,note=a.note)
 elif a.mode=='audit-prefix':result=audit_prefix(a.authority)
 elif a.mode=='run':result=run(authority=a.authority,permit=a.permit,max_tasks=a.max_tasks,execute=a.execute)
 else:require(a.execute is True,'Child requires reviewed execution');result=child(authority=a.authority,permit=a.permit,index=a.index,parent_pid=a.supervisor_pid)
 print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
