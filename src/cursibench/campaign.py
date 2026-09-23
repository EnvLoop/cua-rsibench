"""Five-round, model-proposed prompt adaptation with sealed final evaluation.

The held-out cases are withheld from all proposal requests and only instantiated by
the trusted evaluator. Agents are remote API policies, never arbitrary local code.
"""
import argparse
import copy
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from .campaign_runtime import BASE_PROMPT, Ledger, trial, json_object, verify_ledger, BudgetExhausted
from .agentrouter import ProviderFailure
from .workbench_data import suite,digest


def aggregate(results):
    valid=[r for r in results if r['verification']['success'] is not None]
    groups={}
    for r in valid:groups.setdefault(r['task_id'],[]).append(int(r['verification']['success']))
    return {'success_rate':sum(int(r['verification']['success']) for r in valid)/len(valid) if valid else None,
            'valid':len(valid),'total':len(results),'infrastructure_errors':len(results)-len(valid),
            'by_task':{k:sum(v)/len(v) for k,v in groups.items()},
            'input_tokens':sum(r['usage']['input_tokens'] for r in results),
            'output_tokens':sum(r['usage']['output_tokens'] for r in results),
            'unknown_usage_calls':sum(r['usage']['unknown_calls'] for r in results),
            'cost_usd':None,'steps':sum(r['steps'] for r in results)}


def promotion(incumbent,candidate):
    if incumbent['infrastructure_errors'] or candidate['infrastructure_errors']:return False,'infrastructure_incomplete'
    if set(incumbent['by_task'])!=set(candidate['by_task']):return False,'task_mismatch'
    if any(candidate['by_task'][k]<v for k,v in incumbent['by_task'].items()):return False,'task_regression'
    if candidate['success_rate']<=incumbent['success_rate']:return False,'no_strict_gain'
    return True,'strict_gain_without_task_regression'


def evaluate(cases,prompt,model,path,ledger,repeats=3,workers=2):
    jobs=[(case,repeat) for case in cases for repeat in range(repeats)]
    def one(job):
        case,repeat=job
        result=trial(case,prompt,model,path/f'{case.id}-r{repeat}',ledger)
        print(json.dumps({'trial':str(path.name),'task':case.id,'repeat':repeat,'success':result['verification']['success'],'error':result['infrastructure_error']}),flush=True)
        return result
    with ThreadPoolExecutor(max_workers=workers) as pool:results=list(pool.map(one,jobs))
    summary=aggregate(results);(path/'summary.json').write_text(json.dumps(summary,indent=2))
    return summary,results


def feedback(results):
    # This function is called only on train results; no final/acceptance trajectories.
    return [{'family':r['family'],'success':r['verification']['success'],
             'steps':r['steps'],'termination':r['termination'],'trajectory':r['trace']}
            for r in results]


def propose(parent,train_results,model,ledger,round_,arm):
    text='''You are the researcher for a browser-use harness experiment. Improve ONLY the reusable standing strategy. Do not change tasks, scoring, tools, budgets or models. Diagnose visible training trajectories; propose general rules rather than memorizing IDs, numbers, or answers. Preserve helpful parts of the inherited strategy. Return JSON with "diagnosis" (short string), "strategy" (string, maximum 2200 characters). If all tasks succeed, an honest unchanged proposal is allowed. No guaranteed improvement is required.\n'''
    raw,receipt=ledger.call(text+json.dumps({'parent_strategy':parent,'train_feedback':feedback(train_results)}),model,f'proposal:{arm}:{round_}')
    data=json_object(raw)
    if not isinstance(data.get('strategy'),str) or not 20<=len(data['strategy'])<=2200:raise ValueError('invalid strategy length')
    if not isinstance(data.get('diagnosis'),str):raise ValueError('missing diagnosis')
    return data


