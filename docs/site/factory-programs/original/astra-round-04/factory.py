import argparse
import json
import hashlib
from pathlib import Path
from itertools import combinations
from collections import Counter

ROOT = Path('/workspace')
INPUTS = Path('/inputs')

def generate():
    source = json.loads((INPUTS / 'sources.json').read_text())
    records = source['records']
    tagged = sorted((r for r in records if r['state'] == 'open' and 'triage needed' in r['labels']), key=lambda r: (r['updated_at'], r['number']))
    oldest, middle, newer, newest = [r['number'] for r in (tagged[0], tagged[1], tagged[-2], tagged[-1])]
    workflow = 'Keep every local task status unchanged: do not close, archive, move, or delete any task. Only owner, priority and complexity may change. Inspect the RUNBOOK and candidate descriptions. Determine the selected references before editing. Keep completed and remaining references in working memory. For every selected task set owner, priority and complexity, save, and visibly verify all three fields. Finish only after every selected task is verified. Saved tasks must remain open in their original project and column. Preserve unrelated tasks and the archive. Source state and timestamps are immutable source metadata, distinct from local task status.'
    tasks = [
        {'id': 'fresh-rank-newest-two-v5', 'source_numbers': [middle, newest, newer], 'mode': 'rank', 'where': {'all': [{'field': 'state', 'op': 'eq', 'value': 'open'}, {'field': 'labels', 'op': 'contains', 'value': 'triage needed'}]}, 'order_by': [{'field': 'updated_at', 'direction': 'desc'}], 'limit': 2, 'changes': {'owner': 'Singh', 'priority': 2, 'score': 3}, 'notes': workflow},
        {'id': 'fresh-allocation-dependent-two-v5', 'source_numbers': [newer, oldest, newest], 'mode': 'allocation', 'cost_limit': 7, 'hour_limit': 5, 'planning': [
            {'number': newer, 'cost': 7, 'hours': 5, 'value': 12},
            {'number': oldest, 'cost': 3, 'hours': 2, 'value': 7},
            {'number': newest, 'cost': 4, 'hours': 3, 'value': 9, 'requires': oldest}
        ], 'changes': {'owner': 'Rivera', 'priority': 1, 'score': 5}, 'notes': workflow + ' Planning values, costs, hours and dependencies are synthetic inputs. Compare feasible sets under both budgets, including required dependencies.'},
        {'id': 'fresh-direct-single-v5', 'source_numbers': [newest, oldest], 'mode': 'direct', 'select_numbers': [oldest], 'changes': {'owner': 'Chen', 'priority': 3, 'score': 8}, 'notes': workflow}
    ]
    approved_numbers = {r['number'] for r in records}
    for task in tasks:
        assert len(set(task['source_numbers'])) == len(task['source_numbers'])
        assert set(task['source_numbers']) <= approved_numbers
    allocation = tasks[1]
    feasible = []
    for count in range(4):
        for subset in combinations(allocation['planning'], count):
            numbers = {e['number'] for e in subset}
            cost, hours = sum(e['cost'] for e in subset), sum(e['hours'] for e in subset)
            if cost <= allocation['cost_limit'] and hours <= allocation['hour_limit'] and all(e.get('requires') is None or e['requires'] in numbers for e in subset):
                feasible.append((-sum(e['value'] for e in subset), cost, sorted(numbers)))
    optimum = min(feasible)
    assert len(optimum[2]) == 2
    (ROOT / 'tasks.json').write_text(json.dumps(tasks, indent=2) + '\n')
    print(json.dumps({'task_ids': [t['id'] for t in tasks], 'source_numbers': [t['source_numbers'] for t in tasks], 'local_rank_check': [newest, newer], 'local_allocation_check': optimum, 'source_snapshot': source['snapshot_sha256']}))

def inspect():
    rows = json.loads((INPUTS / 'examples.json').read_text())
    episodes = sorted({r['record_id'].split(':')[0] for r in rows})
    for ep in episodes:
        ds = [r for r in rows if r['record_id'].startswith(ep + ':') and r['representation'] == 'decision']
        print(ep, 'decisions', len(ds), 'case', ds[0]['case_sha256'])
        if ep not in ('episode-00', 'episode-01', 'episode-02', 'episode-03', 'episode-04'):
            for r in ds:
                output = json.loads(r['messages'][-1]['content'])
                print(r['record_id'], json.dumps(output['action']), output.get('memory', ''))
    history = json.loads((INPUTS / 'historical-submissions.json').read_text())
    print('HISTORICAL', json.dumps(history))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['generate', 'inspect'], default='generate', nargs='?')
    args = parser.parse_args()
    {'generate': generate, 'inspect': inspect}[args.command]()
