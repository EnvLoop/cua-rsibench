"""Build a two-cohort report only after both audited studies are complete.

The figures and explorer import this module's publication gate. No score is
pooled across cohorts, and a missing/infrastructure-invalid score is never zero.
"""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COHORT_SPECS = (
    {'id': 'original', 'label': 'Original cohort', 'file': 'factory-study.json',
     'models': {'gpt-6-astra', 'gpt-5.6-sol'},
     'interface_note': 'The original cohort added an explicit remaining-turn deadline in round 5. Its early rounds did not expose the same round-1 baseline diagnostics as the extension.',
     'baseline_note': 'The repaired base-student selection execution is the source evidence subsequently reused by the extension.'},
    {'id': 'model6', 'label': 'Sol 6 / Luna 6 extension', 'file': 'model6-study.json',
     'models': {'gpt-6-sol', 'gpt-6-luna'},
     'interface_note': 'The extension starts fresh factory lineages with explicit remaining-turn deadlines and baseline diagnostics from round 1.',
     'baseline_note': 'The selection baseline is explicitly reused from the original cohort; it is not a new execution or independent sample.'},
)
BOUNDARY = ('These are separate cohorts, not a matched four-model ranking. Selection tasks and base-selection evidence are shared, '
            'but final source records and task instances differ. The extension starts with explicit turn deadlines and baseline '
            'diagnostics from round 1. Compare each selected student with its own cohort final baseline; do not pool scores or final trials across cohorts.')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def assert_english(text):
    require(not re.search(r'[\u3400-\u9fff\uf900-\ufaff]', text), 'CJK found in English publication')
    require(not re.search(r'(?:tml-|e2b_|sk-)[A-Za-z0-9_-]{20,}', text), 'possible credential in publication')


def score(value):
    return 'Unscored' if value is None else f'{value * 100:.1f}%'


def valid_number(value):
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1


def validate_final_evaluation(evaluation, expected_count):
    require(evaluation.get('status') in ('scored', 'infrastructure_error'), 'final execution is still incomplete')
    expected = evaluation.get('expected_tasks', [])
    require(len(expected) == expected_count and len(set(expected)) == len(expected), 'final task identities are incomplete')
    rows = evaluation.get('tasks', [])
    names = [row.get('task') for row in rows]
    require(len(names) == len(set(names)) and set(names) <= set(expected), 'duplicate or unexpected final task')
    if evaluation['status'] == 'scored':
        require(set(names) == set(expected), 'scored final execution has missing tasks')
        require(all(type(row.get('score')) in (int, float) and row['score'] in (0, 1) and not row.get('error_type') for row in rows), 'invalid scored task outcome')
        require(valid_number(evaluation.get('score')) and math.isclose(evaluation['score'], sum(row['score'] for row in rows) / len(rows)), 'final mean differs from task outcomes')
    else:
        require(evaluation.get('score') is None, 'infrastructure-invalid final score must be undefined')


