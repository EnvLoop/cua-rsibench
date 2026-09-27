"""Independently audit all 100 GitLab GUI controls after bounded recovery.

This reads evaluator-private receipts and writes only an aggregate public
projection. It never dispatches a browser, model, or failed-ID retry.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess

from gitlab_world import (bootstrap, factory, failure_ledger,
                          pre_result_recovery, quarantine, runtime, sweep)


ROOT = Path(__file__).resolve().parents[1]
PRIVATE = runtime.PRIVATE
PRIVATE_OUT = PRIVATE / 'requalification-100-audit.private.json'
PUBLIC_OUT = ROOT / 'docs/evidence/gitlab-requalification-100-2026-09-28.json'


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def write_new(path: Path, value: dict, mode: int) -> str:
    raw = (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return sha(raw)


def audit() -> tuple[dict, dict]:
    index_raw = sweep.INDEX.read_bytes()
    index = json.loads(index_raw)
    sweep.reconcile_failure_ledger(index)
    rows = sweep.candidates()
    resolution_path = pre_result_recovery.PRIVATE_RESOLUTION
    resolution_raw = resolution_path.read_bytes()
    resolution = pre_result_recovery.read_private_resolution(resolution_path)
    ledger = failure_ledger.private_entries()
    ledger_public = failure_ledger.audit()
    eligible = pre_result_recovery.eligible_requalification_rows(
        rows, index, ledger, resolution, world=bootstrap.world(),
        private_root=PRIVATE)
    if (eligible or len(rows) != 100 or len(index['items']) != 100 or
            len(ledger) != 6 or
            resolution['original_first_attempt_passes'] != 94 or
            resolution['original_first_attempt_failures'] != 6 or
            resolution['failure_ledger_head_sha256'] != ledger[-1]['entry_sha256']):
        raise ValueError('GitLab first-attempt denominator or recovery is incomplete')
    first = {task_id: item['attempts'][0]
             for task_id, item in index['items'].items()}
    if (factory.sha256(factory.canonical(first)) !=
            resolution['original_first_attempts_sha256'] or
            factory.sha256(factory.canonical(sorted(
                row['task_id'] for row in rows))) !=
            resolution['original_active_roster_sha256']):
        raise ValueError('first-attempt bytes or 100-ID roster changed')
    first_failures = []
    recovered = []
    for row in rows:
        item = index['items'][row['task_id']]
        attempts = item['attempts']
        if (item['status'] != 'development_gui_trio_passed' or
                item['scores'] != [1.0, 0.0, 1.0] or
                item['cold_resets'] != 3 or len(attempts) not in (1, 2) or
                attempts[-1]['status'] != item['status'] or
                attempts[-1]['scores'] != item['scores'] or
                attempts[-1]['cold_resets'] != 3):
            raise ValueError('active GitLab control lacks complete 1/0/1/reset')
        if len(attempts) == 2:
            first_failures.append(attempts[0])
            recovered.append(row['task_id'])
            if (attempts[0]['status'] == 'development_gui_trio_passed'
                    or attempts[0]['failure_ledger_entry_sha256'] not in
                    {entry['entry_sha256'] for entry in ledger}):
                raise ValueError('requalification erased its first failed attempt')
    if len(first_failures) != 6 or len(recovered) != 6:
        raise ValueError('exactly six preserved first failures must recover')
    summary = sweep.public_summary(index)
    if (summary['development_gui_trio_passed'] != 100 or
            summary['verified_cold_resets_for_passed_ids'] != 300 or
            summary['retained_prior_failed_attempts'] != 6 or
            summary['attempted_source_family_count'] != 20 or
            summary['official_final_admitted'] != 0):
        raise ValueError('GitLab aggregate differs from per-ID receipts')
    demo = runtime.proof(runtime.DEMO)
    pre = json.loads((PRIVATE / 'demo-prestop.json').read_bytes())
    if (demo['running'] is not True or demo['health'] != 'healthy' or
            runtime.stable_identity(demo) != runtime.stable_identity(pre)):
        raise ValueError('original GitLab demo was not restored exactly')
    inspected = subprocess.run(['docker', '--context', runtime.CONTEXT,
                                'inspect', runtime.WORLD], capture_output=True,
                               timeout=30)
    if inspected.returncode == 0:
        raise ValueError('disposable GitLab world remains after controls')
    private = {
        'schema': 'envloop-gitlab-requalification-100-audit-private-v1',
        'original_active_denominator': 100,
        'original_first_attempt_passes': 94,
        'original_first_attempt_failures': 6,
        'recovered_same_task_ids': sorted(recovered),
        'current_gui_trios_passed': 100,
        'current_cold_resets_verified': 300,
        'source_families': 20,
        'index_sha256': sha(index_raw),
        'resolution_sha256': sha(resolution_raw),
        'failure_ledger_head_sha256': ledger[-1]['entry_sha256'],
        'ledger_public': ledger_public,
        'demo_container_id_sha256': demo['container_id_sha256'],
        'demo_identity_preserved': True,
        'disposable_world_removed': True,
        'model_calls': 0,
        'official_final_admitted': 0,
    }
    public = {
        'schema': 'envloop-gitlab-requalification-100-audit-public-v1',
        'date': '2026-09-28',
        'original_active_denominator': 100,
        'original_first_attempt_passes': 94,
        'original_first_attempt_failures_retained': 6,
        'same_id_whole_case_requalifications_passed': 6,
        'current_gui_trios_passed': 100,
        'current_cold_resets_verified': 300,
        'source_families': 20,
        'index_sha256': private['index_sha256'],
        'private_resolution_sha256': private['resolution_sha256'],
        'failure_ledger_head_sha256': private['failure_ledger_head_sha256'],
        'demo_identity_preserved': True,
        'disposable_world_removed': True,
        'model_calls': 0,
        'official_final_admitted': 0,
        'remaining_gates': ['v066_live_train_actor', 'per_id_original_software_admission',
                            'six_cell_pre_campaign_freeze'],
    }
    return private, public


def main() -> None:
    if PRIVATE_OUT.exists() or PUBLIC_OUT.exists():
        raise FileExistsError('fresh private/public audit paths required')
    private, public = audit()
    private_sha = write_new(PRIVATE_OUT, private, 0o600)
    public['private_audit_sha256'] = private_sha
    public_sha = write_new(PUBLIC_OUT, public, 0o644)
    print(json.dumps({'status': '100_development_gui_controls_audited',
                      'public_sha256': public_sha,
                      'original_failures_retained': 6,
                      'official_final_admitted': 0}, sort_keys=True))


if __name__ == '__main__':
    main()
