"""Actual v22 authority and metadata-first original Office package boundary."""
from pathlib import Path
import json
from tools import office_owned_folder_runtime_v2 as office
from tools.office_neutral_lifecycle_pilot_v4 import V4_FILES
from tools.office_current_package_v4 import Package
from cursibench import full_study_runtime_v2 as study_runtime
from cursibench import full_study_final_dispatch_v1 as final
from cursibench import full_study_matrix_v1 as matrix
from cursibench.scale_vision_proxy import MODEL

ADAPTER_FILES=('tools/office_current_authority_v4.py','tools/office_current_execution_v4.py',
 'tools/office_current_paid_v4.py','tools/office_current_evidence_v4.py','tools/office_current_worker_cli_v4.py',
 'tools/office_current_native_clock_v4.py','tools/office_current_cua_pump_v4.mjs','tools/office_current_budget_performance_v4.py',
 'tools/office_current_protocol_v4.py','tools/office_current_workers_v4.py','tools/office_current_teacher_v4.py','tools/office_current_package_v4.py','tools/office_current_neutral_v4.py','src/cursibench/full_study_teacher_adapter_v1.py','src/cursibench/http_transport.py')


def current_sources(repo):
 root=Path(repo);return {name:office.sha((root/name).read_bytes()) for name in (*office.SOURCE_FILES,*V4_FILES,*ADAPTER_FILES)}


class Authority:
 def __init__(self,*,authority,cell_id,owner_slot,session=None,started=None,final_command=None,teacher=False):
  office.require(cell_id in office.CELLS and owner_slot in ['shared-base',*matrix.RESEARCHERS],'Original Office/five-slot scope required')
  study=authority.study if type(authority) is study_runtime.FinalGate else authority
  office.require(type(study) is study_runtime.FrozenStudy and study.plan['distinct_official_task_identities']==600 and study.plan['campaign_count']==24,
   'Actual witnessed600-task study required before private package/provider work')
  office.require(study.policy_manifest['native_environment_by_cell'].get(cell_id)=='owned_local_browser_cloud_account','Witnessed original Office account environment required')
  from tools.office_current_protocol_v4 import require_epoch
  require_epoch(study)
  self.study,self.authority,self.cell,self.owner,self.session,self.started,self.command,self.teacher=study,authority,cell_id,owner_slot,session,started,final_command,teacher
  self.cell_plan=next(r for r in study.plan['cells'] if r['cell_id']==cell_id)
  if final_command is not None:
   office.require(type(authority) is study_runtime.FinalGate and len(authority.freezes)==24 and final_command.get('cell_id')==cell_id and final_command.get('owner_slot')==owner_slot and
    final_command.get('max_actions')==90 and final_command.get('max_wall_seconds')==720 and final_command.get('matched_bindings')==self.cell_plan['matched_bindings'],'Actual all24-chain final command required before hidden body')
   self.checkpoint=final_command['checkpoint_sha256'];self.checkpoint_path=final_command['sampler_path'];self.split='final_candidate'
   record=authority.budget.owner_attempts(cell_id+':'+owner_slot).get(final_command['attempt_id'])
   office.require(record and record['status']=='dispatched' and record['request_sha256']==final.sha(final.canonical(final_command)),'Actual final dispatched reservation required before body/provider')
  else:
   office.require(session is not None and session.study is study and session.intent['cell_id']==cell_id and session.intent['researcher_id']==owner_slot and callable(session.dispatch_paid),'Actual paid scoped selection session required')
   if teacher:
    office.require(owner_slot in matrix.RESEARCHERS and type(session) is study_runtime.CampaignSession,'Authentic campaign teacher callback authority required');self.split='train';self.checkpoint=office.sha(matrix.TEACHER.encode());self.checkpoint_path=None
   elif owner_slot=='shared-base':
    office.require(getattr(session,'policy_amendment_sha256',None)==study.amendment_sha256,'Actual v22 shared-base reservation session required');self.checkpoint=session.started['checkpoint_path_sha256'];self.checkpoint_path=None;self.split='selection'
   else:
    office.require(type(session) is study_runtime.CampaignSession and isinstance(started,dict),'Actual checkpoint selection start required')
    matches=[r for r in session._events('selection_started') if r['data']['attempt_id']==started['attempt_id']]
    office.require(len(matches)==1 and matches[0]['data']['checkpoint_path_sha256']==started['checkpoint_path_sha256'],'Selection checkpoint/start changed')
    checkpoints=[r for r in session._events('tinker_checkpoint') if r['data']['checkpoint_path_sha256']==started['checkpoint_path_sha256']]
    office.require(len(checkpoints)==1,'Actual trained checkpoint lineage required');self.checkpoint=started['checkpoint_path_sha256'];self.checkpoint_path=session.checkpoint_result(checkpoints[0])['checkpoint_path'];self.split='selection'
  if not teacher:office.require(office.sha((self.checkpoint_path or MODEL).encode())==self.checkpoint,'Exact base/checkpoint sampler binding required')
  training,_=study.student_training_configuration();self.sampling={'seed':training['seed'],'max_output_tokens':training['sample_max_tokens']}

 def identities(self):
  if self.command is not None:return [{'task_id':self.command['task_id'],'package_sha256':self.command['package_sha256']}]
  return [{k:r[k] for k in ('task_id','package_sha256')} for r in self.study.task_views(self.cell)[self.split]]

 def load_package(self,identity,metadata_index):
  # Read metadata only until exact authority, identity, source and scope pass.
  rows=json.loads(office.private(metadata_index));office.require(isinstance(rows,list),'Frozen Office metadata index required')
  matches=[r for r in rows if r['cell_id']==self.cell and r['split']==self.split and {k:r[k] for k in ('task_id','package_sha256')}==identity]
  office.require(identity in self.identities() and len(matches)==1,'Office identity outside actual frozen scope')
  row=matches[0];root=Path(row['package_root']);descriptor=Path(row['descriptor'])
  office.require(root.resolve().is_relative_to(self.study.repo_root/'work') and descriptor.resolve().is_relative_to(root.resolve()) and office.sha(office.private(descriptor))==identity['package_sha256'],'Actual source-bound Office evaluator descriptor required')
  package=Package(descriptor,package_root=root)
  office.require(package.binding_sha256==identity['package_sha256'] and package.actor.cell_id==self.cell and package.actor.split==self.split,'Office sealed body/metadata binding changed');return package

 def qualify(self,path,expected_sha):return verify_qualification(self.study,self.cell,path,expected_sha)

