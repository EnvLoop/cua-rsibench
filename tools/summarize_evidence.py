"""Curated public evidence index; no secrets, raw API envelopes, or account identifiers."""
import json,hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[1]
out=root/'outputs';out.mkdir(exist_ok=True)

def load(path):
 p=root/path
 return json.loads(p.read_text()) if p.exists() else None

evidence={'project':'CUA-RSIBench','release_status':'in_progress','date':'2026-09-23','scope':'Real-application computer-use benchmark and data-research pipeline',
 'source_data':{k:v for k,v in load('datasets/public/kanboard_issues.json').items() if k!='records'},'trials':[]}
for path in sorted((root/'work').glob('kanboard-*/result.json')):
 r=json.loads(path.read_text())
 if 'model' not in r or 'case' not in r:continue
 verification=r.get('verification',{})
 regrade=path.with_name('regraded.json')
 if regrade.exists():verification=json.loads(regrade.read_text())['verification']
 row={k:r.get(k) for k in ['case','model','steps','max_steps','elapsed_seconds','infrastructure_error','sandbox_destroyed']}
 row.update(run=path.parent.name,verification=verification,evidence_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),regraded=regrade.exists())
 usage=[x.get('usage') for x in r.get('receipts',[]) if x.get('usage')]
 row['input_tokens']=sum(u.get('input_tokens',0) for u in usage);row['output_tokens']=sum(u.get('output_tokens',0) for u in usage);row['cost_usd']=None
 evidence['trials'].append(row)
training=load('work/tinker-sft-03/training.json')
if training:evidence['tinker']={k:v for k,v in training.items() if k not in ['checkpoint','sample_text']};evidence['tinker']['checkpoint_sha256']=hashlib.sha256(training['checkpoint'].encode()).hexdigest()
chain=load('work/cloud-chain-01/harbor/checkpoint-browser/result.json')
if chain:evidence['cloud_chain']={'completed':chain['stats']['n_completed_trials'],'errors':chain['stats']['n_errored_trials'],'reward':next(iter(chain['stats']['evals'].values()))['metrics'][0]['mean'],'provider_cleanup':load('work/cloud-chain-01/result.json').get('proxy_destroyed')}
oracle=load('work/harbor-jobs/cua-oracle-02/result.json')
if oracle:evidence['harbor_oracle']={'completed':oracle['stats']['n_completed_trials'],'errors':oracle['stats']['n_errored_trials'],'reward':next(iter(oracle['stats']['evals'].values()))['metrics'][0]['mean']}
evidence['planning_analysis']=[]
for p in (root/'work').glob('kanboard-planning-*/decision-analysis.json'):
 evidence['planning_analysis'].append(dict(run=p.parent.name,**json.loads(p.read_text())))
native=load('work/kanboard-harbor-jobs/native-basic-02/result.json')
evidence['native_harbor']={'completed':native['stats']['n_completed_trials'],'errors':native['stats']['n_errored_trials'],'reward':next(iter(native['stats']['evals'].values()))['metrics'][0]['mean']} if native else None
evidence['native_training_runs']=[]
for p in (root/'work').glob('native-tinker-*/training.json'):
 r=json.loads(p.read_text())
 evidence['native_training_runs'].append({'run':p.parent.name,'model':r['model'],'records':r['record_count'],'steps_completed':len(r.get('events',[])),'scheduled_tokens':r.get('scheduled_tokens'),'verified':r.get('verified_training_and_sampling',False)})
(out/'evidence.json').write_text(json.dumps(evidence,indent=2))
print('curated',len(evidence['trials']),'trial records')
