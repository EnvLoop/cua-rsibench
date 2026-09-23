import json
from collections import defaultdict
from pathlib import Path

records = json.loads(Path('/inputs/examples.json').read_text())
episodes = defaultdict(list)
for record in records:
    episode, step, variant = record['record_id'].split(':')
    if variant != 'decision':
        continue
    user = json.loads(record['messages'][-2]['content'].split('\n', 1)[1])
    answer = json.loads(record['messages'][-1]['content'])
    action = answer['action']
    controls = user['observation']['controls']
    control = next((c for c in controls if c['id'] == action.get('control')), {})
    episodes[episode].append((int(step), user['observation']['url'], action['type'], control.get('label', ''), action.get('value', ''), answer.get('memory', '')[-160:]))
for episode, steps in sorted(episodes.items()):
    print('\n', episode, len(steps))
    for step, url, kind, label, value, memory in sorted(steps):
        print(step, kind, repr(label), repr(value), url.split('?')[0], memory)
