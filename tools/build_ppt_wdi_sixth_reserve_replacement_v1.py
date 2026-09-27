"""Replace one pre-result quarantined PowerPoint source family from WDI CSV.

Existing unexposed task specifications remain unchanged. The four replacement
IDs use a new private random seed committed separately from the original
partition seed. This creates offline candidates, never web admissions.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
from urllib.parse import urlparse

from native_desktop_factory import source as wdi
from ppt_wdi_factory import plan as ppt
from tools.build_ppt_wdi_reserve_replacement_v1 import (
    facts_from_official_response, require, sha, write_new,
)
from tools.extract_wdi_country_csv_reserve_v1 import extract


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prior-root', type=Path, required=True)
    parser.add_argument('--prior-plan-sha256', required=True)
    parser.add_argument('--sixth-quarantine', type=Path, required=True)
    parser.add_argument('--replacement-seed-file', type=Path, required=True)
    parser.add_argument('--country-zip', type=Path, required=True)
    parser.add_argument('--country-snapshot', type=Path, required=True)
    parser.add_argument('--country-provenance', type=Path, required=True)
    parser.add_argument('--out-dir', type=Path, required=True)
    args = parser.parse_args()
    private = (Path.cwd() / 'work').resolve()
    prior_root, out = args.prior_root.resolve(), args.out_dir.resolve()
    require(prior_root.is_relative_to(private) and out.is_relative_to(private)
            and not out.exists(), 'prior private inventory and fresh output required')
    prior_raw = (prior_root / 'candidate-plan.private.json').read_bytes()
    require(sha(prior_raw) == args.prior_plan_sha256,
            'five-reserve candidate plan digest changed')
    prior = json.loads(prior_raw)
    require(prior.get('revision') == 'private_wdi_five_reserves_and_web_chart_v7'
            and {key: len(rows) for key, rows in prior['sets'].items()} == ppt.COUNTS
            and len({row['source_group'] for row in prior['sets']['final_candidate']}) == 25,
            'five-reserve inventory is not a 20/20/100 source pool')
    seed = bytes.fromhex(args.replacement_seed_file.read_text().strip())
    require(len(seed) == 32 and args.replacement_seed_file.stat().st_mode & 0o077 == 0,
            'mode-0600 private replacement seed required')
    quarantine_raw = args.sixth_quarantine.read_bytes()
    quarantine = json.loads(quarantine_raw)
    require(quarantine['schema'] ==
            'envloop-ppt-wdi-sixth-family-quarantine-private-v1' and
            quarantine['plan_sha256'] == args.prior_plan_sha256 and
            quarantine['family_indices'] == [20, 21, 22, 23] and
            quarantine['remaining_current_final_candidates'] == 96 and
            quarantine['new_replacement_tasks_required'] == 4 and
            quarantine['model_calls'] == quarantine['official_final_admitted'] == 0,
            'sixth source-family quarantine changed')
    old = prior['sets']['final_candidate']
    qrows = [old[index] for index in quarantine['family_indices']]
    require([row['task_id'] for row in qrows] == quarantine['task_ids'] and
            {row['source_group'] for row in qrows} == {quarantine['source_group']},
            'quarantined source/task binding changed')
    zip_raw = args.country_zip.read_bytes()
    snapshot_raw = args.country_snapshot.read_bytes()
    provenance_raw = args.country_provenance.read_bytes()
    provenance = json.loads(provenance_raw)
    require(provenance['schema'] ==
            'envloop-wdi-official-country-csv-extract-private-v1' and
            provenance['source_type'] == 'worldbank_official_country_csv_zip' and
            provenance['zip_sha256'] == sha(zip_raw) and
            provenance['snapshot_sha256'] == sha(snapshot_raw) and
            provenance['catalog_license'] == 'CC BY 4.0' and
            urlparse(provenance['official_download_url']).hostname ==
            'api.worldbank.org' and
            urlparse(provenance['official_page_url']).hostname ==
            'data.worldbank.org',
            'official CSV provenance binding changed')
    iso = provenance['country_iso']
    extracted, detail = extract(zip_raw, iso)
    require(extracted == snapshot_raw and
            detail['data_member_sha256'] == provenance['data_member_sha256'] and
            detail['data_last_updated'] == provenance['data_last_updated'] and
            detail['numeric_observation_count'] == 30 and
            iso not in set(wdi.COUNTRIES) and
            iso not in {row['source_group'] for rows in prior['sets'].values()
                        for row in rows},
            'sixth source is incomplete or overlaps the partition')
    facts = facts_from_official_response(snapshot_raw)
    require(facts['iso3'] == iso and facts['name'] == provenance['country_name'],
            'CSV extract and country source disagree')
    revised = json.loads(prior_raw)
    revised['revision'] = 'private_wdi_six_reserves_and_web_chart_v8'
    revised['previous_plan_sha256'] = args.prior_plan_sha256
    revised['sixth_quarantine_receipt_sha256'] = sha(quarantine_raw)
    revised['sixth_reserve_source_sha256'] = sha(snapshot_raw)
    revised['sixth_reserve_zip_sha256'] = sha(zip_raw)
    revised['sixth_reserve_provenance_sha256'] = sha(provenance_raw)
    revised['sixth_reserve_seed_commitment_sha256'] = sha(seed)
    replacements = []
    for slot, index in enumerate(quarantine['family_indices']):
        previous = old[index]
        row = ppt.task(seed, 'final_candidate', iso, 5, slot, facts)
        require(row['workflow'] == previous['workflow'] and
                row['target_keys'] == previous['target_keys'],
                'replacement would alter workflow quota or target locations')
        row.update({'source_scope': 'private_wdi_country_csv_reserve_v1',
                    'source_snapshot_sha256': sha(snapshot_raw),
                    'source_snapshot_date': provenance['download_date'],
                    'source_zip_sha256': sha(zip_raw),
                    'source_provenance_sha256': sha(provenance_raw),
                    'source_csv_data_last_updated': detail['data_last_updated']})
        revised['sets']['final_candidate'][index] = row
        replacements.append(row)
    finals = revised['sets']['final_candidate']
    require(len({row['task_id'] for rows in revised['sets'].values()
                 for row in rows}) == 140 and
            len({row['source_group'] for row in finals}) == 25 and
            set(Counter(row['workflow'] for row in finals).values()) == {10} and
            sum(row.get('source_scope') == 'private_wdi_reserve_v1'
                for row in finals) == 4 and
            sum(row.get('source_scope') == 'private_wdi_country_csv_reserve_v1'
                for row in finals) == 20 and
            quarantine['source_group'] not in
            {row['source_group'] for row in finals} and
            not ({row['source_group'] for row in
                  revised['sets']['train'] + revised['sets']['selection']} &
                 {row['source_group'] for row in finals}),
            'sixth reserve breaks source isolation or final balance')
    out.mkdir(parents=True, mode=0o700)
    plan_raw = ppt.canonical(revised)
    write_new(out / 'candidate-plan.private.json', plan_raw)
    for row in finals:
        scope = row.get('source_scope')
        if scope not in ('private_wdi_reserve_v1',
                         'private_wdi_country_csv_reserve_v1') or row in replacements:
            continue
        old_package = prior_root / 'packages/final_candidate' / row['task_id']
        new_package = out / 'packages/final_candidate' / row['task_id']
        names = (('source-snapshot.private.json',) if
                 scope == 'private_wdi_reserve_v1' else
                 ('source-snapshot.private.json',
                  'source-country.private.zip',
                  'source-provenance.private.json'))
        for name in names:
            write_new(new_package / name, (old_package / name).read_bytes())
    for row in replacements:
        package = out / 'packages/final_candidate' / row['task_id']
        write_new(package / 'source-snapshot.private.json', snapshot_raw)
        write_new(package / 'source-country.private.zip', zip_raw)
        write_new(package / 'source-provenance.private.json', provenance_raw)
    receipt = {'schema': 'envloop-ppt-wdi-sixth-reserve-private-v1',
               'status': 'six_reserve_20_20_100_offline_candidates_not_web_admitted',
               'prior_plan_sha256': args.prior_plan_sha256,
               'revised_plan_sha256': sha(plan_raw),
               'sixth_quarantine_receipt_sha256': sha(quarantine_raw),
               'sixth_reserve_seed_commitment_sha256': sha(seed),
               'sixth_reserve_zip_sha256': sha(zip_raw),
               'sixth_reserve_source_sha256': sha(snapshot_raw),
               'sixth_reserve_provenance_sha256': sha(provenance_raw),
               'replacement_tasks': 4, 'final_candidate_count': 100,
               'final_source_families': 25, 'final_workflows': 10,
               'model_calls': 0, 'official_final_admitted': 0}
    receipt_raw = ppt.canonical(receipt)
    write_new(out / 'sixth-reserve-receipt.private.json', receipt_raw)
    print(json.dumps({'status': receipt['status'],
                      'revised_plan_sha256': sha(plan_raw),
                      'private_receipt_sha256': sha(receipt_raw),
                      'replacement_tasks': 4,
                      'final_candidate_count': 100,
                      'official_final_admitted': 0}, sort_keys=True))


if __name__ == '__main__':
    main()
