"""Fresh owned Compose bootstrap; only explicitly named public-demo resources."""
from pathlib import Path
import os,secrets,subprocess,xmlrpc.client,socket,json,shutil
from .loader import activate
from .fixture import seed
from .config import canonical,Config
ROLE_SQL='CREATE ROLE bench_verify LOGIN; GRANT CONNECT ON DATABASE bench TO bench_verify; GRANT USAGE ON SCHEMA public TO bench_verify; GRANT SELECT ON ALL TABLES IN SCHEMA public TO bench_verify; ALTER DEFAULT PRIVILEGES FOR ROLE odoo IN SCHEMA public GRANT SELECT ON TABLES TO bench_verify;'
def compose(workspace,*args):
 return subprocess.run(['docker','compose','--env-file','.env',*args],cwd=workspace,capture_output=True,check=True)
def bootstrap(config):
 Config(**config).validate();workspace=Path(config['workspace'])
 if workspace.exists():raise RuntimeError('fresh public workspace required; no resume/reseed')
 with socket.socket() as probe:
  if probe.connect_ex(('127.0.0.1',config['port']))==0:raise RuntimeError('loopback port already occupied')
 # No removals, pruning, existing-resource stop or extra account are allowed.
 for key in list(os.environ):
  if key.startswith('ODOO_') or key.startswith('COMPOSE_'):os.environ.pop(key)
 if config['docker_context']:os.environ['DOCKER_CONTEXT']=config['docker_context']
 existing=subprocess.run(['docker','ps','-a','--filter','label=com.docker.compose.project='+config['project'],'-q'],capture_output=True,check=True)
 if existing.stdout.strip():raise RuntimeError('project namespace already exists')
 for kind in ('volume','network'):
  result=subprocess.run(['docker',kind,'ls','--filter','label=com.docker.compose.project='+config['project'],'-q'],capture_output=True,check=True)
  if result.stdout.strip():raise RuntimeError('orphaned project namespace already exists')
 for kind,name in (('volume',config['project']+'_pgdata'),('volume',config['project']+'_filestore'),('network',config['project']+'_default')):
  result=subprocess.run(['docker',kind,'inspect',name],capture_output=True,check=False)
  if result.returncode==0:raise RuntimeError('reserved project resource name already exists')
 workspace.mkdir(mode=0o700,parents=True);(workspace/'private').mkdir(mode=0o700)
 shutil.copyfile(Path(__file__).parent/'compose.yaml',workspace/'compose.yaml')
 password='p'+secrets.token_urlsafe(24);db='p'+secrets.token_urlsafe(24)
 env=workspace/'.env';env.write_text(f'ODOO_PROJECT={config["project"]}\nODOO_PORT={config["port"]}\nODOO_PARTITION=train\nODOO_ADMIN_PASSWORD={password}\nODOO_DB_PASSWORD={db}\n');env.chmod(0o600)
 factory,lease,verify,reset,_=activate(workspace)
 with lease.exclusive_worker_operation('public_train_bootstrap'):
  compose(workspace,'up','-d','db');compose(workspace,'--profile','bootstrap','run','--rm','init');compose(workspace,'up','-d','web');reset.wait_web()
  url=f'http://127.0.0.1:{config["port"]}';common=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/common',allow_none=True);models=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/object',allow_none=True)
  uid=common.authenticate('bench','admin','admin',{})
  if uid!=2:raise RuntimeError('fresh built-in admin account required')
  models.execute_kw('bench',uid,'admin','res.users','write',[[uid],{'password':password}])
  compose(workspace,'exec','-T','db','psql','-U','odoo','-d','bench','-v','ON_ERROR_STOP=1','-c',ROLE_SQL)
  seed(factory);baseline=verify.snapshot();p=factory.PRIVATE/'baseline_snapshot.json';p.write_bytes(canonical(baseline));p.chmod(0o600)
  checkpoint=reset.checkpoint()
  from .audit import audit_public_sources
  audit_public_sources(baseline,json.loads((factory.PRIVATE/'baseline-filestore-manifest.json').read_bytes()),json.loads((factory.PRIVATE/'development_gold.json').read_bytes()))
  for file in factory.PRIVATE.iterdir():
   if file.is_file():file.chmod(0o600)
 return checkpoint