def run(out,rounds=5,repeats=3,seed=230923,executor='gpt-5.6-sol',researcher='gpt-6-astra',workers=2,arms=('recursive','nonrecursive')):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    data=suite(seed);train=[c for c in data if c.split=='train'];accept=[c for c in data if c.split=='acceptance']
    # Seal before any API call, no hidden task content in model prompts or public manifest.
    test=[c for c in data if c.split=='test']
    manifest={'source_hashes':{name:digest(Path(__file__).with_name(name).read_text()) for name in ('campaign.py','campaign_runtime.py','workbench_data.py','agentrouter.py')},'app_hash':digest(Path(__file__).with_name('web').joinpath('workbench.html').read_text()),'version':'0.3.0','rounds':rounds,'repeats':repeats,'seed':seed,'executor':executor,'researcher':researcher,
              'workers':workers,'arms':arms,'action_space':'visible DOM controls','max_steps':12,'trial_seconds':240,
              'split_hashes':{s:digest([asdict(c) for c in data if c.split==s]) for s in ('train','acceptance','test')},
              'counts':{s:sum(c.split==s for c in data) for s in ('train','acceptance','test')},
              'request_cap':1800,'input_byte_cap':30000000,'campaign_seconds':14400,
              'isolation':'host-held expected state; remote API agent has only visible observations; prompt-only edits',
              'limitations':['synthetic app','small related task families; not unseen-app transfer','single search seed','provider cost unknown']}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2));(out/'manifest.sha256').write_text(digest(manifest))
    ledger=Ledger(out/'ledger.jsonl',1800,30000000,14400)
    ledger.append('manifest',manifest)
    base_train,base_train_results=evaluate(train,BASE_PROMPT,executor,out/'base-train',ledger,repeats,workers)
    base_accept,_=evaluate(accept,BASE_PROMPT,executor,out/'base-acceptance',ledger,repeats,workers)
    chosen={};histories={}
    for arm in arms:
        current=BASE_PROMPT;current_accept=copy.deepcopy(base_accept);current_train_results=base_train_results
        history=[]
        for round_ in range(1,rounds+1):
            parent=current if arm=='recursive' else BASE_PROMPT
            context=current_train_results if arm=='recursive' else base_train_results
            folder=out/f'{arm}-{round_:02}';folder.mkdir()
            try:
                proposal=propose(parent,context,researcher,ledger,round_,arm)
            except (ProviderFailure,ValueError,BudgetExhausted) as exc:
                entry={'round':round_,'accepted':False,'reason':type(exc).__name__,'parent_hash':digest(parent)}
                history.append(entry);ledger.append('candidate_rejected',entry)
                if isinstance(exc,BudgetExhausted):raise
                continue
            (folder/'proposal.json').write_text(json.dumps(proposal,indent=2))
            candidate=proposal['strategy']
            train_summary,train_results=evaluate(train,candidate,executor,folder/'train',ledger,repeats,workers)
            accept_summary,_=evaluate(accept,candidate,executor,folder/'acceptance',ledger,repeats,workers)
            admitted,reason=promotion(current_accept,accept_summary)
            entry={'round':round_,'arm':arm,'parent_hash':digest(parent),'candidate_hash':digest(candidate),
                   'train':train_summary,'acceptance':accept_summary,'accepted':admitted,'reason':reason,
                   'incumbent_acceptance_before':current_accept['success_rate']}
            if admitted:current=candidate;current_accept=accept_summary;current_train_results=train_results
            entry['inherited_hash']=digest(current);history.append(entry)
            ledger.append('candidate_decision',entry)
            (out/f'{arm}-history.json').write_text(json.dumps(history,indent=2))
        chosen[arm]=current;histories[arm]=history
    # Search must be finished before any held-out evaluation or scores are created.
    ledger.append('search_frozen',{'selected':{k:digest(v) for k,v in chosen.items()}})
    (out/'selection.json').write_text(json.dumps(chosen,indent=2))
    heldout={}
    for name,prompt in [('baseline',BASE_PROMPT)]+list(chosen.items()):
        summary,_=evaluate(test,prompt,executor,out/f'final-{name}',ledger,repeats,workers)
        heldout[name]=summary
    result={'manifest':manifest,'histories':histories,'heldout':heldout,
            'delta':{k:heldout[k]['success_rate']-heldout['baseline']['success_rate'] if heldout[k]['success_rate'] is not None and heldout['baseline']['success_rate'] is not None else None for k in chosen},
            'improvement_claim':False,'ledger_valid':verify_ledger(out/'ledger.jsonl'),
            'complete':all(v['infrastructure_errors']==0 for v in heldout.values()) and all(len(h)==rounds and all('acceptance' in r and not r['acceptance']['infrastructure_errors'] and not r['train']['infrastructure_errors'] for r in h) for h in histories.values())}
    (out/'result.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({'finished':str(out),'delta':result['delta'],'complete':result['complete']}),flush=True)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--rounds',type=int,default=5);p.add_argument('--repeats',type=int,default=3);p.add_argument('--workers',type=int,default=2);args=p.parse_args();run(args.out,args.rounds,args.repeats,workers=args.workers)
