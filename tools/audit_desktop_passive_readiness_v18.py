"""Read-only audit of the exact closed v17 six-sample passive capture."""
import json
from pathlib import Path

from native_desktop_factory.factory import digest
from native_desktop_factory import pre_observation_readiness_v12 as legacy
from native_desktop_factory.qwen_v064_adapter import application_frame_digest
from native_desktop_factory.qwen_v066_adapter import _single_caret_column
from native_desktop_factory.v066_final_control_audit import _bound_file


def audit(root, out, *, freeze_sha256):
    receipt = json.loads((out / 'receipt.json').read_bytes())
    intent = json.loads((out / 'intent.json').read_bytes())
    rows = [json.loads(line) for line in (out / 'pre-observation-readiness-v12.ndjson').read_bytes().splitlines()]
    if not (receipt['source_freeze_sha256'] == intent['source_freeze_sha256'] == freeze_sha256 and
            receipt['status'] == 'control_failed_or_infrastructure_invalid' and
            receipt['stage'] == 'current_frame_gui' and receipt['error_type'] == 'ValueError' and
            len(receipt['actor_steps']) == 7 and
            all(s['step'] == index and s['status'] == 'applied' for index, s in enumerate(receipt['actor_steps'])) and
            receipt['actor_steps'][-1]['action_type'] == 'click' and receipt['kill_returned'] is True and
            receipt['is_running_after_kill'] is False and intent['attempt'] == 'positive' and
            intent['lease_seconds'] == receipt['sandbox_timeout_seconds'] == 1200 and
            intent['same_intent_replay_authorized'] is False and len(rows) == 6):
        raise ValueError('Exact closed v17 passive failure or full lease changed')
    frames = []
    for index, row in enumerate(rows):
        raw = _bound_file(root, row['frame'])
        if not (row['schema'] == 'cua-native-passive-focus-readiness-v12' and row['step'] == 7 and
                row['preceding_step'] == 6 and row['sample'] == index and
                row['requested_delay_ms'] == legacy.SAMPLE_DELAYS_MS[index] and
                row['native_window_unchanged'] is True and row['full_frame_sha256'] == digest(raw) and
                row['application_frame_sha256'] == application_frame_digest(raw) and
                type(row['monotonic_before_ns']) is type(row['monotonic_after_ns']) is type(row['elapsed_ns']) is int and
                row['monotonic_after_ns'] >= row['monotonic_before_ns'] >= row['monotonic_after_ns'] - row['elapsed_ns'] and
                row['elapsed_ns'] >= 0):
            raise ValueError('Closed passive PNG, native identity or timestamp binding changed')
        frames.append(raw)
    if not (len({r['monotonic_after_ns'] - r['elapsed_ns'] for r in rows}) == 1 and
            len({(r['window_id_sha256'], r['window_title_sha256']) for r in rows}) == 1 and
            all(a['elapsed_ns'] <= legacy.MAX_WALL_MS * 1_000_000 for a in rows[:-1]) and
            legacy.MAX_WALL_MS * 1_000_000 < rows[-1]['elapsed_ns'] < 60_000 * 1_000_000 and
            all(b['monotonic_before_ns'] - a['monotonic_after_ns'] >= b['requested_delay_ms'] * 1_000_000
                for a, b in zip(rows, rows[1:])) and
            not (out / 'readiness-07-06.png').exists() and
            all(frame == frames[-4] or _single_caret_column(frames[-4], frame) for frame in frames[-4:])):
        raise ValueError('Closed passive evidence no longer supports time-bound diagnosis')
    return {'schema': 'cua-native-v17-passive-readiness-offline-audit-v18',
            'status': 'raw_six_samples_verified_time_bound_crossed_before_seventh',
            'failed_receipt_sha256': digest((out / 'receipt.json').read_bytes()),
            'journal_sha256': digest((out / 'pre-observation-readiness-v12.ndjson').read_bytes()),
            'full_frame_sha256s': [digest(f) for f in frames],
            'application_frame_sha256s': [application_frame_digest(f) for f in frames],
            'elapsed_ns': [r['elapsed_ns'] for r in rows],
            'capture_ns': [r['monotonic_after_ns'] - r['monotonic_before_ns'] for r in rows],
            'last_four_full_bytes_equal': all(f == frames[-4] for f in frames[-4:]),
            'last_four_exact_or_narrow_caret': True, 'native_window_unchanged': True,
            'captured_samples': 6, 'required_samples': 7, 'applied_actor_steps': 7,
            'seventh_sample_captured': False, 'old_max_wall_ms': legacy.MAX_WALL_MS,
            'proposed_max_wall_ms': 60_000, 'new_control_credit': 0,
            'new_live_readiness_success': False, 'provider_calls': 0, 'model_calls': 0}