def validate_study(data, expected_models):
    require(all(data.get(key) is True for key in ('audit_pass', 'search_finished', 'all_final_executions_finished', 'all_final_recoveries_finished')), 'both cohorts must finish search, final executions, declared recoveries, and audit before publication')
    require(data.get('teacher') == 'gpt-5.6-sol', 'unexpected fixed teacher identity')
    require(data.get('student') == 'Qwen/Qwen3.5-4B', 'unexpected fixed student identity')
    require(data.get('selection_tasks') == 3 and data.get('final_tasks') == 6, 'task counts differ from the declared study design')
    require(data.get('training') == {'profile': 'factory-v1', 'steps': 32, 'batch_size': 2, 'rank': 8,
                                    'learning_rate': 0.0001, 'seed': 23, 'token_cap_per_run': 262144},
            'training configuration differs from the report methods')
    require(data.get('sampling') == {'max_tokens': 512, 'temperature': 0, 'seed': 23}, 'sampling configuration differs from the report methods')
    campaigns = data.get('campaigns', [])
    require({campaign['researcher'] for campaign in campaigns} == set(expected_models) and len(campaigns) == len(expected_models), 'cohort model identifiers do not match the intended study')
    names = [campaign['name'] for campaign in campaigns]
    require(len(names) == len(set(names)) and 'base' not in names, 'ambiguous researcher aliases')
    for campaign in campaigns:
        require(campaign.get('selection_frozen') is True and campaign.get('pending_training') == 0, 'research search is not closed')
        require(bool(campaign.get('attempts')), 'completed cohort has no research attempts')
        require(valid_number(campaign.get('selection_score')), 'missing retained selection score')
        require(campaign.get('training_token_budget') == 1048576 and campaign.get('max_attempts') == 5,
                'campaign limits differ from the report methods')
    comparison = data.get('final_comparison') or {}
    bindings = comparison.get('bindings') or {}
    require(set(bindings) == {'base', *names}, 'final comparison roles do not match researchers')
    repetitions = comparison.get('repetitions')
    require(type(repetitions) is int and repetitions > 0, 'final repetition count is missing')
    executions = data.get('final_executions', [])
    lookup = {run['label']: run for run in executions}
    require(len(lookup) == len(executions), 'duplicate final execution labels')
    planned = [run['label'] for run in comparison.get('executions', [])]
    require(planned and len(planned) == len(set(planned)) and set(planned) <= set(lookup), 'prescribed final executions have not all completed')
    expected_sets = []
    for labels in bindings.values():
        require(len(labels) == repetitions and len(labels) == len(set(labels)), 'comparison binding has missing or repeated repetitions')
        for label in labels:
            require(label in lookup and label in planned, 'comparison binds an absent or unplanned execution')
            run = lookup[label]
            require(run.get('selection_precedes_test') is True, 'final execution lacks selection-before-test evidence')
            validate_final_evaluation(run['evaluation'], data['final_tasks'])
            if 'recovered_evaluation' in run:
                recovered = run['recovered_evaluation']
                recovery = run.get('recovery') or {}
                require(run['evaluation']['status'] == 'infrastructure_error', 'recovery unexpectedly replaces a scored original execution')
                require(recovery.get('new_independent_repetition') is False and recovery.get('retried_tasks'), 'recovery must declare its non-independent, limited retry scope')
                validate_final_evaluation(recovered, data['final_tasks'])
                original_rows = {row['task']: row for row in run['evaluation']['tasks']}
                recovered_rows = {row['task']: row for row in recovered['tasks']}
                require(set(recovered['expected_tasks']) == set(run['evaluation']['expected_tasks']), 'recovery changed the final task set')
                if recovery.get('policy_kind') == 'full_suite_replay':
                    require(recovery.get('original_rows_reused') is False and recovery.get('new_research_seed') is False,
                            'full-suite replay must use fresh rows without adding a research seed')
                    require(recovery.get('logical_comparison_slot') == label and recovery.get('amendment_sha256') and recovery.get('chunk_plan_sha256'),
                            'full-suite replay lacks its frozen comparison and amendment binding')
                    require(set(recovery['retried_tasks']) == set(recovered['expected_tasks']), 'full-suite replay has partial retry scope')
                else:
                    for task, row in original_rows.items():
                        if row.get('score') is not None and not row.get('error_type'):
                            require(task in recovered_rows and recovered_rows[task].get('score') == row['score'] and not recovered_rows[task].get('error_type'), 'recovery altered an originally scored result')
            expected_sets.append(set(run['evaluation']['expected_tasks']))
    require(all(tasks == expected_sets[0] for tasks in expected_sets), 'final task set changes within a cohort')
    assert_english(json.dumps(data, ensure_ascii=False))


