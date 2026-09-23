"""Real checkpoint -> E2B proxy -> Harbor/E2B browser task -> separate verifier."""
import json,os,secrets,subprocess,sys,time
from pathlib import Path
from e2b import Sandbox
root=Path(__file__).resolve().parents[1]
import argparse
p=argparse.ArgumentParser();p.add_argument('--out',default='work/cloud-chain-01');p.add_argument('--training');p.add_argument('--model');p.add_argument('--task',default='work/harbor-tasks/support-train');p.add_argument('--native',action='store_true');p.add_argument('--factory',action='store_true');p.add_argument('--concurrency',type=int,default=1);p.add_argument('--job-timeout',type=int,default=1800);p.add_argument('--base',action='store_true');p.add_argument('--environment',choices=['bounded','read-retry','journal'],default='bounded');a=p.parse_args()
if not 1<=a.concurrency<=3 or not 60<=a.job_timeout<=2700:raise SystemExit('bounded execution requires concurrency 1..3 and timeout 60..2700')
from cursibench.cloud_launch import model_input
training=model_input(root/a.training if a.training else None,a.base,a.model)
out=root/a.out;out.mkdir(exist_ok=False)
environment={'bounded':'cursibench.cloud_env:BoundedE2B','read-retry':'cursibench.recovery_env:ReadRetryE2B','journal':'cursibench.journal_env:JournalE2B'}[a.environment]
task_path=root/a.task
task_count=1 if (task_path/'task.toml').exists() else len(list(task_path.rglob('task.toml')))
from cursibench.sample_cache import request_capacity
capacity=request_capacity(task_count)
secret=secrets.token_urlsafe(32);sb=None
result={'training_checkpoint':training['checkpoint'],'training_model':training['model'],'inference_kind':training['inference_kind'],'environment':a.environment,'factory_contract':a.factory,'concurrency':a.concurrency,'job_timeout_seconds':a.job_timeout,'task_count':task_count,'proxy_request_capacity':capacity}
try:
 sb=Sandbox.create(template='cua-tinker-proxy-v1',timeout=3000,envs={'TINKER_API_KEY':os.environ['TINKER_API_KEY'],'TINKER_MODEL_PATH':training['checkpoint'],'TINKER_BASE_MODEL':training['model'],'CUA_PROXY_TOKEN':secret,'CUA_TASK_COUNT':str(task_count)})
 sb.commands.run('python -c "import tinker, jinja2"',user='root',timeout=20)
 sb.files.write('/app/sample_cache.py',(root/'src/cursibench/sample_cache.py').read_text())
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
 import shutil
 local_harbor=Path(sys.executable).parent/'harbor'
 harbor=str(local_harbor) if local_harbor.exists() else (shutil.which('harbor') or str(root/'work/harbor-venv/bin/harbor'))
 cmd=[harbor,'run','-p',str(root/a.task),'-a',('cursibench.factory_harbor:FactoryTinkerAgent' if a.factory else ('cursibench.kanboard_harbor:TinkerKanboardAgent' if a.native else 'cursibench.harbor_adapter:TinkerBrowserAgent')),'-m',training['checkpoint'],'--env',environment,'-n',str(a.concurrency),'--jobs-dir',str(out/'harbor'),'--job-name','checkpoint-browser']
 with (out/'harbor.log').open('w') as log:
  process=subprocess.Popen(cmd,env=env,stdout=log,stderr=subprocess.STDOUT)
  (out/'process.json').write_text(json.dumps({'pid':process.pid,'started':time.time()}))
  result['harbor_exit']=process.wait(timeout=a.job_timeout)
 try:(out/'proxy-usage.jsonl').write_text(sb.files.read('/app/proxy-usage.jsonl'))
 except Exception:pass
except Exception as exc:
 result['error_type']=type(exc).__name__
 if 'process' in locals() and process.poll() is None:
  process.terminate()
  try:process.wait(timeout=30)
  except subprocess.TimeoutExpired:process.kill();process.wait()
 if sb:
  try:(out/'proxy.log').write_text(sb.files.read('/app/tinker-proxy.log'))
  except Exception:pass
finally:
 if sb:
  try:sb.kill();result['proxy_destroyed']=True
  except Exception:result['proxy_destroyed']=False
 (out/'result.json').write_text(json.dumps(result,indent=2))
 print(json.dumps(result),flush=True)
