"""Prepare a separate Sol 6/Luna 6 cohort locally; never invoke paid services."""
import argparse
import copy
import datetime
import hashlib
import itertools
import json
from pathlib import Path
import re
import shutil

from cursibench.factory_campaign import CampaignRegistry, digest as protocol_digest
from cursibench.factory_cases import SourceRegistry, compile_case, digest
from cursibench.factory_export import export_case
from cursibench.factory_results import summarize


ROOT = Path(__file__).resolve().parents[1]
MODELS = {'sol6': 'gpt-6-sol', 'luna6': 'gpt-6-luna'}
TEACHER = 'gpt-5.6-sol'
SELECTION = ['selection-direct-01', 'selection-rank-01', 'selection-allocation-01']


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def tree_hashes(root):
    root = Path(root)
    result = {}
    for path in sorted(root.rglob('*')):
        require(not path.is_symlink(), 'input tree contains a symlink')
        if path.is_file():
            result[path.relative_to(root).as_posix()] = sha(path)
    require(bool(result), 'empty evidence/package tree')
    return result


def case_from_package(path):
    case = read(path / 'environment/scenario.json')
    case['targets'] = read(path / 'tests/targets.json')
    require(digest(case) == read(path / 'contract.json')['case_sha256'], 'task package case hash mismatch')
    return case


def planning_profile(spec):
    """Check the alternatives exhaustively, independently of the task compiler."""
    entries = spec['planning']
    feasible = []
    for flags in itertools.product((False, True), repeat=len(entries)):
        chosen = [row for row, yes in zip(entries, flags) if yes]
        ids = {row['number'] for row in chosen}
        if any(row.get('blocked') or (row.get('requires') is not None and row['requires'] not in ids) for row in chosen):
            continue
        groups = [row['exclusive_group'] for row in chosen if row.get('exclusive_group', 'none') != 'none']
        if len(groups) != len(set(groups)):
            continue
        cost = sum(row['cost'] for row in chosen)
        hours = sum(row['hours'] for row in chosen)
        if cost <= spec['cost_limit'] and hours <= spec['hour_limit']:
            feasible.append({'numbers': sorted(ids), 'cost': cost, 'hours': hours,
                             'value': sum(row['value'] for row in chosen)})
    best_value = max(row['value'] for row in feasible)
    rivals = [row for row in feasible if row['value'] == best_value]
    require(len(rivals) == 2 and {len(row['numbers']) for row in rivals} == {1, 2}, 'allocation lost its one-item versus dependent-pair alternatives')
    require(len({row['cost'] for row in rivals}) == 2, 'allocation lacks the declared minimum-cost tie-break')
    winner = min(rivals, key=lambda row: (row['cost'], row['numbers']))
    require(any(row.get('requires') for row in entries), 'allocation dependency is missing')
    require(any(row.get('blocked') and row['value'] > best_value for row in entries), 'allocation lacks its tempting blocked distractor')
    return {'feasible_set_count': len(feasible), 'maximum_value': best_value,
            'maximum_value_alternative_count': len(rivals), 'winning_cost': winner['cost'],
            'winning_target_count': len(winner['numbers']), 'winner_numbers': winner['numbers']}


def original_planning_spec(case):
    policy = json.loads(case['tasks'][0]['description'].split('```json\n', 1)[1].rsplit('\n```', 1)[0])['policy']
    bounds = re.search(r'total cost <= (\d+) and hours <= (\d+)', policy)
    require(bounds is not None, 'original planning bounds cannot be verified')
    planning = []
    for task in case['tasks'][1:]:
        encoded = task['description'].split('SYNTHETIC PLANNING INPUTS\n\n', 1)[1]
        entry = json.loads(encoded.split('```json\n', 1)[1].rsplit('\n```', 1)[0])
        row = {'number': int(entry['id'][3:]), 'cost': entry['cost'], 'hours': entry['hours'],
               'value': entry['value'], 'blocked': entry['blocked'] == 'yes', 'exclusive_group': entry['exclusive_group']}
        if entry['requires'] != 'none':
            row['requires'] = int(entry['requires'][3:])
        planning.append(row)
    return {'cost_limit': int(bounds[1]), 'hour_limit': int(bounds[2]), 'planning': planning}


