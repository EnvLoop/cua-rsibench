"""Explicit new observer version; never overwrites a frozen v2 task package."""
import argparse,hashlib,json,shutil
from pathlib import Path
from .kanboard_harbor_export import export


def export_v3(out,kind='public',seed=51):
    task=export(out,kind=kind,seed=seed)
    source=Path(__file__).parent
    shutil.copyfile(source/'kanboard_rpc_v3.py',task/'environment/kanboard_rpc.py')
    shutil.copyfile(source/'stable_observer.py',task/'environment/stable_observer.py')
    docker=task/'environment/Dockerfile'
    docker.write_text(docker.read_text().replace('kanboard_rpc.py start.sh','kanboard_rpc.py stable_observer.py start.sh'))
    config=task/'task.toml'
    config.write_text(config.read_text()+''.join(f'\n[[artifacts]]\nsource = "/app/{name}"\n' for name in ('observer-metrics.jsonl','observer-errors.jsonl','rpc.log')))
    (task/'observer-version.json').write_text(json.dumps({'version':'v3','changes':['batched DOM snapshot','stable element binding','native visibility check including closed details','modal active surface','2-second screenshot timeout'],
        'source_sha256':{name:hashlib.sha256((source/name).read_bytes()).hexdigest() for name in ('kanboard_rpc_v3.py','stable_observer.py')}},indent=2))
    return task

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--kind',default='public');p.add_argument('--seed',type=int,default=51);a=p.parse_args();print(export_v3(a.out,a.kind,a.seed))
