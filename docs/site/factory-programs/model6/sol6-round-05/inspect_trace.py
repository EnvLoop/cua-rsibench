import json
from pathlib import Path

trace = json.loads(Path('/inputs/episode-02.json').read_text())['trace']
for row in trace:
    response = json.loads(row['response'])
    observation = row['observation']
    action = response['action']
    control = next((c for c in observation['controls'] if c['id'] == action.get('control')), None)
    print(json.dumps({'step': row['step'], 'url': observation['url'], 'action': action, 'control_label': control.get('label') if control else None, 'outcome': row.get('outcome'), 'memory': response.get('memory', '')[-500:], 'visible_text': observation['text'][-900:]}, ensure_ascii=True))
