import argparse
import json
import hashlib
from pathlib import Path
from itertools import combinations, zip_longest
from collections import Counter

ROOT = Path('/workspace')
INPUTS = Path('/inputs')

def load(name):
    return json.loads((INPUTS / name).read_text())

def episode(row):
    return row['record_id'].split(':')[0]

def step(row):
    return int(row['record_id'].split(':')[1])

def generate():
    source = load('sources.json')
    tagged = sorted([r for r in source['records'] if r['state'] == 'open' and 'triage needed' in r['labels']], key=lambda r: (r['updated_at'], r['number']))
    oldest, middle, newer, newest = [r['number'] for r in (tagged[0], tagged[1], tagged[-2], tagged[-1])]
    workflow = 'Read the RUNBOOK and inspect candidate source descriptions before selecting. Source state and timestamps are immutable source metadata. For each selected reference set assignee, priority and complexity, save, and visibly verify all three fields. Track remaining selected references and continue until all are verified. Keep local task status, project and column unchanged. Preserve unrelated tasks and the archive.'
    tasks = [
        {'id': 'rank-recent-pair-v6', 'source_numbers': [newer, oldest, newest], 'mode': 'rank', 'where': {'all': [{'field': 'state', 'op': 'eq', 'value': 'open'}, {'field': 'labels', 'op': 'contains', 'value': 'triage needed'}]}, 'order_by': [{'field': 'updated_at', 'direction': 'desc'}], 'limit': 2, 'changes': {'owner': 'Chen', 'priority': 3, 'score': 5}, 'notes': workflow},
        {'id': 'allocation-prerequisite-pair-v6', 'source_numbers': [middle, newest, oldest], 'mode': 'allocation', 'cost_limit': 8, 'hour_limit': 5, 'planning': [
            {'number': middle, 'cost': 8, 'hours': 5, 'value': 13},
            {'number': newest, 'cost': 5, 'hours': 3, 'value': 10, 'requires': oldest},
            {'number': oldest, 'cost': 3, 'hours': 2, 'value': 8}
        ], 'changes': {'owner': 'Singh', 'priority': 2, 'score': 8}, 'notes': workflow + ' Costs, hours, values and dependencies are synthetic planning inputs. Compare feasible sets under both budgets and include prerequisites.'}
    ]
    approved = {r['number'] for r in source['records']}
    for task in tasks:
        assert set(task['source_numbers']) <= approved
        assert len(task['source_numbers']) == len(set(task['source_numbers']))
    allocation = tasks[1]
    feasible = []
    for count in range(4):
        for subset in combinations(allocation['planning'], count):
            refs = {p['number'] for p in subset}
            cost = sum(p['cost'] for p in subset)
            hours = sum(p['hours'] for p in subset)
            if cost <= allocation['cost_limit'] and hours <= allocation['hour_limit'] and all(p.get('requires') is None or p['requires'] in refs for p in subset):
                feasible.append((-sum(p['value'] for p in subset), cost, sorted(refs)))
    optimum = min(feasible)
    assert optimum[2] == sorted([oldest, newest])
    (ROOT / 'tasks.json').write_text(json.dumps(tasks, indent=2) + '\n')
    baseline = sorted({episode(r) for r in load('examples.json')})
    (ROOT / 'baseline_episodes.json').write_text(json.dumps(baseline))
    print(json.dumps({'tasks': tasks, 'local_checks': {'rank': [newest, newer], 'allocation': optimum}, 'baseline_episodes': baseline}))

def inspect():
    rows = load('examples.json')
    baseline = set(json.loads((ROOT / 'baseline_episodes.json').read_text()))
    print('SCHEMA', list(rows[0]))
    print('METADATA', json.dumps({k: v for k, v in rows[0].items() if k != 'messages'})[:2500])
    print('MESSAGE_SHAPE', [(m['role'], len(json.dumps(m['content']))) for m in rows[0]['messages']])
    for ep in sorted({episode(r) for r in rows}):
        ds = sorted([r for r in rows if episode(r) == ep and r['representation'] == 'decision'], key=step)
        print('EPISODE', ep, 'decisions', len(ds), 'case', ds[0].get('case_sha256'))
        if ep not in baseline:
            for r in ds:
                print(r['record_id'], r['messages'][-1]['content'])

def emit():
    rows = load('examples.json')
    baseline = set(json.loads((ROOT / 'baseline_episodes.json').read_text()))
    fresh = ['episode-07', 'episode-08']
    assert set(fresh).isdisjoint(baseline)
    assert set(fresh) <= {episode(r) for r in rows}, 'Missing verified episodes'
    groups = []
    for ep in ['episode-00'] + fresh:
        group = sorted([r for r in rows if episode(r) == ep and r['representation'] == 'decision'], key=step)
        expected = 11 if ep == 'episode-00' else 25
        assert len(group) == expected, (ep, len(group))
        assert [step(r) for r in group] == list(range(expected))
        actions = [json.loads(r['messages'][-1]['content'])['action']['type'] for r in group]
        assert actions[-1] == 'done' and actions.count('done') == 1
        assert actions.count('select') == (2 if ep == 'episode-00' else 4)
        assert actions.count('fill') == (1 if ep == 'episode-00' else 2)
        groups.append(group)
    # Preserve every direct decision and complete new episodes when coverage permits.
    # If necessary remove redundant early navigation, retaining selection and all edits.
    while sum(map(len, groups)) > 64:
        candidates = [(len(g), i) for i, g in enumerate(groups) if i > 0 and len(g) > 4 and step(g[0]) < 3]
        assert candidates, 'Inspect before more aggressive filtering'
        _, i = max(candidates)
        groups[i].pop(0)
    selected = [r for batch in zip_longest(*groups) for r in batch if r is not None]
    assert len({r['record_id'] for r in selected}) == len(selected)
    canonical = {r['record_id']: r for r in rows}
    assert all(r == canonical[r['record_id']] for r in selected)
    history = load('historical-submissions.json')
    ids = [r['record_id'] for r in selected]
    assert all(ids != h['record_ids'] for h in history)
    text = ''.join(json.dumps(r, ensure_ascii=False, separators=(',', ':')) + '\n' for r in selected)
    assert len(text.encode()) <= 2 * 1024 * 1024
    output = ROOT / 'train_messages.jsonl'
    output.write_text(text)
    report = {'records': len(selected), 'bytes': len(text.encode()), 'episodes': dict(Counter(episode(r) for r in selected)), 'representation': 'decision', 'sha256': hashlib.sha256(text.encode()).hexdigest(), 'historical_overlap': [{'factory': h['factory'], 'retained': len(set(ids) & set(h['record_ids'])), 'prior_records': len(h['record_ids'])} for h in history], 'record_ids': ids}
    (ROOT / 'mixture_report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['generate', 'inspect', 'emit'])
    args = parser.parse_args()
    {'generate': generate, 'inspect': inspect, 'emit': emit}[args.command]()
