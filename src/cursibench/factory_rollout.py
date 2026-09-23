"""Fixed teacher service: newly generated task -> native GUI -> independent state check."""
import base64
import hashlib
import json
import time
import uuid
from pathlib import Path
from .agentrouter import response_receipt,ProviderFailure
from .campaign_runtime import json_object
from .gui_contract import prompt,MAX_OUTPUT_TOKENS,MAX_MEMORY_CHARS,VERSION
from .kanboard_cases import verify
from .factory_cases import digest


def command(sandbox,text,timeout=20):
    request_id=uuid.uuid4().hex;encoded=base64.b64encode(text.encode()).decode()
    wrapped=f"python /tmp/cua_command_journal.py --root /tmp/cua-command-journal --request-id {request_id} --command-b64 '{encoded}' --timeout {timeout}"
    for attempt in range(3):
        try:return sandbox.commands.run(wrapped,timeout=timeout+10,user='root')
        except Exception:
            try:
                saved=json.loads(sandbox.files.read('/tmp/cua-command-journal/'+request_id+'.json',user='root'))
                if saved['return_code']:raise RuntimeError('remote command returned nonzero')
                from types import SimpleNamespace
                return SimpleNamespace(stdout=saved['stdout'],stderr=saved['stderr'],exit_code=saved['return_code'])
            except Exception:
                if attempt==2:raise
                time.sleep(attempt+1)


def run_case(case,out,budget,model='gpt-5.6-sol',max_steps=60):
    from e2b import Sandbox
    if case['provenance'].get('source_split')!='train':raise ValueError('teacher rollout is train-only')
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    budget.reserve('rollouts',1,'rollout:'+str(out.resolve()))
    (out/'case.json').write_text(json.dumps(case,indent=2))
    visible={k:v for k,v in case.items() if k!='targets'}
    (out/'manifest.json').write_text(json.dumps({'case_hash':digest(case),'teacher_model':model,'contract':VERSION,'max_steps':max_steps,'max_output_tokens':MAX_OUTPUT_TOKENS},indent=2))
    sandbox=None;history=[];receipts=[];result={};started=time.monotonic()
    try:
        sandbox=Sandbox.create(template='cua-kanboard-1-2-54',timeout=1800)
        (out/'sandbox.json').write_text(json.dumps({'id':sandbox.sandbox_id}))
        package=Path(__file__).parent
        for source,destination in [('kanboard_seed.py','/app/kanboard_seed.py'),('kanboard_rpc_v3.py','/app/kanboard_rpc.py'),('stable_observer.py','/app/stable_observer.py'),('command_journal.py','/tmp/cua_command_journal.py')]:
            sandbox.files.write(destination,(package/source).read_text(),user='root')
        sandbox.files.write('/app/scenario.json',json.dumps(visible),user='root')
        sandbox.files.write('/opt/kanboard/config.php',"<?php define('API_AUTHENTICATION_TOKEN', 'fixture-setup-only-not-a-provider-secret');",user='root')
        command(sandbox,'nohup php -S 127.0.0.1:8080 -t /opt/kanboard >/app/php.log 2>&1 </dev/null &',15)
        command(sandbox,'python /app/kanboard_seed.py',90)
        baseline=json.loads(sandbox.files.read('/app/baseline.json',user='root'))
        mapping=json.loads(sandbox.files.read('/app/seed-map.json',user='root'))
        command(sandbox,'nohup python /app/kanboard_rpc.py >/app/rpc.log 2>&1 </dev/null &',15)
        for _ in range(20):
            try:obs=json.loads(command(sandbox,'curl -sf http://127.0.0.1:4318/observe').stdout);break
            except Exception:time.sleep(1)
        else:raise RuntimeError('GUI service did not become ready')
        memory=''
        for step in range(max_steps):
            if time.monotonic()-started>1500:raise TimeoutError('teacher rollout wall limit reached')
            if step:obs=json.loads(command(sandbox,'curl -sf http://127.0.0.1:4318/observe').stdout)
            text=prompt(case['instruction'],obs,memory,history[-1]['outcome'] if history else None)
            for attempt in range(3):
                budget.reserve('teacher_calls',1,f'{out.name}:{step}:{attempt}')
                try:
                    response,receipt=response_receipt(text,model,MAX_OUTPUT_TOKENS,180);receipts.append(receipt);break
                except ProviderFailure as exc:
                    receipts.append(exc.receipt)
                    if attempt==2 or exc.receipt['error'] not in ('TimeoutError','URLError','http_502','http_503','http_504'):raise
                    time.sleep(1+attempt)
            try:
                parsed=json_object(response);action=parsed['action'];memory=str(parsed.get('memory',memory))[:MAX_MEMORY_CHARS]
                encoded=base64.b64encode(json.dumps(action).encode()).decode()
                outcome=json.loads(command(sandbox,f"printf %s '{encoded}' | base64 -d | curl -sf -X POST --data-binary @- http://127.0.0.1:4318/act").stdout)
            except (ValueError,KeyError):outcome={'error':'invalid response'}
            history.append({'step':step,'prompt':text,'observation':obs,'response':response,'outcome':outcome})
            (out/'trace.json').write_text(json.dumps(history,indent=2));(out/'receipts.json').write_text(json.dumps(receipts,indent=2))
            print(json.dumps({'case':case['id'],'step':step,'outcome':outcome}),flush=True)
            if outcome.get('done'):break
        command(sandbox,'python /app/kanboard_seed.py /app/final-db.json')
        final=json.loads(sandbox.files.read('/app/final-db.json',user='root'))
        result={'case':case['id'],'case_hash':digest(case),'contract':VERSION,'model':model,'steps':len(history),
                'verification':verify(baseline,final,mapping,case['targets']),'baseline':baseline,'final':final,'mapping':mapping,
                'trace':history,'infrastructure_error':None,'source_numbers':case['source_numbers']}
        for name in ('observer-metrics.jsonl','observer-errors.jsonl'):
            try:(out/name).write_text(sandbox.files.read('/app/'+name,user='root'))
            except Exception:pass
        try:
            command(sandbox,'tar -czf /app/rollout-screenshots.tar.gz -C /app screenshots',30)
            (out/'screenshots.tar.gz').write_bytes(sandbox.files.read('/app/rollout-screenshots.tar.gz',format='bytes',user='root'))
        except Exception:pass
    except Exception as exc:
        result={'case':case['id'],'case_hash':digest(case),'contract':VERSION,'model':model,'steps':len(history),'trace':history,
                'verification':{'success':None},'infrastructure_error':type(exc).__name__,'source_numbers':case['source_numbers']}
        if sandbox:
            for name in ('rpc.log','observer-errors.jsonl'):
                try:(out/name).write_text(sandbox.files.read('/app/'+name,user='root'))
                except Exception:pass
    finally:
        if sandbox:
            try:sandbox.kill();result['sandbox_destroyed']=True
            except Exception:result['sandbox_destroyed']=False
        result['elapsed_seconds']=time.monotonic()-started
        (out/'result.json').write_text(json.dumps(result,indent=2))
    return result


