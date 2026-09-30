"""Connect a private cropped local-browser frame to the existing v0.6.6 action contract.

No browser/provider call, source/gold read or registration is performed here.
The evaluator supplies the visible instruction and the current bridge frame.
The CUA dispatcher independently rechecks pixels, URL, focus, lease and regions.
"""
from __future__ import annotations
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import re
import time

from cursibench import scale_action_contract as contract
from cursibench import scale_action_output_v066 as output
from tools import office_single_account_train_pilot_v1 as private


def make_local_observation(frame: dict, screenshot: bytes,
                           visible_instruction: str, *, current_frame_id: str,
                           now_ms: int | None = None, memory: str = '',
                           previous_action_result: dict | None = None):
    now_ms = int(time.time()*1000) if now_ms is None else now_ms
    fields={'schema','frame_id','task_id','task_binding_sha256','step','width','height',
            'expires_at_ms','screenshot_sha256','screenshot_ref','local_profile'}
    if (type(frame) is not dict or set(frame)!=fields or
            frame['schema']!='office-local-browser-frame-v1' or
            type(frame['frame_id']) is not str or not re.fullmatch(r'[a-f0-9]{32}',frame['frame_id']) or
            frame['frame_id']!=current_frame_id or
            type(frame['task_id']) is not str or not re.fullmatch(r'ppt-wdi-transfer-[a-f0-9]{16}',frame['task_id']) or
            type(frame['width']) is not int or type(frame['height']) is not int or
            type(frame['expires_at_ms']) is not int or not now_ms<frame['expires_at_ms']<=now_ms+150_000 or
            hashlib.sha256(screenshot).hexdigest()!=frame['screenshot_sha256']):
        raise contract.ContractError('invalid_local_browser_frame')
    profile=frame['local_profile']
    safe_keys={'Enter','Escape','Backspace','Delete','Space','ArrowUp','ArrowDown','ArrowLeft','ArrowRight','Home','End','Shift+End'}
    if (type(profile) is not dict or set(profile)!={'action_types','type_mode','editor_focus_required',
            'keys','actor_navigation_and_exports','safe_regions'} or
            profile['action_types']!=['click','double_click','type','key','scroll','finish'] or
            profile['type_mode']!='insert' or profile['editor_focus_required'] is not True or
            profile['actor_navigation_and_exports'] is not False or
            type(profile['keys']) is not list or not all(type(k) is str for k in profile['keys']) or
            not set(profile['keys'])<=safe_keys or
            type(profile['safe_regions']) is not list or not 1<=len(profile['safe_regions'])<=4 or
            any(type(r) is not dict or set(r)!={'x','y','width','height'} or
                not all(type(v) is int for v in r.values()) or
                r['x']<0 or r['y']<0 or r['width']<=0 or r['height']<=0 or
                r['x']+r['width']>frame['width'] or r['y']+r['height']>frame['height']
                for r in profile['safe_regions'])):
        raise contract.ContractError('invalid_local_browser_profile')
    # Use the existing complete image, task, text, coordinate and expiry
    # validator. The random ID originally minted by the local trusted bridge
    # replaces only make_observation's own random nonce.
    obs=contract.make_observation(task_id=frame['task_id'],task_binding_sha256=frame['task_binding_sha256'],
        instruction=visible_instruction,step=frame['step'],screenshot_bytes=screenshot,
        previous_action_result=previous_action_result,
        memory=memory,
        limits=contract.ContractLimits(max_step=120,typed_text_bytes=2000,memory_bytes=2048,
            frame_ttl_seconds=max(1,(frame['expires_at_ms']-now_ms)//1000)))
    if obs.screenshot['width']!=frame['width'] or obs.screenshot['height']!=frame['height']:
        raise contract.ContractError('local_browser_crop_dimensions_changed')
    return replace(obs,frame_id=frame['frame_id'])


def normalize_local_action(raw_text: str, frame: dict, screenshot: bytes,
                           visible_instruction: str, *, current_frame_id: str,
                           now_ms: int | None = None, memory: str = '',
                           previous_action_result: dict | None = None) -> dict:
    obs=make_local_observation(frame,screenshot,visible_instruction,
        current_frame_id=current_frame_id,now_ms=now_ms,memory=memory,
        previous_action_result=previous_action_result)
    profile=frame['local_profile']
    action=output.normalize_model_action(raw_text,obs,current_frame_id=current_frame_id)
    kind=action['type']
    if (kind not in profile['action_types'] or
            (kind=='type' and (action['mode']!='insert' or re.search(r'https?://|www\.|mailto:|file:|javascript:',action['text'],re.I))) or
            (kind=='key' and action['key'] not in profile['keys']) or
            (kind=='scroll' and (action['dx']!=0 or abs(action['dy'])>720 or 'target' not in action))):
        raise contract.ContractError('unsupported_local_browser_action')
    if 'target' in action:
        target=action['target']
        if (set(target)!={'x','y'} or not any(
                type(r) is dict and set(r)=={'x','y','width','height'} and
                all(type(v) is int for v in r.values()) and
                r['x']<=target['x']<r['x']+r['width'] and r['y']<=target['y']<r['y']+r['height']
                for r in profile['safe_regions'])):
            raise contract.ContractError('unsafe_local_browser_region')
    return action


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frame',type=Path,required=True)
    parser.add_argument('--model-output',type=Path,required=True)
    parser.add_argument('--visible-instruction',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    root=Path.cwd()/'work'
    frame,_=private._json(args.frame,root.resolve())
    _,image=private._ref(frame['screenshot_ref'],root.resolve())
    raw=private._private(args.model_output,root.resolve(),16_384).decode()
    instruction=private._private(args.visible_instruction,root.resolve(),16_384).decode()
    action=normalize_local_action(raw,frame,image,instruction,current_frame_id=frame['frame_id'])
    private._require(args.out.absolute().parent.resolve().is_relative_to(root.resolve()),'private_action_output_required')
    sha=private._write_new(args.out,private._canonical(action))
    print(json.dumps({'status':'normalized_private_action_only','action_sha256':sha,
                      'browser_calls':0,'provider_calls':0,'official_final_credit':0}))


if __name__=='__main__':
    main()
