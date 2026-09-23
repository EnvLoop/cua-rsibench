"""Read-only audit of frozen v2 campaigns; exports no account or checkpoint IDs."""
import hashlib
import json,subprocess
from datetime import datetime
from pathlib import Path
from cursibench.data_campaign import summarize_cloud
from cursibench.workbench_data import digest

ROOT=Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text()) if path.exists() else None


def cloud_evidence(path):
    job=read(path/'harbor/checkpoint-browser/result.json')
    if not job or not job.get('finished_at'):
        return {'status':'running' if job else 'not_started','reward':None}
    result=summarize_cloud(path)
    result['status']='infrastructure_error' if result['infrastructure_errors'] else 'scored'
    trial=next((path/'harbor/checkpoint-browser').glob('*/result.json'))
    raw=read(trial)
    result.update(started_at=raw['started_at'],finished_at=raw['finished_at'],
                  result_sha256=hashlib.sha256(trial.read_bytes()).hexdigest(),
                  separate_verifier=raw['verifier_environment_mode']=='separate')
    verification=read(trial.parent/'verifier/evidence.json')
    if verification:result['saved_state_verification']=verification
    error=raw.get('exception_info') or {}
    if error:
        trace=error.get('exception_traceback','')
        result['error_type']=error.get('exception_type')
        result['error_stage']='observe' if '4318/observe' in trace else ('act' if '4318/act' in trace else 'other')
        result['transport_disconnect']='TLS close_notify' in trace or 'unexpected-eof' in trace
    trace=read(trial.parent/'agent/trace.json') or []
    actions=[]
    for event in trace:
        response=event.get('response','').strip()
        if response.startswith('```'):response='\n'.join(response.splitlines()[1:-1])
        try:
            action=json.loads(response)['action']
        except (ValueError,KeyError,TypeError):
            actions.append(('invalid_json',None));continue
        controls={str(c['id']):c for c in event['observation']['controls']}
        label=controls.get(str(action.get('control')),{}).get('label')
        actions.append((action.get('type'),label))
    result['action_types']={kind:sum(x[0]==kind for x in actions) for kind in sorted(set(x[0] for x in actions)) if kind}
    result['distinct_action_labels']=len(set(x for x in actions))
    if trace:result['trace_sha256']=hashlib.sha256((trial.parent/'agent/trace.json').read_bytes()).hexdigest()
    wrapper=read(path/'result.json') or {}
    result['proxy_destroyed']=wrapper.get('proxy_destroyed')
    return result


