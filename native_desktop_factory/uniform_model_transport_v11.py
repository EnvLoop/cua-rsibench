"""Common real-model Desktop transport; no task gold or evaluator script path.

Construction is offline. Only a gated worker may invoke create/start. Base and
checkpoint samplers share the same vision renderer, grammar, clock and GUI
transport. The immutable v9 proxy records neutral Calc Enter samples.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
import json
import os
from pathlib import Path
import time

from cursibench import scale_action_output_v066 as output
from cursibench.scale_action_contract import ContractError
from cursibench.scale_vision_proxy import MODEL,PROCESSOR,RENDERER
from . import runtime_fingerprint_probe, qwen_v064_adapter as pixels
from . import qwen_v066_adapter_v4_strict as strict
from . import v066_scoped_profile_guard as profile
from . import pre_observation_readiness_v12 as readiness
from . import structural_guest_attestation_v16 as runtime_policy
from . import bounded_guest_transport_v17 as bounded_transport
from .gui_control_shell import wait_for_document_ready
from .post_enter_control_proxy_v9 import PostEnterControlProxyV9
from .v066_post_enter_control_attempt_v9 import RecordingDesktop
from .v066_storage_budget import reserve_and_write
from .factory import digest

MAX_ACTIONS=90
ACTOR_WALL_SECONDS=720
LEASE_SECONDS=1200
MAX_OUTPUT_TOKENS=4096


@contextmanager
def evidence_scope(root:Path,out:Path):
 names={'ENVLOOP_DESKTOP_V4_ATTEMPTS_ROOT':str(root.resolve()),
        'ENVLOOP_DESKTOP_V4_ATTEMPT_DIR':str(out.resolve()),
        'ENVLOOP_DESKTOP_V4_FREEZE':'v11-gated-model-transport'}
 old={key:os.environ.get(key) for key in names}
 os.environ.update(names)
 try:yield
 finally:
  for key,value in old.items():
   if value is None:os.environ.pop(key,None)
   else:os.environ[key]=value


class ModelGuest:
 """Trusted setup/readback surrounds a screenshot-only actor interface."""
 def __init__(self,sandbox,*,root:Path,out:Path,filename:str):
  self.sandbox=sandbox;self.root=root;self.out=out;self.filename=filename
  self.remote='/home/user/'+filename;self.receipt={};self.killed=False;self.close_attempted=False
  self.proxy=PostEnterControlProxyV9(sandbox,storage_root=root,attempt_dir=out,document_filename=filename)
  self.recorder=RecordingDesktop(self.proxy)

 def persist(self):
  path=self.out/'guest.private.json'
  path.write_text(json.dumps(self.receipt,sort_keys=True,indent=2)+'\n');path.chmod(0o600)

 def prepare(self,*,source:bytes,guest_reference:dict,profile_reference:Path):
  info=self.sandbox.get_info(request_timeout=12)
  if (info.template_id!=guest_reference['provider_template_id'] or
      info.envd_version!=guest_reference['provider_envd_version'] or
      info.cpu_count!=guest_reference['provider_shape']['vcpu'] or
      info.memory_mb!=guest_reference['provider_shape']['memory_mb']):
   raise ValueError('v11_provider_shape_changed')
  self.receipt={'sandbox_id_sha256':digest(self.sandbox.sandbox_id.encode()),
                'lease_seconds':LEASE_SECONDS,'provider_shape_attested':True}
  self.persist()
  _run,observed,attestation=runtime_policy.execute_probe(self.sandbox,root=self.root,out=self.out,reference=guest_reference)
  self.receipt.update(guest_content_sha256=observed['content_tree_sha256'],
       guest_content_identity_kind=attestation['identity_kind'],raw_guest_content_sha256=attestation['raw_tree_sha256'],
       raw_tree_equals_legacy_reference=attestation['raw_tree_equals_legacy_reference'])
  self.persist()
  if self.sandbox.commands.run('test ! -e /home/user/.config/libreoffice/4/user').exit_code!=0:
   raise ValueError('v11_profile_not_fresh')
  self.receipt['fresh_profile_absent']=True
  self.sandbox.files.write(self.remote,source)
  if self.read_saved()!=source:raise ValueError('v11_staged_original_bytes_changed')
  self.sandbox.open(self.remote);wait_for_document_ready(self.sandbox,self.filename)
  time.sleep(7);self.sandbox.press('esc');time.sleep(1)
  kind={'.xlsx':'calc','.pptx':'impress','.docx':'writer'}[Path(self.filename).suffix]
  profile.attest(sandbox=self.sandbox,attempts_root=self.root,out=self.out,app_kind=kind,
                reference_path=profile_reference,receipt=self.receipt,persist=self.persist)
  self.receipt['input_sha256']=digest(source);self.persist()

 def observe(self,*,identity:dict,instruction:str,step:int,previous=None,memory=''):
  with evidence_scope(self.root,self.out):
   return readiness.observe(self.recorder,task_id=identity['task_id'],task_binding_sha256=identity['package_sha256'],
                            instruction=instruction,step=step,previous_action_result=previous,memory=memory,max_actions=MAX_ACTIONS)

 def dispatch_model(self,raw:str,observation,*,actor_deadline:float):
  """At most five no-model caret retries; material/modal drift never retries."""
  first=observation;attempts=[]
  with evidence_scope(self.root,self.out):
   for attempt in range(5):
    if time.monotonic()>=actor_deadline:raise TimeoutError('v11_actor_wall_budget')
    ref=reserve_and_write(self.root,self.out/f'frame-{first.step:02d}-{attempt}.png',observation.screenshot_bytes)
    try:
     action=strict.parse_current_action(raw,observation,self.recorder)
     break
    except strict.PhysicalFrameDrift:
     drift=reserve_and_write(self.root,self.out/f'drift-{first.step:02d}-{attempt}.png',self.recorder.last_screenshot)
     attempts.append({'step':first.step,'attempt':attempt,'observed':ref,'changed':drift})
     time.sleep(1)
     observation=self.observe(identity={'task_id':first.task_id,'package_sha256':first.task_binding_sha256},
                              instruction=first.instruction,step=first.step,previous=first.previous_action_result,memory=first.memory)
   else:raise strict.MaterialFrameDrift()
   pre=reserve_and_write(self.root,self.out/f'predispatch-{first.step:02d}-{attempt}.png',self.recorder.last_screenshot)
   if time.monotonic()>=actor_deadline:raise TimeoutError('v11_actor_wall_budget')
   self.proxy.current_actor_step=first.step
   kind=readiness.dispatch(self.proxy,action)
  return action,{'observation':ref,'predispatch':pre,'caret_resamples':attempts,
                 'frame_id_sha256':digest(observation.frame_id.encode()),'action_type':kind}

 def read_saved(self):return bytes(self.sandbox.files.read(self.remote,format='bytes'))

 def close(self):
  if self.close_attempted:return self.killed
  self.close_attempted=True  # Consume before kill/status acknowledgement; never replay cleanup HTTP.
  try:
   self.receipt['kill_returned']=bool(self.sandbox.kill())
   self.receipt['is_running_after_kill']=bool(self.sandbox.is_running(request_timeout=12))
  except Exception as exc:self.receipt['kill_error_type']=type(exc).__name__
  self.killed=self.receipt.get('kill_returned') is True and self.receipt.get('is_running_after_kill') is False
  self.persist();return self.killed


def create_guest(*,root:Path,out:Path,filename:str):
 """Called only inside the worker's durable, pre-reserved paid callback."""
 from e2b_desktop import Sandbox
 sandbox=Sandbox.create(template='desktop',resolution=(1280,800),timeout=LEASE_SECONDS,
                        allow_internet_access=False,metadata={'envloop_purpose':'v11-uniform-model-desktop'})
 return ModelGuest(bounded_transport.BoundedSandbox(sandbox),root=root,out=out,filename=filename)


