"""Execute one feedback-driven factory round through fixed real services."""
import argparse,hashlib,json,os,subprocess,sys,time
from pathlib import Path
from cursibench.factory_campaign import CampaignRegistry
from cursibench.factory_results import summarize,selection_feedback
from cursibench.factory_preflight import preflight,SubmissionRejected

ROOT=Path(__file__).resolve().parents[1]

def write(path,value):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,indent=2));temp.replace(path)

def child(command,directory,label):
    directory.mkdir(parents=True,exist_ok=True)
    log=directory/(label+'.log');status=directory/(label+'-process.json')
    if log.exists():raise RuntimeError('phase already exists; inspect its recorded process/result before resuming')
    with log.open('w') as stream:
        process=subprocess.Popen(command,cwd=ROOT,env=dict(os.environ,PYTHONPATH=str(ROOT/'src')),stdout=stream,stderr=subprocess.STDOUT)
        write(status,{'pid':process.pid,'started_at':time.time(),'label':label})
        result=process.wait()
    write(status,{'pid':process.pid,'finished_at':time.time(),'return_code':result,'label':label})
    if result:raise RuntimeError(label+' process failed')

def run(study,name,number):
    study=Path(study).resolve();registry=CampaignRegistry(study/(name+'-campaign.json'));state=registry.snapshot()
    if not 1<=number<=state['protocol']['max_attempts']:raise ValueError('round outside declared budget')
    if number!=len(state['attempts'])+1:raise ValueError('round must follow the recorded history')
    if state['baseline'] is None:raise ValueError('matched baseline must finish first')
    if state['final_selection'] is not None:raise ValueError('search already frozen')
    if state['best_score']==1:
        print(json.dumps({'stopped':'selection ceiling reached'}));return
    # A conservative upper bound is checked before paid generation as well.
    pending=sum(r['token_bound'] for r in state['reservations'].values())
    if state['used_training_tokens']+pending+262144>state['protocol']['training_token_budget']:
        print(json.dumps({'stopped':'insufficient conservative training reservation'}));return
    factory_root=study/state['protocol']['factory_directory'] if state['protocol'].get('factory_directory') else ROOT/'work'
    parent=factory_root/f'factory-{name}-{number-1:02}' if number>1 else None
    if parent and not (parent/'result.json').exists():raise ValueError('previous factory must be completed')
    factory=factory_root/f'factory-{name}-{number:02}'
    work=study/f'round-{number}';work.mkdir(exist_ok=True)
    feedback={'baseline':selection_feedback(state['baseline']),
        'candidate_history':[{'attempt':r['attempt_id'],'feedback':selection_feedback(r['evaluation']),'promoted':r['promoted']} for r in state['attempts'] if r['evaluation'].get('tasks')],
        'submission_rejections':[{'attempt':r['attempt_id'],'feedback':r['submission_feedback']} for r in state['attempts'] if 'submission_feedback' in r],
        'incumbent':state['selected'],'remaining_training_tokens':state['protocol']['training_token_budget']-state['used_training_tokens'],
        'fixed_training_contract':{'profile':'factory-v1','steps':32,'batch_size':2,'max_records_with_full_coverage':64,'max_sequence_tokens':16384,'scheduled_token_cap':262144,'student_output_tokens':512},
        'instruction':'Use selection feedback to revise the inherited executable data factory. Final-test evidence is unavailable. Preserve demonstrated skills while improving weak task families.'}
    feedback_path=work/(name+'-feedback.json');write(feedback_path,feedback)
    model={'astra':'gpt-6-astra','sol':'gpt-5.6-sol'}[name]
    command=[sys.executable,'-m','cursibench.factory_research','--out',str(factory),'--researcher',model,'--feedback',str(feedback_path)]
    if parent:command+=['--parent',str(parent)]
    child(command,work,name+'-factory')
    factory_result=json.loads((factory/'result.json').read_text())
    if not factory_result.get('complete'):
        report={'accepted':False,'reason':'research round ended without a verified submission','research_turns':factory_result['research_turns']}
        registry.record_submission_rejection(f'round-{number}',None,report)
        print(json.dumps({'researcher':name,'attempt':f'round-{number}','status':'no_submission'}));return
    data=factory/'train_messages.jsonl'
    try:pre=preflight(data)
    except SubmissionRejected as exc:
        write(work/(name+'-preflight-rejected.json'),exc.report)
        registry.record_submission_rejection(f'round-{number}',hashlib.sha256(data.read_bytes()).hexdigest(),exc.report)
        print(json.dumps({'researcher':name,'attempt':f'round-{number}','status':'submission_rejected'}));return
    write(work/(name+'-preflight.json'),pre)
    attempt=f'round-{number}'
    registry.reserve_training(attempt,pre['data_sha256'],pre['scheduled_tokens'])
    training=work/('train-'+name)
    try:
        child([sys.executable,'-m','cursibench.tinker_backend','--data',str(data),'--out',str(training),'--steps','32','--profile','factory-v1'],work,name+'-training')
    except Exception:
        registry.record_training_failure(attempt,'training process failed; reservation retained');raise
    metadata=json.loads((training/'training.json').read_text())
    if not metadata.get('verified_training_and_sampling') or metadata['scheduled_tokens']!=pre['scheduled_tokens'] or metadata['data_sha256']!=pre['data_sha256']:
        registry.record_training_failure(attempt,'training evidence does not match frozen preflight');raise RuntimeError('training mismatch')
    evaluation=work/('eval-'+name)
    child([sys.executable,str(ROOT/'tools/run_cloud_chain.py'),'--out',str(evaluation),'--training',str(training/'training.json'),
           '--task',str(study/'selection'),'--factory','--environment','journal','--concurrency','3','--job-timeout','2700'],work,name+'-evaluation')
    summary=summarize(evaluation,state['protocol']['selection_tasks']);write(evaluation/'summary.json',summary)
    admitted=registry.register(attempt,pre['data_sha256'],training/'training.json',metadata['scheduled_tokens'],summary)
    print(json.dumps({'researcher':name,'attempt':attempt,'status':summary['status'],'score':summary['score'],'promoted':admitted['promoted']}),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--study',default='work/factory-study-02');parser.add_argument('--researcher',choices=['astra','sol'],required=True);parser.add_argument('--round',type=int,required=True);a=parser.parse_args();run(a.study,a.researcher,a.round)
