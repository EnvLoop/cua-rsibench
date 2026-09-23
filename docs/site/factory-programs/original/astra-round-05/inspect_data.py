import json
from pathlib import Path
from collections import defaultdict
rows=json.loads(Path('/inputs/examples.json').read_text())
groups=defaultdict(list)
for r in rows:
    groups[r['record_id'].split(':')[0]].append(r)
print('TOTAL',len(rows))
for ep,rs in groups.items():
    ds=[r for r in rs if r.get('representation')=='decision']
    print('\nEPISODE',ep,'variants',len(rs),'decisions',len(ds))
    if ds:
        print('METADATA',json.dumps({k:v for k,v in ds[0].items() if k!='messages'}))
        print('FIRST_CONTEXT',json.dumps(ds[0]['messages'])[:10000])
    for r in ds:
        print(r['record_id'],r['messages'][-1]['content'])
    if rs:
        print('REPRESENTATIONS', sorted(set(r.get('representation','') for r in rs)))
        print('SIZE_RANGE',min(len(json.dumps(r['messages'])) for r in rs),max(len(json.dumps(r['messages'])) for r in rs))
