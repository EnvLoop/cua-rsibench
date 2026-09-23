"""Real checkpoint -> E2B proxy -> Harbor/E2B browser task -> separate verifier."""
import json,os,secrets,subprocess,time
from pathlib import Path
from e2b import Sandbox
root=Path(__file__).resolve().parents[1]
out=root/'work/cloud-chain-01';out.mkdir(exist_ok=False)
training=json.loads((root/'work/tinker-sft-03/training.json').read_text())
if not training.get('verified_training_and_sampling'):raise SystemExit('verified training required')
secret=secrets.token_urlsafe(32);sb=None
result={'training_checkpoint':training['checkpoint'],'training_model':training['model']}
try:
 sb=Sandbox.create(template='support-train__272943137319',timeout=1800,envs={'TINKER_API_KEY':os.environ['TINKER_API_KEY'],'TINKER_MODEL_PATH':training['checkpoint'],'TINKER_BASE_MODEL':training['model'],'CUA_PROXY_TOKEN':secret})
 sb.commands.run('pip install tinker==0.30.0 jinja2',user='root',timeout=240)
 sb.files.write('/app/tinker_proxy.py',(root/'src/cursibench/tinker_proxy.py').read_text())
 sb.commands.run('nohup python /app/tinker_proxy.py >/app/tinker-proxy.log 2>&1 </dev/null &',user='root',timeout=10)
 for _ in range(90):
  try:
   health=sb.commands.run('curl -sf http://127.0.0.1:8088/health',timeout=10)
   if json.loads(health.stdout).get('ready'):break
  except Exception:pass
  time.sleep(2)
 else:raise RuntimeError('proxy not ready')
 result['proxy_ready']=True
 env=os.environ.copy();env['CUA_TINKER_PROXY_URL']='https://'+sb.get_host(8088);env['CUA_PROXY_TOKEN']=secret;env['PYTHONPATH']=str(root/'src')
 cmd=[str(root/'work/harbor-venv/bin/harbor'),'run','-p',str(root/'work/harbor-tasks/support-train'),'-a','cursibench.harbor_adapter:TinkerBrowserAgent','-m',training['checkpoint'],'--env','cursibench.cloud_env:BoundedE2B','-n','1','--jobs-dir',str(out/'harbor'),'--job-name','checkpoint-browser']
 with (out/'harbor.log').open('w') as log:
  process=subprocess.Popen(cmd,env=env,stdout=log,stderr=subprocess.STDOUT)
  (out/'process.json').write_text(json.dumps({'pid':process.pid,'started':time.time()}))
  result['harbor_exit']=process.wait(timeout=900)
 try:(out/'proxy-usage.jsonl').write_text(sb.files.read('/app/proxy-usage.jsonl'))
 except Exception:pass
except Exception as exc:
 result['error_type']=type(exc).__name__
 if sb:
  try:(out/'proxy.log').write_text(sb.files.read('/app/tinker-proxy.log'))
  except Exception:pass
finally:
 if sb:
  try:sb.kill();result['proxy_destroyed']=True
  except Exception:result['proxy_destroyed']=False
 (out/'result.json').write_text(json.dumps(result,indent=2))
 print(json.dumps(result),flush=True)
