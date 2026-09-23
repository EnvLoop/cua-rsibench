"""One complete fresh-environment evaluation of an invalid trained candidate.

The checkpoint, complete task set, actor/verifier and sampling remain fixed.
Original partial scores are retained but never mixed into the recovered mean.
"""
import argparse,json,sys,time
from pathlib import Path
from cursibench.factory_campaign import CampaignRegistry,digest
from cursibench.factory_final import validate_study,verify_execution,sha
from cursibench.factory_provenance import validate_selection_packages
from cursibench.factory_roster import study_roster
from cursibench.factory_results import summarize
from run_factory_round import child,write,ROOT


def recover(study,name,number):
    study=Path(study).resolve();model=study_roster(study)[name];registry=CampaignRegistry(study/(name+'-campaign.json'));state=registry.snapshot()
    attempt_id=f'round-{number}'
    if state['final_selection'] is not None or state['reservations'] or not state['attempts'] or state['attempts'][-1]['attempt_id']!=attempt_id:
        raise ValueError('recovery must precede further search/selection')
    attempt=state['attempts'][-1]
    if attempt['evaluation']['status']!='infrastructure_error' or not attempt['training_manifest'] or attempt.get('recovery'):
        raise ValueError('one recovery is allowed only for an infrastructure-invalid trained candidate')
    integrity=validate_study(ROOT,study,state);selection=validate_selection_packages(ROOT,study,state)
    training=json.loads(Path(attempt['training_manifest']).read_text())
    if training['data_sha256']!=attempt['dataset_hash'] or not training.get('verified_training_and_sampling'):raise ValueError('training proof mismatch')
    original=study/f'round-{number}'/('eval-'+name);out=study/'selection-recoveries'/f'{name}-round-{number}'
    declaration={'candidate':attempt_id,'researcher':model,'checkpoint_sha256':digest(training['checkpoint']),
        'training_manifest_sha256':sha(attempt['training_manifest']),'original_evaluation':attempt['evaluation'],
        'original_wrapper_sha256':sha(original/'result.json'),'selection_integrity':selection,
        'runtime_hashes':integrity['runtime_hashes'],'policy':'one full-suite fresh-environment evaluation; no retraining and no partial-score mixing'}
    out.mkdir(parents=True,exist_ok=True)
    if (out/'plan.json').exists():
        if json.loads((out/'plan.json').read_text())!=declaration:raise ValueError('recovery plan changed')
    else:
        write(out/'plan.json',declaration);write(out/'started.json',{'started_at':time.time()})
    destination=out/'evaluation'
    if not (destination/'result.json').exists():
        child([sys.executable,str(ROOT/'tools/run_cloud_chain.py'),'--out',str(destination),'--training',attempt['training_manifest'],
            '--task',str(study/'selection'),'--factory','--environment','journal','--concurrency','3','--job-timeout','2700'],out,'evaluation')
    valid=verify_execution(destination,{'binding':{'candidate':attempt_id,'checkpoint_sha256':declaration['checkpoint_sha256'],'model':training['model']}})
    summary=summarize(destination,state['protocol']['selection_tasks'])
    if summary['status'] in ('running','not_started'):raise ValueError('recovery has no finished suite; inspect provider bootstrap evidence')
    if not valid:summary.update(status='infrastructure_error',score=None)
    write(destination/'summary.json',summary)
    record=registry.recover_evaluation(attempt_id,summary,destination,original,out/'plan.json')
    print(json.dumps({'researcher':model,'candidate':attempt_id,'status':summary['status'],'score':summary['score'],'promoted':record['promoted']}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--study',required=True);p.add_argument('--researcher',required=True);p.add_argument('--round',type=int,required=True);a=p.parse_args();recover(a.study,a.researcher,a.round)