def examples(case,result,episode_id):
    """Reconstruct positive targets from trusted execution; never trust a success flag alone."""
    if case['provenance'].get('source_split')!='train':raise ValueError('evaluation evidence cannot become training data')
    if result.get('infrastructure_error') or result.get('case_hash')!=digest(case):raise ValueError('rollout is invalid or belongs to another case')
    checked=verify(result['baseline'],result['final'],result['mapping'],case['targets'])
    if not checked['success']:raise ValueError('rollout did not pass saved-state verification')
    records=[];memory='';last=None;history=[]
    for event in result['trace']:
        expected_prompt=prompt(case['instruction'],event['observation'],memory,last)
        if event.get('prompt')!=expected_prompt:raise ValueError('observation/response contract mismatch')
        try:
            parsed=json_object(event['response']);parsed['action'];memory=str(parsed.get('memory',memory))[:MAX_MEMORY_CHARS]
        except (ValueError,KeyError):parsed=None
        messages=[{'role':'user','content':expected_prompt},{'role':'assistant','content':event['response']}]
        if parsed and (event['outcome'].get('executed') or event['outcome'].get('done')):
            for representation,items in [('decision',messages),('history',history+messages)]:
                if len(json.dumps(items).encode())>64000:continue
                record={'record_id':f'{episode_id}:{event["step"]}:{representation}','source_split':'train',
                        'source_numbers':case['source_numbers'],'contract':VERSION,'representation':representation,
                        'episode_sha256':digest(result),'case_sha256':digest(case),'messages':items}
                records.append(record)
        history=history+messages;last=event['outcome']
    return records
