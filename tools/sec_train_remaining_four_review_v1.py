"""Field review for four additional TRAIN-only original SEC 10-K bundles.

Only the frozen raw TRAIN source pool, source allocation and reviewed causal
skill cards are read. Selection/final workbook material is out of scope.
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta
from hashlib import sha256
import json
import math
import os
from pathlib import Path

from lxml import html


GRAPH = {
    'pension_full': 'pension_full_asset_movement_participant_fx',
    'afs': 'afs_fair_value_loss_aging_and_maturity_reconciliation',
}
PENSION = {
    12: {'table': 71, 'column': {2024: 3, 2025: 2},
         'rows': {'opening_assets': 18, 'return': 19,
                  'employer': 20, 'participant': 21,
                  'fx_or_other': 24, 'benefits': 22,
                  'settlements_or_other': 23,
                  'closing_assets': 25, 'obligation': 15,
                  'reported_funded': 26},
         'absent': ('acquisition',),
         'fx_scope': 'Other, including foreign currency adjustment'},
    13: {'table': 76, 'column': {2024: 3, 2025: 2},
         'rows': {'opening_assets': 17, 'acquisition': 18,
                  'return': 19, 'employer': 20, 'participant': 21,
                  'fx_or_other': 22, 'benefits': 23,
                  'settlements_or_other': 24,
                  'closing_assets': 25, 'obligation': 15,
                  'reported_funded': 26},
         'absent': (),
         'fx_scope': 'Foreign exchange rate changes'},
}
PENSION_LABELS = {
    'opening_assets': ('Fair value at beginning of year',
                       'Fair value of plan assets at beginning of year'),
    'acquisition': ('Acquisitions/(divestitures)',),
    'return': ('Actual return on plan assets',),
    'employer': ('Employer contributions/funding', 'Company contributions'),
    'participant': ('Participant contributions',),
    'fx_or_other': ('Other, including foreign currency adjustment',
                    'Foreign exchange rate changes'),
    'benefits': ('Benefit payments',),
    'settlements_or_other': ('Settlement',
                             'Settlements, curtailments, special termination benefits and other'),
    'closing_assets': ('Fair value at end of year',
                       'Fair value of plan assets at end of year'),
    'obligation': ('Obligation at end of year',
                   'Benefit obligation at end of year'),
    'reported_funded': ('Funded status', 'Funded status at end of year'),
}
AFS = {
    18: {'bridge': {2024: (237, 16), 2025: (237, 4)},
         'aging': {2024: (239, 12), 2025: (238, 12)},
         'maturity_table': 241, 'maturity_rows': [4, 5, 6, 7, 8],
         'maturity_total_row': 9,
         'maturity_cost_basis': 'net_of_allowance',
         'bucket_labels': ['Due within one year', 'Years two through five',
                           'Years six through ten', 'After year ten',
                           'No single maturity date']},
    19: {'bridge': {2024: (81, 13), 2025: (80, 13)},
         'aging': {2024: (86, 9), 2025: (85, 9)},
         'maturity_table': 82, 'maturity_rows': [2, 3, 4, 5, 7],
         'maturity_total_row': 8,
         'maturity_cost_basis': 'gross_amortized_cost',
         'bucket_labels': ['Due within one year', 'Years two through five',
                           'Years six through ten', 'After year ten',
                           'No single maturity date']},
}
AFS_FIELDS = (
    'amortized_cost', 'acl_signed', 'unrealized_gains',
    'unrealized_losses_signed', 'fair_value',
    'loss_age_lt_fair', 'loss_age_lt_loss',
    'loss_age_ge_fair', 'loss_age_ge_loss',
    'loss_position_fair', 'loss_position_loss',
)


def _hash(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _need(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def _row(table, index: int, labels: tuple[str, ...]):
    rows = table.xpath('.//tr')
    _need(index < len(rows), 'missing_reviewed_table_row')
    row = rows[index]
    text = ' '.join(' '.join(row.itertext()).split())
    _need(any(text.lower().startswith(label.lower()) for label in labels),
          f'wrong_reviewed_row:{index}')
    return row, text


def _period(tree, context_ref: str) -> dict:
    matches = tree.xpath('//*[name()="xbrli:context" and @id=$cid]',
                         cid=context_ref)
    _need(len(matches) == 1, 'ixbrl_context_not_unique')
    period = matches[0].xpath('.//*[name()="xbrli:period"]')
    _need(len(period) == 1, 'ixbrl_period_not_unique')
    result = {}
    for key in ('instant', 'startdate', 'enddate'):
        values = period[0].xpath(f'.//*[name()="xbrli:{key}"]')
        if values:
            _need(len(values) == 1 and values[0].text,
                  'ixbrl_period_field_not_unique')
            result[key] = values[0].text
    members = _dimensions(tree, context_ref)
    result['dimension_member_count'] = len(members)
    result['dimension_members'] = members
    return result


def _omitted() -> dict:
    return {'value': None, 'presence': 'not_separately_reported',
            'ixbrl_tag': None, 'context_ref': None,
            'context_period': None, 'row_sha256': None,
            'row_index': None, 'column_index': None,
            'row_label': None}


def _signed(item: dict) -> float:
    return 0.0 if item['value'] is None else float(item['value'])


def _companyfacts_match(facts: dict, accession: str, year: int,
                        field: dict) -> bool:
    tag = field['ixbrl_tag']
    if not tag or not tag.startswith('us-gaap:'):
        return False
    concept = facts.get('facts', {}).get('us-gaap', {}).get(tag.split(':', 1)[1])
    if not concept:
        return False
    dollars = concept.get('units', {}).get('USD', [])
    return any(x.get('accn') == accession and x.get('form') == '10-K'
               and x.get('end') == f'{year}-12-31'
               and math.isclose(float(x.get('val', float('nan'))) / 1e6,
                                float(field['value']), abs_tol=1e-6)
               for x in dollars)


def _dimensions(tree, context_ref: str) -> list[dict]:
    """Read lowercase namespace names produced by lxml's HTML parser."""
    matches = tree.xpath('//*[name()="xbrli:context" and @id=$cid]',
                         cid=context_ref)
    _need(len(matches) == 1, 'ixbrl_context_not_unique')
    context = matches[0]
    members = []
    for node in context.xpath('.//*[name()="xbrldi:explicitmember"]'):
        dimension = node.get('dimension')
        member = ' '.join(' '.join(node.itertext()).split())
        _need(dimension and member, 'explicit_dimension_member_incomplete')
        members.append({'kind': 'explicit', 'dimension': dimension,
                        'member': member})
    for node in context.xpath('.//*[name()="xbrldi:typedmember"]'):
        dimension = node.get('dimension')
        member = ' '.join(' '.join(node.itertext()).split())
        _need(dimension and member, 'typed_dimension_member_incomplete')
        members.append({'kind': 'typed', 'dimension': dimension,
                        'member': member})
    return sorted(members, key=lambda row:
                  (row['kind'], row['dimension'], row['member']))


