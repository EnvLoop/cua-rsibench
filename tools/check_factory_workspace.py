"""Live isolation evidence for the real E2B data-research workspace."""
import argparse,json,secrets
from pathlib import Path
from cursibench.factory_budget import Budget
from cursibench.factory_workspace import FactoryWorkspace
from cursibench.factory_cases import SourceRegistry

p=argparse.ArgumentParser();p.add_argument('--out',required=True);a=p.parse_args()
out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False)
private=out/'private';private.mkdir(mode=0o700)
canary=private/'hidden-evaluation-canary.txt';canary.write_text(secrets.token_hex(32));canary.chmod(0o600)
source=json.loads(Path('datasets/public/kanboard_issues.json').read_text())
registry=SourceRegistry(source,[r['number'] for r in source['records'][:12]],[r['number'] for r in source['records'][12:36]])
budget=Budget(private/'budget.jsonl',{'program_runs':2})
workspace=FactoryWorkspace(out/'workspace',budget)
result={}
probe='''import json,os,socket
from pathlib import Path
report={'netns_inode':os.stat('/proc/self/ns/net').st_ino,'non_root':os.getuid()!=0,'provider_credentials_present':any(k in os.environ for k in ['OPENAI_API_KEY','TINKER_API_KEY','E2B_API_KEY']),'host_canary_visible':Path(CANARY_PATH).exists()}
try:
 with socket.create_connection(('1.1.1.1',443),timeout=3):report['outbound_internet']=True
except Exception:report['outbound_internet']=False
try:
 with open('/inputs/sources.json','a') as f:f.write('tamper')
 report['inputs_writable']=True
except PermissionError:report['inputs_writable']=False
try:
 Path('/service/results').iterdir().__next__();report['service_results_readable']=True
except PermissionError:report['service_results_readable']=False
source=json.loads(Path('/inputs/sources.json').read_text())
Path('generated.json').write_text(json.dumps({'source_numbers':[r['number'] for r in source['records'][:3]]}))
print(json.dumps(report))
'''.replace('CANARY_PATH',repr(str(canary)))
try:
 result['initialization']=workspace.start({'sources.json':json.dumps(registry.training_input())})
 workspace.write('probe.py',probe)
 executed=workspace.run('probe.py',seconds=15)
 if executed.get('exit_code')!=0:raise RuntimeError('probe failed: '+str(executed))
 result['isolation']=json.loads(executed['stdout'])
 result['isolated_network_namespace']=result['isolation'].pop('netns_inode')!=executed['supervisor_netns']
 generated=workspace.read('generated.json');result['generated']=json.loads(generated['content'])
 result['pass']=result['isolated_network_namespace'] and result['isolation']=={'non_root':True,'provider_credentials_present':False,'host_canary_visible':False,'outbound_internet':False,'inputs_writable':False,'service_results_readable':False}
 if not result['pass']:raise RuntimeError('isolation contract failed')
 result['budget']=budget.snapshot()
finally:
 workspace.close();(out/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
