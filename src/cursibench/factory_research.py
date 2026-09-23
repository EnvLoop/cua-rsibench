"""Researcher-controlled executable data factory behind fixed, private services."""
import argparse
import fcntl
import os
import json
import time
from pathlib import Path
from .agentrouter import response_receipt,ProviderFailure,RESEARCHER_CHOICES,resolve_researcher_model
from .campaign_runtime import json_object
from .factory_budget import Budget
from .factory_cases import SourceRegistry,compile_case,digest,object_keys,semantic_case_key
from .factory_corpus import VerifiedCorpus
from .factory_rollout import run_case
from .factory_workspace import FactoryWorkspace

ROOT=Path(__file__).resolve().parents[2]

CONTRACT='''You are the data researcher for a native computer-use training profile. Write and revise Python programs in an isolated E2B workspace to create NEW executable training tasks from approved real source records, request fixed-teacher GUI rollouts, inspect failures, and construct a verified messages JSONL dataset. You own the generator, filtering, deduplication, representation choice, mixture and ordering. The environment, teacher service, verifier, source permissions and budgets are fixed. There is no internet, host filesystem, API key or evaluator access inside your workspace.

Return exactly JSON {"action":{...},"notes":"persistent research notes","hypothesis":"current data hypothesis"}. One action per turn.
Actions:
- {"type":"read","path":"inputs/contract.md"}: read a permitted file (long text may be truncated in feedback).
- {"type":"write","path":"factory.py","content":"Python source"}: write a workspace file.
- {"type":"run","path":"factory.py","args":[],"seconds":30}: execute Python as a non-root user in a network-isolated namespace, with resource limits. Python may read /inputs and write /workspace. Working directory is /workspace. No pip/network installs.
- {"type":"rollout","path":"tasks.json","index":0}: compile one generated case from a JSON list and run the fixed teacher in a separate real Kanboard sandbox. This consumes rollout and teacher-call budget. The controller independently verifies actual saved state.
- {"type":"submit","path":"train_messages.jsonl"}: submit the data emitted by your program. Every row must exactly match a controller-verified example in /inputs/examples.json. You may filter, reorder, duplicate or mix those records. You may choose decision-only or full-history variants. Do not fabricate observations or successful outcomes.

The integration objective is a reusable Python factory producing at least two non-identical task states, with an editing lesson and a conditional/ranking or planning lesson. Obtain two independently verified episodes, then submit a useful mixture of their behaviors. Keep tasks tractable under the fixed GUI action budget. Inspect data and service feedback to revise code; do not merely emit a hand-written dataset. This is a generation/validation integration run, not a claim of trained-student improvement.
'''

CASE_CONTRACT='''# Native training-task contract

Read `/inputs/sources.json` for the ONLY approved real issue records. Write a JSON list of task recipes from your Python generator; do not invent source facts or use source IDs absent from that file.

Common fields:
- `id`: unique lowercase slug, 3-48 characters.
- `source_numbers`: 1-16 distinct approved issue numbers. Their order determines initial native task insertion order.
- `mode`: `direct`, `rank`, or `allocation`.
- `changes`: {"owner":"Chen|Rivera|Singh","priority":1..3,"score":1..13}.
- `notes`: optional synthetic workflow notes (at most 2000 characters), rendered as inert text.

Direct: add `select_numbers`, a nonempty subset of source_numbers. This teaches native edits, save and verification.

Rank: add `where`, `order_by`, and `limit` (1..4). A predicate is {"field":"state","op":"eq","value":"open"}, or {"all":[predicates]}, or {"any":[predicates]} (depth <=3). Scalar source fields: number, state, created_at, updated_at, comment_count. Operations: eq, neq, gte, lte. Labels support {"field":"labels","op":"contains","value":"label"}. order_by is 1-3 {"field":"updated_at","direction":"asc|desc"} entries; smaller source number breaks the final tie. Empty matches are rejected. State/timestamps refer to immutable GitHub source facts, not local import status.

Allocation: add positive integer cost_limit <=200 and hour_limit <=40, plus a planning list with exactly one entry per source number. Each entry has number, cost(1..100), hours(1..20), value(0..200), optional requires(other included source number), exclusive_group(alphanumeric/hyphen string; default none), blocked(boolean). These are explicitly synthetic planning inputs. The service derives the value-maximizing feasible set, then minimum cost, then lexicographic reference tie-break. Tasks selecting zero or more than four records are rejected.

The controller constructs the native application state and RUNBOOK from these recipes. It never accepts proposed verifier targets. Authentic metadata are inserted from its source registry. The archive project and unrelated objects must remain unchanged.

Rollout feedback supplies episode identifiers and record counts. `/inputs/examples.json` contains approved records, including canonical messages, provenance and decision/history representation variants. Your Python program should read this file, apply its chosen filtering/mixture/ordering policy, and write one complete approved record per JSONL line. The submit service accepts 1..256 records and at most 2MB. Shorter inputs may be preferable to excessive full-history context. A training backend may enforce a tighter token/exposure budget separately; no training is run by this integration entrypoint.

The read-only /inputs/historical-submissions.json file lists earlier approved training mixtures by record ID. Compare and preserve useful prior data; exact duplicate datasets reuse cached results rather than creating new training evidence.

Failure traces remain available for diagnosis. A success flag authored by your code cannot register examples. Public program output and notes must be in English.
'''


