import json
from pathlib import Path
from collections import Counter
p=Path('/inputs')
f=json.loads((p/'episode-05.json').read_text())
print('FAILED ALLOCATION ACTIONS')
for t in f['trace']:
    try:
        r=json.loads(t['response'])
        a=r['action']
        controls=t.get('observation',{}).get('controls',[])
        control=next((c for c in controls if str(c['id'])==str(a.get('control'))),{})
        print(json.dumps({'step':t['step'],'action':a,'label':control.get('label'),'memory':r.get('memory'),'outcome':t.get('outcome')}))
    except Exception as e:
        print(t['step'],str(e),t.get('response'))
print('HISTORY')
h=json.loads((p/'historical-submissions.json').read_text())
print(json.dumps(h))
rows=json.loads((p/'examples.json').read_text())
print('COUNTS',dict(Counter(r['record_id'].split(':')[0]+' '+str(r.get('representation')) for r in rows)))
print('SCHEMA',list(rows[0]))
print('ALLOCATION SELECTION DECISIONS')
for r in rows:
    if r['record_id'].split(':')[0]=='episode-03' and r.get('representation')=='decision' and 3<=int(r['record_id'].split(':')[1])<=13:
        print(r['record_id'],r['messages'][-1]['content'])
