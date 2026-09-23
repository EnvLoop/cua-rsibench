import json
from pathlib import Path
from collections import defaultdict
rows=json.loads(Path('/inputs/examples.json').read_text())
groups=defaultdict(list)
for r in rows:
    if r['representation']=='decision': groups[r['record_id'].split(':')[0]].append(r)
for ep,rs in groups.items():
    print('EPISODE',ep,'rows',len(rs),'sources',rs[0]['source_numbers'])
    for r in rs:
        out=json.loads(r['messages'][-1]['content'])
        print(json.dumps({'id':r['record_id'],'action':out['action'],'memory':out.get('memory',''),'chars':sum(len(m['content']) for m in r['messages'])}))
print('INPUT FILES', sorted(p.name for p in Path('/inputs').iterdir()))
