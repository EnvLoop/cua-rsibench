"""Operate a private all-in ledger only from a revalidated pre-campaign manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cursibench import full_study_pre_campaign_v1 as pre_campaign
from cursibench import scale_final_v06 as cell_final
from cursibench.full_study_budget_v1 import StudyBudgetLedger


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol-manifest', type=Path, required=True)
    parser.add_argument('--ledger', type=Path, required=True)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('snapshot')
    reserve = sub.add_parser('reserve')
    reserve.add_argument('--attempt-id', required=True)
    reserve.add_argument('--owner', required=True)
    reserve.add_argument('--category', required=True)
    reserve.add_argument('--amount-usd', required=True)
    reserve.add_argument('--work-sha256', required=True)
    dispatch = sub.add_parser('dispatch-started')
    dispatch.add_argument('--attempt-id', required=True)
    dispatch.add_argument('--request-sha256', required=True)
    uncertain = sub.add_parser('uncertain')
    uncertain.add_argument('--attempt-id', required=True)
    uncertain.add_argument('--failure-type', required=True)
    settle = sub.add_parser('settle')
    settle.add_argument('--attempt-id', required=True)
    settle.add_argument('--actual-usd', required=True)
    settle.add_argument('--usage-sha256', required=True)
    cancel = sub.add_parser('cancel-no-charge')
    cancel.add_argument('--attempt-id', required=True)
    cancel.add_argument('--no-charge-sha256', required=True)
    args = parser.parse_args()
    protocol_path = args.protocol_manifest.resolve()
    raw = protocol_path.read_bytes()
    plan = pre_campaign.build(json.loads(raw), protocol_path.parent,
                              cell_final.digest(raw))
    ledger = StudyBudgetLedger(args.ledger, plan)
    if args.action == 'reserve':
        state = ledger.reserve(args.attempt_id, args.owner, args.category,
                               args.amount_usd, args.work_sha256)
    elif args.action == 'dispatch-started':
        state = ledger.mark_dispatched(args.attempt_id, args.request_sha256)
    elif args.action == 'uncertain':
        state = ledger.mark_uncertain(args.attempt_id, args.failure_type)
    elif args.action == 'settle':
        state = ledger.settle(args.attempt_id, args.actual_usd,
                              args.usage_sha256)
    elif args.action == 'cancel-no-charge':
        state = ledger.cancel_with_no_charge(args.attempt_id,
                                              args.no_charge_sha256)
    else:
        state = None
    snapshot = ledger.snapshot()
    print(json.dumps({'action': args.action,
                      'attempt_status': state['status'] if state else None,
                      'global_reserved_or_spent_usd':
                          snapshot['global_reserved_or_spent_usd'],
                      'uncertain_attempts': snapshot['uncertain_attempts']},
                     sort_keys=True))


if __name__ == '__main__':
    main()
