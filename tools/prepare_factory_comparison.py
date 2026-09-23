"""Freeze completed searches and prescribe shared final comparisons before testing."""
import json,time
from pathlib import Path
from cursibench.factory_campaign import CampaignRegistry
from cursibench.factory_final import make_plan

ROOT=Path(__file__).resolve().parents[1]

def prepare(study):
    study=Path(study).resolve();target=study/'final-comparison.json'
    if target.exists():raise ValueError('final comparison already exists')
    registries={n:CampaignRegistry(study/(n+'-campaign.json')) for n in ('astra','sol')}
    for name,r in registries.items():
        s=r.snapshot();p=s['protocol']
        if s['reservations']:raise ValueError('training still pending: '+name)
        if len(s['attempts'])<p['max_attempts'] and s['best_score']!=1 and s['used_training_tokens']+262144<=p['training_token_budget']:
            raise ValueError('declared search stopping condition not reached: '+name)
    for r in registries.values():r.freeze_selection('declared round, selection-ceiling, or conservative token-budget stopping condition reached')
    states={n:r.snapshot() for n,r in registries.items()};base=make_plan(ROOT,study,states['astra'],'base')
    identities={'base':base['binding']['checkpoint_sha256']}
    for name,s in states.items():identities[name]=make_plan(ROOT,study,s,'selected')['binding']['checkpoint_sha256']
    executions=[];bindings={k:[] for k in identities};unique={}
    for role,key in identities.items():
        if key not in unique:
            name='astra' if role=='base' else role;purpose='base' if role=='base' else 'selected'
            labels=[]
            for repeat in (1,2):
                label=f'{name}-{purpose}-repeat-{repeat}';labels.append(label)
                executions.append({'label':label,'researcher':name,'role':purpose,'repetition':repeat,'checkpoint_sha256':key})
            unique[key]=labels
        bindings[role]=unique[key]
    plan={'created_at':time.time(),'repetitions':2,'bindings':bindings,'executions':executions,
          'comparison':'same-seed fresh-environment repetitions; identical checkpoints share execution evidence',
          'selection_frozen_at':{n:s['final_selection']['frozen_at'] for n,s in states.items()}}
    target.write_text(json.dumps(plan,indent=2));print(json.dumps({'frozen':True,'distinct_checkpoints':len(unique),'planned_executions':len(executions)}))

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--study',default='work/factory-study-02');a=p.parse_args();prepare(a.study)
