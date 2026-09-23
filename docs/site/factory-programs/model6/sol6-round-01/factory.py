import json
from pathlib import Path

ROOT = Path('/workspace')
records = json.loads(Path('/inputs/sources.json').read_text())['records']
by_number = {r['number']: r for r in records}
assert {5869, 5871, 5894, 5895} <= by_number.keys()

recipes = [
    {
        'id': 'ldap-notification-edit',
        'source_numbers': [5869, 5895],
        'mode': 'direct',
        'select_numbers': [5869],
        'changes': {'owner': 'Chen', 'priority': 2, 'score': 5},
    },
    {
        'id': 'open-triage-recent',
        'source_numbers': [5869, 5871, 5894, 5895],
        'mode': 'rank',
        'where': {'all': [
            {'field': 'state', 'op': 'eq', 'value': 'open'},
            {'field': 'labels', 'op': 'contains', 'value': 'triage needed'},
        ]},
        'order_by': [{'field': 'updated_at', 'direction': 'desc'}],
        'limit': 1,
        'changes': {'owner': 'Rivera', 'priority': 1, 'score': 8},
    },
]
ROOT.joinpath('tasks.json').write_text(json.dumps(recipes, indent=2) + '\n')

approved = json.loads(Path('/inputs/examples.json').read_text())
selected = []
for episode in ('episode-00', 'episode-01'):
    decisions = [r for r in approved if r['record_id'].startswith(episode + ':') and r['representation'] == 'decision']
    decisions.sort(key=lambda r: int(r['record_id'].split(':')[1]))
    selected.extend(decisions)
    print(episode, 'decision records:', len(decisions))
assert len(selected) >= 2
assert len({r['episode_sha256'] for r in selected}) == 2
assert len({r['record_id'] for r in selected}) == len(selected)
out = ROOT / 'train_messages.jsonl'
with out.open('w') as stream:
    for record in selected:
        stream.write(json.dumps(record, ensure_ascii=False) + '\n')
print('Wrote', len(selected), 'approved records; bytes:', out.stat().st_size)
