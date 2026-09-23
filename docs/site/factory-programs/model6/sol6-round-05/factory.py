import json
from collections import Counter, defaultdict
from pathlib import Path

root = Path('/workspace')
sources = json.loads(Path('/inputs/sources.json').read_text())['records']
known = {record['number'] for record in sources}
recipes = [
    {'id': 'ldap-notification-edit', 'source_numbers': [5869, 5895], 'mode': 'direct', 'select_numbers': [5869], 'changes': {'owner': 'Chen', 'priority': 2, 'score': 5}},
    {'id': 'open-security-ranking', 'source_numbers': [5895, 5871, 5894], 'mode': 'rank', 'where': {'all': [{'field': 'state', 'op': 'eq', 'value': 'open'}, {'field': 'comment_count', 'op': 'gte', 'value': 1}]}, 'order_by': [{'field': 'updated_at', 'direction': 'desc'}], 'limit': 1, 'changes': {'owner': 'Rivera', 'priority': 1, 'score': 8}},
    {'id': 'planning-choice-revised', 'source_numbers': [5895, 5869], 'mode': 'allocation', 'cost_limit': 6, 'hour_limit': 3, 'planning': [{'number': 5895, 'cost': 6, 'hours': 3, 'value': 8}, {'number': 5869, 'cost': 4, 'hours': 2, 'value': 17}], 'changes': {'owner': 'Singh', 'priority': 2, 'score': 6}},
]
assert all(set(task['source_numbers']) <= known for task in recipes)
(root / 'tasks.json').write_text(json.dumps(recipes, indent=2) + '\n')
approved = json.loads(Path('/inputs/examples.json').read_text())
by_episode = defaultdict(lambda: defaultdict(dict))
for record in approved:
    episode, step, variant = record['record_id'].split(':')
    by_episode[episode][int(step)][variant] = record

buckets = defaultdict(list)
for episode, steps in sorted(by_episode.items()):
    for step, variants in sorted(steps.items()):
        decision = variants.get('decision')
        if decision is None:
            continue
        action = json.loads(decision['messages'][-1]['content'])['action']
        if action['type'] == 'invalid_response':
            continue
        if step < 30:
            buckets[episode].append(decision)
        if action['type'] in ('fill', 'select', 'done') and 'history' in variants and len(variants['history']['messages']) <= 16:
            buckets[episode].append(variants['history'])
    print(episode, 'approved steps', len(steps), 'selected', len(buckets[episode]))
assert {'episode-00', 'episode-01', 'episode-06'} <= buckets.keys()
selected = []
for position in range(max(map(len, buckets.values()))):
    for episode in ('episode-00', 'episode-01', 'episode-06'):
        if position < len(buckets[episode]):
            selected.append(buckets[episode][position])

# Repeat the decisions that turn inspected source facts into a selected task and
# complete the edit. Keep the full incumbent direct-edit trajectory intact.
for episode, steps in (('episode-01', (12, 13, 15, 16, 17, 18, 19)),
                       ('episode-06', (9, 10, 12, 13, 14, 15, 16))):
    selected.extend(by_episode[episode][step]['decision'] for step in steps)

assert len({record['episode_sha256'] for record in selected}) == 3
assert len(selected) <= 64
assert all(record in approved for record in selected)
out = root / 'train_messages.jsonl'
with out.open('w') as stream:
    for record in selected:
        stream.write(json.dumps(record, ensure_ascii=False) + '\n')
assert out.stat().st_size <= 2_000_000
print('selected', len(selected), 'bytes', out.stat().st_size, 'representations', dict(Counter(record['representation'] for record in selected)))
