"""Additive generic Office Qwen callback with witnessed paid admission.

The old diagnostic sampler remains unchanged. Only cropped current-frame
observations enter the clean terminal process; no account data, oracle or UI
controller capability enters model RPC. Formal authorities are real v22 objects.
"""
from __future__ import annotations
import json
import math
import re
import time
from pathlib import Path
from tools.office_owned_folder_runtime_v2 import require,private,sha,canonical,write_new,source_hashes,AccountLease,CELLS,Package
from cursibench import native_surface_guard_policy_v1 as guard
from cursibench import full_study_matrix_v1 as matrix
from cursibench.scale_action_contract import Observation
from cursibench.scale_action_output_v066 import render_for_model
from cursibench.scale_vision_proxy import MODEL
from native_desktop_factory.actor_deadline_future_v21 import ActorDeadlineReached

SCHEMA='office-owned-folder-paid-sampler-admission-v2'
SLOTS={'shared-base',*matrix.RESEARCHERS}

def _formal_types():
 try:from cursibench import full_study_runtime_v2 as runtime
 except ImportError:raise ValueError('Real v22 witnessed 600-task study/24-chain final authority required before paid calls') from None
 return runtime

def validate_admission(value,*,package,runtime_binding,authority=None,session=None,final_command=None):
 require(type(package) is Package,'Real frozen Office package required')
 require(type(value) is dict and value.get('schema')==SCHEMA and value.get('mode') in ['development_train','formal_selection','formal_final'],'Generic Office sampler admission required')
 require(type(value.get('seed')) is int and 0<=value['seed']<2**31 and type(value.get('max_output_tokens')) is int and 1<=value['max_output_tokens']<=4096,'Frozen Qwen seed/output bounds required')
 require(value.get('cell_id') in CELLS and value['cell_id']==package.actor.cell_id and value.get('task_id')==package.actor.task_id and value.get('package_sha256')==package.binding_sha256 and
  value.get('native_policy_sha256')==guard.POLICY_SHA and value.get('source_sha256s')==source_hashes(),'Office sampler task/native/source closure changed')
 require(value.get('account_principal_sha256')==runtime_binding['account_principal_sha256'] and value.get('folder_scope_sha256')==runtime_binding['folder_scope_sha256'] and
  value.get('runtime_binding_sha256')==sha(canonical(runtime_binding)) and value.get('single_account') is True and value.get('graph_used') is False and
  value.get('max_actions')==90 and value.get('max_wall_seconds')==720,'Office account/folder/uniform actor caps changed')
 require(type(value.get('native_window_sha256')) is str and re.fullmatch('[a-f0-9]{64}',value['native_window_sha256']) and type(value.get('viewport')) is list and len(value['viewport'])==2 and all(type(v) is int and 400<=v<=2560 for v in value['viewport']),'Actual native window/cropped viewport required')
 ref=value.get('native_before_ref');root=Path(runtime_binding['native_evidence_root']).resolve();require(type(ref) is dict and set(ref)=={'path','sha256'} and not Path(ref['path']).is_absolute() and '..' not in Path(ref['path']).parts,'Native before artifact reference escaped scope')
 candidate=root/ref['path'];require(candidate.resolve().is_relative_to(root) and sha(private(candidate))==ref['sha256']==value.get('native_before_sha256'),'Actual owner native-before download changed')
 require(value.get('owner_slot') in SLOTS and value.get('source_reviewed') is True and type(value.get('native_before_sha256')) is str and re.fullmatch('[a-f0-9]{64}',value['native_before_sha256']),
  'Reviewed actual native before state and five-slot owner binding required')
 checkpoint=value.get('checkpoint_path');expected=sha((checkpoint or MODEL).encode())
 require(value.get('checkpoint_sha256')==expected and (checkpoint is None or re.fullmatch(r'tinker://[A-Za-z0-9_./:-]{1,400}',checkpoint)) and
  (value['owner_slot']!='shared-base' or checkpoint is None),'Exact Qwen base/checkpoint path binding required')
 if value['mode']=='development_train':
  require(package.actor.split in ['train','train_policy_development'] and value.get('selection_or_final_eligible') is False and value.get('official_final_credit')==0 and
   authority is None and session is None and final_command is None,'TRAIN development cannot borrow formal authority')
 else:
  runtime=_formal_types()
  study=authority.study if type(authority) is runtime.FinalGate else authority
  require(type(study) is runtime.FrozenStudy and study.plan['distinct_official_task_identities']==600 and study.plan['campaign_count']==24 and
   value.get('policy_manifest_sha256')==study.manifest_sha256,'Real witnessed v22 600-task/24-campaign study required before paid calls')
  # The native account lease is free and evaluator-owned. It may never be
  # reported as an E2B allocation. This mapping must be in the witnessed source
  # policy, not an ad-hoc runtime boolean or invented provider receipt.
  mapping=study.policy_manifest.get('native_environment_by_cell',{})
  require(mapping.get(value['cell_id'])=='owned_local_browser_cloud_account','Witnessed native Office account environment mapping required')
  if value['mode']=='formal_selection':
   require(type(authority) is runtime.FrozenStudy and package.actor.split=='selection' and session is not None and getattr(session,'study',None) is study and callable(getattr(session,'dispatch_paid',None)),
    'Real v22 paid selection session required')
   views=study.task_views(value['cell_id']);require({'task_id':package.actor.task_id,'package_sha256':package.binding_sha256} in [{k:r[k] for k in ['task_id','package_sha256']} for r in views['selection']], 'Office selection identity outside frozen20')
   require(value.get('selection_attempt')==getattr(session,'attempt_id',value.get('selection_attempt')) and value.get('selection_identities_sha256')==sha(canonical(list(views['selection']))),'Exact actual paid selection attempt/20-identity binding required')
   training,_=study.student_training_configuration();require(value.get('seed')==training['seed'] and value.get('max_output_tokens')==training['sample_max_tokens'],'Frozen common Qwen decoding changed')
  else:
   require(type(authority) is runtime.FinalGate and len(authority.freezes)==24 and package.actor.split in ['final_candidate','final_candidate_unsealed'] and
    type(final_command) is dict and final_command.get('cell_id')==value['cell_id'] and final_command.get('owner_slot')==value['owner_slot'] and
    final_command.get('task_id')==package.actor.task_id and final_command.get('package_sha256')==package.binding_sha256 and
    final_command.get('sampler_path')==checkpoint and final_command.get('checkpoint_sha256')==expected and
    final_command.get('max_actions')==90 and final_command.get('max_wall_seconds')==720 and int(time.time())>authority.last_selection_frozen_at,
    'Real all24-chain FinalGate and exact five-slot final command required before paid calls')
   require(package.actor.task_id in authority.initial_state_by_task[value['cell_id']],'Task lacks independent qualified final reset')
 return value

