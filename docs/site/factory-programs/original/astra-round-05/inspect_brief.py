import json
from pathlib import Path
from collections import Counter
p=Path('/inputs')
rows=json.loads((p/'examples.json').read_text())
print('Representations',dict(Counter(r['representation'] for r in rows)))
for episode in ['episode-00','episode-01']:
    trace=json.loads((p/(episode+'.json')).read_text())
    print('TRACE',episode)
    if isinstance(trace,dict):
        for k,v in trace.items():
            if isinstance(v,list):
                print(k,'length',len(v),'first_keys',list(v[0]) if v and isinstance(v[0],dict) else '')
            elif isinstance(v,dict):
                print(k,json.dumps(v)[:600])
            else:
                print(k,str(v)[:250])
    for r in rows:
        if r['representation']!='decision' or not r['record_id'].startswith(episode+':'): continue
        answer=json.loads(r['messages'][-1]['content'])
        context=json.loads(r['messages'][-2]['content'].split('\n',1)[1])
        a=answer['action']
        controls=context['observation']['controls']
        label=next((c.get('label','') for c in controls if c.get('id')==a.get('control')),'')
        print(r['record_id'],a['type'],label[:65],a.get('value'), 'last=',json.dumps(context.get('last_action')))
        if episode=='episode-00' and (a['type']=='done' or a['type']=='back'):
            print('MEMORY',answer.get('memory'))
    print('---')
