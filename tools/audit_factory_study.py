"""Export allowlisted study evidence; never export provider envelopes or checkpoint IDs."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from cursibench.factory_campaign import CampaignRegistry, valid_scores, digest
from cursibench.factory_cases import SourceRegistry
from cursibench.factory_recovery import restore_corpus
from cursibench.factory_final import validate_study, make_plan, combine, verify_execution
from cursibench.factory_results import summarize

ROOT=Path(__file__).resolve().parents[1]


def read(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def public_summary(summary):
    return {k:summary[k] for k in ('status','score','expected_tasks','task_identity_matches','tasks') if k in summary}


def evaluation(path,names):
    summary=summarize(path,names)
    proof=[]
    for p in sorted((path/'harbor/checkpoint-browser').glob('*/result.json')):
        raw=read(p)
        proof.append({'task':raw['task_name'],'result_sha256':sha(p),
            'separate_verifier':raw.get('verifier_environment_mode')=='separate',
            'started_at':raw.get('started_at'),'finished_at':raw.get('finished_at')})
    wrapper=read(path/'result.json')
    if summary['status']=='scored' and (wrapper.get('harbor_exit')!=0 or wrapper.get('error_type') or not all(p['separate_verifier'] for p in proof)):
        raise ValueError('scored evaluation lacks separate successful execution')
    return dict(public_summary(summary),proof=proof,proxy_destroyed=wrapper.get('proxy_destroyed'))


def audit(study):
    study=Path(study).resolve();manifest=read(study/'manifest.json')
    source=read(ROOT/'datasets/public/kanboard_issues.json')
    registry=SourceRegistry(source,[r['number'] for r in source['records'][:12]],[r['number'] for r in source['records'][12:36]])
    result={'schema':'factory-study-v1','generated_at':datetime.now(timezone.utc).isoformat(),
        'study':'Executable data factories for native browser use','student':manifest['student'],
        'teacher':'gpt-5.6-sol','training':manifest['training'],'sampling':manifest['sampling'],
        'selection_tasks':3,'final_tasks':6,'source_records':37,'source_partition_counts':{'train':12,'selection':12,'final':12,'unused':1},
        'application':'Kanboard 1.2.54','interaction':'DOM-assisted browser use','cost_usd':None,
        'campaigns':[],'final_executions':[],'claim':'bounded data-centric research pilot; no sustained RSI or broad model ranking'}
    source_sets=[{r['number'] for r in source['records'][i:i+12]} for i in (0,12,24)]
    result['source_partitions_disjoint']=all(not source_sets[i]&source_sets[j] for i in range(3) for j in range(i+1,3))
    for name,model in [('astra','gpt-6-astra'),('sol','gpt-5.6-sol')]:
        state=CampaignRegistry(study/(name+'-campaign.json')).snapshot()
        integrity=validate_study(ROOT,study,state)
        base=evaluation(study/'cache-repair/base',state['protocol']['selection_tasks'])
        if public_summary(state['baseline'])!=public_summary(base):raise ValueError('baseline registry mismatch')
        campaign={'name':name,'researcher':model,'baseline':base,'attempts':[],'factories':[],
            'used_training_tokens':state['used_training_tokens'],'training_token_budget':state['protocol']['training_token_budget'],
            'max_attempts':state['protocol']['max_attempts'],'selected':state['selected'],'selection_score':state['best_score'],
            'selection_frozen':state['final_selection'] is not None,'pending_training':len(state['reservations']),
            'protocol_hash':state['protocol_hash'],'runtime_hashes':integrity['runtime_hashes']}
        prior=state['baseline'];incumbent='base';best=prior['score'];total=0
        for record in state['attempts']:
            number=int(record['attempt_id'].split('-')[-1]);factory=ROOT/'work'/f'factory-{name}-{number:02}'
            fr=read(factory/'result.json');corpus,_,incomplete=restore_corpus(factory,registry)
            if incomplete:raise ValueError('unresolved teacher episode')
            histories=read(factory/'research-history.json')
            events=[h for h in histories if h['action'].get('type')=='rollout']
            new_episodes=[]
            for event in events:
                eid=event['reply'].get('episode_id')
                if eid:
                    p=factory/'controller'/eid;r=read(p/'result.json');case=read(p/'case.json')
                    new_episodes.append({'episode':eid,'mode':case['kind'],'steps':r['steps'],
                        'success':r['verification'].get('success'),'infrastructure_error':r.get('infrastructure_error'),
                        'sandbox_destroyed':r.get('sandbox_destroyed'),'result_sha256':sha(p/'result.json')})
            campaign['factories'].append({'round':number,'complete':fr['complete'],'research_turns':fr['research_turns'],
                'resources':fr['budget']['reserved'],'resource_limits':fr['budget']['limits'],
                'verified_episodes_available':len(corpus.episodes),'new_episodes':new_episodes,
                'wall_seconds':fr.get('wall_elapsed_seconds',fr['elapsed_seconds']),
                'history_sha256':sha(factory/'research-history.json')})
            row={'round':number,'dataset_sha256':record['dataset_hash'],'training_tokens':record['training_tokens'],
                 'promoted':record['promoted'],'accounting':record.get('accounting','historical import before reservation guard')}
            if record['training_manifest']:
                data=factory/'train_messages.jsonl';rows=corpus.validate_submission(data.read_text());training=read(record['training_manifest'])
                if sha(data)!=record['dataset_hash'] or training['data_sha256']!=record['dataset_hash']:
                    raise ValueError('training dataset mismatch')
                if (not training.get('verified_training_and_sampling') or training['scheduled_tokens']!=record['training_tokens']
                    or training['steps_requested']!=32 or len(training['events'])!=32 or training['record_count']!=len(rows)
                    or training['covered_records']!=len(rows) or training['training_profile']!='factory-v1'):
                    raise ValueError('training proof mismatch')
                path=study/'cache-repair'/name if number==1 else study/f'round-{number}'/('eval-'+name)
                ev=evaluation(path,state['protocol']['selection_tasks'])
                if public_summary(ev)!=public_summary(record['evaluation']):raise ValueError('registered score differs from execution')
                row.update(evaluation=ev,records=len(rows),checkpoint_sha256=digest(training['checkpoint']),
                    data_provenance_verified=True,optimizer_steps=32)
            else:
                row.update(evaluation=record['evaluation'],submission_feedback=record.get('submission_feedback'),records=None)
            ev=row['evaluation'];scores=valid_scores(ev,state['protocol']['selection_tasks'])
            old=valid_scores(prior,state['protocol']['selection_tasks'])
            admitted=scores is not None and ev['score']>best and all(scores[k]>=old[k] for k in old)
            if admitted!=record['promoted']:raise ValueError('promotion rule mismatch')
            if admitted:incumbent=record['attempt_id'];best=ev['score'];prior=ev
            total+=record['training_tokens'];row.update(incumbent_after=incumbent,best_after=best,cumulative_training_tokens=total)
            campaign['attempts'].append(row)
        if total!=state['used_training_tokens'] or incumbent!=state['selected'] or total>state['protocol']['training_token_budget']:
            raise ValueError('campaign accounting mismatch')
        if state['final_selection']:
            campaign['frozen_at']=state['final_selection']['frozen_at'];campaign['stopping_reason']=state['final_selection']['reason']
        result['campaigns'].append(campaign)
    directory=study/'final-executions'
    for out in sorted(directory.iterdir()) if directory.exists() else []:
        if not (out/'summary.json').exists():continue
        plan=read(out/'plan.json');name=out.name.split('-')[0];state=CampaignRegistry(study/(name+'-campaign.json')).snapshot()
        if plan!=make_plan(ROOT,study,state,plan['role'],plan['repetition']):raise ValueError('final plan changed')
        started=read(out/'started.json')['started_at']
        if started<max(c['frozen_at'] for c in result['campaigns']):raise ValueError('final test preceded a closed search')
        pieces=[]
        for chunk,tasks in plan['chunks'].items():
            valid=verify_execution(out/chunk,plan);ev=evaluation(out/chunk,tasks)
            if not valid:ev.update(status='infrastructure_error',score=None)
            pieces.append(ev)
        combined=combine(pieces,state['protocol']['final_tasks'])
        if combined!=read(out/'summary.json'):raise ValueError('final summary differs from evidence')
        result['final_executions'].append({'label':out.name,'role':plan['role'],'candidate':plan['binding']['candidate'],
            'checkpoint_sha256':plan['binding']['checkpoint_sha256'],'repetition':plan['repetition'],
            'started_at':started,'evaluation':combined,'chunk_proofs':[p['proof'] for p in pieces],
            'plan_sha256':sha(out/'plan.json'),'selection_precedes_test':True})
    comparison=study/'final-comparison.json'
    if comparison.exists():
        plan=read(comparison);result['final_comparison']=plan
        by_label={r['label']:r for r in result['final_executions']}
        for role,labels in plan['bindings'].items():
            s=CampaignRegistry(study/(('astra' if role=='base' else role)+'-campaign.json')).snapshot()
            expected=make_plan(ROOT,study,s,'base' if role=='base' else 'selected')['binding']['checkpoint_sha256']
            for label in labels:
                if label in by_label and (by_label[label]['checkpoint_sha256']!=expected or by_label[label]['started_at']<plan['created_at']):
                    raise ValueError('final comparison identity or timing mismatch')
        result['all_final_executions_finished']=all(r['label'] in by_label for r in plan['executions'])
    else:result['all_final_executions_finished']=False
    result['audit_pass']=True
    result['search_finished']=all(c['selection_frozen'] and c['pending_training']==0 for c in result['campaigns'])
    result['limitations']=['one application and three task families','one research seed per system',
        'no equal-budget non-adaptive search control','final repetitions use the same sampling seed',
        'public issue metadata plus synthetic workflow rules; no unseen-application claim',
        'provider monetary totals unavailable; token and call budgets are reported instead']
    text=json.dumps(result,indent=2,ensure_ascii=False)
    import re
    if re.search(r'[\u3400-\u9fff]',text):raise ValueError('CJK found in English publication evidence')
    if re.search(r'(?:tml-|e2b_|sk-)[A-Za-z0-9_-]{20,}',text):raise ValueError('possible credential in publication evidence')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--study',default='work/factory-study-02');p.add_argument('--out',default='outputs/factory-study.json');a=p.parse_args()
    data=audit(a.study);out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(data,indent=2,ensure_ascii=False))
    print(json.dumps({'audit_pass':data['audit_pass'],'search_finished':data['search_finished'],'final_executions':len(data['final_executions'])}))
