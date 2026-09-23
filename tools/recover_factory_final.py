"""Replay only build-failed final cases that never reached agent setup/execution.

Original executions and scored cases are immutable. Recovery is a separately
registered first-valid result, not another research attempt or an independent repeat.
"""
import argparse,json,time,sys
from pathlib import Path
from cursibench.factory_campaign import CampaignRegistry
from cursibench.factory_final import make_plan,read,sha,verify_execution
from cursibench.factory_final_recovery import replace_build_failures
from cursibench.factory_results import summarize
from run_factory_round import child,write,ROOT


def recover(study,label):
    study=Path(study).resolve();comparison=read(study/'final-comparison.json')
    execution=next((r for r in comparison['executions'] if r['label']==label),None)
    if not execution:raise ValueError('label is not a prescribed final execution')
    if not read(study/'template-prewarm-01/result.json').get('complete'):raise ValueError('finish the serial template barrier first')
    original=study/'final-executions'/label;original_summary=read(original/'summary.json');plan=read(original/'plan.json')
    registry=CampaignRegistry(study/(execution['researcher']+'-campaign.json'));state=registry.snapshot()
    if plan!=make_plan(ROOT,study,state,execution['role'],execution['repetition']):raise ValueError('frozen original plan changed')
    failures={r['task'] for r in original_summary['tasks'] if r.get('score') is None and r.get('error_type')=='BuildException'}
    if not failures:raise ValueError('no eligible build-failed cases')
    proofs=[]
    for task in sorted(failures):
        files=[]
        for p in original.glob('chunk-*/harbor/checkpoint-browser/*/result.json'):
            r=read(p)
            if r['task_name']==task:files.append((p,r))
        if len(files)!=1:raise ValueError('original case evidence is ambiguous')
        p,raw=files[0]
        if raw.get('agent_setup') is not None or raw.get('agent_execution') is not None or (p.parent/'agent/trace.json').exists():raise ValueError('case reached agent work and is not eligible for build-only recovery')
        if (raw.get('exception_info') or {}).get('exception_type')!='BuildException':raise ValueError('unexpected original error')
        proofs.append({'task':task,'original_result_sha256':sha(p),'agent_work_started':False})
    out=study/'final-recoveries'/label;out.mkdir(parents=True,exist_ok=True)
    declaration={'original_label':label,'original_plan_sha256':sha(original/'plan.json'),'original_summary_sha256':sha(original/'summary.json'),
        'checkpoint_sha256':plan['binding']['checkpoint_sha256'],'cases':proofs,'policy':'one retry per build-failed pre-agent case; all scored original cases retained unchanged',
        'new_independent_repetition':False,'changes_to_training_or_sampling':False}
    if (out/'plan.json').exists():
        if read(out/'plan.json')!=declaration:raise ValueError('recovery declaration changed')
    else:
        write(out/'plan.json',declaration);write(out/'started.json',{'started_at':time.time()})
    retry_rows=[]
    for task in sorted(failures):
        if plan!=make_plan(ROOT,study,registry.snapshot(),execution['role'],execution['repetition']):raise ValueError('inputs changed during recovery')
        chunk=next(c for c,names in plan['chunks'].items() if task in names);destination=out/task
        if not (destination/'result.json').exists():
            command=[sys.executable,str(ROOT/'tools/run_cloud_chain.py'),'--out',str(destination),'--task',str(study/'sealed-final'/chunk/task),
                '--factory','--environment','journal','--concurrency','3','--job-timeout','2700']
            training=plan['binding']['training_manifest'];command+=['--training',training] if training else ['--base','--model',plan['binding']['model']]
            child(command,out,task+'-execution')
        wrapper_ok=verify_execution(destination,plan);summary=summarize(destination,[task])
        if summary['status'] in ('running','not_started'):raise ValueError('recovery is not finished')
        if len(summary['tasks'])!=1:raise ValueError('recovery did not produce one case result')
        row=summary['tasks'][0]
        if not wrapper_ok:row.update(score=None,error_type=row.get('error_type') or 'RecoveryInfrastructureError')
        retry_rows.append(row)
    recovered=replace_build_failures(original_summary,retry_rows,state['protocol']['final_tasks']);write(out/'summary.json',recovered)
    started=read(out/'started.json')['started_at'];registered_label=label+'-recovered'
    existing=[r for r in registry.snapshot()['final_results'] if r['label']==registered_label]
    if existing:
        if existing[0]['evaluation']!=recovered:raise ValueError('recovered registry result differs')
    else:registry.record_final(registered_label,recovered,started)
    print(json.dumps({'original_label':label,'retried_tasks':sorted(failures),'status':recovered['status'],'score':recovered['score'],'new_independent_repetition':False}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--study',default='work/factory-study-02');p.add_argument('--label',required=True);a=p.parse_args();recover(a.study,a.label)
