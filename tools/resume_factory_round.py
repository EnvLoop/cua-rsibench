"""Resume one interrupted pre-training factory without resetting its resource ledger."""
import argparse,fcntl,hashlib,json,shutil,sys,time,re
from pathlib import Path
from cursibench.factory_campaign import CampaignRegistry
from cursibench.factory_budget import Budget
from cursibench.factory_cases import SourceRegistry
from cursibench.factory_recovery import restore_corpus
from cursibench.factory_roster import study_roster
from run_factory_round import child,finish_submission,write,ROOT


def recovery_path(study,name,number,recovery_id=None):
    if recovery_id is not None and not re.fullmatch('[a-z0-9-]{1,40}',recovery_id):raise ValueError('invalid controller recovery ID')
    suffix='-'+recovery_id if recovery_id else ''
    return Path(study)/'controller-recoveries'/f'{name}-round-{number}{suffix}'


def resume(study,name,number,recovery_id=None,stop_before_evaluation=False):
    study=Path(study).resolve();model=study_roster(study)[name];r=CampaignRegistry(study/(name+'-campaign.json'));state=r.snapshot()
    if state['final_selection'] is not None or state['reservations'] or number!=len(state['attempts'])+1:raise ValueError('not an interrupted pre-training round')
    factory_root=study/state['protocol'].get('factory_directory','factories');factory=factory_root/f'factory-{name}-{number:02}'
    saved=json.loads((factory/'result.json').read_text());spec=json.loads((factory/'spec.json').read_text())
    if saved['complete'] or spec['researcher']!=model:raise ValueError('only incomplete exact-model factories can be resumed')
    lock=(factory/'controller.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);lock.close()
    source=json.loads((ROOT/'datasets/public/kanboard_issues.json').read_text());sources=SourceRegistry(source,[x['number'] for x in source['records'][:12]],[x['number'] for x in source['records'][12:36]])
    corpus,recipes,incomplete=restore_corpus(factory,sources)
    if incomplete:raise ValueError('unresolved native episode requires a separate recovery')
    if not (factory/'workspace/sandbox.json').exists():raise ValueError('no existing workspace identity to resume')
    budget=Budget(factory/'controller/budget.jsonl',spec['limits']);next_turn=budget.next_research_turn()
    if next_turn>=spec['max_turns']:raise ValueError('logical research turn budget exhausted')
    out=recovery_path(study,name,number,recovery_id)
    out.mkdir(parents=True,exist_ok=False)
    preserved={}
    for file in ('result.json','spec.json','research-history.json','controller/budget.jsonl','workspace/cleanup.json'):
        p=factory/file
        if p.exists():
            dest=out/'before'/file;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest);preserved[file]=hashlib.sha256(p.read_bytes()).hexdigest()
    declaration={'created_at':time.time(),'researcher':model,'round':number,'next_logical_turn':next_turn,
        'remaining_logical_turns':spec['max_turns']-next_turn,'resource_ledger_before':budget.snapshot(),
        'verified_episodes_retained':len(corpus.episodes),'executed_recipes_retained':len(recipes),
        'preserved_hashes':preserved,'stop_before_evaluation':stop_before_evaluation,
        'policy':'resume existing workspace; retain charged calls and all prior episode results; no completed rollout replay'}
    write(out/'plan.json',declaration)
    command=[sys.executable,'-m','cursibench.factory_research','--out',str(factory),'--researcher',model,'--resume',
        '--feedback',str(study/f'round-{number}'/(name+'-feedback.json'))]
    if spec.get('parent'):command+=['--parent',spec['parent']]
    child(command,out,'factory-resume')
    continuation=finish_submission(study,name,number,factory,stop_before_evaluation=stop_before_evaluation)
    write(out/'result.json',{'complete':True,'finished_at':time.time(),'resource_ledger_after':budget.snapshot(),
        'continuation_status':continuation.get('status') if continuation else 'round_finished'})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--study',required=True);p.add_argument('--researcher',required=True);p.add_argument('--round',type=int,required=True);p.add_argument('--recovery-id');p.add_argument('--stop-before-evaluation',action='store_true');a=p.parse_args();resume(a.study,a.researcher,a.round,a.recovery_id,a.stop_before_evaluation)
