"""Commit a bounded, ordered pre-result WDI replacement queue without IDs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re

from native_desktop_factory import source as wdi


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


SELECTION_RULE = ('first unused ordered country whose official WDI CSV has '
                  'all five pinned indicators for 2019-2024; retain every rejection')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-plan', type=Path, required=True)
    parser.add_argument('--queue', type=Path, required=True)
    parser.add_argument('--seventh-quarantine', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    private = (Path.cwd() / 'work').resolve()
    require(all(path.resolve().is_relative_to(private) for path in
                (args.private_plan, args.queue, args.seventh_quarantine)) and
            not args.out.exists(),
            'private inputs and fresh public receipt required')
    plan_raw = args.private_plan.read_bytes()
    qraw = args.seventh_quarantine.read_bytes()
    queue_raw = args.queue.read_bytes()
    plan, quarantine, queue = (json.loads(raw) for raw in
                               (plan_raw, qraw, queue_raw))
    require(plan['revision'] == 'private_wdi_seven_reserves_and_web_chart_v9'
            and quarantine['schema'] ==
            'envloop-ppt-wdi-seventh-family-quarantine-private-v1'
            and queue['schema'] ==
            'envloop-ppt-future-reserve-queue-private-v1'
            and queue['current_plan_sha256'] == sha(plan_raw)
            and queue['seventh_quarantine_receipt_sha256'] == sha(qraw)
            and queue['declared_after_quarantined_source_families'] == 7
            and queue['maximum_total_quarantined_source_families'] == 10
            and queue['no_model_result_or_final_admission_at_declaration']
            is True,
            'pre-result queue, cap or plan commitment changed')
    codes = queue['ordered_future_country_iso']
    used = {row['source_group'] for rows in plan['sets'].values()
            for row in rows}
    require(isinstance(codes, list) and len(codes) == 10 and
            len(codes) == len(set(codes)) and codes == sorted(codes) and
            all(isinstance(code, str) and
                re.fullmatch(r'[A-Z]{3}', code) and
                code not in used and code not in wdi.COUNTRIES
                for code in codes) and
            queue['selection_rule'] == SELECTION_RULE,
            'future candidate source queue is not disjoint and deterministic')
    result = {
        'schema': 'envloop-ppt-future-reserve-queue-public-v1',
        'status': 'pre_result_queue_and_attrition_cap_frozen',
        'current_plan_sha256': sha(plan_raw),
        'seventh_quarantine_receipt_sha256': sha(qraw),
        'private_queue_sha256': sha(queue_raw),
        'ordered_future_country_count': len(codes),
        'declared_after_quarantined_source_families': 7,
        'maximum_total_quarantined_source_families': 10,
        'maximum_additional_family_replacements': 3,
        'future_source_complete_observation_screen_required': True,
        'every_rejected_source_retained': True,
        'if_cap_exceeded': 'fail_cell_and_re_register_study_before_model_results',
        'country_identities_public': False,
        'model_calls': 0, 'official_final_admitted': 0,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(result, sort_keys=True, indent=2) + '\n').encode()
    fd = os.open(args.out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
    print(json.dumps({'status': result['status'],
                      'maximum_additional_family_replacements': 3,
                      'official_final_admitted': 0}, sort_keys=True))


if __name__ == '__main__':
    main()
