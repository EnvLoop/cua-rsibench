"""Seal source-disjoint final instances before checkpoint selection or testing."""
import copy,datetime,hashlib,json
from pathlib import Path
from cursibench.factory_cases import SourceRegistry,compile_case,digest
from cursibench.factory_export import export_case
from cursibench.factory_campaign import CampaignRegistry
from cursibench.factory_results import summarize

root=Path('work/factory-study-02');destination=root/'sealed-final';destination.mkdir(exist_ok=False)
raw=json.loads(Path('datasets/public/kanboard_issues.json').read_text());rows=raw['records'][24:36]
registry=SourceRegistry(raw,[r['number'] for r in rows],[r['number'] for r in raw['records'][:24]],partition='final')
opened=sorted([r for r in rows if r['state']=='open'],key=lambda r:r['number']);closed=sorted([r for r in rows if r['state']=='closed'],key=lambda r:r['number'])
assert len(opened)>=3 and closed
ids=[r['number'] for r in opened[:3]]+[closed[0]['number']]
base={'id':'final-direct-a','mode':'direct','source_numbers':[ids[3],ids[0]],'select_numbers':[ids[0]],'changes':{'owner':'Chen','priority':2,'score':5}}
other=copy.deepcopy(base);other.update(id='final-direct-b',source_numbers=list(reversed(base['source_numbers'])),changes={'owner':'Singh','priority':3,'score':8})
cases=[base,other]
rank={'id':'final-rank-a','mode':'rank','source_numbers':[ids[3],ids[2],ids[0],ids[1]],'where':{'field':'state','op':'eq','value':'open'},'order_by':[{'field':'updated_at','direction':'asc'}],'limit':2,'changes':{'owner':'Rivera','priority':3,'score':8}}
other=copy.deepcopy(rank);other.update(id='final-rank-b',source_numbers=list(reversed(rank['source_numbers'])),order_by=[{'field':'updated_at','direction':'desc'}],changes={'owner':'Chen','priority':1,'score':3})
cases.extend([rank,other])
allocation={'id':'final-allocation-a','mode':'allocation','source_numbers':ids,'cost_limit':9,'hour_limit':4,'changes':{'owner':'Singh','priority':1,'score':3},'planning':[
 {'number':ids[0],'cost':3,'hours':2,'value':8},{'number':ids[1],'cost':5,'hours':2,'value':9,'requires':ids[0]},
 {'number':ids[2],'cost':9,'hours':4,'value':17},{'number':ids[3],'cost':3,'hours':1,'value':30,'blocked':True}]}
other=copy.deepcopy(allocation);other.update(id='final-allocation-b',source_numbers=list(reversed(ids)),changes={'owner':'Rivera','priority':2,'score':5});other['planning'][2]['cost']=7
cases.extend([allocation,other]);manifest=[]
# Each chunk has three tasks, so all tasks receive their complete per-task budget.
for index,spec in enumerate(cases):
 chunk='chunk-'+str(index//3);case=compile_case(spec,registry);parent=destination/chunk;parent.mkdir(exist_ok=True)
 export_case(case,parent/spec['id']);manifest.append({'task':spec['id'],'chunk':chunk,'case_sha256':digest(case),'target_count':len(case['targets'])})
selection=['selection-direct-01','selection-rank-01','selection-allocation-01']
seal={'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'purpose':'final evaluation only; not researcher feedback','cases':manifest,'source_ids':[r['number'] for r in rows],'claim_boundary':'six fixed task instances in one real application; no broad generalization or causal shortcut claim'}
(destination/'manifest.json').write_text(json.dumps(seal,indent=2))
protocol={'selection_tasks':selection,'final_tasks':[x['task'] for x in manifest],
          'selection_manifest_sha256':hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest(),'final_manifest_sha256':digest(seal),
          'max_attempts':5,'training_token_budget':1048576,'promotion':'no_regression','early_stop':'all selection tasks solved or budget exhausted','training_steps':32,'training_profile':'factory-v1'}
for name in ('astra','sol'):
 registry=CampaignRegistry(root/(name+'-campaign.json'),protocol)
 baseline=summarize(root/'cache-repair/base',selection);registry.set_baseline(baseline)
 summary=summarize(root/'cache-repair'/name,selection)
 train=root/('train-'+name)/'training.json';training=json.loads(train.read_text())
 registry.register('round-1',training['data_sha256'],train.resolve(),training['scheduled_tokens'],summary,historical_import=True)
print('Sealed six final cases and froze selection/promotion rules before round-2 evaluation')
