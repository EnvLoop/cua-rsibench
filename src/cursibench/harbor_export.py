"""Export real Harbor 0.23 tasks with separate verifier environments."""
import argparse,json,shutil
from pathlib import Path
from .workbench_data import suite

DOCKER='''FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends chromium curl fonts-dejavu && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir playwright==1.63.0
WORKDIR /app
COPY app.html browser_rpc.py /app/
'''
CONFIG='''version = "1.0"
[metadata]
category = "computer-use"
tags = ["browser", "synthetic", "host-agent"]
[environment]
cpus = 2
memory_mb = 2048
build_timeout_sec = 1200
[agent]
timeout_sec = 600
[verifier]
timeout_sec = 120
 environment_mode = "separate"
[verifier.environment]
cpus = 1
memory_mb = 1024
build_timeout_sec = 600
[[artifacts]]
source = "/app/final.json"
[[artifacts]]
source = "/app/screenshots"
'''
VERIFY='''import json
from pathlib import Path
expected=json.loads(Path('/tests/expected.json').read_text())
try:actual=json.loads(Path('/app/final.json').read_text()); passed=(actual==expected)
except Exception:passed=False
Path('/logs/verifier').mkdir(parents=True,exist_ok=True)
Path('/logs/verifier/reward.txt').write_text('1' if passed else '0')
print(json.dumps({'success':passed,'verifier':'exact persisted state including source integrity'}))
'''
ORACLE='''import json,time,urllib.request
from pathlib import Path
expected=json.loads(Path('/solution/expected.json').read_text())
visible=json.loads(Path('/solution/visible.json').read_text())
for _ in range(30):
 try:urllib.request.urlopen('http://127.0.0.1:4318/observe');break
 except Exception:time.sleep(1)
def act(a):
 r=urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:4318/act',data=json.dumps({'actions':[a]}).encode(),headers={'Content-Type':'application/json'}))
 assert not json.load(r).get('error')
for row in expected['records']:
 for field,kind in visible['fields'].items():
  act({'type':'select' if isinstance(kind,list) else 'fill','control':row['id']+':'+field,'value':row[field]})
act({'type':'click','control':'save'});act({'type':'click','control':'confirm'})
assert json.load(urllib.request.urlopen('http://127.0.0.1:4318/finalize'))==expected
'''

def export(out,split='train'):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    package=Path(__file__).parent
    for case in suite():
        if case.split!=split:continue
        task=out/case.id
        for directory in ('environment','tests','solution'):(task/directory).mkdir(parents=True)
        (task/'task.toml').write_text(CONFIG)
        (task/'instruction.md').write_text(case.instruction+'\nUse the browser-only action interface. Persist the result through Save and Confirm.\n')
        (task/'environment/Dockerfile').write_text(DOCKER)
        (task/'environment/app.html').write_text((package/'web/workbench.html').read_text().replace('VISIBLE_TASK',json.dumps(case.visible()).replace('</','<\\/')))
        shutil.copyfile(package/'cloud_browser_rpc.py',task/'environment/browser_rpc.py')
        expected={'records':case.expected,'source':case.source,'policy':case.policy}
        (task/'tests/expected.json').write_text(json.dumps(expected))
        (task/'tests/verify.py').write_text(VERIFY)
        (task/'tests/test.sh').write_text('#!/bin/sh\nset -eu\npython /tests/verify.py\n')
        (task/'tests/Dockerfile').write_text('FROM python:3.12-slim\nWORKDIR /tests\nCOPY . /tests/\n')
        (task/'solution/expected.json').write_text(json.dumps(expected))
        (task/'solution/visible.json').write_text(json.dumps(case.visible()))
        (task/'solution/oracle.py').write_text(ORACLE)
        (task/'solution/solve.sh').write_text('#!/bin/sh\nset -eu\nnohup python /app/browser_rpc.py >/app/browser.log 2>&1 </dev/null &\npython /solution/oracle.py\n')
    return out

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--split',choices=['train','acceptance','test'],default='train');a=p.parse_args();print(export(a.out,a.split))
