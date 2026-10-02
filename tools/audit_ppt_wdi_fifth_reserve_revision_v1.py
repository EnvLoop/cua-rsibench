"""Publish aggregate-only evidence for five pre-result WDI replacements."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urlparse

from ppt_wdi_factory import verify
from tools.audit_ppt_wdi_reserve_revision_v1 import require, sha
from tools.audit_ppt_wdi_second_reserve_revision_v1 import (
    audit_axes, semantic_deck_equal, write_new,
)
from tools.extract_wdi_country_csv_reserve_v1 import extract


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prior-root', type=Path, required=True)
    parser.add_argument('--prior-staging', type=Path, required=True)
    parser.add_argument('--private-root', type=Path, required=True)
    parser.add_argument('--fifth-quarantine', type=Path, required=True)
    parser.add_argument('--country-zip', type=Path, required=True)
    parser.add_argument('--country-provenance', type=Path, required=True)
    parser.add_argument('--replacement-seed-file', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    private = (Path.cwd() / 'work').resolve()
    root, prior_root = args.private_root.resolve(), args.prior_root.resolve()
    prior_stage = args.prior_staging.resolve()
    require(root.is_relative_to(private) and prior_root.is_relative_to(private)
            and prior_stage.is_relative_to(private)
            and not args.out.exists(),
            'private revised roots and new public output required')
    raw_plan = (root / 'candidate-plan.private.json').read_bytes()
    prior_raw = (prior_root / 'candidate-plan.private.json').read_bytes()
    plan, prior = json.loads(raw_plan), json.loads(prior_raw)
    qraw = args.fifth_quarantine.read_bytes()
    quarantine = json.loads(qraw)
    zip_raw = args.country_zip.read_bytes()
    praw = args.country_provenance.read_bytes()
    provenance = json.loads(praw)
    seed = bytes.fromhex(args.replacement_seed_file.read_text().strip())
    require(len(seed) == 32 and
            plan['revision'] == 'private_wdi_five_reserves_and_web_chart_v7'
            and plan['previous_plan_sha256'] == sha(prior_raw) and
            prior['revision'] == 'private_wdi_four_reserves_and_web_chart_v6'
            and plan['fifth_quarantine_receipt_sha256'] == sha(qraw) and
            plan['fifth_reserve_provenance_sha256'] == sha(praw) and
            plan['fifth_reserve_zip_sha256'] == sha(zip_raw) and
            plan['fifth_reserve_seed_commitment_sha256'] == sha(seed) and
            quarantine['plan_sha256'] == sha(prior_raw) and
            quarantine['family_indices'] == [16, 17, 18, 19] and
            provenance['schema'] ==
            'envloop-wdi-official-country-csv-extract-private-v1' and
            provenance['catalog_license'] == 'CC BY 4.0' and
            provenance['numeric_observation_count'] == 30 and
            urlparse(provenance['official_download_url']).hostname ==
            'api.worldbank.org' and
            urlparse(provenance['official_page_url']).hostname ==
            'data.worldbank.org',
            'fifth-reserve plan/source/quarantine provenance changed')
    failures = [prior_stage / 'case-016' /
                f'attempt-{attempt}-failure.private.json'
                for attempt in (0, 1)]
    failure_raw = [path.read_bytes() for path in failures]
    failure = [json.loads(raw) for raw in failure_raw]
    require([sha(raw) for raw in failure_raw] ==
            quarantine['attempt_failure_sha256'] and
            [item['attempt'] for item in failure] == [0, 1] and
            all(item['task_id'] ==
                prior['sets']['final_candidate'][16]['task_id'] and
                item['model_calls'] == item['official_final_admitted'] == 0
                for item in failure) and
            failure[1]['candidate_ineligible_under_pre_result_rule'] is True,
            'two retained evaluator infrastructure failures changed')
    extracted, detail = extract(zip_raw, provenance['country_iso'])
    require(sha(extracted) == plan['fifth_reserve_source_sha256'] and
            detail['data_member_sha256'] == provenance['data_member_sha256'],
            'retained official country CSV no longer reproduces observations')
    require({key: len(rows) for key, rows in plan['sets'].items()} ==
            {'train': 20, 'selection': 20, 'final_candidate': 100},
            'revised split counts changed')
    finals = plan['sets']['final_candidate']
    first = [row for row in finals if row.get('source_scope') ==
             'private_wdi_reserve_v1']
    csv_rows = [row for row in finals if row.get('source_scope') ==
                'private_wdi_country_csv_reserve_v1']
    fifth = [row for row in csv_rows if row['source_snapshot_sha256'] ==
             plan['fifth_reserve_source_sha256']]
    require(len(first) == 4 and len(csv_rows) == 16 and len(fifth) == 4 and
            len({row['source_group'] for row in csv_rows}) == 4 and
            len({row['source_group'] for row in finals}) == 25 and
            set(Counter(row['workflow'] for row in finals).values()) == {10} and
            {row['task_id'] for row in finals}.isdisjoint(
                quarantine['task_ids']) and
            quarantine['source_group'] not in
            {row['source_group'] for row in finals} and
            not ({row['source_group'] for row in
                  plan['sets']['train'] + plan['sets']['selection']} &
                 {row['source_group'] for row in finals}),
            'five-reserve final pool or source isolation changed')
    prior_by_id = {row['task_id']: row for rows in prior['sets'].values()
                   for row in rows}
    preserved = 0
    for split in ('train', 'selection', 'final_candidate'):
        for row in plan['sets'][split]:
            if row['task_id'] not in prior_by_id:
                continue
            package = root / 'packages' / split / row['task_id']
            require(row == prior_by_id[row['task_id']] and
                    semantic_deck_equal(
                        prior_root / 'packages' / split / row['task_id'] /
                        'source.pptx', package / 'source.pptx'),
                    'unexposed prior task or visible/chart/workbook source changed')
            preserved += 1
    require(preserved == 136, '136 prior task and semantic deck contracts required')
    for row in first + csv_rows:
        package = root / 'packages/final_candidate' / row['task_id']
        oracle = verify.freeze(package / 'source.pptx', row)
        require(oracle['source_snapshot_sha256'] ==
                row['source_snapshot_sha256'] and
                json.loads((package / 'calibration.private.json').read_bytes())
                ['offline_controls_pass'] is True,
                'reserve source/oracle/calibration changed')
        if row in fifth:
            require(sha((package / 'source-snapshot.private.json').read_bytes())
                    == plan['fifth_reserve_source_sha256'] and
                    sha((package / 'source-country.private.zip').read_bytes())
                    == plan['fifth_reserve_zip_sha256'] and
                    sha((package / 'source-provenance.private.json').read_bytes())
                    == plan['fifth_reserve_provenance_sha256'],
                    'official CSV source not retained in new replacement package')
    build_raw = (root / 'build-receipt.private.json').read_bytes()
    qa_raw = (root / 'qa-aggregate.private.json').read_bytes()
    calibration_raw = (root / 'calibration-run.private.json').read_bytes()
    build, qa, calibration = (json.loads(raw) for raw in
                              (build_raw, qa_raw, calibration_raw))
    require(build['plan_sha256'] == calibration['plan_sha256'] ==
            sha(raw_plan) and len(build['rows']) == 140 and
            qa == {'candidate_decks': 140, 'package_integrity_pass': 140,
                   'layout_geometry_pass': 140,
                   'chart_workbook_contract_pass': 140} and
            calibration['candidate_count'] ==
            calibration['offline_passed'] == 140,
            'full five-reserve build/QA/calibration receipt incomplete')
    axis_pass = audit_axes(root, plan)
    visual = root / 'visual-qa/fifth-reserve.pdf'
    pages = subprocess.check_output(['pdfinfo', str(visual)], text=True,
                                    timeout=15)
    require(re.search(r'^Pages:\s+7$', pages, re.MULTILINE) is not None and
            (root / 'visual-qa/fifth-reserve-contact-sheet.png').is_file(),
            'seven-page replacement visual QA missing')
    public = {'schema': 'envloop-ppt-wdi-five-reserve-revision-public-v1',
              'status': 'five_reserve_20_20_100_offline_candidates_not_web_admitted',
              'prior_plan_sha256': sha(prior_raw),
              'revised_plan_sha256': sha(raw_plan),
              'fifth_quarantine_private_sha256': sha(qraw),
              'fifth_source_provenance_private_sha256': sha(praw),
              'fifth_seed_commitment_sha256': sha(seed),
              'five_quarantined_source_families': 5,
              'five_reserve_source_families': 5,
              'replacement_tasks_total': 20,
              'pre_admission_infrastructure_failures_retained': 2,
              'unchanged_prior_task_specs_and_semantic_decks': preserved,
              'split_candidate_counts': {key: len(rows) for key, rows in
                                         plan['sets'].items()},
              'final_source_families': 25,
              'final_workflows': 10,
              'fifth_source_observations': 30,
              'fifth_source_kind': 'official_world_bank_country_csv_extract',
              'source_license': 'World Development Indicators CC BY 4.0',
              'build_receipt_private_sha256': sha(build_raw),
              'qa_receipt_private_sha256': sha(qa_raw),
              'calibration_receipt_private_sha256': sha(calibration_raw),
              'package_integrity_pass': 140,
              'layout_geometry_pass': 140,
              'native_chart_workbook_contract_pass': 140,
              'native_chart_axis_bounds_and_unsmoothed_pass': axis_pass,
              'offline_positive_negative_controls_pass': 140,
              'visual_qa_pages': 7,
              'office_web_gui_admitted': 0,
              'official_final_tasks_admitted': 0,
              'model_calls': 0,
              'researcher_campaigns': 0}
    write_new(args.out, (json.dumps(public, sort_keys=True, indent=2) + '\n').encode())
    print(json.dumps({'status': public['status'],
                      'revised_plan_sha256': sha(raw_plan),
                      'preserved_prior_semantic_decks': preserved,
                      'offline_passed': 140,
                      'official_final_tasks_admitted': 0}, sort_keys=True))


if __name__ == '__main__':
    main()