class GenericOfficePaidSampler:
 def __init__(self,*,admission_path,package,runtime_binding,output_root,repo_root,authority=None,session=None,final_command=None,delegate_factory=None):
  raw=private(admission_path);self.admission=json.loads(raw);self.admission_raw=raw;self.package=package;self.runtime_binding=runtime_binding
  self.authority,self.session,self.final_command=authority,session,final_command
  validate_admission(self.admission,package=package,runtime_binding=runtime_binding,authority=authority,session=session,final_command=final_command)
  self.root=Path(output_root);self.root.mkdir(mode=0o700,exist_ok=False);self.repo_root=Path(repo_root);self.delegate_factory=delegate_factory;self.delegate=None
  self.step=0;self.deadline=None;self.used_frames=set();self.results=[];self.deadline_proof=None;self.shutdown_ack=None;self.closed=False
  write_new(self.root/'sampler-intent.private.json',canonical({'schema':SCHEMA,'admission_sha256':sha(raw),'one_use':True,'mode':self.admission['mode']}))
 def bind_actor_clock(self,*,started_monotonic,deadline_monotonic):
  require(self.deadline is None and type(started_monotonic) in [int,float] and type(deadline_monotonic) in [int,float] and math.isfinite(started_monotonic) and math.isfinite(deadline_monotonic) and deadline_monotonic==started_monotonic+720,'Uniform 720-second actor clock required once')
  self.started,self.deadline=started_monotonic,deadline_monotonic
 def authorize(self,observation=None):
  validate_admission(self.admission,package=self.package,runtime_binding=self.runtime_binding,authority=self.authority,session=self.session,final_command=self.final_command)
  self.package.revalidate();require(self.deadline is not None and time.monotonic()<self.deadline and not self.closed,'Office sampler actor clock expired or closed')
  lease=AccountLease(self.admission['account_principal_sha256'],expires_at_ms=0);value=json.loads(private(lease.path));require(value['expires_at_ms']>int(time.time()*1000),'Actual shared Office account lease inactive')
  if observation is not None:
   path=Path(self.admission['native_actor_root'])/f'turn-{observation.step:03d}/observation-envelope.private.json';envelope=json.loads(private(path));guard.validate_envelope(envelope)
   require(envelope['owned_surface'] is True and envelope['frame_id']==observation.frame_id and envelope['lease']['window_sha256']==self.admission['native_window_sha256'] and
    envelope['lease']['lease_id']==value['token'] and envelope['raw_image']['sha256']==sha(observation.screenshot_bytes) and envelope['viewport']==self.admission['viewport'],
    'Actual owned native current frame/window/account lease must precede paid sampling')
  if self.admission['mode']=='formal_final':
   owner=self.admission['cell_id']+':'+self.admission['owner_slot'];attempt=self.authority.budget.owner_attempts(owner).get(self.final_command['attempt_id'])
   require(type(attempt) is dict and attempt.get('status')=='dispatched','Actual FinalController paid intent/reservation must precede provider setup')
 def dispatch_paid(self,operation,request,callback):
  if self.admission['mode']!='formal_selection':return callback(request)
  ordinal=request.get('step',0);prefix=self.admission['selection_attempt'];attempt_id=prefix+('-sampler-setup-0' if operation=='setup' else f'-sample-{self.admission["task_index"]:02d}-{ordinal:03d}')
  reserve=self.admission.get('sample_reserve_usd');require(type(reserve) is str,'Frozen paid sampling upper reservation required')
  result=self.session.dispatch_paid(attempt_id=attempt_id,category='tinker',work=request,request=request,reserve_usd=reserve,resource_reservation={},provider=callback)
  require(result.get('attempt_id')==attempt_id and type(result.get('result')) is dict,'Actual paid selection result missing');return result['result']
 def start(self):
  self.authorize();write_new(self.root/'setup-intent.private.json',canonical({'checkpoint_sha256':self.admission['checkpoint_sha256'],'one_use':True}))
  if self.delegate_factory is None:
   from native_desktop_factory.deadline_model_transport_v21 import ModelSampler
   factory=ModelSampler
  else:factory=self.delegate_factory
  self.delegate=factory(repo_root=self.repo_root,journal_root=self.root/'model-rpc.private',plan_sha256=sha(self.admission_raw))
  request={'schema':'office-owned-folder-sampler-setup-v2','cell_id':self.admission['cell_id'],'owner_slot':self.admission['owner_slot'],'checkpoint_sha256':self.admission['checkpoint_sha256'],
   'native_before_sha256':self.admission['native_before_sha256'],'runtime_binding_sha256':self.admission['runtime_binding_sha256']}
  if self.admission['mode']=='formal_selection':request.update({'selection_attempt':self.admission['selection_attempt'],'selection_identities_sha256':self.admission['selection_identities_sha256'],'checkpoint_path_sha256':self.admission['checkpoint_sha256']})
  result=self.dispatch_paid('setup',request,lambda _:self.delegate.start(checkpoint_path=self.admission['checkpoint_path'],checkpoint_sha256=self.admission['checkpoint_sha256'],
   seed=self.admission['seed'],max_output_tokens=self.admission['max_output_tokens'],attempt_id='office-'+sha(self.admission_raw)[:16]))
  require(result.get('status')=='ready' and result.get('checkpoint_path_sha256')==self.admission['checkpoint_sha256'],'Actual base/checkpoint setup uncertain; no replay')
  write_new(self.root/'setup-result.private.json',canonical(result))
 def __call__(self,observation):
  self.authorize(observation);require(type(observation) is Observation and observation.task_id==self.package.actor.task_id and observation.task_binding_sha256==self.package.binding_sha256 and
   observation.instruction==self.package.actor.visible_instruction and observation.step==self.step and self.step<90 and observation.frame_id not in self.used_frames and
   time.monotonic()<observation.expires_at,'Actual Office current frame/task/crop binding changed')
  if self.delegate is None:self.start()
  frame=self.root/f'frame-{self.step:03d}.image';write_new(frame,observation.screenshot_bytes);self.used_frames.add(observation.frame_id)
  request={'schema':'office-owned-folder-sampler-current-frame-v2','cell_id':self.admission['cell_id'],'task_id':observation.task_id,'package_sha256':observation.task_binding_sha256,
   'owner_slot':self.admission['owner_slot'],'checkpoint_sha256':self.admission['checkpoint_sha256'],'step':self.step,'frame_id':observation.frame_id,
   'frame_sha256':sha(observation.screenshot_bytes),'actor_deadline_monotonic':self.deadline,'native_before_sha256':self.admission['native_before_sha256']}
  if self.admission['mode']=='formal_selection':request.update({'selection_attempt':self.admission['selection_attempt'],'selection_identities_sha256':self.admission['selection_identities_sha256'],'checkpoint_path_sha256':self.admission['checkpoint_sha256'],'task_index':self.admission['task_index']})
  write_new(self.root/f'sample-{self.step:03d}-intent.private.json',canonical(request));ordinal=self.step;self.step+=1
  def call(_):return self.delegate.sample(observation=observation,request_id='office-'+sha(self.admission_raw)[:16]+'-'+str(ordinal),task_dir=self.root,
   remaining_seconds=max(0,self.deadline-time.monotonic()),actor_deadline=self.deadline)
  try:result=self.dispatch_paid('sample',request,call)
  except ActorDeadlineReached as error:
   self.deadline_proof=error.proof.receipt();write_new(self.root/f'sample-{ordinal:03d}-deadline.private.json',canonical(self.deadline_proof));raise
  except BaseException as error:
   write_new(self.root/f'sample-{ordinal:03d}-uncertain.private.json',canonical({'error_class':type(error).__name__,'same_request_replay_authorized':False,'cost_usd':None}));raise
  require(result.get('status')=='completed' and result.get('new_dispatch') is True and result.get('reused') is False and type(result.get('text')) is str and type(result.get('usage')) is dict,
   'Actual sampler result/usage uncertain; no replay')
  write_new(self.root/f'sample-{ordinal:03d}-result.private.json',canonical(result));self.results.append(result);return result
 def close(self,*,success):
  if self.closed:return self.shutdown_ack
  self.closed=True
  if self.delegate is not None:self.shutdown_ack=self.delegate.close(success)
  else:self.shutdown_ack={'status':'no_provider_created'}
  write_new(self.root/'shutdown.private.json',canonical({'acknowledgement':self.shutdown_ack,'automatic_retries':0,'cost_usd':None}));return self.shutdown_ack
 def usage(self):
  # Returned token counts are observed; no invoice or dollar settlement is
  # invented. v22 money reconciliation remains independent of performance.
  return {'schema':'office-owned-folder-sampling-usage-v2','completed_calls':len(self.results),'attempted_frame_calls':self.step,
   'input_tokens':sum(r['usage']['input_tokens'] for r in self.results),'image_tokens':sum(r['usage']['image_tokens'] for r in self.results),
   'output_tokens':sum(r['usage']['output_tokens'] for r in self.results),'cost_usd':None,'provider_invoice_verified':False,'actor_deadline_proof':self.deadline_proof}
