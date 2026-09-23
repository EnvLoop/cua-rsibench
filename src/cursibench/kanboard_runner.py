"""Actual Kanboard on E2B, restricted GUI model actor and independent SQLite readback."""
import argparse
import base64
import json
import time
from pathlib import Path
from e2b import Sandbox
from .agentrouter import response_receipt,ProviderFailure
from .kanboard_cases import build_case,verify,public_issue_case,public_allocation_case
from .campaign_runtime import json_object

CONTRACT='''Operate the real Kanboard GUI. Return exactly JSON {"action":{"type":"...","control":"id","value":"..."},"memory":"your concise working notes for future steps"}. One action per turn. Allowed types: click, fill, select (option label), press (Enter/Tab/Escape), back, done. Use only control IDs in the CURRENT observation. IDs change after navigation. No arbitrary URLs, code, shell, API or database access. Keep source facts and remaining work in memory (max 6000 characters). An action that saves data should be followed by visible verification. Your task is complete only when all required edits are saved. The session is already logged in as a fixture admin.'''


def run(out,model='gpt-5.6-sol',kind='triage',seed=51,strategy='',max_steps=90):
    out=Path(out);out.mkdir(parents=True,exist_ok=False);case=public_issue_case(seed) if kind=='public' else (public_allocation_case(seed) if kind=='public-allocation' else build_case(kind,seed))
    # Never upload expected targets. The remote agent receives instruction and visible UI only.
    visible={k:v for k,v in case.items() if k!='targets'}
    import hashlib
    manifest={'case':case['id'],'model':model,'reasoning_effort':'low','max_steps':max_steps,'max_output_tokens':1200,'per_call_timeout':180,'transient_retries':1,'trial_seconds':1500,'template':'cua-kanboard-1-2-54','kanboard_version':'1.2.54','visible_sha256':hashlib.sha256(json.dumps(visible,sort_keys=True).encode()).hexdigest(),'verifier_sha256':hashlib.sha256(Path(__file__).with_name('kanboard_cases.py').read_bytes()).hexdigest(),'track':'difficulty_calibration'}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    sb=None;trace=[];receipts=[];error=None;result={};start=time.monotonic()
    try:
        sb=Sandbox.create(template='cua-kanboard-1-2-54',timeout=1800)
        out.joinpath('sandbox.json').write_text(json.dumps({'id':sb.sandbox_id,'template':'cua-kanboard-1-2-54'}))
        pkg=Path(__file__).parent
        for name in ('kanboard_seed.py','kanboard_rpc.py'):
            sb.files.write('/app/'+name,(pkg/name).read_text())
        sb.files.write('/app/scenario.json',json.dumps(visible))
        sb.files.write('/opt/kanboard/config.php',"<?php\ndefine('API_AUTHENTICATION_TOKEN', 'fixture-setup-only-not-a-provider-secret');\n")
        sb.commands.run('nohup php -S 127.0.0.1:8080 -t /opt/kanboard >/app/php.log 2>&1 </dev/null &',timeout=15,user='root')
        seeded=sb.commands.run('python /app/kanboard_seed.py',timeout=90,user='root')
        (out/'seed.log').write_text(seeded.stdout)
        baseline=json.loads(sb.files.read('/app/baseline.json'));mapping=json.loads(sb.files.read('/app/seed-map.json'))
        sb.commands.run('nohup python /app/kanboard_rpc.py >/app/rpc.log 2>&1 </dev/null &',timeout=15,user='root')
        for _ in range(20):
            try:
                obs=json.loads(sb.commands.run('curl -sf http://127.0.0.1:4318/observe',timeout=10).stdout);break
            except Exception:time.sleep(1)
        else:raise RuntimeError('Kanboard GUI failed to start')
        memory=''
        for step in range(max_steps):
            if time.monotonic()-start>1500:break
            if step:obs=json.loads(sb.commands.run('curl -sf http://127.0.0.1:4318/observe',timeout=15).stdout)
            message=CONTRACT+'\nStanding strategy:'+strategy+'\n'+json.dumps({'task':case['instruction'],'observation':obs,'memory':memory,'last_action':trace[-1]['outcome'] if trace else None})
            for attempt in range(2):
                try:
                    raw,receipt=response_receipt(message,model,1200,180);receipts.append(receipt);break
                except ProviderFailure as exc:
                    receipts.append(exc.receipt)
                    if attempt==1 or exc.receipt['error'] not in ('TimeoutError','URLError','http_502','http_503'):raise
            try:
                data=json_object(raw);action=data['action'];memory=str(data.get('memory',memory))[:6000]
                body=base64.b64encode(json.dumps(action).encode()).decode()
                reply=sb.commands.run(f"printf %s '{body}' | base64 -d | curl -sf -X POST --data-binary @- http://127.0.0.1:4318/act",timeout=20)
                outcome=json.loads(reply.stdout)
            except (ValueError,KeyError):outcome={'error':'invalid response'}
            trace.append({'step':step,'observation':obs,'response':raw,'outcome':outcome})
            (out/'trace.json').write_text(json.dumps(trace,indent=2));(out/'usage.json').write_text(json.dumps(receipts,indent=2))
            print(json.dumps({'step':step,'model':model,'case':case['id'],'action':data.get('action') if 'data' in locals() else None,'outcome':outcome}),flush=True)
            if outcome.get('done'):break
        sb.commands.run('python /app/kanboard_seed.py /app/final-db.json',timeout=20,user='root')
        final=json.loads(sb.files.read('/app/final-db.json'))
        result={'case':case['id'],'model':model,'strategy':strategy,'verification':verify(baseline,final,mapping,case['targets']),
                'steps':len(trace),'max_steps':max_steps,'elapsed_seconds':time.monotonic()-start,'baseline':baseline,'final':final,
                'mapping':mapping,'expected_targets':case['targets'],'receipts':receipts,'trace':trace,'environment':'Kanboard 1.2.54 in E2B',
                'observation':'DOM visible text and controls; screenshots recorded','infrastructure_error':None}
        # Preserve actual screenshots for human QA, without provider secrets.
        for n in (0,max(0,len(trace)-1)):
            try:(out/f'{n:03}.png').write_bytes(sb.files.read(f'/app/screenshots/{n:03}.png',format='bytes'))
            except Exception:pass
    except Exception as exc:
        result.update(case=case['id'],model=model,infrastructure_error=type(exc).__name__,verification={'success':None},steps=len(trace),receipts=receipts)
        if isinstance(exc,ProviderFailure):result['provider_failure']=exc.receipt
        if sb and 'baseline' in locals() and 'mapping' in locals():
            try:
                sb.commands.run('python /app/kanboard_seed.py /app/final-db.json',timeout=20,user='root')
                partial=json.loads(sb.files.read('/app/final-db.json'))
                result['diagnostic_verification']=verify(baseline,partial,mapping,case['targets'])
            except Exception:pass
        if sb:
            for log in ('/app/rpc.log','/app/php.log'):
                try:(out/Path(log).name).write_text(sb.files.read(log))
                except Exception:pass
        if hasattr(exc,'stderr'):(out/'command-error.log').write_text(exc.stderr)
        print('trial error',type(exc).__name__,flush=True)
    finally:
        if sb:
            try:sb.kill();result['sandbox_destroyed']=True
            except Exception:result['sandbox_destroyed']=False
        (out/'result.json').write_text(json.dumps(result,indent=2))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--model',default='gpt-5.6-sol');p.add_argument('--kind',default='triage',choices=['basic','triage','allocation','public','public-allocation']);p.add_argument('--seed',type=int,default=51);p.add_argument('--max-steps',type=int,default=90);a=p.parse_args();r=run(a.out,a.model,a.kind,a.seed,max_steps=a.max_steps);print(json.dumps({k:r.get(k) for k in ['case','model','verification','steps','infrastructure_error','sandbox_destroyed']}))