def final_recipes(ids):
    direct = {'id': 'model6-final-direct-a', 'mode': 'direct', 'source_numbers': [ids[3], ids[0]],
              'select_numbers': [ids[0]], 'changes': {'owner': 'Chen', 'priority': 2, 'score': 5}}
    other = copy.deepcopy(direct)
    other.update(id='model6-final-direct-b', source_numbers=list(reversed(direct['source_numbers'])),
                 changes={'owner': 'Singh', 'priority': 3, 'score': 8})
    cases = [direct, other]
    rank = {'id': 'model6-final-rank-a', 'mode': 'rank', 'source_numbers': [ids[3], ids[2], ids[0], ids[1]],
            'where': {'field': 'state', 'op': 'eq', 'value': 'open'},
            'order_by': [{'field': 'updated_at', 'direction': 'asc'}], 'limit': 2,
            'changes': {'owner': 'Rivera', 'priority': 3, 'score': 8}}
    other = copy.deepcopy(rank)
    other.update(id='model6-final-rank-b', source_numbers=list(reversed(rank['source_numbers'])),
                 order_by=[{'field': 'updated_at', 'direction': 'desc'}],
                 changes={'owner': 'Chen', 'priority': 1, 'score': 3})
    cases.extend([rank, other])
    allocation = {'id': 'model6-final-allocation-a', 'mode': 'allocation', 'source_numbers': ids,
                  'cost_limit': 9, 'hour_limit': 4, 'changes': {'owner': 'Singh', 'priority': 1, 'score': 3},
                  'planning': [{'number': ids[0], 'cost': 3, 'hours': 2, 'value': 8},
                               {'number': ids[1], 'cost': 5, 'hours': 2, 'value': 9, 'requires': ids[0]},
                               {'number': ids[2], 'cost': 9, 'hours': 4, 'value': 17},
                               {'number': ids[3], 'cost': 3, 'hours': 1, 'value': 30, 'blocked': True}]}
    other = copy.deepcopy(allocation)
    other.update(id='model6-final-allocation-b', source_numbers=list(reversed(ids)),
                 changes={'owner': 'Rivera', 'priority': 2, 'score': 5})
    other['planning'][2]['cost'] = 7
    return cases + [allocation, other]


def inspect_original(original):
    manifest = read(original / 'manifest.json')
    original_seal = read(original / 'sealed-final/manifest.json')
    for alias in ('astra', 'sol'):
        state = read(original / f'{alias}-campaign.json')
        require(protocol_digest(state['protocol']) == state['protocol_hash'], 'original protocol hash mismatch')
        require(state['protocol']['selection_manifest_sha256'] == sha(original / 'manifest.json'), 'original selection manifest changed')
        require(state['protocol']['final_manifest_sha256'] == digest(original_seal), 'original final manifest changed')
    require(sorted(path.name for path in (original / 'selection').iterdir()) == sorted(SELECTION), 'original selection identities changed')
    by_id = {entry['id']: entry for entry in manifest['cases']}
    for task in SELECTION:
        case = case_from_package(original / 'selection' / task)
        require(by_id[case['id']]['hash'] == digest(case), 'selection package differs from its frozen manifest')
    used = set()
    for row in original_seal['cases']:
        case = case_from_package(original / 'sealed-final' / row['chunk'] / row['task'])
        require(digest(case) == row['case_sha256'], 'original final package differs from its seal')
        used.update(case['source_numbers'])
    base = original / 'cache-repair/base'
    summary = summarize(base, SELECTION)
    require(summary['status'] == 'scored', 'complete matched baseline is required')
    result = read(base / 'result.json')
    expected = {'inference_kind': 'base', 'training_model': manifest['student'],
                'training_checkpoint': manifest['student'], 'environment': 'journal',
                'factory_contract': True, 'task_count': 3, 'proxy_request_capacity': 270,
                'proxy_destroyed': True, 'proxy_ready': True, 'harbor_exit': 0}
    require(all(result.get(key) == value for key, value in expected.items()), 'baseline runtime is not the matched repaired base execution')
    for alias in ('astra', 'sol'):
        require(read(original / f'{alias}-campaign.json')['baseline'] == summary, 'baseline summary does not match original campaign evidence')
    return manifest, original_seal, used, summary


