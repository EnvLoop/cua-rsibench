"""Inspect or advance a frozen full-study campaign; no synthetic shortcuts.

The current repository intentionally fails `check`: a genuine 600-task
pre-campaign manifest, six-cell v0.6.6 ratification, and immutable public
freeze witness have not been produced. Only `researcher-call` may send a paid
request, and it must pass every gate first.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from cursibench.full_study_campaign_dispatch_v1 import DispatchError, FrozenStudy


ROOT = Path(__file__).resolve().parents[1]


def _private_file_sha(path: Path, study: FrozenStudy) -> tuple[bytes, str]:
    if path.is_symlink():
        raise ValueError('private work evidence required')
    path = path.resolve()
    if (not path.is_file() or
            not path.is_relative_to(study.repo_root / 'work') or
            path.stat().st_mode & 0o077):
        raise ValueError('private work evidence required')
    raw = path.read_bytes()
    return raw, hashlib.sha256(raw).hexdigest()


def _private_evidence(path: Path, study: FrozenStudy) -> tuple[dict, str]:
    raw, digest = _private_file_sha(path, study)
    value = json.loads(raw)
    if type(value) is not dict:
        raise ValueError('private JSON object required')
    return value, digest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, default=ROOT)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--prepared-dir', type=Path, required=True)
    parser.add_argument('--ratification', type=Path, required=True)
    parser.add_argument('--public-commit', required=True)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('check')
    base_admit = sub.add_parser('base-admit')
    base_admit.add_argument('--cell', required=True)
    base_admit.add_argument('--receipt', type=Path, required=True)
    for name in ('start', 'snapshot', 'base-selection', 'researcher-call',
                 'selection-start', 'selection-invalid', 'selection-score',
                 'selection-freeze',
                 'reconcile'):
        command = sub.add_parser(name)
        command.add_argument('--private-dir', type=Path, required=True)
        command.add_argument('--cell', required=True)
        command.add_argument('--researcher', required=True)
        if name == 'base-selection':
            command.add_argument('--receipt', type=Path, required=True)
        elif name == 'researcher-call':
            command.add_argument('--round', type=int, required=True)
            command.add_argument('--train-context', type=Path, required=True)
        elif name == 'selection-start':
            command.add_argument('--round', type=int, required=True)
            command.add_argument('--attempt-id', required=True)
            command.add_argument('--retry-rule-sha256')
        elif name == 'selection-score':
            command.add_argument('--attempt-id', required=True)
            command.add_argument('--result', type=Path, required=True)
            command.add_argument('--paid-attempt-ids', type=Path, required=True)
        elif name == 'selection-invalid':
            command.add_argument('--attempt-id', required=True)
            command.add_argument('--failure-type', required=True,
                                 choices=('provider', 'transport',
                                          'environment', 'verifier'))
            command.add_argument('--evaluator-proof', type=Path, required=True)
        elif name == 'reconcile':
            command.add_argument('--attempt-id', required=True)
            command.add_argument('--actual-usd')
            command.add_argument('--provider-proof', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        study = FrozenStudy(
            repo_root=args.repo_root, manifest_path=args.manifest,
            prepared_dir=args.prepared_dir,
            ratification_path=args.ratification,
            public_commit_sha1=args.public_commit)
        if args.command == 'check':
            result = {'state': 'qualified_pre_campaign_freeze_verified',
                      'campaign_count': 24,
                      'official_task_identities': 600,
                      'plan_sha256': study.plan_sha256,
                      'public_witness_sha256': study.public_witness_sha256,
                      'provider_calls': 0}
        elif args.command == 'base-admit':
            result = study.admit_shared_base_selection(
                args.cell, args.receipt)
        else:
            session = study.open_campaign(
                args.private_dir, cell_id=args.cell,
                researcher_id=args.researcher)
            if args.command in {'start', 'snapshot'}:
                result = session.snapshot()
            elif args.command == 'base-selection':
                result = session.record_base_selection(
                    shared_receipt_path=args.receipt)
            elif args.command == 'researcher-call':
                result = session.dispatch_researcher(
                    round_index=args.round,
                    train_context_path=args.train_context)
            elif args.command == 'selection-start':
                started = session.start_selection_attempt(
                    round_index=args.round,
                    attempt_id=args.attempt_id,
                    retry_rule_sha256=args.retry_rule_sha256)
                result = {key: value for key, value in started.items()
                          if key != 'selection_tasks'}
            elif args.command == 'selection-score':
                value, _ = _private_evidence(args.result, study)
                paid, _ = _private_evidence(args.paid_attempt_ids, study)
                if (paid.get('schema') !=
                        'cua-full-study-selection-paid-attempt-list-v1' or
                        type(paid.get('attempt_ids')) is not list):
                    raise ValueError('invalid private selection paid attempt list')
                result = session.record_selection_scored(
                    attempt_id=args.attempt_id, result=value,
                    paid_attempt_ids=paid['attempt_ids'])
            elif args.command == 'selection-invalid':
                _, evidence_sha = _private_file_sha(args.evaluator_proof, study)
                result = session.record_selection_invalid(
                    attempt_id=args.attempt_id,
                    failure_type=args.failure_type,
                    evaluator_receipt_sha256=evidence_sha)
            elif args.command == 'selection-freeze':
                result = session.freeze_selection()
            elif args.command == 'reconcile':
                _, evidence_sha = _private_file_sha(args.provider_proof, study)
                if args.actual_usd is None:
                    result = session.reconcile_paid(
                        args.attempt_id, actual_usd=None,
                        provider_no_charge_sha256=evidence_sha)
                else:
                    result = session.reconcile_paid(
                        args.attempt_id, actual_usd=args.actual_usd,
                        provider_usage_sha256=evidence_sha)
                result = {'attempt_id': args.attempt_id,
                          'billing_state': result['status'],
                          'provider_proof_sha256': evidence_sha}
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as exc:
        # Avoid printing provider response bodies, task content, paths to
        # private account files, or credentials into public terminal logs.
        print(json.dumps({'state': 'refused',
                          'reason_type': type(exc).__name__,
                          'reason_code': (str(exc) if isinstance(exc, DispatchError)
                                          else None)}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
