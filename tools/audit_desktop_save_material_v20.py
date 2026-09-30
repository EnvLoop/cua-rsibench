"""Read-only frame delta and frozen generic Save-tail binding for closed v19."""
from collections import Counter
import io
import json
from PIL import Image, ImageChops
from native_desktop_factory.factory import digest
from native_desktop_factory.qwen_v064_adapter import application_frame_digest
from native_desktop_factory.qwen_v066_adapter import _single_caret_column
from native_desktop_factory.v066_final_control_audit import _bound_file
from native_desktop_factory.selection_control_scripts_v10 import SAVE
from native_desktop_factory.v066_control_plan import compile_script


def audit(root, out, *, freeze_sha256):
    receipt = json.loads((out / 'receipt.json').read_bytes()); intent = json.loads((out / 'intent.json').read_bytes())
    probe = json.loads((out / 'probe-step-21-00.json').read_bytes()); steps = receipt['actor_steps']
    save, _guards = compile_script('\n'.join(SAVE) + '\n')
    save_key, pending_wait = save[:2]
    payload_sha = lambda value: digest(json.dumps(value, separators=(',', ':')).encode())
    if not (receipt['source_freeze_sha256'] == intent['source_freeze_sha256'] == freeze_sha256 and
            receipt['status'] == 'control_failed_or_infrastructure_invalid' and receipt['stage'] == 'current_frame_gui' and
            receipt['error_type'] == 'MaterialFrameDrift' and receipt['contract_error_code'] == 'stale_frame' and
            receipt['kill_returned'] is True and receipt['is_running_after_kill'] is False and
            receipt['sandbox_timeout_seconds'] == intent['lease_seconds'] == 1200 and intent['same_intent_replay_authorized'] is False and
            len(steps) == 21 and all(s['step'] == index and s['status'] == 'applied' for index, s in enumerate(steps)) and
            steps[-1]['action_payload_sha256'] == payload_sha(save_key) and probe['action_sha256'] == payload_sha(pending_wait) and
            probe['step'] == 21 and probe['frame_attempt'] == 0 and probe['status'] == 'rejected_material_or_third_state' and
            len(probe['sample_frames']) == 1):
        raise ValueError('Closed Save dispatch, raw material rejection or full lease changed')
    first_path = out / 'frame-21-0.png'; first = first_path.read_bytes(); second = _bound_file(root, probe['sample_frames'][0])
    if digest(first) != probe['observed_sha256'] or [application_frame_digest(second)] != probe['sample_application_sha256s']:
        raise ValueError('Closed observed or direct probe bytes changed')
    with Image.open(io.BytesIO(first)) as opened:a = opened.convert('RGB')
    with Image.open(io.BytesIO(second)) as opened:b = opened.convert('RGB')
    bounds = ImageChops.difference(a, b).getbbox()
    if bounds is None or a.size != b.size or a.size != (1280, 800) or _single_caret_column(first, second):
        raise ValueError('Closed actual non-caret material delta changed')
    count = 0; pairs = Counter()
    for y in range(bounds[1], bounds[3]):
        for x in range(bounds[0], bounds[2]):
            left, right = a.getpixel((x, y)), b.getpixel((x, y))
            if left != right:count += 1; pairs[left, right] += 1
    return {'schema': 'cua-native-v19-save-material-offline-audit-v20',
        'status': 'exact_save_then_pending_wait_direct_material_delta_verified',
        'receipt_sha256': digest((out / 'receipt.json').read_bytes()), 'probe_sha256': digest((out / 'probe-step-21-00.json').read_bytes()),
        'observed_frame_sha256': digest(first), 'direct_probe_sha256': digest(second), 'delta_bbox': list(bounds),
        'changed_pixels': count, 'most_common_color_changes': [{'before': list(a), 'after': list(b), 'pixels': n} for (a, b), n in pairs.most_common(10)],
        'original_single_caret_classifier': False, 'preceding_input': save_key, 'pending_action': pending_wait,
        'recorded_applied_actions': 21, 'pending_action_dispatched': False, 'new_control_credit': 0,
        'native_modal_id_captured_for_comparison': False,
        'animation_cause_is_inference_from_two_frames': True,
        'new_live_success': False, 'provider_calls': 0, 'model_calls': 0}