def dataset_text(workspace,path):
    result=workspace.read(path)
    if 'content' not in result:raise ValueError(result.get('message','artifact read failed'))
    return result['content']


def run(out,researcher='gpt-6-astra',max_turns=20,rollout_limit=3,teacher_calls=100,resume=False,parent=None,feedback=None):
    researcher=resolve_researcher_model(researcher)
    out=Path(out).resolve();out.mkdir(exist_ok=resume,parents=True)
    lock=(out/'controller.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if resume and (out/'result.json').exists() and json.loads((out/'result.json').read_text()).get('complete'):raise ValueError('completed factory run cannot be resumed')
    private=out/'controller';private.mkdir(mode=0o700,exist_ok=resume)
    snapshot=json.loads((ROOT/'datasets/public/kanboard_issues.json').read_text())
    registry=SourceRegistry(snapshot,[r['number'] for r in snapshot['records'][:12]],
                            [r['number'] for r in snapshot['records'][12:36]])
    limits={'researcher_calls':max_turns*2,'program_runs':12,'rollouts':rollout_limit,'teacher_calls':teacher_calls}
    if resume:
        saved=json.loads((out/'spec.json').read_text());limits=saved['limits'];max_turns=saved['max_turns'];researcher=resolve_researcher_model(saved['researcher'])
    budget=Budget(private/'budget.jsonl',limits);workspace=FactoryWorkspace(out/'workspace',budget,resume=resume)
    corpus=VerifiedCorpus();history=[];notes='';submission=None;started=time.monotonic();recipes={}
    spec={'parent':str(parent) if parent else None,'feedback':feedback,'created_at':time.time(),'researcher':researcher,'teacher':'gpt-5.6-sol','max_turns':max_turns,'limits':limits,'source_hash':registry.source_hash,
          'mode':'executable-data-factory-integration','training_and_evaluation_performed':False}
    if resume:
        if saved['source_hash']!=registry.source_hash:raise ValueError('cannot resume with different source snapshot')
        spec=saved
    else:(out/'spec.json').write_text(json.dumps(spec,indent=2))
    (out/'controller-process.json').write_text(json.dumps({'pid':os.getpid(),'started_at':time.time(),'resume':resume}))
    try:
        if resume:
            from .factory_recovery import restore_corpus
            corpus,recipes,incomplete=restore_corpus(out,registry)
            if incomplete:raise RuntimeError('incomplete native episode requires explicit recovery before resuming')
            workspace.reconnect()
            history=json.loads((out/'research-history.json').read_text())
            notes='Controller resumed after interruption. Completed verified episodes and source code remain available. Continue from the existing workspace; do not rerun completed rollouts.'
            workspace.add_input('examples.json',json.dumps(corpus.export()))
            (out/'resume.json').write_text(json.dumps({'at':time.time(),'verified_episodes':len(corpus.episodes),'next_turn':budget.next_research_turn()},indent=2))
        else:
            inherited=[];parent_record={}
            if parent:
                from .factory_parent import inherit
                corpus,recipes,inherited,parent_record=inherit(parent,out,registry)
                (out/'parent.json').write_text(json.dumps(parent_record,indent=2))
                notes='Continue the inherited data factory using the supplied selection feedback. You may synthesize additional training tasks or revise filtering, representation and mixture. Existing verified episodes remain usable.'
            workspace.start({'sources.json':json.dumps(registry.training_input(),indent=2),'contract.md':CASE_CONTRACT,'examples.json':json.dumps(corpus.export()),'historical-submissions.json':json.dumps(parent_record.get('historical_submissions',[]))})
            for entry in inherited:workspace.write(entry['path'],entry['content'])

        for turn in range(budget.next_research_turn(),max_turns):
            if time.monotonic()-started>3000:break
            prompt=CONTRACT+'\n'+json.dumps({'case_contract':CASE_CONTRACT,'budget':budget.snapshot(),
                    'notes':notes,'selection_feedback':feedback,'inherited_factory':bool(parent),'recent_actions':history[-6:],'turn':turn,
                    'max_research_turns':max_turns,'remaining_research_turns_including_this':max_turns-turn,
                    'submission_deadline':'A run or write action does not submit a dataset. Reserve a final action to submit the emitted JSONL before the logical turn cap.'},ensure_ascii=False)
            raw=None
            for retry in range(2):
                budget.reserve('researcher_calls',1,f'researcher:{turn}:{retry}')
                try:raw,receipt=response_receipt(prompt,researcher,6000,240);break
                except ProviderFailure as exc:
                    (private/f'researcher-failure-{turn}-{retry}.json').write_text(json.dumps(exc.receipt))
                    if retry:raise
                    time.sleep(2)
            (private/f'researcher-receipt-{turn}.json').write_text(json.dumps(receipt,indent=2))
            (private/f'researcher-response-{turn}.txt').write_text(raw)
            action={};proposal={}
            try:
                proposal=json_object(raw);notes=str(proposal.get('notes',notes))[:6000];action=proposal['action'];object_keys(action,{'type','path','content','args','seconds','index'},{'type'});kind=action.get('type')
                if kind=='read':
                    object_keys(action,{'type','path'},{'type','path'});reply=workspace.read(action['path'])
                    if len(reply.get('content',''))>32000:reply['content']=reply['content'][:32000];reply['content_truncated']=True
                elif kind=='write':
                    object_keys(action,{'type','path','content'},{'type','path','content'});reply=workspace.write(action['path'],action['content'])
                elif kind=='run':
                    object_keys(action,{'type','path','args','seconds'},{'type','path'});reply=workspace.run(action['path'],action.get('args',[]),action.get('seconds',30))
                elif kind=='rollout':
                    object_keys(action,{'type','path','index'},{'type','path','index'})
                    candidates=json.loads(dataset_text(workspace,action['path']));index=action['index']
                    if not isinstance(candidates,list) or not 1<=len(candidates)<=16 or type(index) is not int or not 0<=index<len(candidates):raise ValueError('invalid case list or index')
                    recipe=candidates[index];case=compile_case(recipe,registry);key=semantic_case_key(case)
                    if any(r.get('case_hash')==digest(case) for r in corpus.episodes.values()):raise ValueError('this generated case already has a verified episode')
                    if key in recipes:raise ValueError('this task recipe was already executed; revise the generator')
                    episode_id=f'episode-{len(recipes):02}';recipes[key]=episode_id
                    result=run_case(case,private/episode_id,budget,model='gpt-5.6-sol',max_steps=60)
                    records=[]
                    if result.get('verification',{}).get('success') and not result.get('infrastructure_error'):
                        records=corpus.add(case,result,episode_id)
                        workspace.add_input('examples.json',json.dumps(corpus.export()))
                    workspace.add_input(episode_id+'.json',json.dumps({'case':{k:v for k,v in case.items() if k!='targets'},'trace':result['trace'],'verification':result['verification'],'infrastructure_error':result.get('infrastructure_error')}))
                    reply={'episode_id':episode_id,'verification':result['verification'],'infrastructure_error':result.get('infrastructure_error'),
                           'steps':result['steps'],'new_verified_records':len(records),'total_verified_records':len(corpus.records),'trace_file':'inputs/'+episode_id+'.json'}
                elif kind=='submit':
                    object_keys(action,{'type','path'},{'type','path'})
                    if len(corpus.episodes)<2:raise ValueError('integration requires two verified non-identical generated episodes')
                    rows=corpus.validate_submission(dataset_text(workspace,action['path']))
                    used={r['record_id'].split(':')[0] for r in rows}
                    if len(used)<2:raise ValueError('integration submission must cover two verified generated episodes')
                    if feedback and feedback.get('fixed_training_contract'):
                        from .factory_preflight import preflight_rows
                        preflight_rows(rows)
                    data=''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows)
                    (out/'train_messages.jsonl').write_text(data)
                    submission={'records':len(rows),'dataset_sha256':digest(rows),'episodes':sorted(used),'validated':True,'trained':False}
                    reply={'submission':submission}
                else:raise ValueError('unknown researcher action')
            except (ValueError,KeyError,TypeError,RecursionError) as exc:
                if not isinstance(action,dict):action={}
                reply={'error':type(exc).__name__,'message':str(exc)[:2000]}
            event={'turn':turn,'action':action,'hypothesis':proposal.get('hypothesis') if 'proposal' in locals() else None,'notes':notes,'reply':reply}
            history.append(event);(out/'research-history.json').write_text(json.dumps(history,indent=2))
            print(json.dumps({'turn':turn,'action':action.get('type'),'outcome':{k:v for k,v in reply.items() if k not in ('content','stdout','stderr')}}),flush=True)
            if submission:break
    finally:
        try:
            if workspace.sandbox:workspace.snapshot()
        except Exception as exc:(out/'workspace-preservation-error.json').write_text(json.dumps({'error':type(exc).__name__}))
        workspace.close()
        result={'spec':spec,'submission':submission,'budget':budget.snapshot(),'research_turns':len(history),'verified_generated_episodes':len(corpus.episodes),
                'elapsed_seconds':time.monotonic()-started,'wall_elapsed_seconds':time.time()-spec.get('created_at',(out/'spec.json').stat().st_mtime),'complete':submission is not None,'student_improvement_claim':False}
        (out/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
        lock.close()
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--researcher',choices=RESEARCHER_CHOICES,default='gpt-6-astra');p.add_argument('--max-turns',type=int,default=20);p.add_argument('--resume',action='store_true');p.add_argument('--parent');p.add_argument('--feedback');a=p.parse_args();run(a.out,a.researcher,a.max_turns,resume=a.resume,parent=a.parent,feedback=json.loads(Path(a.feedback).read_text()) if a.feedback else None)
