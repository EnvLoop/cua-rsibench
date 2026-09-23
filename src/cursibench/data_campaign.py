"""Budgeted RSIBench-Data-style research over real Kanboard observations.

Research changes dataset selection / validated ID augmentation only. Training,
student model, Harbor agent, app, verifier and sampling configuration stay fixed.
"""
import argparse,fcntl,json,os,subprocess,sys,time
from pathlib import Path
from .native_data_factory import extract,research
from .workbench_data import digest

ROOT=Path(__file__).resolve().parents[2]

def dump(path,data):
    p=Path(path);p.parent.mkdir(exist_ok=True,parents=True);tmp=p.with_suffix(p.suffix+'.tmp')
    tmp.write_text(json.dumps(data,indent=2));tmp.replace(p)


def child(cmd,log,root):
    if Path(log).exists():raise RuntimeError('Incomplete phase exists; inspect before restarting '+str(log))
    with Path(log).open('w') as f:
        process=subprocess.Popen(cmd,cwd=ROOT,env=dict(os.environ,PYTHONPATH=str(ROOT/'src')),stdout=f,stderr=subprocess.STDOUT)
        dump(root/'live-process.json',{'pid':process.pid,'phase':str(log),'started':time.time()})
        code=process.wait()
    if code:raise RuntimeError('phase failed: '+str(log))


def summarize_cloud(path):
    directory=Path(path)/'harbor/checkpoint-browser'
    job=json.loads((directory/'result.json').read_text())
    if not job.get('finished_at'):raise RuntimeError('Harbor job still running')
    stats=job['stats'];trials=list(directory.glob('*/result.json'))
    reward=None
    if stats['n_completed_trials']==1 and stats['n_errored_trials']==0:
        result=json.loads(trials[0].read_text());reward=result['verifier_result']['rewards']['reward']
    traces=list(directory.glob('*/agent/trace.json'))
    steps=json.loads(traces[0].read_text()) if traces else []
    valid=sum(bool(x.get('outcome',{}).get('executed') or x.get('outcome',{}).get('done')) for x in steps)
    return {'reward':reward,'infrastructure_errors':stats['n_errored_trials'],'actions':len(steps),
            'valid_action_rate':valid/len(steps) if steps else None,'input_tokens':stats.get('n_input_tokens'),
            'output_tokens':stats.get('n_output_tokens'),'cost_usd':stats.get('cost_usd')}


