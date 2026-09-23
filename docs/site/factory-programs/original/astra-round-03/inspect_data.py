import json
from pathlib import Path
from collections import Counter
p=Path('/inputs')
f=json.loads((p/'episode-05.json').read_text())
print('FAILED EPISODE SUMMARY')
print('Top-level keys:',list(f))
for t in f['trace']:
    print(json.dumps({'step':t['step'],'response':t.get('response'),'outcome':t.get('outcome')},ensure_ascii=False))
print('HISTORICAL SUBMISSIONS')
print((p/'historical-submissions.json').read_text())
rows=json.loads((p/'examples.json').read_text())
print('APPROVED COUNTS',dict(Counter((r['record_id'].split(':')[0],r.get('representation')) for r in rows)))
print('RECORD SCHEMA',list(rows[0]))
for r in rows:
    if r.get('representation')=='decision' and r['record_id'].split(':')[0] in ('episode-02','episode-03','episode-04'):
        print(json.dumps({'id':r['record_id'],'response':r['messages'][-1]['content'],'characters':sum(len(str(m['content'])) for m in r['messages'])},ensure_ascii=False))