def verify_qualification(study,cell,path,expected_sha):
 raw=office.private(path);value=json.loads(raw)
 office.require(office.sha(raw)==expected_sha and value.get('schema')=='office-current-source-qualification-v4' and value.get('accepted') is True and
  value.get('cell_id')==cell and value.get('source_sha256s')==current_sources(study.repo_root) and value.get('all_actor_paths_same_native_source') is True and
  value.get('native_policy_sha256')==office.safety.POLICY_SHA and value.get('native_lifecycle_qualified') is True and value.get('strict_saved_scorer_qualified') is True,
  'Fresh actual Office V4 lifecycle/scorer qualification required before provider')
 controls=value.get('controls');office.require(isinstance(controls,list) and len(controls)>=3,'Actual saved positive/near-miss/reset controls required')
 kinds=set()
 for ref in controls:
  _,artifact=final.private_reference(Path(path).parent,ref,'office_qualification_control');control=json.loads(artifact)
  from tools.office_current_evidence_v4 import reopen_native
  descriptor=Path(control['package_descriptor']['path']);raw=office.private(descriptor)
  office.require(descriptor.resolve().is_relative_to(study.repo_root/'work') and office.sha(raw)==control['package_descriptor']['sha256'],'Qualification original package changed')
  package=Package(descriptor,package_root=control['package_root']);episode=Path(control['episode_root'])
  office.require(episode.resolve().is_relative_to(study.repo_root/'work') and package.actor.cell_id==cell,'Qualification outside actual native cell/owned work')
  checked=reopen_native(package,episode);office.require(checked['score']==control['expected_strict_score'],'Qualification original scorer control failed')
  kinds.add((control['kind'],checked['score']))
 office.require({('positive',1),('near_miss',0),('neutral',0)}<=kinds,'Actual positive/near-miss/neutral controls incomplete')
 return value
