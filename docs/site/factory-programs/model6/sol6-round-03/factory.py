import json
from collections import Counter, defaultdict
from pathlib import Path

root = Path('/workspace')
sources = json.loads(Path('/inputs/sources.json').read_text())['records']
known = {r['number'] for r in sources}
recipes = [
    {'id': 'ldap-notification-edit', 'source_numbers': [5869, 5895], 'mode': 'direct', 'select_numbers': [5869], 'changes': {'owner': 'Chen', 'priority': 2, 'score': 5}},
    {'id': 'single-open-ranking', 'source_numbers': [5869, 5895], 'mode': 'rank', 'where': {'field': 'number', 'op': 'eq', 'value': 5869}, 'order_by': [{'field': 'updated_at', 'direction': 'desc'}], 'limit': 1, 'changes': {'owner': 'Rivera', 'priority': 1, 'score': 8}},
    {'id': 'planning-choice-final', 'source_numbers': [5869, 5895], 'mode': 'allocation', 'cost_limit': 5, 'hour_limit': 2, 'planning': [{'number': 5869, 'cost': 4, 'hours': 2, 'value': 15}, {'number': 5895, 'cost': 5, 'hours': 2, 'value': 7}], 'changes': {'owner': 'Singh', 'priority': 2, 'score': 6}},
]
assert all(set(t['source_numbers']) <= known for t in recipes)
(root / 'tasks.json').write_text(json.dumps(recipes, indent=2) + '\n')
approved = json.loads(Path('/inputs/examples.json').read_text())
by_episode = defaultdict(lambda: defaultdict(dict))
for record in approved:
    episode, step, variant = record['record_id'].split(':')
    by_episode[episode][int(step)][variant] = record
buckets = defaultdict(list)
for episode, steps in sorted(by_episode.items()):
    for step, variants in sorted(steps.items()):
        decision = variants['decision']
        action = json.loads(decision['messages'][-1]['content'])['action']
        if step < 24 and action['type'] != 'invalid_response':
            buckets[episode].append(decision)
            if action['type'] in ('fill', 'select', 'done') and 'history' in variants and len(variants['history']['messages']) <= 16:
                buckets[episode].append(variants['history'])
    print(episode, 'approved steps', len(steps), 'selected', len(buckets[episode]))
assert len(buckets) >= 2
# Interleave episodes so successive examples alternate between navigation and editing contexts.
selected = []
for position in range(max(map(len, buckets.values()))):
    for episode in sorted(buckets):
        if position < len(buckets[episode]):
            selected.append(buckets[episode][position])
assert len({r['episode_sha256'] for r in selected}) >= 2
assert len({r['record_id'] for r in selected}) == len(selected)
out = root / 'train_messages.jsonl'
with out.open('w') as stream:
    for record in selected:
        stream.write(json.dumps(record, ensure_ascii=False) + '\n')
print('selected', len(selected), 'bytes', out.stat().st_size, 'representations', dict(Counter(r['representation'] for r in selected)))
