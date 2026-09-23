import json
from collections import defaultdict, Counter
from pathlib import Path
records = json.loads(Path('/inputs/examples.json').read_text())
groups = defaultdict(list)
for r in records:
    episode, step, variant = r['record_id'].split(':')
    if variant != 'decision':
        continue
    action = json.loads(r['messages'][-1]['content'])['action']
    user = json.loads(r['messages'][-2]['content'].split('\n', 1)[1])
    controls = {c['id']: c.get('label', '') for c in user['observation']['controls']}
    groups[episode].append((int(step), action['type'], controls.get(action.get('control'), ''), action.get('value', ''), user['observation']['url'], len(r['messages'])))
for episode, steps in sorted(groups.items()):
    print('\n', episode, 'steps', len(steps), 'types', dict(Counter(s[1] for s in steps)))
    for step, kind, label, value, url, length in sorted(steps):
        if step < 30 or kind in ('fill', 'select', 'done'):
            print(step, kind, repr(label[:35]), repr(value[:35]), url.split('controller=')[-1][:55])