def _ix(tree, table, row_idx: int, col: int, labels: tuple[str, ...],
        *, sign_policy: str = 'source', allow_custom: bool = False) -> dict:
    row, text = _row(table, row_idx, labels)
    nodes = row.xpath('.//*[name()="ix:nonfraction"]')
    _need(col < len(nodes), 'reviewed_ixbrl_column_missing')
    node = nodes[col]
    name = node.get('name') or ''
    _need(node.get('unitref') == 'usd' and
          (node.get('scale') == '6' or node.get('xsi:nil') == 'true') and
          (name.startswith('us-gaap:') or
           (allow_custom and ':' in name)) and
          node.get('contextref'),
          'reviewed_fact_not_usd_millions_ixbrl')
    raw_text = ''.join(node.itertext()).strip()
    if node.get('xsi:nil') == 'true' or not raw_text:
        value, presence = None, 'not_separately_reported'
    elif raw_text in {'—', '–', '-'}:
        value, presence = 0.0, 'disclosed_dash'
    else:
        value = float(raw_text.replace(',', '').replace('$', ''))
        if node.get('sign') == '-':
            value = -value
        if sign_policy == 'outflow':
            value = -abs(value)
        presence = 'reported'
    return {'value': value, 'presence': presence,
            'ixbrl_tag': name,
            'context_ref': node.get('contextref'),
            'context_period': _period(tree, node.get('contextref')),
            'row_sha256': _hash(text.encode()),
            'row_index': row_idx, 'column_index': col,
            'row_label': (labels[0] if text.lower().startswith(labels[0].lower())
                          else labels[-1])}


