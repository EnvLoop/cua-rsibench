"""Resume-aware real Kanboard harness campaign with source-disjoint final evaluation.

Quality is primary. At perfect quality, >=20% median action reduction is an explicit
secondary promotion criterion. This is action efficiency, not a monetary-cost claim.
"""
import argparse,json,re,statistics
from pathlib import Path
from .agentrouter import response_receipt
from .kanboard_runner import run
from .kanboard_cases import public_issue_case
from .workbench_data import digest


def score(results):
    valid=[r for r in results if not r.get('infrastructure_error')]
    return {'success_rate':sum(r['verification']['success'] for r in valid)/len(valid) if valid else None,
            'median_steps':statistics.median(r['steps'] for r in valid) if valid else None,
            'infrastructure_errors':len(results)-len(valid),'n':len(results)}


def gate(before,after):
    if before['infrastructure_errors'] or after['infrastructure_errors']:return False,'infrastructure_incomplete'
    if after['success_rate']>before['success_rate']:return True,'quality_gain'
    if after['success_rate']==before['success_rate']==1 and after['median_steps']<=.8*before['median_steps']:return True,'action_efficiency_gain'
    return False,'no_preregistered_gain'


def batch(root,phase,seed,strategy,executor,repeats):
    results=[]
    for repeat in range(repeats):
        path=root/f'{phase}-r{repeat}'
        if (path/'result.json').exists():
            r=json.loads((path/'result.json').read_text())
        elif path.exists():raise RuntimeError('Incomplete trial exists; inspect before resuming: '+str(path))
        else:r=run(path,executor,'public',seed,strategy,max_steps=90)
        results.append(r)
        print(json.dumps({'phase':phase,'repeat':repeat,'success':r['verification']['success'],'steps':r['steps'],'infra':r.get('infrastructure_error')}),flush=True)
    return score(results),results


def proposal(parent,training,researcher):
    views=[{'success':r['verification']['success'],'steps':r['steps'],'trajectory':r.get('trace',[])} for r in training]
    instruction='You improve a browser-use standing strategy. Use training evidence only. Diagnose wasted actions or task failures; propose general operating guidance. Do not memorize issue IDs, project names, dates or answers. Preserve correctness and source integrity. Efficient native UI workflows may help. Return JSON {"diagnosis":"...","strategy":"..."}; strategy <=2200 characters. The actor has only GUI controls, no code/API/SQL tools.'
    raw,receipt=response_receipt(instruction+'\n'+json.dumps({'parent':parent,'training':views}),researcher,1800,180)
    from .campaign_runtime import json_object
    data=json_object(raw)
    if not isinstance(data.get('strategy'),str) or not 20<=len(data['strategy'])<=2200:raise ValueError('invalid strategy')
    if re.search(r'GH-\d+|Kanboard Public Issue Review \d+',data['strategy']):raise ValueError('task identifiers in reusable strategy')
    return data,receipt


def campaign(out,rounds=5,repeats=3,executor='gpt-5.6-sol',researcher='gpt-6-astra',resume=False):
    root=Path(out)
    if root.exists() and not resume:raise ValueError('use --resume only after auditing existing run')
    root.mkdir(parents=True,exist_ok=True)
    spec={'rounds':rounds,'repeats':repeats,'executor':executor,'researcher':researcher,'steps':90,'quality_primary':True,'action_gain_threshold':.2,
          'train_seed':51,'acceptance_seed':52,'test_seed':53,'source_hashes':{str(seed):digest(public_issue_case(seed)) for seed in (51,52,53)},
          'arms':['recursive','nonrecursive'],'isolation':'remote API actor; host-held oracle; source issue IDs disjoint'}
    if (root/'spec.json').exists() and json.loads((root/'spec.json').read_text())!=spec:raise ValueError('resume spec mismatch')
    (root/'spec.json').write_text(json.dumps(spec,indent=2))
    base='Read the task and apply the visible policy through the native interface. Preserve unrelated data and verify that changes are saved.'
    train_score,train_results=batch(root,'base-train',51,base,executor,repeats)
    accept_score,_=batch(root,'base-acceptance',52,base,executor,repeats)
    selected={};histories={}
    for arm in ('recursive','nonrecursive'):
        current=base;current_accept=accept_score;current_train=train_results;history=[]
        for number in range(1,rounds+1):
            parent=current if arm=='recursive' else base
            feedback=current_train if arm=='recursive' else train_results
            folder=root/f'{arm}-{number:02}';folder.mkdir(exist_ok=True)
            file=folder/'proposal.json'
            if file.exists():data=json.loads(file.read_text())
            else:
                data,receipt=proposal(parent,feedback,researcher)
                file.write_text(json.dumps(data,indent=2));(folder/'receipt.json').write_text(json.dumps(receipt,indent=2))
            proposed=data['strategy']
            candidate_train,candidate_results=batch(folder,'train',51,proposed,executor,repeats)
            candidate_accept,_=batch(folder,'acceptance',52,proposed,executor,repeats)
            accepted,reason=gate(current_accept,candidate_accept)
            row={'round':number,'parent_hash':digest(parent),'candidate_hash':digest(proposed),'accepted':accepted,'reason':reason,'train':candidate_train,'acceptance':candidate_accept}
            if accepted:current=proposed;current_accept=candidate_accept;current_train=candidate_results
            row['inherited_hash']=digest(current);history.append(row)
            (root/f'{arm}-history.json').write_text(json.dumps(history,indent=2))
        selected[arm]=current;histories[arm]=history
    (root/'selection.json').write_text(json.dumps(selected,indent=2))
    # No test cases or scores are passed to proposal(). Selection is frozen first.
    heldout={}
    for name,strategy in [('baseline',base)]+list(selected.items()):heldout[name]=batch(root,'final-'+name,53,strategy,executor,repeats)[0]
    result={'spec':spec,'heldout':heldout,'histories':histories,'complete':all(not r['infrastructure_errors'] for r in heldout.values()),'claim_scope':'bounded prompt adaptation; no weight RSI claim'}
    (root/'result.json').write_text(json.dumps(result,indent=2));return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--rounds',type=int,default=5);p.add_argument('--repeats',type=int,default=3);p.add_argument('--resume',action='store_true');a=p.parse_args();campaign(a.out,a.rounds,a.repeats,resume=a.resume)
