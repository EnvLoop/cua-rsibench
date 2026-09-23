"""Export allowlisted study evidence; never export provider envelopes or checkpoint IDs."""
import argparse
import hashlib
import collections
import json
from datetime import datetime, timezone
from pathlib import Path
from cursibench.factory_campaign import CampaignRegistry, valid_scores, digest
from cursibench.factory_cases import SourceRegistry
from cursibench.factory_recovery import restore_corpus
from cursibench.factory_final import validate_study, make_plan, combine, verify_execution
from cursibench.factory_results import summarize
from cursibench.factory_roster import study_roster
from cursibench.factory_provenance import validate_selection_packages,verify_factory_identity
from cursibench.factory_final_recovery import replace_build_failures
from remote_evidence_audit import audit_remote, audit_full_suite_recoveries

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
    result['cohort']={'id':manifest.get('cohort','original-factory-study'),'purpose':manifest['purpose'],
        'created_at':manifest['created_at'],'researchers':study_roster(study),
        'teacher':manifest.get('teacher','gpt-5.6-sol'),'prior_lineages_inherited':manifest.get('prior_lineages_inherited',False)}
    result['source_record_ids']={
        'selection':sorted({n for p in (study/'selection').glob('*/environment/scenario.json') for n in read(p)['source_numbers']}),
        'final':sorted({n for p in (study/'sealed-final').glob('chunk-*/*/environment/scenario.json') for n in read(p)['source_numbers']})}
    reuse_path=study/'reuse-provenance.json'
    if reuse_path.exists():
        reuse=read(reuse_path)
        if sha(reuse_path)!=manifest['baseline_reuse_manifest_sha256']:raise ValueError('baseline reuse provenance changed')
        for relative,expected in reuse['selection_file_hashes'].items():
            if sha(study/'selection'/relative)!=expected:raise ValueError('reused selection artifact changed')
        for relative,expected in reuse['baseline_file_hashes'].items():
            if sha(study/'baseline'/relative)!=expected:raise ValueError('reused baseline artifact changed')
        result['baseline_reuse']={k:reuse[k] for k in ('kind','new_execution','source_study','source_baseline','source_manifest_sha256','baseline_summary_sha256','boundary')}
        result['baseline_reuse']['provenance_sha256']=sha(reuse_path)
    else:result['baseline_reuse']=None
    source_sets=[{r['number'] for r in source['records'][i:i+12]} for i in (0,12,24)]
    result['source_records_used']={'selection':len({n for p in (study/'selection').glob('*/environment/scenario.json') for n in read(p)['source_numbers']}),'final':len({n for p in (study/'sealed-final').glob('chunk-*/*/environment/scenario.json') for n in read(p)['source_numbers']})}
    training_source_ids=set()
    result['source_partitions_disjoint']=all(not source_sets[i]&source_sets[j] for i in range(3) for j in range(i+1,3))
    for name,model in study_roster(study).items():
        state=CampaignRegistry(study/(name+'-campaign.json')).snapshot()
        integrity=validate_study(ROOT,study,state)
        selection_integrity=validate_selection_packages(ROOT,study,state)
        base=evaluation(study/state['protocol'].get('baseline_directory','cache-repair/base'),state['protocol']['selection_tasks'])
        if public_summary(state['baseline'])!=public_summary(base):raise ValueError('baseline registry mismatch')
        campaign={'name':name,'researcher':model,'baseline':base,'attempts':[],'factories':[],
            'used_training_tokens':state['used_training_tokens'],'training_token_budget':state['protocol']['training_token_budget'],
            'max_attempts':state['protocol']['max_attempts'],'selected':state['selected'],'selection_score':state['best_score'],
            'selection_frozen':state['final_selection'] is not None,'pending_training':len(state['reservations']),
            'protocol_hash':state['protocol_hash'],'runtime_hashes':integrity['runtime_hashes'],'selection_package_hashes':selection_integrity['task_package_hashes']}
        prior=state['baseline'];incumbent='base';best=prior['score'];total=0
        for record in state['attempts']:
            number=int(record['attempt_id'].split('-')[-1]);factory_root=study/state['protocol']['factory_directory'] if state['protocol'].get('factory_directory') else ROOT/'work';factory=factory_root/f'factory-{name}-{number:02}'
            fr=read(factory/'result.json');verify_factory_identity(factory,model,manifest.get('teacher','gpt-5.6-sol'));corpus,_,incomplete=restore_corpus(factory,registry)
            if incomplete:raise ValueError('unresolved teacher episode')
            receipt_counts=collections.Counter()
            for receipt_path in (factory/'controller').glob('researcher-receipt-*.json'):
                receipt=read(receipt_path)
                if receipt.get('requested_model')!=model or receipt.get('reported_model')!=model:
                    raise ValueError('researcher provider receipt identity differs from declared model')
                receipt_counts[(receipt['requested_model'],receipt['reported_model'],receipt.get('status'))]+=1
            histories=read(factory/'research-history.json')
            events=[h for h in histories if h['action'].get('type')=='rollout']
            new_episodes=[]
            for event in events:
                eid=event['reply'].get('episode_id')
                if eid:
                    p=factory/'controller'/eid;r=read(p/'result.json');case=read(p/'case.json')
                    new_episodes.append({'episode':eid,'mode':case['kind'],'steps':r['steps'],
                        'success':r['verification'].get('success'),'infrastructure_error':r.get('infrastructure_error'),
                        'sandbox_destroyed':r.get('sandbox_destroyed'),'result_sha256':sha(p/'result.json'),
                        'available_receipts':len(read(p/'receipts.json')) if (p/'receipts.json').exists() else 0,
                        'terminal_error_receipt_available':any(x.get('error') for x in read(p/'receipts.json')) if r.get('infrastructure_error') and (p/'receipts.json').exists() else None})
            campaign['factories'].append({'round':number,'complete':fr['complete'],'research_turns':fr['research_turns'],
                'resources':fr['budget']['reserved'],'resource_limits':fr['budget']['limits'],
                'verified_episodes_available':len(corpus.episodes),'new_episodes':new_episodes,
                'model_receipts':[{'requested_model':k[0],'reported_model':k[1],'status':k[2],'count':v} for k,v in sorted(receipt_counts.items())],
                'wall_seconds':fr.get('wall_elapsed_seconds',fr['elapsed_seconds']),
                'history_sha256':sha(factory/'research-history.json')})
            row={'round':number,'dataset_sha256':record['dataset_hash'],'training_tokens':record['training_tokens'],
                 'promoted':record['promoted'],'accounting':record.get('accounting','historical import before reservation guard')}
            if record['training_manifest']:
                data=factory/'train_messages.jsonl';rows=corpus.validate_submission(data.read_text());training=read(record['training_manifest'])
                training_source_ids.update(n for r in rows for n in r['source_numbers'])
                if sha(data)!=record['dataset_hash'] or training['data_sha256']!=record['dataset_hash']:
                    raise ValueError('training dataset mismatch')
                if (not training.get('verified_training_and_sampling') or training['scheduled_tokens']!=record['training_tokens']
                    or training['steps_requested']!=32 or len(training['events'])!=32 or training['record_count']!=len(rows)
                    or training['covered_records']!=len(rows) or training['training_profile']!='factory-v1'):
                    raise ValueError('training proof mismatch')
                path=study/'cache-repair'/name if number==1 and not state['protocol'].get('round1_layout') else study/f'round-{number}'/('eval-'+name)
                if record.get('evaluation_path'):path=Path(record['evaluation_path'])
                if record.get('recovery'):
                    original=evaluation(Path(record['recovery']['original_path']),state['protocol']['selection_tasks'])
                    if public_summary(original)!=public_summary(record['original_evaluation']):raise ValueError('original recovery evidence changed')
                    row['original_evaluation']=original
                    row['recovery_plan_sha256']=sha(record['recovery']['plan_path'])
                    path=Path(record['evaluation_path'])
                ev=evaluation(path,state['protocol']['selection_tasks'])
                if (path.parent/'remote-completion.json').exists():
                    row['remote_execution']=audit_remote(path.parent,state['protocol']['selection_tasks'],digest(training['checkpoint']))
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
    result['source_records_used']['training_supervision']=len(training_source_ids)
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
    for execution in result['final_executions']:
        recovery=study/'final-recoveries'/execution['label']
        if not (recovery/'summary.json').exists():continue
        declaration=read(recovery/'plan.json');original=study/'final-executions'/execution['label'];plan=read(original/'plan.json')
        if declaration['original_plan_sha256']!=sha(original/'plan.json') or declaration['original_summary_sha256']!=sha(original/'summary.json') or declaration['checkpoint_sha256']!=execution['checkpoint_sha256']:
            raise ValueError('final recovery original binding mismatch')
        started=read(recovery/'started.json')['started_at']
        if started<execution['started_at']:raise ValueError('recovery predates original final execution')
        retries=[];retry_proofs=[]
        for item in declaration['cases']:
            matches=[]
            for p in original.glob('chunk-*/harbor/checkpoint-browser/*/result.json'):
                raw=read(p)
                if raw['task_name']==item['task']:matches.append((p,raw))
            if len(matches)!=1:raise ValueError('ambiguous original recovery case')
            p,raw=matches[0]
            if sha(p)!=item['original_result_sha256'] or raw.get('agent_setup') is not None or raw.get('agent_execution') is not None or (p.parent/'agent/trace.json').exists():
                raise ValueError('recovery case was not an untouched pre-agent failure')
            ev=evaluation(recovery/item['task'],[item['task']]);ok=verify_execution(recovery/item['task'],plan)
            if len(ev['tasks'])!=1:raise ValueError('recovery task identity mismatch')
            row=ev['tasks'][0]
            if not ok:row.update(score=None,error_type=row.get('error_type') or 'RecoveryInfrastructureError')
            retries.append(row);retry_proofs.extend(ev['proof'])
        recovered=replace_build_failures(execution['evaluation'],retries,execution['evaluation']['expected_tasks'])
        if recovered!=read(recovery/'summary.json'):raise ValueError('recovered final score differs from evidence')
        execution['recovered_evaluation']=recovered
        execution['recovery']={'policy':declaration['policy'],'new_independent_repetition':False,
            'retried_tasks':[r['task'] for r in retries],'started_at':started,'plan_sha256':sha(recovery/'plan.json'),'proof':retry_proofs}
    superseded,remote_recoveries_finished=audit_full_suite_recoveries(study,result['final_executions'],evaluation)
    comparison=study/'final-comparison.json'
    if comparison.exists():
        plan=read(comparison);result['final_comparison']=plan
        by_label={r['label']:r for r in result['final_executions']}
        for role,labels in plan['bindings'].items():
            s=CampaignRegistry(study/((next(iter(study_roster(study))) if role=='base' else role)+'-campaign.json')).snapshot()
            expected=make_plan(ROOT,study,s,'base' if role=='base' else 'selected')['binding']['checkpoint_sha256']
            for label in labels:
                if label in by_label and (by_label[label]['checkpoint_sha256']!=expected or by_label[label]['started_at']<plan['created_at']):
                    raise ValueError('final comparison identity or timing mismatch')
        result['all_final_executions_finished']=all(r['label'] in by_label for r in plan['executions'])
    else:result['all_final_executions_finished']=False
    result['all_final_recoveries_finished']=remote_recoveries_finished and all(
        not any(t.get('error_type')=='BuildException' for t in run['evaluation']['tasks']) or 'recovered_evaluation' in run
        for run in result['final_executions'])
    recovery_root=study/'final-recoveries'
    if recovery_root.exists():
        result['all_final_recoveries_finished']=result['all_final_recoveries_finished'] and all(
            (p.parent/'summary.json').exists() or p.parent.name in superseded for p in recovery_root.glob('*/plan.json'))
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