PENSION_DIMENSIONS = {
    12: [{'kind': 'explicit',
          'dimension': 'us-gaap:RetirementPlanTypeAxis',
          'member': 'us-gaap:ForeignPlanMember'}],
    13: [{'kind': 'explicit',
          'dimension': 'us-gaap:RetirementPlanSponsorLocationAxis',
          'member': 'us-gaap:ForeignPlanMember'},
         {'kind': 'explicit',
          'dimension': 'us-gaap:RetirementPlanTypeAxis',
          'member': 'us-gaap:PensionPlansDefinedBenefitMember'}],
}


def _checked_period(item: dict, *, end: str | None = None,
                    start: str | None = None,
                    instant: str | None = None) -> None:
    period = item.get('context_period')
    _need(isinstance(period, dict), 'missing_original_ixbrl_context')
    if instant is not None:
        _need(period.get('instant') == instant,
              'wrong_instant_period_for_filed_fact')
    else:
        _need(period.get('startdate') == start and
              period.get('enddate') == end,
              'wrong_duration_period_for_filed_fact')


def _pension(source_idx: int, tree, report_end: str) -> list[dict]:
    spec = PENSION[source_idx]
    table = tree.xpath('//table')[spec['table']]
    header = ' '.join(' '.join(table.itertext()).split())[:600]
    _need('2025' in header and '2024' in header and
          'International' in header and 'pension' in header.lower(),
          'international_pension_table_scope_changed')
    periods = []
    for year in (2024, 2025):
        col = spec['column'][year]
        facts = {}
        for key, row in spec['rows'].items():
            facts[key] = _ix(
                tree, table, row, col, PENSION_LABELS[key],
                sign_policy='outflow' if key in
                    ('benefits', 'settlements_or_other') or
                    (key == 'acquisition' and source_idx == 13)
                    else 'source',
                allow_custom=key in ('acquisition', 'settlements_or_other'))
        for key in spec['absent']:
            facts[key] = _omitted()
        end = facts['closing_assets']['context_period']['instant']
        opening_end = facts['opening_assets']['context_period']['instant']
        _need(end.endswith(str(year) + '-12-31') or
              end.startswith(str(year) + '-'),
              'pension_filed_year_changed')
        _need(end == report_end if year == 2025 else end < report_end,
              'current_or_prior_filing_period_changed')
        for key in ('closing_assets', 'obligation', 'reported_funded'):
            _checked_period(facts[key], instant=end)
        _checked_period(facts['opening_assets'], instant=opening_end)
        first = (date.fromisoformat(opening_end) + timedelta(days=1)).isoformat()
        for key in ('acquisition', 'return', 'employer', 'participant',
                    'fx_or_other', 'benefits', 'settlements_or_other'):
            if facts[key]['value'] is not None:
                _checked_period(facts[key], start=first, end=end)
        for item in facts.values():
            if item.get('context_period') is not None:
                _need(item['context_period']['dimension_members'] ==
                      PENSION_DIMENSIONS[source_idx] and
                      item['context_period']['dimension_member_count'] ==
                      len(PENSION_DIMENSIONS[source_idx]),
                      'pension_fact_outside_exact_foreign_plan_scope')
        _need(all(facts[key]['value'] is not None for key in
                  ('opening_assets', 'return', 'employer', 'participant',
                   'fx_or_other', 'benefits', 'settlements_or_other',
                   'closing_assets', 'obligation', 'reported_funded')),
              'full_pension_asset_movement_field_unreported')
        rebuilt = sum(_signed(facts[key]) for key in
                      ('opening_assets', 'acquisition', 'return', 'employer',
                       'participant', 'fx_or_other', 'benefits',
                       'settlements_or_other'))
        _need(math.isclose(rebuilt, facts['closing_assets']['value'],
                           abs_tol=1e-6) and
              math.isclose(facts['closing_assets']['value']
                           - facts['obligation']['value'],
                           facts['reported_funded']['value'], abs_tol=1e-6),
              'pension_full_asset_or_funded_bridge_does_not_reconcile')
        periods.append({'period_end': end, 'period_start': first,
                        'fields': facts})
    _need(periods[0]['fields']['closing_assets']['value'] ==
          periods[1]['fields']['opening_assets']['value'] and
          periods[0]['period_end'] ==
          periods[1]['fields']['opening_assets']['context_period']['instant'],
          'pension_prior_close_not_current_open')
    return periods


