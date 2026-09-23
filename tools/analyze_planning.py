import json
from pathlib import Path
from cursibench.kanboard_cases import public_allocation_case
case=public_allocation_case(51)
data={t['reference']:json.loads(t['description'].split('CONSTRUCTED PLANNING INPUTS (not upstream estimates):\n')[1]) for t in case['tasks'][1:]}
for folder in Path('work').glob('kanboard-planning-*'):
 p=folder/'result.json'
 if not p.exists():continue
 r=json.loads(p.read_text())
 if 'final' not in r:continue
 selected={t['reference'] for t in r['final']['tasks'] if t['project_id']==r['mapping']['project'] and t['owner_id']==r['mapping']['users']['Rivera'] and t['priority']==3 and t['score']==5}
 expected=set(r['expected_targets']);rows=[data[k] for k in selected if k in data]
 groups=[x['exclusive_group'] for x in rows if x['exclusive_group']!='none']
 findings={'selected':sorted(selected),'optimal':sorted(expected),'selected_value':sum(x['value'] for x in rows),'optimal_value':sum(data[k]['value'] for k in expected),'cost':sum(x['cost'] for x in rows),'hours':sum(x['hours'] for x in rows),'blocked_selected':[x['id'] for x in rows if x['blocked']=='yes'],'missing_dependencies':[x['requires'] for x in rows if x['requires']!='none' and x['requires'] not in selected],'exclusive_violation':len(groups)!=len(set(groups))}
 findings['feasible']=findings['cost']<=70 and findings['hours']<=17 and not findings['blocked_selected'] and not findings['missing_dependencies'] and not findings['exclusive_violation']
 (folder/'decision-analysis.json').write_text(json.dumps(findings,indent=2));print(folder.name,findings)
