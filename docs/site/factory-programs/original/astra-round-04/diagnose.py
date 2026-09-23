import json
from pathlib import Path
p = Path('/inputs/episode-06.json')
data = json.loads(p.read_text())
print('TRACE_METADATA', json.dumps({k:v for k,v in data.items() if k not in ('trace','case')}, ensure_ascii=False)[:3000])
for step in data.get('trace', []):
    response = step.get('response')
    try:
        response = json.loads(response) if isinstance(response, str) else response
    except (ValueError, TypeError):
        pass
    print(json.dumps({'step':step.get('step'), 'response':response, 'outcome':step.get('outcome')}, ensure_ascii=False))
print('FINAL_OBSERVATION', data.get('trace', [{}])[-1].get('observation', {}).get('text', '')[-6500:])
rows = json.loads(Path('/inputs/examples.json').read_text())
from collections import Counter
print('APPROVED_COUNTS', json.dumps(dict(Counter((r['record_id'].split(':')[0] + ':' + r['representation']) for r in rows))))