def load_publication(source_dir=None):
    """Fail before writing any artifact unless both intended cohorts are complete."""
    source_dir = Path(source_dir or ROOT / 'outputs')
    cohorts = []
    for spec in COHORT_SPECS:
        path = source_dir / spec['file']
        require(path.exists(), f'missing completed cohort evidence: {spec["file"]}')
        raw = path.read_bytes()
        data = json.loads(raw)
        validate_study(data, spec['models'])
        cohorts.append({key: value for key, value in spec.items() if key != 'models'} |
                       {'evidence_sha256': hashlib.sha256(raw).hexdigest(), 'data': data})
    first, second = [cohort['data'] for cohort in cohorts]
    for key in ('student', 'teacher', 'training', 'sampling', 'application', 'interaction'):
        require(first[key] == second[key], f'cohort shared setting differs: {key}')
    for data in (first, second):
        source_ids = data.get('source_record_ids') or {}
        require(set(source_ids) >= {'selection', 'final'}, 'audited source identities are required for cohort comparison')
        require(len(set(source_ids['selection'])) == data['source_records_used']['selection'] and
                len(set(source_ids['final'])) == data['source_records_used']['final'], 'source counts differ from identities')
    require(set(first['source_record_ids']['selection']) == set(second['source_record_ids']['selection']), 'cohorts do not share the declared selection sources')
    require(not set(first['source_record_ids']['final']) & set(second['source_record_ids']['final']), 'cohort final source records overlap')
    package_hashes = [campaign.get('selection_package_hashes') for data in (first, second) for campaign in data['campaigns']]
    require(package_hashes[0] and all(value == package_hashes[0] for value in package_hashes), 'selection packages differ across cohorts')
    reuse = second.get('baseline_reuse') or {}
    require(reuse.get('new_execution') is False and reuse.get('kind') == 'reused_execution_evidence', 'extension baseline reuse is not explicitly audited')
    require((second.get('cohort') or {}).get('prior_lineages_inherited') is False, 'extension lineage boundary is not audited')
    return {'schema': 'factory-publication-v1', 'cohorts': cohorts, 'comparability': BOUNDARY,
            'teacher': first['teacher'], 'student': first['student'], 'pooled_results': False}


def write_bundle(publication, out):
    path = Path(out) / 'combined-study.json'
    path.write_text(json.dumps(publication, indent=2, ensure_ascii=False) + '\n')
    return path


def role_label(data, role):
    if role == 'base':
        return 'Base student'
    campaign = next(campaign for campaign in data['campaigns'] if campaign['name'] == role)
    return 'Student selected by ' + campaign['researcher']


def has_recovery(data):
    labels = {label for labels in data['final_comparison']['bindings'].values() for label in labels}
    return any(run['label'] in labels and 'recovered_evaluation' in run for run in data['final_executions'])


def final_rows(data, recovered=False):
    lookup = {run['label']: run for run in data['final_executions']}
    rows = []
    for role, labels in data['final_comparison']['bindings'].items():
        runs = [dict(lookup[label], evaluation=lookup[label].get('recovered_evaluation', lookup[label]['evaluation']))
                if recovered else lookup[label] for label in labels]
        values = [run['evaluation']['score'] if run['evaluation']['status'] == 'scored' else None for run in runs]
        mean = sum(values) / len(values) if all(value is not None for value in values) else None
        shared = role != 'base' and labels == data['final_comparison']['bindings']['base']
        rows.append({'role': role, 'label': role_label(data, role), 'values': values,
                     'mean': mean, 'shared_base': shared, 'runs': runs})
    return rows


def table(rows):
    return '\n'.join('| ' + ' | '.join(str(cell) for cell in row) + ' |' for row in rows)


def cohort_selection(cohort):
    data = cohort['data']
    rows = [['Researcher model', 'Trained / rounds', 'First / best / last scored', 'Selected', 'Train tokens']]
    text = []
    for campaign in data['campaigns']:
        attempts = campaign['attempts']
        values = [attempt['evaluation']['score'] for attempt in attempts if attempt['evaluation']['status'] == 'scored']
        trained = sum(bool(attempt.get('optimizer_steps')) for attempt in attempts)
        series = ' / '.join(score(value) for value in (values[0], max(values), values[-1])) if values else 'Unscored'
        rows.append([campaign['researcher'], f'{trained} / {len(attempts)}', series, campaign['selected'], f'{campaign["used_training_tokens"]:,}'])
        text.append(f'{campaign["researcher"]} retains {campaign["selected"]} at {score(campaign["selection_score"])} after {len(attempts)} research rounds. '
                    f'{trained} candidates completed training; {len(attempts) - len(values)} rounds have no scored candidate. '
                    'Its scored candidate sequence is ' + (', '.join(score(value) for value in values) if values else 'empty') + '.')
        recovered = sum(bool(attempt.get('original_evaluation')) for attempt in attempts)
        if recovered:
            text.append(f'{campaign["researcher"]} has {recovered} recorded evaluation recovery; the audit retains the original execution separately.')
        historical = sum(attempt.get('accounting') == 'historical import' for attempt in attempts)
        if historical:
            text.append(f'{historical} of its rounds were imported historically because they preceded the pre-execution training reservation guard.')
    return table(rows), '\n\n'.join(text)


