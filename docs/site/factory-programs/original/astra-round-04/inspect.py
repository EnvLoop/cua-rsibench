import json
from pathlib import Path
from collections import Counter
rows=json.loads(Path('/inputs/examples.json').read_text())
print('groups',dict(Counter(r['record_id'].split(':')[0]+' '+r['representation'] for r in rows)))
for ep in ['episode-00','episode-01','episode-02']:
 print('EPISODE',ep)
 for r in rows:
  if r['record_id'].startswith(ep+':') and r['representation']=='decision':
   a=json.loads(r['messages'][-1]['content'])
   print(r['record_id'],json.dumps(a['action']),a.get('memory','')[:650])
print('HISTORY_SIZES',[(r['record_id'],len(json.dumps(r['messages']))) for r in rows if r['representation']=='history' and int(r['record_id'].split(':')[1]) in [3,8,12,18,25]])
