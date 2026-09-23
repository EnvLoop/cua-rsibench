import json
from pathlib import Path
from collections import Counter

root = Path('/inputs')
rows = json.loads((root / 'examples.json').read_text())
print('Representations:', dict(Counter(r['representation'] for r in rows)))
for name in ['episode-00', 'episode-01']:
    trace = json.loads((root / (name + '.json')).read_text())
    print('TRACE', name, 'structure', list(trace) if isinstance(trace, dict) else type(trace).__name__)
    if isinstance(trace, dict):
        for key, value in trace.items():
            if isinstance(value, list):
                print('TRACE LIST', key, 'length', len(value))
                if value:
                    print('FIRST ITEM', json.dumps(value[0])[:1800])
            else:
                print('TRACE FIELD', key, json.dumps(value)[:2200])
    for r in rows:
        if not r['record_id'].startswith(name + ':') or r['representation'] != 'decision':
            continue
        response = json.loads(r['messages'][-1]['content'])
        user = r['messages'][-2]['content']
        try:
            obs = json.loads(user[user.index('\n')+1:])
            controls = obs['observation']['controls']
            action = response['action']
            selected = [c for c in controls if c.get('id') == action.get('control')]
            context = {'last_action': obs.get('last_action'), 'control': selected, 'incoming_memory': obs.get('memory')}
        except (ValueError, KeyError, TypeError):
            context = {'parse_failed': True}
        print('DECISION', r['record_id'], json.dumps(response), 'CONTEXT', json.dumps(context), 'bytes', len(json.dumps(r).encode()))
