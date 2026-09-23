"""Package real-source Kanboard tasks as Harbor tasks with a separate verifier."""
import argparse,inspect,json,shutil
from pathlib import Path
from .kanboard_cases import public_issue_case,verify,build_case

START='''#!/bin/bash
set -eu
printf '%s\\n' "<?php define('API_AUTHENTICATION_TOKEN', 'fixture-setup-only-not-a-provider-secret');" > /opt/kanboard/config.php
nohup php -S 127.0.0.1:8080 -t /opt/kanboard >/app/php.log 2>&1 </dev/null &
python /app/kanboard_seed.py
nohup python /app/kanboard_rpc.py >/app/rpc.log 2>&1 </dev/null &
for i in $(seq 1 30); do if curl -sf http://127.0.0.1:4318/observe >/dev/null; then exit 0; fi; sleep 1; done
exit 1
'''
VERIFY_MAIN='''
import json
from pathlib import Path
try:
 baseline=json.loads(Path('/app/baseline.json').read_text())
 final=json.loads(Path('/app/final-db.json').read_text())
 mapping=json.loads(Path('/app/seed-map.json').read_text())
 targets=json.loads(Path('/tests/targets.json').read_text())
 result=verify(baseline,final,mapping,targets)
except Exception as e:result={'success':False,'error':type(e).__name__}
Path('/logs/verifier').mkdir(parents=True,exist_ok=True)
Path('/logs/verifier/reward.txt').write_text('1' if result['success'] else '0')
Path('/logs/verifier/evidence.json').write_text(json.dumps(result,indent=2))
'''
DOCKER='''FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends chromium curl php-cli php-sqlite3 php-mbstring php-xml php-gd php-curl php-zip fonts-dejavu && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir playwright==1.63.0
WORKDIR /app
COPY kanboard.tar.gz /tmp/kanboard.tar.gz
RUN mkdir -p /opt/kanboard && tar -xzf /tmp/kanboard.tar.gz -C /opt/kanboard --strip-components=1 && chmod -R a+rwX /opt/kanboard/data
COPY scenario.json kanboard_seed.py kanboard_rpc.py start.sh /app/
'''
CONFIG='''version = "1.0"
[metadata]
category = "computer-use"
tags = ["kanboard", "real-software", "public-source-metadata"]
[environment]
cpus = 2
memory_mb = 2048
build_timeout_sec = 1200
[agent]
timeout_sec = 1500
[verifier]
timeout_sec = 120
environment_mode = "separate"
[verifier.environment]
cpus = 1
memory_mb = 1024
build_timeout_sec = 600
[[artifacts]]
source = "/app/final-db.json"
[[artifacts]]
source = "/app/baseline.json"
[[artifacts]]
source = "/app/seed-map.json"
[[artifacts]]
source = "/app/screenshots"
'''

def export(out,kind='public',seed=51,archive='work/kanboard-1.2.54.tar.gz'):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    case=public_issue_case(seed) if kind=='public' else build_case(kind,seed)
    for directory in ('environment','tests'):(out/directory).mkdir()
    (out/'instruction.md').write_text(case['instruction'])
    (out/'task.toml').write_text(CONFIG)
    (out/'environment/scenario.json').write_text(json.dumps({k:v for k,v in case.items() if k!='targets'}))
    (out/'environment/Dockerfile').write_text(DOCKER)
    (out/'environment/start.sh').write_text(START)
    for name in ('kanboard_seed.py','kanboard_rpc.py'):shutil.copyfile(Path(__file__).with_name(name),out/'environment'/name)
    shutil.copyfile(archive,out/'environment/kanboard.tar.gz')
    (out/'tests/targets.json').write_text(json.dumps(case['targets']))
    (out/'tests/verify.py').write_text(inspect.getsource(verify)+VERIFY_MAIN)
    (out/'tests/test.sh').write_text('#!/bin/sh\nset -eu\npython /tests/verify.py\n')
    (out/'tests/Dockerfile').write_text('FROM python:3.12-slim\nWORKDIR /tests\nCOPY . /tests/\n')
    return out

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--kind',default='public');a=p.parse_args();print(export(a.out,a.kind))
