import json
from pathlib import Path
rows=json.loads(Path('/inputs/examples.json').read_text())
print('SCHEMA',json.dumps({k:v for k,v in rows[0].items() if k!='messages'}))
print('MESSAGE_SCHEMA',[(m['role'],type(m['content']).__name__) for m in rows[0]['messages']])
for r in rows:
    if r['representation']=='decision' and r['record_id'].split(':')[0] in ['episode-01','episode-02']:
        out=json.loads(r['messages'][-1]['content'])
        print(json.dumps({'id':r['record_id'],'action':out['action'],'memory':out.get('memory','')}))