def audit_model_readiness(root:Path,out:Path,actions:list,trace:list):
 """Bind passive captures to model observations, including an invalid last turn."""
 from .v066_final_control_audit import _bound_file
 expected=[i+1 for i,a in enumerate(actions) if readiness.needs_readiness(a) and i+1<len(trace)]
 path=out/'pre-observation-readiness-v12.ndjson'
 rows=[json.loads(line) for line in path.read_bytes().splitlines()] if path.exists() else []
 if len(rows)!=len(expected)*7:raise ValueError('v11_model_readiness_sample_count_changed')
 for ordinal,step in enumerate(expected):
  group=rows[ordinal*7:(ordinal+1)*7];frames=[]
  for index,row in enumerate(group):
   raw=_bound_file(root,row['frame']);frames.append(raw)
   if (row.get('schema')!='cua-native-passive-focus-readiness-v12' or row.get('step')!=step or
       row.get('preceding_step')!=step-1 or row.get('sample')!=index or
       row.get('requested_delay_ms')!=readiness.SAMPLE_DELAYS_MS[index] or row.get('native_window_unchanged') is not True or
       row.get('full_frame_sha256')!=digest(raw) or row.get('application_frame_sha256')!=pixels.application_frame_digest(raw) or
       type(row.get('monotonic_before_ns')) is not int or type(row.get('monotonic_after_ns')) is not int or
       row['monotonic_after_ns']<row['monotonic_before_ns'] or not 0<=row.get('elapsed_ns',-1)<=readiness.MAX_WALL_MS*1_000_000):
    raise ValueError('v11_model_readiness_raw_binding_changed')
  if (not readiness.settled_suffix(frames) or
      len({(r['window_id_sha256'],r['window_title_sha256']) for r in group})!=1 or
      len({r['monotonic_after_ns']-r['elapsed_ns'] for r in group})!=1 or
      group[-1]['elapsed_ns']<sum(readiness.SAMPLE_DELAYS_MS)*1_000_000 or
      any(b['monotonic_before_ns']-a['monotonic_after_ns']<b['requested_delay_ms']*1_000_000 for a,b in zip(group,group[1:])) or
      _bound_file(root,trace[step]['sampled_frame'])!=frames[-1]):
   raise ValueError('v11_model_readiness_not_bound_to_actual_sampled_frame')
 return len(expected)


