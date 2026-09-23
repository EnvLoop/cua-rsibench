import json
from pathlib import Path
from collections import defaultdict
rows=json.loads(Path('/inputs/examples.json').read_text())
groups=defaultdict(list)
for r in rows: groups[r['record_id'].split(':')[0]].append(r)
for ep,rs in groups.items():
 ds=[r for r in rs if r['representation']=='decision']
 print(ep,'metadata',json.dumps({k:v for k,v in ds[0].items() if k!='messages'}))
 print('steps',len(ds),'history_sizes',[(r['record_id'],len(json.dumps(r['messages']))) for r in rs if r['representation']=='history'][::6])
 for r in ds:
  out=json.loads(r['messages'][-1]['content'])
  print(r['record_id'],json.dumps(out['action']),out.get('memory','')[:210])
print('INPUT_FILES',[p.name for p in Path('/inputs').iterdir()])