def prepare(original, destination, check_only=False):
    original, destination = Path(original).resolve(), Path(destination).resolve()
    require(not destination.exists(), 'destination already exists; refuse to overwrite a study')
    require(ROOT in original.parents and ROOT in destination.parents, 'study paths must stay inside this checkout')
    require(original != destination and original not in destination.parents, 'extension must be separate from the original study')
    manifest, original_seal, used, baseline = inspect_original(original)
    snapshot = read(ROOT / 'datasets/public/kanboard_issues.json')
    final_rows = snapshot['records'][24:36]
    available = [row for row in final_rows if row['number'] not in used]
    opened = sorted((row for row in available if row['state'] == 'open'), key=lambda row: row['number'])
    closed = sorted((row for row in available if row['state'] == 'closed'), key=lambda row: row['number'])
    require(len(opened) >= 3 and len(closed) >= 1, 'unused final pool cannot support the original nontrivial task structure; no study prepared')
    ids = [row['number'] for row in opened[:3]] + [closed[0]['number']]
    require(len({row['updated_at'] for row in opened[:3]}) == 3, 'fresh ranking cases lack three distinct dates')
    registry = SourceRegistry(snapshot, ids, [row['number'] for row in snapshot['records'] if row['number'] not in ids], partition='final')
    recipes = final_recipes(ids)
    compiled = [compile_case(spec, registry) for spec in recipes]
    require([len(case['targets']) for case in compiled] == [1, 1, 2, 2, 2, 1], 'final target counts differ from the original difficulty profile')
    require(set(compiled[2]['targets']) != set(compiled[3]['targets']), 'rank-direction variation selects the same targets')
    planning = {}
    for spec, case in zip(recipes[4:], compiled[4:]):
        profile = planning_profile(spec)
        require(set(case['targets']) == {f'GH-{n}' for n in profile['winner_numbers']}, 'independent allocation enumeration disagrees with compiler')
        planning[spec['id']] = profile
    for suffix, spec in zip(('a', 'b'), recipes[4:]):
        old = next(row for row in original_seal['cases'] if row['task'] == f'final-allocation-{suffix}')
        old_case = case_from_package(original / 'sealed-final' / old['chunk'] / old['task'])
        old_profile = planning_profile(original_planning_spec(old_case))
        new_profile = planning[spec['id']]
        require({key: value for key, value in old_profile.items() if key != 'winner_numbers'} ==
                {key: value for key, value in new_profile.items() if key != 'winner_numbers'},
                'fresh allocation difficulty profile differs from the original sealed task')
    selection_hashes = tree_hashes(original / 'selection')
    baseline_hashes = tree_hashes(original / 'cache-repair/base')
    if check_only:
        return {'status': 'ready_to_prepare', 'researchers': MODELS, 'teacher': TEACHER,
                'unused_final_open_records': len(opened), 'unused_final_closed_records': len(closed),
                'final_source_overlap_with_original_instances': False,
                'target_counts': [len(case['targets']) for case in compiled], 'provider_calls': 0}
    destination.mkdir(parents=True, exist_ok=False)
    (destination / 'factories').mkdir()
    shutil.copytree(original / 'selection', destination / 'selection')
    shutil.copytree(original / 'cache-repair/base', destination / 'baseline')
    require(tree_hashes(destination / 'selection') == selection_hashes, 'selection copy is not byte-identical')
    require(tree_hashes(destination / 'baseline') == baseline_hashes, 'baseline copy is not byte-identical')
    require(summarize(destination / 'baseline', SELECTION) == baseline, 'copied baseline summary changed')
    created = datetime.datetime.now(datetime.timezone.utc).isoformat()
    provenance = {'kind': 'reused_execution_evidence', 'new_execution': False,
                  'source_study': original.relative_to(ROOT).as_posix(), 'source_baseline': 'cache-repair/base',
                  'source_manifest_sha256': sha(original / 'manifest.json'),
                  'selection_file_hashes': selection_hashes, 'baseline_file_hashes': baseline_hashes,
                  'baseline_summary_sha256': digest(baseline),
                  'boundary': 'The original repaired baseline execution is shared evidence, not an additional execution or independent sample.'}
    write(destination / 'reuse-provenance.json', provenance)
    seal_dir = destination / 'sealed-final'
    seal_dir.mkdir()
    entries = []
    for index, (spec, case) in enumerate(zip(recipes, compiled)):
        chunk = f'chunk-{index // 3}'
        export_case(case, seal_dir / chunk / spec['id'], archive=str(ROOT / 'work/kanboard-1.2.54.tar.gz'))
        entries.append({'task': spec['id'], 'chunk': chunk, 'case_sha256': digest(case),
                        'target_count': len(case['targets'])})
    seal = {'created_at': created, 'purpose': 'sealed final evaluation only; never researcher feedback',
            'cases': entries, 'source_ids': ids, 'permitted_final_pool_ids': [row['number'] for row in final_rows],
            'original_final_instance_source_ids': sorted(used), 'overlap_with_original_final_instances': [],
            'original_final_manifest_sha256': digest(original_seal), 'planning_difficulty': planning,
            'claim_boundary': 'Separate late-addition cohort with four fresh final source IDs shared across six cases. Same application and task templates; no unseen-template or population ranking claim.'}
    write(seal_dir / 'manifest.json', seal)
    new_manifest = {key: copy.deepcopy(manifest[key]) for key in ('student', 'training', 'sampling', 'evaluation', 'cases')}
    new_manifest.update(created_at=created, purpose='separate late-addition Sol 6/Luna 6 executable data-research cohort',
                        cohort='model6-extension', researchers=MODELS, teacher=TEACHER, data_hashes={},
                        engine_hashes={name: sha(ROOT / 'src/cursibench' / name) for name in manifest['engine_hashes']},
                        factory_directory='factories', baseline_directory='baseline',
                        baseline_reuse_manifest_sha256=sha(destination / 'reuse-provenance.json'),
                        final_source_ids_not_evaluated=ids,
                        generation={'logical_turns': 20, 'charged_calls_with_retries': 40, 'program_runs': 12,
                                    'new_teacher_rollouts': 3, 'teacher_calls': 100, 'teacher_steps_per_rollout': 60},
                        final_repetitions=2, prior_lineages_inherited=False,
                        preparation_script_sha256=sha(Path(__file__)))
    write(destination / 'manifest.json', new_manifest)
    common = {'selection_tasks': SELECTION, 'final_tasks': [row['task'] for row in entries],
              'selection_manifest_sha256': sha(destination / 'manifest.json'), 'final_manifest_sha256': digest(seal),
              'max_attempts': 5, 'training_token_budget': 1048576, 'promotion': 'no_regression',
              'early_stop': 'all selection tasks solved or budget exhausted', 'training_steps': 32,
              'training_profile': 'factory-v1', 'baseline_directory': 'baseline', 'factory_directory': 'factories',
              'round1_layout': 'round-1', 'researchers': MODELS, 'teacher': TEACHER,
              'baseline_evidence_reused': True, 'reuse_manifest_sha256': sha(destination / 'reuse-provenance.json')}
    for alias, model in MODELS.items():
        protocol = dict(common, researcher_alias=alias, researcher_model=model)
        campaign = CampaignRegistry(destination / f'{alias}-campaign.json', protocol)
        campaign.set_baseline(baseline)
        state = campaign.snapshot()
        require(not state['attempts'] and not state['reservations'] and state['used_training_tokens'] == 0,
                'new campaign is not empty')
        require(state['final_selection'] is None and state['final_results'] == [], 'new campaign contains final results')
    require(not list((destination / 'factories').iterdir()), 'new factory lineages are not empty')
    return {'status': 'prepared', 'study': destination.relative_to(ROOT).as_posix(), 'researchers': MODELS,
            'teacher': TEACHER, 'selection_packages_byte_identical': True, 'baseline_evidence_reused': True,
            'final_cases': 6, 'fresh_final_source_records': 4, 'training_tokens_used': 0, 'provider_calls': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original', default=str(ROOT / 'work/factory-study-02'))
    parser.add_argument('--out', default=str(ROOT / 'work/factory-model6-extension'))
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    print(json.dumps(prepare(args.original, args.out, args.check_only), indent=2))
