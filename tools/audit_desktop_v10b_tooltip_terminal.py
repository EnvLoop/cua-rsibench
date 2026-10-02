"""Read-only terminal tooltip audit; never creates, replays or reads other gold."""
from __future__ import annotations

import argparse
from hashlib import sha256
import io
import json
from pathlib import Path
import sqlite3

from PIL import Image, ImageChops


def digest(raw):
    return sha256(raw).hexdigest()


def audit(*, attempts_root, dispatch_root):
    attempts_root, dispatch_root = Path(attempts_root), Path(dispatch_root)
    intents = list(attempts_root.glob('*/*/intent.json'))
    receipts = list(attempts_root.glob('*/*/receipt.json'))
    if len(intents) != 1 or len(receipts) != 1 or intents[0].parent != receipts[0].parent:
        raise ValueError('Expected one immutable positive attempt')
    out = receipts[0].parent
    receipt = json.loads(receipts[0].read_bytes())
    intent = json.loads(intents[0].read_bytes())
    child = json.loads((out / 'child-started.json').read_bytes())
    terminal = json.loads((dispatch_root / 'worker-terminal.private.json').read_bytes())
    if not (intent['attempt'] == receipt['attempt'] == 'positive' and
            intent['split'] == receipt['split'] == 'selection' and
            child['intent_sha256'] == digest(intents[0].read_bytes()) and
            intent['source_freeze_sha256'] == child['source_freeze_sha256'] == receipt['source_freeze_sha256'] and
            receipt['status'] == 'control_failed_or_infrastructure_invalid' and
            receipt['stage'] == 'current_frame_gui' and
            receipt['error_type'] == 'MaterialFrameDrift' and
            receipt['contract_error_code'] == 'stale_frame' and
            receipt['kill_returned'] is True and receipt['is_running_after_kill'] is False and
            terminal['exit_code'] == 1 and terminal['automatic_restarts'] == terminal['model_calls'] == 0):
        raise ValueError('Terminal source, failure or cleanup boundary changed')
    for name in ('stdout', 'stderr'):
        if digest((dispatch_root / f'worker.{name}.private.log').read_bytes()) != terminal[f'{name}_sha256']:
            raise ValueError('Detached terminal log changed')
    steps = receipt['actor_steps']
    if [s['step'] for s in steps] != list(range(8)) or any(s['status'] != 'applied' for s in steps):
        raise ValueError('Retained applied action prefix changed')
    expected = {'type': 'type', 'text': "'Two-factor review'.B5", 'mode': 'insert'}
    probe = json.loads((out / 'probe-step-08-00.json').read_bytes())
    if not (probe['step'] == 8 and probe['frame_attempt'] == 0 and
            probe['status'] == 'rejected_material_or_third_state' and
            probe['action_sha256'] == digest(json.dumps(expected, separators=(',', ':')).encode()) and
            len(probe['sample_frames']) == 1 and receipt['physical_frame_resamples'] == []):
        raise ValueError('First insertion rejection was changed')
    observed = (out / 'frame-08-0.png').read_bytes()
    ref = probe['sample_frames'][0]
    rejected = (attempts_root / ref['private_path']).read_bytes()
    if digest(observed) != probe['observed_sha256'] or digest(rejected) != ref['sha256'] or len(rejected) != ref['bytes']:
        raise ValueError('Retained failure frame changed')
    first = Image.open(io.BytesIO(observed)).convert('RGB')
    second = Image.open(io.BytesIO(rejected)).convert('RGB')
    bounds = ImageChops.difference(first, second).getbbox()
    pixels = sum(a != b for a, b in zip(first.getdata(), second.getdata()))
    if first.size != second.size or first.size != (1280, 800) or bounds != (14, 183, 98, 215) or pixels != 2666:
        raise ValueError('Known native tooltip mismatch changed')
    db = sqlite3.connect(f'file:{attempts_root / "storage-ledger.sqlite3"}?mode=ro', uri=True)
    try:
        reserved = db.execute('SELECT reserved_bytes FROM budget WHERE id=1').fetchone()[0]
        rows = db.execute('SELECT path,bytes,sha256,status FROM evidence ORDER BY path').fetchall()
    finally:
        db.close()
    if reserved != sum(r[1] for r in rows):
        raise ValueError('Storage budget changed')
    for relative, size, checksum, status in rows:
        raw = (attempts_root / relative).read_bytes()
        if status != 'written' or len(raw) != size or digest(raw) != checksum:
            raise ValueError('Retained storage evidence changed')
    manifest = {str(path.relative_to(attempts_root)): digest(path.read_bytes())
                for path in sorted(attempts_root.rglob('*')) if path.is_file()}
    return {'schema': 'cua-native-desktop-v10b-tooltip-terminal-public-audit',
            'status': 'terminal_material_hover_overlay_before_first_insertion',
            'failed_attempt_receipt_sha256': digest(receipts[0].read_bytes()),
            'source_freeze_sha256': receipt['source_freeze_sha256'],
            'permit_sha256': receipt['permit_sha256'],
            'worker_terminal_sha256': digest((dispatch_root / 'worker-terminal.private.json').read_bytes()),
            'retained_manifest_sha256': digest(json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode()),
            'retained_file_count': len(manifest), 'consumed_intents': 1,
            'applied_actor_actions': 8, 'rejected_next_step': 8,
            'rejected_action_type': 'type',
            'rejected_action_reached_dispatch': False,
            'observed_frame_sha256': digest(observed), 'rejected_frame_sha256': digest(rejected),
            'difference_bbox_xyxy': list(bounds), 'changed_rgb_pixels': pixels,
            'visual_adjudication': 'Native Name Box tooltip appeared beneath the stationary pointer.',
            'post_enter_windows_reached': 0, 'saved_artifact_readback_reached': False,
            'recorded_guest_kill_returned': True, 'recorded_guest_running_after_kill': False,
            'current_provider_inventory_rechecked': False,
            'storage_ledger_rows': len(rows), 'storage_reserved_bytes': reserved,
            'storage_unresolved_writes': 0, 'all_ledger_bytes_reopened': True,
            'automatic_restarts': 0, 'same_intent_replay_authorized': False,
            'model_calls': 0, 'new_guest_creates_by_audit': 0,
            'official_final_admissions': 0, 'official_model_results': 0,
            'actual_provider_billed_usd': None}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--attempts-root', required=True, type=Path)
    p.add_argument('--dispatch-root', required=True, type=Path)
    p.add_argument('--public-out', required=True, type=Path)
    a = p.parse_args()
    result = audit(attempts_root=a.attempts_root, dispatch_root=a.dispatch_root)
    with a.public_out.open('x') as stream:
        stream.write(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'status': result['status'], 'public_sha256': digest(a.public_out.read_bytes())}))


if __name__ == '__main__':
    main()