class CleanRuntimeSampler:
 """Clean existing Qwen vision/image path, identical base/checkpoint policy."""
 def __init__(self):self.service=None;self.backend=None;self.adapters={}

 def start(self,*,checkpoint_path:str|None,checkpoint_sha256:str,seed:int,max_output_tokens:int,attempt_id:str):
  from cursibench.scale_vision_proxy import QwenVisionRenderer,TinkerVisionBackend,campaign_metadata,digest as vision_digest
  import tinker
  expected=digest(checkpoint_path.encode()) if checkpoint_path else vision_digest(MODEL)
  if expected!=checkpoint_sha256 or not 0<max_output_tokens<=MAX_OUTPUT_TOKENS:
   raise ValueError('v11_sampler_checkpoint_or_tokens_changed')
  from tinker.lib.retry_handler import RetryConfig
  self.service=tinker.ServiceClient(max_retries=0,user_metadata=campaign_metadata('desktop-v11-'+digest(attempt_id.encode())[:12]))
  renderer=QwenVisionRenderer.load()
  retry=RetryConfig(enable_retry_logic=False)
  client=self.service.create_sampling_client(retry_config=retry,**(
       {'model_path':checkpoint_path} if checkpoint_path else {'base_model':MODEL}))
  if client.get_base_model()!=MODEL:raise ValueError('v11_sampler_base_model_changed')
  self.backend=TinkerVisionBackend(client,renderer,checkpoint=checkpoint_path,seed=seed)
  if (self.backend.identity.get('model')!=MODEL or self.backend.identity.get('renderer')!=RENDERER or
      self.backend.identity.get('image_processor')!=PROCESSOR or
      self.backend.identity.get('checkpoint_sha256')!=vision_digest(checkpoint_path or MODEL) or
      self.backend.identity.get('sampling_kind')!=('checkpoint' if checkpoint_path else 'base')):
   raise ValueError('v11_clean_vision_sampler_identity_changed')
  self.max_output_tokens=max_output_tokens
  self.checkpoint_sha256=checkpoint_sha256
  return {'status':'ready','checkpoint_path_sha256':checkpoint_sha256,'sampling_kind':self.backend.identity['sampling_kind']}

 def sample(self,*,observation,request_id:str,task_dir:Path,remaining_seconds:float):
  return self.sample_rendered(request_id=request_id,task_dir=task_dir,remaining_seconds=remaining_seconds,
                              **output.render_for_model(observation))

 def sample_rendered(self,*,request_id:str,task_dir:Path,remaining_seconds:float,
                     image_bytes:bytes,instruction:str,visible_text:str):
  from cursibench.scale_vision_proxy import Limits,VisionSamplingAdapter
  if remaining_seconds<1:raise TimeoutError('v11_actor_wall_budget')
  key=str(task_dir.resolve());adapter=self.adapters.get(key)
  if adapter is None:
   adapter=VisionSamplingAdapter(self.backend,task_dir/'sampling-journal',
            limits=Limits(max_actions=MAX_ACTIONS,input_tokens=32768,output_tokens=self.max_output_tokens,request_timeout_seconds=120))
   self.adapters[key]=adapter
  adapter.limits=replace(adapter.limits,request_timeout_seconds=min(120,max(1,int(remaining_seconds))))
  result=adapter.sample(request_id=request_id,image_bytes=image_bytes,instruction=instruction,visible_text=visible_text)
  if result.get('reused') or result.get('new_dispatch') is not True or result.get('status')!='completed':
   self.last_failure=result
   raise ValueError('v11_model_sample_failed_or_uncertain_no_replay')
  return {**result,'reported_model':MODEL,'checkpoint_path_sha256':self.checkpoint_sha256,
          'backend_checkpoint_identity_sha256':self.backend.identity['checkpoint_sha256']}

 def close(self,success:bool):
  if self.service is not None:
   service,self.service=self.service,None
   service.close('success' if success else 'errored').result(timeout=30)


