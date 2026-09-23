"""Restore an expired research workspace from its complete bounded text snapshot.

Only files and approved inputs are restored; no researcher program/teacher/model
is executed, and the existing controller resource ledger is unchanged.
"""
import argparse,hashlib,json,shutil,time,re,fcntl
from pathlib import Path
from cursibench.factory_budget import Budget
from cursibench.factory_cases import SourceRegistry
from cursibench.factory_recovery import restore_corpus
from cursibench.factory_research import CASE_CONTRACT
from cursibench.factory_worker import resolve_path,MAX_BYTES
from cursibench.factory_roster import study_roster
from cursibench.factory_campaign import CampaignRegistry
from run_factory_round import ROOT,write
from restoration_io import RestorationWorkspace


def restore(study,name,number,snapshot,restoration_id=None):
    study=Path(study).resolve();model=study_roster(study)[name];state=CampaignRegistry(study/(name+'-campaign.json')).snapshot()
    if state['final_selection'] is not None or state['reservations'] or number!=len(state['attempts'])+1:raise ValueError('not an interrupted pre-training round')
    factory=study/state['protocol']['factory_directory']/f'factory-{name}-{number:02}'
    lock=(factory/'controller.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    spec=json.loads((factory/'spec.json').read_text());old_result=json.loads((factory/'result.json').read_text())
    if spec['researcher']!=model or old_result['complete']:raise ValueError('factory cannot be restored')
    snapshot=Path(snapshot).resolve();saved=json.loads(snapshot.read_text());files=saved['files']
    if not isinstance(files,list) or not files or saved.get('truncated'):raise ValueError('complete bounded snapshot required')
    if any(hashlib.sha256(f['content'].encode()).hexdigest()!=f['sha256'] for f in files):raise ValueError('snapshot file integrity mismatch')
    if len(files)>128 or len({f['path'] for f in files})!=len(files):raise ValueError('snapshot file count/identity violation')
    if any(len(f['content'].encode())>MAX_BYTES for f in files) or sum(len(f['content'].encode()) for f in files)>8_000_000:raise ValueError('snapshot size limit exceeded')
    for item in files:resolve_path(item['path'],writing=True)
    raw=json.loads((ROOT/'datasets/public/kanboard_issues.json').read_text());source=SourceRegistry(raw,[r['number'] for r in raw['records'][:12]],[r['number'] for r in raw['records'][12:36]])
    corpus,recipes,incomplete=restore_corpus(factory,source)
    if incomplete or spec['source_hash']!=source.source_hash:raise ValueError('source/episode state is not recoverable')
    budget=Budget(factory/'controller/budget.jsonl',spec['limits']);before=budget.snapshot()
    if restoration_id is not None and not re.fullmatch('[a-z0-9-]{1,40}',restoration_id):raise ValueError('invalid restoration ID')
    suffix='-'+restoration_id if restoration_id else ''
    out=study/'controller-recoveries'/f'{name}-round-{number}-workspace{suffix}';out.mkdir(parents=True,exist_ok=False)
    old_workspace=factory/'workspace'
    for filename in ('sandbox.json','initialization.json','cleanup.json'):
        p=old_workspace/filename
        if p.exists():shutil.copyfile(p,out/('old-'+filename))
    declaration={'created_at':time.time(),'researcher':model,'round':number,
        'snapshot_sha256':hashlib.sha256(snapshot.read_bytes()).hexdigest(),'restored_file_count':len(files),
        'restored_content_bytes':sum(len(f['content'].encode()) for f in files),'resource_ledger_before':before,
        'verified_episodes_retained':len(corpus.episodes),'executed_recipes_retained':len(recipes),
        'policy':'new sandbox after lease expiry; restore exact recorded file contents and approved inputs; no model/program/teacher replay or budget reset'}
    write(out/'plan.json',declaration)
    parent=json.loads((factory/'parent.json').read_text()) if (factory/'parent.json').exists() else {}
    inputs={'sources.json':json.dumps(source.training_input(),indent=2),'contract.md':CASE_CONTRACT,
        'examples.json':json.dumps(corpus.export()),'historical-submissions.json':json.dumps(parent.get('historical_submissions',[]))}
    for episode in (factory/'controller').glob('episode-*'):
        case=json.loads((episode/'case.json').read_text());result=json.loads((episode/'result.json').read_text())
        inputs[episode.name+'.json']=json.dumps({'case':{k:v for k,v in case.items() if k!='targets'},'trace':result['trace'],
            'verification':result['verification'],'infrastructure_error':result.get('infrastructure_error')})
    workspace=RestorationWorkspace(out/'new-workspace')
    report={'complete':False,'model_calls':0,'program_runs':0,'teacher_calls':0}
    try:
        workspace.start(inputs,(ROOT/'src/cursibench/factory_worker.py').read_text())
        for item in files:
            reply=workspace.restore_file(item)
            if reply.get('sha256')!=item['sha256']:raise ValueError('restored content hash mismatch')
        verified=workspace.snapshot()
        if {f['path']:f['sha256'] for f in verified['files']}!={f['path']:f['sha256'] for f in files}:raise ValueError('restored complete snapshot mismatch')
        if budget.snapshot()!=before:raise ValueError('restoration changed researcher resource ledger')
        # Switch the reconnect descriptor only after all contents are verified.
        descriptor=json.loads((out/'new-workspace/sandbox.json').read_text())
        write(old_workspace/'sandbox.json',descriptor)
        write(old_workspace/'restoration.json',{'at':time.time(),'plan_sha256':hashlib.sha256((out/'plan.json').read_bytes()).hexdigest(),'resource_ledger_unchanged':True})
        report.update(complete=True,resource_ledger_after=budget.snapshot(),finished_at=time.time())
    except Exception as exc:
        report['error_type']=type(exc).__name__;workspace.close();raise
    finally:
        workspace.save_io_receipt()
        write(out/'result.json',report)
        lock.close()
    print(json.dumps({'restored':True,'files':len(files),'model_calls':0,'program_runs':0,'budget_unchanged':True}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--study',required=True);p.add_argument('--researcher',required=True);p.add_argument('--round',type=int,required=True);p.add_argument('--snapshot',required=True);p.add_argument('--restoration-id');a=p.parse_args();restore(a.study,a.researcher,a.round,a.snapshot,a.restoration_id)