def _afs(source_idx: int, tree, report_end: str) -> tuple[list[dict], dict]:
    spec = AFS[source_idx]
    tables = tree.xpath('//table')
    periods = []
    for year in (2024, 2025):
        bridge_table, bridge_row = spec['bridge'][year]
        aging_table, aging_row = spec['aging'][year]
        bridge = tables[bridge_table]
        aging = tables[aging_table]
        bridge_header = ' '.join(' '.join(bridge.itertext()).split())
        aging_header = ' '.join(' '.join(aging.itertext()).split())
        # One original annual report splits these tables across physical
        # pages. The preceding continuation owns the carried year/header.
        if source_idx == 18 and year == 2025:
            bridge_header += ' ' + ' '.join(' '.join(
                tables[235].itertext()).split())
        if source_idx == 18 and year == 2024:
            aging_header += ' ' + ' '.join(' '.join(
                tables[238].itertext()).split())
        _need('Amortized Cost' in bridge_header and
              'Gross Unrealized' in bridge_header and
              'Fair Value' in bridge_header and
              str(year) in bridge_header and
              'Less than 12' in aging_header and
              'Total' in aging_header and str(year) in aging_header,
              'afs_cost_or_loss_aging_table_scope_changed')
        row_labels = ('Total bonds available for sale',) if source_idx == 18 \
            else ('Total',)
        facts = {}
        for col, key in enumerate(AFS_FIELDS[:5]):
            facts[key] = _ix(tree, bridge, bridge_row, col, row_labels,
                             sign_policy='outflow' if key in
                                 ('acl_signed', 'unrealized_losses_signed')
                                 else 'source')
        for col, key in enumerate(AFS_FIELDS[5:]):
            facts[key] = _ix(tree, aging, aging_row, col, row_labels)
        end = facts['fair_value']['context_period']['instant']
        _need(end == f'{year}-12-31' and
              (end == report_end if year == 2025 else True),
              'afs_reported_period_changed')
        for item in facts.values():
            _checked_period(item, instant=end)
            _need(item['value'] is not None,
                  'required_afs_source_fact_unreported')
            _need(item['context_period']['dimension_members'] == [] and
                  item['context_period']['dimension_member_count'] == 0,
                  'afs_aggregate_fact_has_unexpected_dimension')
        fair = (facts['amortized_cost']['value'] +
                facts['acl_signed']['value'] +
                facts['unrealized_gains']['value'] +
                facts['unrealized_losses_signed']['value'])
        aging_fair = (facts['loss_age_lt_fair']['value'] +
                      facts['loss_age_ge_fair']['value'])
        aging_loss = (facts['loss_age_lt_loss']['value'] +
                      facts['loss_age_ge_loss']['value'])
        _need(math.isclose(fair, facts['fair_value']['value'], abs_tol=1e-6)
              and math.isclose(aging_fair,
                               facts['loss_position_fair']['value'], abs_tol=1e-6)
              and math.isclose(aging_loss,
                               facts['loss_position_loss']['value'], abs_tol=1e-6)
              and 0 <= facts['loss_position_loss']['value'] <=
              -facts['unrealized_losses_signed']['value'] + 1e-6,
              'afs_fair_value_or_loss_subset_does_not_reconcile')
        periods.append({'period_end': end, 'fields': facts,
                        'gross_loss_less_aging_scope_difference':
                        -facts['unrealized_losses_signed']['value'] -
                        facts['loss_position_loss']['value']})
    maturity = tables[spec['maturity_table']]
    maturity_text = ' '.join(' '.join(maturity.itertext()).split())
    _need('2025' in maturity_text and
          'Amortized Cost' in maturity_text and
          'Fair Value' in maturity_text,
          'afs_maturity_table_scope_changed')
    bucket = []
    for row, label in zip(spec['maturity_rows'], spec['bucket_labels']):
        actual_label = ('Mortgage-backed' if label ==
                        'No single maturity date' else 'Due')
        cost = _ix(tree, maturity, row, 0, (actual_label,))
        fair = _ix(tree, maturity, row, 1, (actual_label,))
        _checked_period(cost, instant=report_end)
        _checked_period(fair, instant=report_end)
        _need(cost['context_period']['dimension_members'] == [] and
              fair['context_period']['dimension_members'] == [],
              'afs_maturity_bucket_scope_changed')
        bucket.append({'label': label, 'cost': cost, 'fair': fair})
    total_cost = _ix(tree, maturity, spec['maturity_total_row'], 0,
                     ('Total',))
    total_fair = _ix(tree, maturity, spec['maturity_total_row'], 1,
                     ('Total',))
    _checked_period(total_cost, instant=report_end)
    _checked_period(total_fair, instant=report_end)
    _need(total_cost['context_period']['dimension_members'] == [] and
          total_fair['context_period']['dimension_members'] == [],
          'afs_maturity_total_scope_changed')
    expected_cost = (periods[1]['fields']['amortized_cost']['value'] +
                     (periods[1]['fields']['acl_signed']['value'] if
                      spec['maturity_cost_basis'] == 'net_of_allowance' else 0))
    _need(math.isclose(sum(x['cost']['value'] for x in bucket),
                       total_cost['value'], abs_tol=1e-6) and
          math.isclose(sum(x['fair']['value'] for x in bucket),
                       total_fair['value'], abs_tol=1e-6) and
          math.isclose(total_cost['value'], expected_cost, abs_tol=1e-6) and
          math.isclose(total_fair['value'],
                       periods[1]['fields']['fair_value']['value'], abs_tol=1e-6),
          'afs_maturity_bucket_or_allowance_basis_reconciliation_failed')
    return periods, {'period_end': report_end,
                     'cost_basis': spec['maturity_cost_basis'],
                     'buckets': bucket,
                     'filed_total_cost': total_cost,
                     'filed_total_fair': total_fair}


