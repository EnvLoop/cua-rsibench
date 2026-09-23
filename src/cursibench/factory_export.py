"""Export generated or controller-held cases with the exact native v3 environment."""
import inspect,json,shutil
from pathlib import Path
from .kanboard_harbor_export import START,VERIFY_MAIN,CONFIG,DOCKER
from .kanboard_cases import verify
from .gui_contract import VERSION
from .factory_cases import digest


def export_case(case,out,archive='work/kanboard-1.2.54.tar.gz'):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    for name in ('environment','tests'):(out/name).mkdir()
    (out/'instruction.md').write_text(case['instruction'])
    (out/'task.toml').write_text(CONFIG+'\n[[artifacts]]\nsource = "/app/observer-errors.jsonl"\n')
    (out/'contract.json').write_text(json.dumps({'contract':VERSION,'case_sha256':digest(case),'source_partition':case['provenance']['source_split']},indent=2))
    (out/'environment/scenario.json').write_text(json.dumps({k:v for k,v in case.items() if k!='targets'}))
    (out/'environment/Dockerfile').write_text(DOCKER.replace('kanboard_rpc.py start.sh','kanboard_rpc.py stable_observer.py start.sh'))
    (out/'environment/start.sh').write_text(START)
    package=Path(__file__).parent
    for source,target in [('kanboard_seed.py','kanboard_seed.py'),('kanboard_rpc_v3.py','kanboard_rpc.py'),('stable_observer.py','stable_observer.py')]:
        shutil.copyfile(package/source,out/'environment'/target)
    shutil.copyfile(archive,out/'environment/kanboard.tar.gz')
    (out/'tests/targets.json').write_text(json.dumps(case['targets']))
    (out/'tests/verify.py').write_text(inspect.getsource(verify)+VERIFY_MAIN)
    (out/'tests/test.sh').write_text('#!/bin/sh\nset -eu\npython /tests/verify.py\n')
    (out/'tests/Dockerfile').write_text('FROM python:3.12-slim\nWORKDIR /tests\nCOPY . /tests/\n')
    return out
