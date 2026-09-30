"""Independent closed-v18 raw Enter and completed-focus sample readback."""
import json
from native_desktop_factory.factory import digest
from native_desktop_factory import post_enter_train_probe_v1 as train
from native_desktop_factory import pre_observation_readiness_v18 as focus
from native_desktop_factory.qwen_v064_adapter import application_frame_digest
from native_desktop_factory.v066_final_control_audit import _bound_file


def audit(root, out, *, freeze_sha256):
    receipt = json.loads((out / 'receipt.json').read_bytes()); intent = json.loads((out / 'intent.json').read_bytes())
    steps = receipt['actor_steps']
    if not (receipt['source_freeze_sha256'] == intent['source_freeze_sha256'] == freeze_sha256 and
            receipt['stage'] == 'current_frame_gui' and receipt['error_type'] == 'ValueError' and
            receipt['status'] == 'control_failed_or_infrastructure_invalid' and receipt['kill_returned'] is True and
            receipt['is_running_after_kill'] is False and receipt['sandbox_timeout_seconds'] == intent['lease_seconds'] == 1200 and
            intent['attempt'] == 'positive' and intent['same_intent_replay_authorized'] is False and len(steps) == 17 and
            all(s['step'] == index and s['status'] == 'applied' for index, s in enumerate(steps[:-1])) and
            steps[-1]['step'] == 16 and steps[-1]['action_type'] == 'key' and steps[-1]['status'] == 'validated_pre_dispatch'):
        raise ValueError('Closed v18 raw dispatch state, failure, teardown or full lease changed')
    rows = [json.loads(line) for line in (out / 'post-enter-samples.ndjson').read_bytes().splitlines()]
    if len(rows) != 15:raise ValueError('Exactly three closed Enter windows required')
    windows = []
    for ordinal in range(3):
        group = rows[ordinal * 5:(ordinal + 1) * 5]; frames = []
        for index, row in enumerate(group):
            raw = _bound_file(root, row['frame']); frames.append(raw)
            if not (row['schema'] == 'cua-native-wdi-post-enter-control-sample-v9' and
                    row['enter_ordinal'] == ordinal and row['sample'] == index and
                    row['requested_delay_ms_before_sample'] == train.SAMPLE_DELAYS_MS[index] and
                    row['full_frame_sha256'] == digest(raw) and row['application_frame_sha256'] == application_frame_digest(raw) and
                    row['document_window_stable'] is True and row['window_id_before_sha256'] == row['window_id_after_sha256'] and
                    row['window_title_before_sha256'] == row['window_title_after_sha256'] and
                    row['monotonic_after_ns'] >= row['monotonic_before_ns'] >= row['monotonic_after_ns'] - row['elapsed_since_enter_ns']):
                raise ValueError('Closed Enter raw PNG, timestamp or native identity changed')
        app = [r['application_frame_sha256'] for r in group]; transitions = []
        for value in app:
            if not transitions or value != transitions[-1]:transitions.append(value)
        if not (len({r['preceding_actor_step'] for r in group}) == 1 and
                len({r['monotonic_after_ns'] - r['elapsed_since_enter_ns'] for r in group}) == 1 and
                len({(r['window_id_after_sha256'], r['window_title_after_sha256']) for r in group}) == 1 and
                app[-1] == app[-2] and len(transitions) <= 2 and len(transitions) == len(set(transitions)) and
                group[-1]['elapsed_since_enter_ns'] >= sum(train.SAMPLE_DELAYS_MS) * 1_000_000 and
                all(b['monotonic_before_ns'] - a['monotonic_after_ns'] >= b['requested_delay_ms_before_sample'] * 1_000_000
                    for a, b in zip(group, group[1:])) and
                all(r['elapsed_since_enter_ns'] <= train.MAX_PROBE_WALL_MS * 1_000_000 for r in group[:-1]) and
                0 < group[-1]['elapsed_since_enter_ns'] < 60_000 * 1_000_000):
            raise ValueError('Closed Enter material settling or elapsed evidence changed')
        windows.append({'ordinal': ordinal, 'preceding_actor_step': group[0]['preceding_actor_step'],
            'elapsed_ns': [r['elapsed_since_enter_ns'] for r in group],
            'capture_ns': [r['monotonic_after_ns'] - r['monotonic_before_ns'] for r in group],
            'full_frame_sha256s': [digest(f) for f in frames], 'application_frame_sha256s': app,
            'all_full_frames_equal': all(f == frames[0] for f in frames), 'final_two_application_equal': True})
    if not (windows[-1]['preceding_actor_step'] == 16 and
            windows[-1]['elapsed_ns'][-1] > train.MAX_PROBE_WALL_MS * 1_000_000 and
            all(w['elapsed_ns'][-1] <= train.MAX_PROBE_WALL_MS * 1_000_000 for w in windows[:-1])):
        raise ValueError('Exact last-sample 30-second boundary diagnosis changed')
    passive = [json.loads(line) for line in (out / 'pre-observation-readiness-v12.ndjson').read_bytes().splitlines()]
    if len(passive) != 28:raise ValueError('Four completed v18 focus windows required')
    for ordinal in range(4):
        group = passive[ordinal * 7:(ordinal + 1) * 7]; frames = []
        for index, row in enumerate(group):
            raw = _bound_file(root, row['frame']); frames.append(raw)
            if not (row['sample'] == index and row['requested_delay_ms'] == focus.SAMPLE_DELAYS_MS[index] and
                    row['native_window_unchanged'] is True and row['full_frame_sha256'] == digest(raw) and
                    row['application_frame_sha256'] == application_frame_digest(raw) and
                    row['monotonic_after_ns'] >= row['monotonic_before_ns'] and
                    0 <= row['elapsed_ns'] <= focus.MAX_WALL_MS * 1_000_000):
                raise ValueError('Closed completed focus raw sample changed')
        if not (focus.settled_suffix(frames) and len({(r['step'], r['preceding_step']) for r in group}) == 1 and
                len({(r['window_id_sha256'], r['window_title_sha256']) for r in group}) == 1 and
                len({r['monotonic_after_ns'] - r['elapsed_ns'] for r in group}) == 1 and
                (out / f'frame-{group[0]["step"]:02d}-0.png').read_bytes() == frames[-1]):
            raise ValueError('Closed completed focus final observation changed')
    return {'schema': 'cua-native-v18-enter-offline-audit-v19',
        'status': 'last_enter_sample_exceeded_30_with_stable_raw_frames',
        'receipt_sha256': digest((out / 'receipt.json').read_bytes()),
        'post_enter_journal_sha256': digest((out / 'post-enter-samples.ndjson').read_bytes()),
        'windows': windows, 'completed_focus_windows': 4, 'recorded_actor_steps': 17,
        'receipt_applied_actor_steps': 16, 'last_receipt_status': 'validated_pre_dispatch',
        'last_enter_has_post_input_captures': True, 'old_max_wall_ms': 30_000,
        'proposed_max_wall_ms': 60_000, 'historical_control_credit': 0,
        'new_live_control_success': False, 'provider_calls': 0, 'model_calls': 0}
