import json
from pathlib import Path
from collections import Counter
rows=json.loads(Path('/inputs/examples.json').read_text())
print('SCHEMA',json.dumps({k:v for k,v in rows[0].items() if k!='messages'}))
print('COUNTS',dict(Counter(r['record_id'].split(':')[0]+' '+r['representation'] for r in rows)))
for r in rows:
    ep=r['record_id'].split(':')[0]
    if r['representation']=='decision' and ep not in ('episode-02','episode-03'):
        out=json.loads(r['messages'][-1]['content'])
        print(json.dumps({'id':r['record_id'],'action':out['action'],'memory':out.get('memory','')[:190]}))
print('TOKENIZERS')
for name in ('tiktoken','transformers','tokenizers'):
    try:
        __import__(name)
        print(name,'available')
    except ImportError:
        print(name,'unavailable')