def cohort_final(cohort, recovered=False):
    data = cohort['data']
    rows = [['Comparison role', 'Mean by repetition', 'Displayed mean' if recovered else 'Original mean']]
    paragraphs = []
    finals = final_rows(data, recovered=recovered)
    base = next(row for row in finals if row['role'] == 'base')
    for row in finals:
        rows.append([row['label'], ' / '.join(score(value) for value in row['values']), score(row['mean'])])
        if row['role'] == 'base':
            continue
        if row['shared_base']:
            paragraphs.append(row['label'] + ' is the base checkpoint and references the same base executions; it adds no independent samples.')
        elif row['mean'] is None or base['mean'] is None:
            paragraphs.append(row['label'] + ' has no complete comparison with the base because at least one prescribed execution is infrastructure-invalid.')
        else:
            difference = 100 * (row['mean'] - base['mean'])
            direction = f'{abs(difference):.1f} percentage points ' + ('above' if difference > 0 else 'below') if difference else 'equal to'
            replayed = recovered and any('recovered_evaluation' in run for run in row['runs'])
            view = 'operationally recovered' if replayed else 'original'
            paragraphs.append(row['label'] + f' has an {view} final mean of {score(row["mean"])}, {direction} its own cohort base mean of {score(base["mean"])}. '
                              'This is a descriptive comparison over the fixed task instances, not a population estimate.')
            if recovered and not replayed:
                paragraphs.append('These valid original executions are retained in this view without replay.')
    if any(row['mean'] is None for row in finals):
        paragraphs.append('Undefined complete means remain unscored; partial successful executions are not substituted for the prescribed mean.')
    if recovered:
        paragraphs.append('The full-suite operational amendment replays all six tasks for each eligible infrastructure-invalid slot on a separate trusted Linux E2B controller. Each recovered score uses six fresh results; no original rows are mixed into it. Frozen checkpoints, task packages, actor, verifier, and sampling settings are preserved. Valid original slots are never replayed. These are the same prescribed repetitions, not new independent samples or research seeds. The unchanged original outcomes remain in the preceding table and evidence.')
        paragraphs.append('In the original cohort this view combines valid Astra-selected executions orchestrated from the Mac with Linux-orchestrated replays for the base and Sol-selected slots. The controller platform is therefore not matched across those roles. Any numerical difference is descriptive and cannot isolate a training-data effect from operational or observation variation.')
    return table(rows), '\n\n'.join(paragraphs)


