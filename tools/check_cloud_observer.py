"""Compare versioned observers in real E2B Kanboard without touching experiments."""
import argparse,json,time
from pathlib import Path
from e2b import Sandbox
from cursibench.kanboard_cases import public_issue_case

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--out',default='work/observer-v3-cloud-check');args=parser.parse_args()
OUT=ROOT/args.out
OUT.mkdir(exist_ok=False)
case=public_issue_case(51)
probe='''import json,statistics,time
from playwright.sync_api import sync_playwright
from kanboard_rpc import controls
from stable_observer import capture
results=[]
with sync_playwright() as pw:
 b=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
 page=b.new_page(viewport={'width':1440,'height':1050});page.set_default_timeout(8000)
 page.goto('http://127.0.0.1:8080/')
 page.locator('input[name=username]').fill('admin');page.locator('input[name=password]').fill('admin');page.locator('button[type=submit]').click()
 def measure(label):
  old=[];new=[];same=True;differences=[]
  for _ in range(5):
   t=time.monotonic();rows,_=controls(page);old.append(time.monotonic()-t)
   t=time.monotonic();frame=capture(page);new.append(time.monotonic()-t)
   latest=frame.observation['controls'];same=same and rows==latest
   if rows!=latest:differences.append({'old_only':[x for x in rows if x not in latest],'new_only':[x for x in latest if x not in rows]})
   frame.dispose()
  results.append({'surface':label,'controls':len(rows),'identical_controls':same,'differences':differences,'old_median_seconds':statistics.median(old),'new_median_seconds':statistics.median(new)})
  open('/app/probe-progress.json','w').write(json.dumps(results))
 measure('dashboard')
 page.get_by_role('link',name='Project management',exact=True).click();measure('project_management')
 project=json.load(open('/app/scenario.json'))['project']
 page.get_by_role('link',name=project,exact=True).first.click();measure('project')
 link=page.get_by_role('link',name='List',exact=True)
 if link.count():link.first.click();measure('task_list')
 page.get_by_role('link',name='Public backlog review policy',exact=False).first.click();measure('task_details')
 page.screenshot(path='/app/observer-check.png')
 b.close()
open('/app/probe-result.json','w').write(json.dumps({'checks':results}))
'''
compile(probe,'cloud-observer-probe','exec')
sb=None;result={}
try:
 sb=Sandbox.create(template='cua-kanboard-1-2-54',timeout=600)
 for name in ('kanboard_seed.py','kanboard_rpc.py','stable_observer.py'):
  sb.files.write('/app/'+name,(ROOT/'src/cursibench'/name).read_text())
 sb.files.write('/app/scenario.json',json.dumps({k:v for k,v in case.items() if k!='targets'}))
 sb.files.write('/opt/kanboard/config.php',"<?php define('API_AUTHENTICATION_TOKEN', 'fixture-setup-only-not-a-provider-secret');")
 sb.commands.run('nohup php -S 127.0.0.1:8080 -t /opt/kanboard >/app/php.log 2>&1 </dev/null &',timeout=15,user='root')
 sb.commands.run('python /app/kanboard_seed.py',timeout=90,user='root')
 sb.files.write('/app/probe.py',probe)
 sb.commands.run('nohup python /app/probe.py >/app/probe.log 2>&1 </dev/null &',timeout=10,user='root')
 for _ in range(90):
  try:
   result=json.loads(sb.files.read('/app/probe-result.json'));break
  except Exception:time.sleep(2)
 else:
  (OUT/'error.log').write_text(sb.files.read('/app/probe.log'))
  raise RuntimeError('cloud probe did not complete; see saved probe log')
 (OUT/'screenshot.png').write_bytes(sb.files.read('/app/observer-check.png',format='bytes'))
 result['all_nonmodal_controls_match']=all(x['identical_controls'] for x in result['checks'])
except Exception as exc:
 result['error_type']=type(exc).__name__
 if getattr(exc,'stderr',None):(OUT/'error.log').write_text(exc.stderr)
 raise
finally:
 if sb:
  try:sb.kill();result['sandbox_destroyed']=True
  except Exception:result['sandbox_destroyed']=False
 (OUT/'result.json').write_text(json.dumps(result,indent=2))
 print(json.dumps(result),flush=True)
