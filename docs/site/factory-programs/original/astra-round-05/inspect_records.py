import json
from pathlib import Path
rows=json.loads(Path('/inputs/examples.json').read_text())
print('SCHEMA', list(rows[0]))
print('FIRST_RECORD',json.dumps(rows[0])[:22000])
for ep in ['episode-00','episode-01','episode-04']:
 print('EPISODE',ep)
 for r in rows:
  if r['record_id'].startswith(ep+':') and r['representation']=='decision':
   print(r['record_id'],r['messages'][-1]['content'])