def audit(path):
    spec=read(path/'frozen-spec.json')
    history=read(path/'history.json') or []
    selection=read(path/'final-selection.json')
    result={'run':path.name,'researcher':spec['researcher'],'student':spec['target_model'],
            'source_commit':'62b99b9','baseline':cloud_evidence(path/'baseline'),
            'attempts':[],'final_tests':[],'checks':{},'cost_usd':None}
    checks=result['checks']
    checks['frozen_engine_available_at_source_commit']=all(digest(subprocess.check_output(['git','show',f'62b99b9:src/cursibench/{name}'],cwd=ROOT,text=True))==value for name,value in spec['engine_hashes'].items())
    result['engine_hashes']=spec['engine_hashes']
    train_records=[];total=0;best=result['baseline']['reward'];best_attempt=None
    for h in history:
        d=path/f'a{h["attempt"]:02}'
        training=read(d/'training/training.json');recipe=read(d/'recipe.json')
        rows=[json.loads(line) for line in (d/'train_messages.jsonl').read_text().splitlines() if line.strip()]
        evaluation=cloud_evidence(d/'evaluation')
        accepted=evaluation['reward'] is not None and evaluation['reward']>best
        if accepted:best=evaluation['reward'];best_attempt=h['attempt']
        total+=training['scheduled_tokens'];train_records.extend(rows)
        check={'data_hash_matches_training':hashlib.sha256((d/'train_messages.jsonl').read_bytes()).hexdigest()==training['data_sha256'],
               'recipe_hash_matches_history':digest(recipe)==h['recipe_hash'],
               'verified_training_and_sampling':training.get('verified_training_and_sampling') is True,
               'fixed_16_updates':training['steps_requested']==16 and len(training['events'])==16,
               'within_attempt_budget':training['scheduled_tokens']<=262144 and 1<=len(rows)<=32,
               'history_matches_actual_score':evaluation['reward']==h['selection_evaluation']['reward'],
               'strict_promotion_rule':accepted==h['selected_as_best'] and best==h['best_reward']}
        result['attempts'].append({'attempt':h['attempt'],'hypothesis':h['hypothesis'],
                                  'recipe':{k:v for k,v in recipe.items() if k in ('record_ids','augmentation','expected_effect')},
                                  'training_tokens':training['scheduled_tokens'],'cumulative_training_tokens':total,
                                  'checkpoint_sha256':hashlib.sha256(training['checkpoint'].encode()).hexdigest(),
                                  'evaluation':evaluation,'promoted':accepted,'best_reward':best,'checks':check})
    checks['train_source_only']=all(r['source_split']=='train' and r['source_issue_pack']==51 for r in train_records)
    checks['total_training_budget']=total<=spec['total_training_tokens']
    checks['history_prefix_complete']=len(history)==spec['attempts']
    def sources(task):
        return {t['reference'] for t in task['tasks'] if t['reference'].startswith('GH-')}
    from cursibench.kanboard_cases import public_issue_case
    train=sources(public_issue_case(51))
    acceptance=read(path/'frozen-acceptance-task/environment/scenario.json')
    test=read(path/'frozen-test-task/environment/scenario.json')
    accept=sources(acceptance);held=sources(test)
    checks['source_packs_disjoint']=not(train&accept or train&held or accept&held)
    checks['answers_excluded_from_agent_scenario']=all('targets' not in x for x in (acceptance,test))
    result['source_counts']={'train':len(train),'acceptance':len(accept),'test':len(held)}
    result['training_tokens']=total
    result['selection']=None
    if selection:
        result['selection']={k:v for k,v in selection.items() if k!='training_manifest'}
        result['selection']['selected_attempt']=best_attempt
        checks['selection_matches_history']=(selection['selected_baseline']==(best_attempt is None) and selection['acceptance_reward']==best and selection['training_tokens']==total)
        selection_time=(path/'final-selection.json').stat().st_mtime
        for i in range(3):
            row=cloud_evidence(path/f'final-test-{i}')
            if row.get('started_at'):
                row['selection_precedes_test']=selection_time<=datetime.fromisoformat(row['started_at'].replace('Z','+00:00')).timestamp()
            result['final_tests'].append(dict(repeat=i,**row))
    result['all_final_tests_scored']=len(result['final_tests'])==3 and all(r['status']=='scored' for r in result['final_tests'])
    result['final_avg']=sum(r['reward'] for r in result['final_tests'])/3 if result['all_final_tests_scored'] else None
    result['campaign_process_finished']=(path/'result.json').exists()
    result['transport_recoveries']=[]
    name='astra' if 'astra' in path.name else 'sol'
    for d in sorted((ROOT/'work').glob(f'recovery-{name}-a*')):
        if d.is_dir():
            result['transport_recoveries'].append({'run':d.name,'original_attempt':int(d.name.rsplit('a',1)[1]),
                                                  'protocol':'read-retries-v1','evaluation':cloud_evidence(d)})
    result['audit_pass']=all(checks.values()) and all(all(r['checks'].values()) for r in result['attempts']) and all(r.get('selection_precedes_test',True) for r in result['final_tests'])
    result['limitations']=['one task per source pack; shared task template','bounded selection / ID augmentation of one verified teacher trajectory','same seed and temperature across three final executions; not three independent task samples','training and evaluation use semantically similar but different instruction headers','no non-recursive search control; no sustained RSI claim']
    return result


if __name__=='__main__':
    reports=[audit(ROOT/'work'/f'formal-data-{name}-v2') for name in ('astra','sol')]
    out=ROOT/'outputs/data-campaigns.json';out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(reports,indent=2,ensure_ascii=False))
    for r in reports:
        print(json.dumps({k:r[k] for k in ('run','training_tokens','audit_pass','all_final_tests_scored','final_avg')}))
    directory=ROOT/'work/journal-recovery'
    if directory.exists():
        journal={'protocol':'journal-env-v1','original_results_preserved':True,'runs':[]}
        for p in sorted(directory.iterdir()):
            if p.is_dir():journal['runs'].append({'run':p.name,'evaluation':cloud_evidence(p)})
        journal['all_scored']=len(journal['runs'])==4 and all(r['evaluation']['status']=='scored' for r in journal['runs'])
        (ROOT/'outputs/journal-recovery.json').write_text(json.dumps(journal,indent=2))
        print(json.dumps({'journal_all_scored':journal['all_scored'],'results':[(r['run'],r['evaluation'].get('reward')) for r in journal['runs']]}))