class ModelSampler:
 """Native SDK host delegates only sampling into the verified clean process."""
 def __init__(self,*,repo_root=None,journal_root=None,plan_sha256=None):
  from .qwen_sampler_process_v11 import SamplerProcess
  self.process=SamplerProcess(repo_root=repo_root,journal_root=journal_root,plan_sha256=plan_sha256)
  self.backend=None;self.checkpoint_sha256=None

 def start(self,**kwargs):
  from types import SimpleNamespace
  result=self.process.call('setup',kwargs)
  if result.get('status')!='ready':raise ValueError('v11_sampler_setup_uncertain_no_replay')
  self.checkpoint_sha256=kwargs['checkpoint_sha256']
  self.backend=SimpleNamespace(identity={'sampling_kind':result['sampling_kind']})
  return result

 def sample(self,*,observation,request_id,task_dir,remaining_seconds):
  import base64
  rendered=output.render_for_model(observation)
  result=self.process.call('sample',{'request_id':request_id,'task_dir':str(task_dir.resolve()),
    'remaining_seconds':remaining_seconds,'image_base64':base64.b64encode(rendered['image_bytes']).decode(),
    'instruction':rendered['instruction'],'visible_text':rendered['visible_text']},
    timeout=min(180,max(1,remaining_seconds)))
  if result.get('status')!='completed' or result.get('reused') or result.get('new_dispatch') is not True:
   raise ValueError('v11_model_sample_failed_or_uncertain_no_replay')
  return result

 def close(self,success):self.process.close(success)
