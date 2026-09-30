"""One-use Qwen base sampling for an admitted local Office TRAIN frame.

The trusted bridge emits the native admission and cropped frame. No task gold,
source CSV, credentials, browser session or content API is given to the model.
The CLI is dormant without --run and never resumes a consumed output directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

from cursibench import scale_action_output_v066 as output
from cursibench.scale_vision_proxy import (
    MODEL, Limits, ProxyError, QwenVisionRenderer, TinkerVisionBackend,
    VisionSamplingAdapter, public_receipt,
)
from tools import office_single_account_train_pilot_v1 as private
from tools.office_local_browser_train_action_adapter_v1 import (
    make_local_observation, normalize_local_action,
)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class LocalQwenBaseSampler:
    """Provider-independent wrapper; an injected adapter supports offline checks."""
    def __init__(self, adapter):
        private._require(adapter.backend.identity.get('model') == MODEL and
                         adapter.backend.identity.get('sampling_kind') == 'base',
                         'local_office_base_sampler_required')
        self.adapter = adapter

    def sample_current_frame(self, frame, image, instruction, *, now_ms=None,
                             memory='', previous_action_result=None):
        obs = make_local_observation(frame,image,instruction,
            current_frame_id=frame['frame_id'],now_ms=now_ms,memory=memory,
            previous_action_result=previous_action_result)
        request = output.render_for_model(obs)
        prompt = json.loads(request['instruction'])
        prompt['local_gui_profile'] = frame['local_profile']
        prompt['local_gui_rule'] = (
            'Use only local_gui_profile actions, keys and safe regions. '
            'Coordinates refer to this cropped image. Type only into a focused '
            'document editor. Navigation, exports and whole-editor selection '
            'are unavailable. Return finish when the visible task is complete.')
        request['instruction'] = json.dumps(prompt,sort_keys=True,separators=(',',':'))
        private._require(len(request['instruction'].encode()) <= 16_384,
                         'local_office_prompt_too_large')
        result = self.adapter.sample(request_id='office-frame-'+frame['frame_id'],**request)
        private._require(type(result) is dict and result.get('status') == 'completed' and
                         type(result.get('text')) is str,
                         'local_office_sampling_failed_no_replay')
        action = normalize_local_action(result['text'],frame,image,instruction,
            current_frame_id=frame['frame_id'],now_ms=now_ms,memory=memory,
            previous_action_result=previous_action_result)
        return action, result


def open_base_sampler(repo_root: Path, journal: Path, max_steps: int,
                      source_review_sha256: str):
    """Paid boundary, after native admission validation and fresh run intent."""
    from cursibench.full_study_qwen_runtime_gate_v1 import pre_dispatch
    runtime = pre_dispatch(repo_root=repo_root,
                           study_plan_sha256=source_review_sha256)
    private._require(bool(os.environ.get('TINKER_API_KEY')),
                     'local_office_tinker_host_key_required')
    import tinker
    from tinker.lib.retry_handler import RetryConfig
    # This is the checked hash-locked Tinker 0.30.0 interface. Disable both
    # transport and higher-level sampling retries for uncertain calls.
    service = tinker.ServiceClient(max_retries=0,timeout=90,
        user_metadata={'purpose':'office-local-browser-qwen-base-train-v1',
                       'split':'train','formal_campaign':'false'})
    try:
        renderer = QwenVisionRenderer.load()
        client = service.create_sampling_client(base_model=MODEL,
            retry_config=RetryConfig(enable_retry_logic=False,
                                     enable_stuck_detection=False,max_connections=1))
        private._require(client.get_base_model()==MODEL,
                         'local_office_sampler_base_model_changed')
        backend = TinkerVisionBackend(client,renderer,seed=23)
        adapter = VisionSamplingAdapter(backend,journal,
            limits=Limits(max_actions=max_steps,request_timeout_seconds=90))
        return LocalQwenBaseSampler(adapter),service,runtime
    except BaseException:
        service.close('errored').result(timeout=30)
        raise


def admit(admission_path: Path, frame_path: Path, instruction_path: Path,
          work_root: Path):
    admission, raw = private._json(admission_path,work_root)
    required={'schema','mode','cell','split','task_id','task_binding_sha256',
              'account_principal_sha256','control_receipt_sha256',
              'source_review_sha256','bridge_source_sha256',
              'action_adapter_source_sha256','sampler_source_sha256',
              'visible_instruction_sha256','max_steps','binding_sha256',
              'actor_before_sha256','selection_or_final_eligible','official_final_credit'}
    private._require(set(admission)==required and
        admission['schema']=='office-local-browser-native-sampler-admission-v1' and
        admission['mode']=='native_development' and admission['cell']=='powerpoint-web' and
        admission['split']=='train' and admission['selection_or_final_eligible'] is False and
        admission['official_final_credit']==0 and type(admission['max_steps']) is int and
        1<=admission['max_steps']<=120,
        'local_office_native_sampler_admission_required')
    source_root=Path(__file__).resolve().parents[1]
    for field, rel in {
        'bridge_source_sha256':'tools/office_local_browser_train_bridge_v1.mjs',
        'action_adapter_source_sha256':'tools/office_local_browser_train_action_adapter_v1.py',
        'sampler_source_sha256':'tools/office_local_browser_qwen_base_sampler_v1.py',
    }.items():
        private._require(sha((source_root/rel).read_bytes())==admission[field],
                         'local_office_reviewed_sampler_source_changed')
    for key in ('account_principal_sha256','control_receipt_sha256',
                'source_review_sha256','visible_instruction_sha256',
                'binding_sha256','actor_before_sha256'):
        private._require(type(admission[key]) is str and private._HEX.fullmatch(admission[key]),
                         'local_office_admission_binding_invalid')
    frame, frame_raw=private._json(frame_path,work_root)
    image_path,image=private._ref(frame['screenshot_ref'],work_root)
    instruction=private._private(instruction_path,work_root,16_384)
    private._require(sha(instruction)==admission['visible_instruction_sha256'] and
        frame['task_id']==admission['task_id'] and
        frame['task_binding_sha256']==admission['task_binding_sha256'] and
        0<=frame['step']<admission['max_steps'],
        'local_office_sampler_task_or_instruction_changed')
    make_local_observation(frame,image,instruction.decode(),current_frame_id=frame['frame_id'])
    return admission,frame,image,instruction.decode(),{
        'native_admission_sha256':sha(raw),'frame_sha256':sha(frame_raw),
        'image_sha256':sha(image),'visible_instruction_sha256':sha(instruction)}


def run(admission_path, frame_path, instruction_path, out, *, repo_root,
        memory='', previous_action_result=None, sampler_factory=open_base_sampler):
    repo_root=Path(repo_root).absolute()
    work_root=repo_root/'work'
    admission,frame,image,instruction,binding=admit(
        admission_path,frame_path,instruction_path,work_root)
    out=Path(out).absolute()
    private._require(not out.exists() and not out.is_symlink() and
                     out.parent.resolve().is_relative_to(work_root.resolve()),
                     'local_office_consumed_sampler_output_no_replay')
    out.mkdir(mode=0o700)
    private._write_new(out/'intent.private.json',private._canonical({
        'schema':'office-local-qwen-base-one-frame-intent-v1',**binding,
        'frame_id':frame['frame_id'],'step':frame['step'],
        'single_dispatch_only':True,'model':MODEL,'selection_or_final_eligible':False}))
    service=None
    status='errored'
    try:
        sampler,service,runtime=sampler_factory(repo_root,out.parent/'model-journal.private',
            admission['max_steps'],admission['source_review_sha256'])
        action,result=sampler.sample_current_frame(frame,image,instruction,
            memory=memory,previous_action_result=previous_action_result)
        private._write_new(out/'model-result.private.json',private._canonical(result))
        action_sha=private._write_new(out/'action.private.json',private._canonical(action))
        receipt={'schema':'office-local-qwen-base-one-frame-result-v1',
            'status':'normalized_current_frame_action_only',**binding,
            'action_sha256':action_sha,'runtime':runtime,
            'sampling':public_receipt(result),'browser_calls':0,
            'independent_saved_state_verified':False,'official_final_credit':0}
        private._write_new(out/'result.private.json',private._canonical(receipt))
        status='success'
        return receipt
    except BaseException as exc:
        private._write_new(out/'terminal-failure.private.json',private._canonical({
            'schema':'office-local-qwen-base-one-frame-failure-v1',
            'status':'failed_or_uncertain_no_replay','exception_type':type(exc).__name__,
            'error_sha256':sha(str(exc).encode()),'official_final_credit':0}))
        raise
    finally:
        if service is not None:
            service.close(status).result(timeout=30)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--admission',type=Path,required=True)
    p.add_argument('--frame',type=Path,required=True)
    p.add_argument('--visible-instruction',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--context',type=Path)
    p.add_argument('--run',action='store_true')
    args=p.parse_args()
    root=Path(__file__).resolve().parents[1]
    if not args.run:
        admission,_,_,_,binding=admit(args.admission,args.frame,args.visible_instruction,root/'work')
        print(json.dumps({'status':'offline_native_frame_admitted_only',**binding,
                          'provider_calls':0,'official_final_credit':0}))
        return
    context={'memory':'','previous_action_result':None}
    if args.context is not None:
        context,_=private._json(args.context,root/'work')
        private._require(set(context)=={'memory','previous_action_result'},
                         'local_office_context_invalid')
    receipt=run(args.admission,args.frame,args.visible_instruction,args.out,repo_root=root,**context)
    print(json.dumps(receipt,sort_keys=True))


if __name__=='__main__':
    try:
        main()
    except (ValueError, OSError) as exc:
        print(json.dumps({'status':'rejected_or_failed_no_replay',
                          'exception_type':type(exc).__name__,'official_final_credit':0}))
        sys.exit(1)
