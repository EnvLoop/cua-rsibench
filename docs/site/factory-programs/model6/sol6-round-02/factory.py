import json
from collections import Counter
from pathlib import Path

ROOT = Path('/workspace')
sources = json.loads(Path('/inputs/sources.json').read_text())['records']
by_number = {r['number']: r for r in sources}
assert {5869, 5871, 5894, 5895} <= by_number.keys()

recipes = [
    {'id': 'ldap-notification-edit', 'source_numbers': [5869, 5895], 'mode': 'direct',
     'select_numbers': [5869], 'changes': {'owner': 'Chen', 'priority': 2, 'score': 5}},
    {'id': 'open-triage-recent', 'source_numbers': [5869, 5871, 5894, 5895], 'mode': 'rank',
     'where': {'all': [{'field': 'state', 'op': 'eq', 'value': 'open'},
                       {'field': 'labels', 'op': 'contains', 'value': 'triage needed'}]},
     'order_by': [{'field': 'updated_at', 'direction': 'desc'}], 'limit': 1,
     'changes': {'owner': 'Rivera', 'priority': 1, 'score': 8}},
    {'id': 'planning-choice-revised', 'source_numbers': [5869, 5895], 'mode': 'allocation',
     'cost_limit': 7, 'hour_limit': 3,
     'planning': [{'number': 5869, 'cost': 5, 'hours': 2, 'value': 12},
                  {'number': 5895, 'cost': 6, 'hours': 3, 'value': 8}],
     'changes': {'owner': 'Singh', 'priority': 2, 'score': 6}},
]
ROOT.joinpath('tasks.json').write_text(json.dumps(recipes, indent=2) + '\n')

approved = json.loads(Path('/inputs/examples.json').read_text())
by_episode = {}
for record in approved:
    episode, step, variant = record['record_id'].split(':')
    by_episode.setdefault(episode, {}).setdefault(int(step), {})[variant] = record
for episode, steps in sorted(by_episode.items()):
    print(episode, 'steps', len(steps), 'sources', steps[0]['decision']['source_numbers'])

selected = []
for episode, steps in sorted(by_episode.items()):
    for step, variants in sorted(steps.items()):
        decision = variants['decision']
        selected.append(decision)
        action = json.loads(decision['messages'][-1]['content'])['action']
        if action['type'] in ('fill', 'select', 'done') and 'history' in variants and len(variants['history']['messages']) <= 16:
            selected.append(variants['history'])
assert len({r['episode_sha256'] for r in selected}) >= 2
assert len({r['record_id'] for r in selected}) == len(selected)
out = ROOT / 'train_messages.jsonl'
with out.open('w') as stream:
    for record in selected:
        stream.write(json.dumps(record, ensure_ascii=False) + '\n')
print('selected', len(selected), 'bytes', out.stat().st_size, 'representations', dict(Counter(r['representation'] for r in selected)))