def manuscript(publication):
    require(publication.get('schema') == 'factory-publication-v1' and len(publication.get('cohorts', [])) == 2, 'combined publication evidence is required')
    for cohort, spec in zip(publication['cohorts'], COHORT_SPECS):
        require(cohort['id'] == spec['id'], 'cohort order or identity changed')
        validate_study(cohort['data'], spec['models'])
    values = {'COMPARABILITY': BOUNDARY}
    summaries = []
    design = [['Cohort / researcher models', 'Protocol and evidence boundary']]
    sources = [['Cohort', 'Selection / final source IDs used', 'Training supervision IDs used']]
    sections = []
    for index, cohort in enumerate(publication['cohorts']):
        data = cohort['data']
        models = ', '.join(campaign['researcher'] for campaign in data['campaigns'])
        rounds = sum(len(campaign['attempts']) for campaign in data['campaigns'])
        trained = sum(bool(attempt.get('optimizer_steps')) for campaign in data['campaigns'] for attempt in campaign['attempts'])
        tokens = sum(campaign['used_training_tokens'] for campaign in data['campaigns'])
        summaries.append(f'{cohort["label"]} ({models}) completes {rounds} research rounds, {trained} training candidates, and {tokens:,} scheduled training tokens.')
        design.append([cohort['label'] + ': ' + models, cohort['interface_note'] + ' ' +
                       f'{data["final_tasks"]} final variants; {data["final_comparison"]["repetitions"]} same-seed environment repetitions. ' + cohort['baseline_note']])
        used = data['source_records_used']
        sources.append([cohort['label'], f'{used["selection"]} / {used["final"]}', used['training_supervision']])
        selection_table, selection_text = cohort_selection(cohort)
        final_table, final_text = cohort_final(cohort)
        recovery_section = ''
        if has_recovery(data):
            recovery_table, recovery_text = cohort_final(cohort, recovered=True)
            recovery_section = f'''---PAGEBREAK---

### {index + 6}.2. Operational recovery, reported separately

{recovery_table}

**Table {4 + index * 2}R.** Audited recovery view of the same final task/repetition assignments. Original invalid means remain undefined in Table {4 + index * 2}. These are not additional independent repetitions.

![Figure {4 + index * 2}R. Operational recovery in {cohort['label'].lower()}. Each replayed slot uses six fresh task results; valid original slots remain unchanged. The original matrix is retained separately. Original-cohort controller platforms differ across roles.](figures/factory-{cohort['id']}-final-recovered-matrix.png)

{recovery_text}'''
        number = index + 6
        sections.append(f'''## {number}. {cohort['label']}

Researcher models: **{models}**. Fixed teacher: **{data['teacher']}**. Trained student: **{data['student']}**.

{cohort['interface_note']} {cohort['baseline_note']}

{selection_table}

**Table {3 + index * 2}.** Selection and resource use within {cohort['label'].lower()}. Unscored research attempts are not zero-score student evaluations. Checkpoints follow the declared strict-gain/no-regression rule.

![Figure {3 + index * 2}. Selection trajectories for {models}. Crosses mark unscored rounds; the dashed line tracks the retained incumbent. These panels belong only to {cohort['label'].lower()}.](figures/factory-{cohort['id']}-trajectories.png)

{selection_text}

---PAGEBREAK---

### {number}.1. Final evaluation within this cohort

{final_table}

**Table {4 + index * 2}.** Complete means require all prescribed task results. Repetitions use the same sampling seed in fresh environments; shared checkpoint bindings do not create independent evidence.

![Figure {4 + index * 2}. Final outcomes for the base and selected students in {cohort['label'].lower()}. Exact researcher identities label the selected students. Infrastructure-invalid cells are shown as unscored.](figures/factory-{cohort['id']}-final-matrix.png)

{final_text}

Final outcomes are not fed back into research or used to choose a replacement checkpoint. The source records and task instances differ between cohorts; no cross-cohort final ranking is computed.

{recovery_section}

---PAGEBREAK---''')
    values.update(COHORT_SUMMARY=' '.join(summaries), COHORT_DESIGN_TABLE=table(design), SOURCE_TABLE=table(sources), COHORT_RESULTS='\n\n'.join(sections))
    text = (ROOT / 'tools/factory_report_template.md').read_text()
    for key, value in values.items():
        text = text.replace('{{' + key + '}}', value)
    require('{{' not in text, 'unresolved manuscript field')
    assert_english(text)
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, default=ROOT / 'outputs')
    parser.add_argument('--out-dir', type=Path, default=ROOT / 'outputs')
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    publication = load_publication(args.source_dir)
    text = manuscript(publication)
    if args.check_only:
        print('Both cohorts passed publication gates; no artifacts written.')
        return
    for match in re.finditer(r'!\[[^]]*\]\(([^)]+)\)', text):
        require((args.out_dir / match[1]).exists(), 'missing report figure: ' + match[1])
    from build_report import render
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / 'CUA-RSIBench-Technical-Report.md').write_text(text)
    render(text, args.out_dir / 'CUA-RSIBench-Technical-Report.pdf', args.out_dir)
    write_bundle(publication, args.out_dir)


if __name__ == '__main__':
    main()
