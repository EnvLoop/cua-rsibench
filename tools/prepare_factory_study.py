"""Freeze a small multi-family selection suite before any student evaluation."""
import argparse,datetime,json,hashlib
from pathlib import Path
from cursibench.factory_cases import SourceRegistry,compile_case,digest
from cursibench.factory_export import export_case

p=argparse.ArgumentParser();p.add_argument('--out',required=True);a=p.parse_args()
root=Path(a.out);root.mkdir(exist_ok=False)
snapshot=json.loads(Path('datasets/public/kanboard_issues.json').read_text())
train=snapshot['records'][:12];selection=snapshot['records'][12:24];final=snapshot['records'][24:36]
registry=SourceRegistry(snapshot,[r['number'] for r in selection],[r['number'] for r in train+final],partition='selection')
opened=sorted([r for r in selection if r['state']=='open'],key=lambda r:r['number'])
closed=sorted([r for r in selection if r['state']=='closed'],key=lambda r:r['number'])
assert len(opened)>=3 and len(closed)>=2
common={'owner':'Chen','priority':2,'score':5}
cases=[
 {'id':'selection-direct-01','mode':'direct','source_numbers':[closed[0]['number'],opened[0]['number']],
  'select_numbers':[opened[0]['number']],'changes':common},
 {'id':'selection-rank-01','mode':'rank','source_numbers':[closed[1]['number'],opened[-1]['number'],opened[0]['number'],opened[1]['number']],
  'where':{'field':'state','op':'eq','value':'open'},'order_by':[{'field':'updated_at','direction':'asc'}],'limit':2,
  'changes':{'owner':'Rivera','priority':3,'score':8}},
]
ids=[opened[0]['number'],opened[1]['number'],opened[2]['number'],closed[0]['number']]
cases.append({'id':'selection-allocation-01','mode':'allocation','source_numbers':ids,'cost_limit':9,'hour_limit':4,
 'changes':{'owner':'Singh','priority':1,'score':3},'planning':[
 {'number':ids[0],'cost':3,'hours':2,'value':8},
 {'number':ids[1],'cost':5,'hours':2,'value':9,'requires':ids[0]},
 {'number':ids[2],'cost':9,'hours':4,'value':17},
 {'number':ids[3],'cost':3,'hours':1,'value':30,'blocked':True}]})
(root/'selection').mkdir();compiled=[]
for spec in cases:
 case=compile_case(spec,registry);export_case(case,root/'selection'/spec['id']);compiled.append({'id':case['id'],'hash':digest(case),'family':spec['mode'],'target_count':len(case['targets'])})
source_files=['factory_cases.py','factory_export.py','factory_harbor.py','gui_contract.py','kanboard_rpc_v3.py','stable_observer.py','kanboard_cases.py','tinker_backend.py','training_contract.py','tinker_proxy.py','journal_env.py','command_journal.py']
manifest={'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'purpose':'paired student calibration of newly synthesized training datasets; not a final leaderboard','student':'Qwen/Qwen3.5-4B',
 'training':{'profile':'factory-v1','steps':32,'batch_size':2,'rank':8,'learning_rate':1e-4,'seed':23,'token_cap_per_run':262144},
 'sampling':{'max_tokens':512,'temperature':0,'seed':23},'evaluation':{'max_actions':90,'agent_timeout_seconds':1500,'task_count':3,'families':['direct','rank','allocation']},
 'cases':compiled,'data_hashes':{name:hashlib.sha256(Path(f'work/factory-{name}-01/train_messages.jsonl').read_bytes()).hexdigest() for name in ('astra','sol')},
 'engine_hashes':{n:hashlib.sha256(Path('src/cursibench',n).read_bytes()).hexdigest() for n in source_files},
 'prior_astra_16_step_run':'training integration smoke only; excluded from paired 32-step comparison','final_source_ids_not_evaluated':[r['number'] for r in final]}
(root/'manifest.json').write_text(json.dumps(manifest,indent=2));print('Frozen',len(compiled),'selection cases before student runs')