def run(out,researcher,teacher,baseline,rounds=5,total_training_tokens=1048576):
    root=Path(out).resolve();root.mkdir(exist_ok=False,parents=True)
    with (root/'run.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        records=extract(teacher)
        from .kanboard_harbor_export import export
        accept_task=root/'frozen-acceptance-task';test_task=root/'frozen-test-task'
        export(accept_task,seed=52);export(test_task,seed=53)
        engine_files=['kanboard_cases.py','kanboard_seed.py','kanboard_rpc.py','kanboard_harbor.py','tinker_backend.py','tinker_proxy.py','native_data_factory.py','data_campaign.py','agentrouter.py','harbor_adapter.py','http_transport.py','sample_cache.py']
        engine_hashes={name:digest(Path(__file__).with_name(name).read_text()) for name in engine_files}
        dump(root/'preflight-spec.json',{'researcher':researcher,'attempts':rounds,'total_training_tokens':total_training_tokens,'engine_hashes':engine_hashes,'source_hash':digest(records)})
        baseline_run=root/'baseline'
        child([sys.executable,str(ROOT/'tools/run_cloud_chain.py'),'--out',str(baseline_run),'--training','work/native-tinker-astra-a1/training.json','--task',str(accept_task),'--native','--base'],root/'baseline.log',root)
        base=summarize_cloud(baseline_run)
        if base['reward'] is None:raise ValueError('completed matched native baseline required')
        spec=json.loads((ROOT/'benchmarks/kanboard_data/spec.json').read_text())
        spec.update(researcher=researcher,attempts=rounds,total_training_tokens=total_training_tokens,
                    teacher_hash=digest(records),baseline_hash=digest(base),starting_reward=base['reward'],engine_hashes=engine_hashes,wall_budget_seconds=10800)
        dump(root/'frozen-spec.json',spec)
        history=[];selected=None;best=base['reward'];used=0;parent=None;started=time.monotonic()
        for number in range(1,rounds+1):
            if time.monotonic()-started>10800:break
            if any(digest(Path(__file__).with_name(name).read_text())!=hash_ for name,hash_ in engine_hashes.items()):raise RuntimeError('frozen engine changed during campaign')
            attempt=root/f'a{number:02}';attempt.mkdir()
            recipe,rows,receipt=research(records,researcher,{'baseline':base,'attempt_history':history,
                                                        'remaining_training_tokens':total_training_tokens-used},parent)
            dump(attempt/'recipe.json',recipe);dump(attempt/'researcher-receipt.json',receipt)
            data=attempt/'train_messages.jsonl';data.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            # Every attempt is capped at 262144 tokens, so reserve that entire maximum
            # before submitting a training request; unused reservation is released after.
            if used+262144>total_training_tokens:
                dump(attempt/'not_started.json',{'reason':'insufficient conservative token reservation'});break
            train=attempt/'training'
            child([sys.executable,'-m','cursibench.tinker_backend','--data',str(data),'--out',str(train),'--steps','16'],attempt/'training.log',root)
            metadata=json.loads((train/'training.json').read_text());used+=metadata['scheduled_tokens']
            evaluation=attempt/'evaluation'
            child([sys.executable,str(ROOT/'tools/run_cloud_chain.py'),'--out',str(evaluation),'--training',str(train/'training.json'),'--task',str(accept_task),'--native'],attempt/'evaluation.log',root)
            summary=summarize_cloud(evaluation)
            accepted=summary['reward'] is not None and summary['reward']>best
            if accepted:best=summary['reward'];selected=str(train/'training.json')
            record={'attempt':number,'hypothesis':recipe.get('hypothesis'),'recipe_hash':digest(recipe),
                    'training_tokens':metadata['scheduled_tokens'],'selection_evaluation':summary,'selected_as_best':accepted,
                    'best_reward':best,'cumulative_training_tokens':used}
            history.append(record);parent=recipe;dump(root/'history.json',history)
            print(json.dumps(record),flush=True)
        # Final selection cannot use any test results. Strict ties retain the baseline.
        selection={'training_manifest':selected,'selected_baseline':selected is None,'acceptance_reward':best,
                   'attempts_completed':len(history),'training_tokens':used}
        dump(root/'final-selection.json',selection)
        if any(digest(Path(__file__).with_name(name).read_text())!=hash_ for name,hash_ in engine_hashes.items()):raise RuntimeError('frozen engine changed before test')
        finals=[]
        baseline_training=str(ROOT/'work/native-tinker-astra-a1/training.json')
        for repeat in range(3):
            out_=root/f'final-test-{repeat}'
            command=[sys.executable,str(ROOT/'tools/run_cloud_chain.py'),'--out',str(out_),
                     '--training',selected or baseline_training,'--task',str(test_task),'--native']
            if selected is None:command.append('--base')
            child(command,root/f'final-test-{repeat}.log',root);finals.append(summarize_cloud(out_))
        complete=len(history)>0 and all(x['reward'] is not None for x in finals)
        result={'spec':spec,'history':history,'selection':selection,'final_test':finals,
                'final_avg':sum(x['reward'] for x in finals)/3 if complete else None,
                'complete':complete,'sustained_RSI_claim':False}
        dump(root/'result.json',result);print(json.dumps({'finished':str(root),'complete':complete,'final_avg':result['final_avg']}),flush=True)
        return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--researcher',default='gpt-6-astra');p.add_argument('--teacher',default='work/kanboard-public-sol-03/result.json');p.add_argument('--baseline',default='work/native-cloud-base');p.add_argument('--rounds',type=int,default=5);a=p.parse_args();run(a.out,a.researcher,a.teacher,a.baseline,a.rounds)