def review(source_pool: Path, source_plan: Path,
           reviewed_cards: Path) -> dict:
    plan_raw = source_plan.read_bytes()
    plan = json.loads(plan_raw)
    _need(plan.get('schema') ==
          'envloop.sec_excel_train_22_raw_source_plan.private.v1' and
          len(plan.get('records', [])) == 22,
          'train_source_plan_shape_changed')
    cards_raw = reviewed_cards.read_bytes()
    cards = json.loads(cards_raw)
    by_graph = {c['final_graph_reservation']: c
                for c in cards.get('cards', [])}
    _need(all(by_graph.get(name, {}).get('independent_skill_review') is True
              and by_graph[name]['minimum_target_edits'] <= 12
              for name in GRAPH.values()),
          'reviewed_skill_card_or_depth_missing')
    cases = []
    issuers = set()
    for idx in (12, 13, 18, 19):
        root = source_pool / f'source-{idx:02}'
        raw_case = (root / 'source-case.private.json').read_bytes()
        source = json.loads(raw_case)
        identity = source['identity']
        profile = 'pension_full' if idx in PENSION else 'afs'
        _need(source.get('source_index') == idx and
              identity == plan['records'][idx] and
              identity['final_graph_reservation'] == GRAPH[profile] and
              identity['skill_signature_sha256'] ==
              by_graph[GRAPH[profile]]['skill_signature_sha256'] and
              source.get('semantic_fact_review_completed') is False and
              source.get('excel_web_admitted') is False and
              identity['issuer_cik'] not in issuers,
              'frozen_train_source_or_graph_identity_changed')
        issuers.add(identity['issuer_cik'])
        for kind, entry in source['response'].items():
            file = {'10k': '10k.html', 'support': 'support.html',
                    'companyfacts': 'companyfacts.json',
                    'index': 'index.html',
                    'submissions': 'submissions.json'}[kind]
            raw = (root / file).read_bytes()
            _need(_hash(raw) == entry['sha256'] and
                  len(raw) == entry['bytes'] and
                  entry['status'] == 200 and
                  entry['url'].startswith(('https://www.sec.gov/',
                                            'https://data.sec.gov/')),
                  'frozen_original_sec_response_changed')
        tree = html.fromstring((root / '10k.html').read_bytes())
        companyfacts = json.loads((root / 'companyfacts.json').read_bytes())
        _need(companyfacts.get('cik') == identity['issuer_cik'],
              'companyfacts_issuer_does_not_match_original_10k')
        if profile == 'pension_full':
            periods = _pension(idx, tree, identity['report_period'])
            maturity = None
        else:
            periods, maturity = _afs(idx, tree, identity['report_period'])
            for period in periods:
                year = int(period['period_end'][:4])
                _need(_companyfacts_match(
                    companyfacts, identity['accession'], year,
                    period['fields']['fair_value']),
                    'same_accession_afs_fair_value_mismatch')
        cases.append({
            'case_index': idx, 'profile': profile,
            'graph': GRAPH[profile],
            'signature_sha256': identity['skill_signature_sha256'],
            'source': {'identity': identity,
                       'original_sec_url': source['urls']['10k'],
                       'source_case_sha256': _hash(raw_case),
                       'raw_sha256': {kind: e['sha256']
                                      for kind, e in source['response'].items()},
                       **({'plan_scope': 'International pension',
                           'fx_scope': PENSION[idx]['fx_scope']}
                          if profile == 'pension_full' else {})},
            'periods': periods,
            **({'maturity': maturity} if maturity else {}),
            'scenario': ({'sponsor_contribution': 80.0,
                          'return_change': -0.012,
                          'fx_shift': -25.0,
                          'obligation_change': 0.008}
                         if profile == 'pension_full' else
                         {'years_two_five_haircut': 0.015,
                          'after_ten_haircut': 0.040,
                          'no_single_date_haircut': 0.025}),
            'review_status':
                'source_field_review_pass; independent_audit_pending',
            'excel_web_admitted': False,
            'official_final_admitted': False,
        })
    return {'schema': 'envloop.sec_excel_train_remaining_four_review.private.v1',
            'scope': 'four TRAIN-only source bundles; no selection/final artifact',
            'reviewer_source_sha256': _hash(Path(__file__).read_bytes()),
            'scope_test_source_sha256': _hash((
                Path(__file__).resolve().parents[1] /
                'tests/test_sec_train_remaining_four_dimensions_v1.py'
            ).read_bytes()),
            'source_plan_sha256': _hash(plan_raw),
            'skill_cards_sha256': _hash(cards_raw),
            'raw_source_root': str(source_pool),
            'cases': cases}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--source-pool', type=Path, required=True)
    ap.add_argument('--source-plan', type=Path, required=True)
    ap.add_argument('--reviewed-cards', type=Path, required=True)
    ap.add_argument('--private-out', type=Path, required=True)
    args = ap.parse_args()
    result = review(args.source_pool, args.source_plan, args.reviewed_cards)
    args.private_out.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(args.private_out.parent, 0o700)
    raw = (json.dumps(result, indent=2, sort_keys=True) + '\n').encode()
    fd = os.open(args.private_out,
                 os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as out:
        out.write(raw)
    print(json.dumps({'status': 'field_review_generated',
                      'train_sources': len(result['cases']),
                      'private_review_sha256': _hash(raw),
                      'independent_audit': 'pending'}))


if __name__ == '__main__':
    main()
