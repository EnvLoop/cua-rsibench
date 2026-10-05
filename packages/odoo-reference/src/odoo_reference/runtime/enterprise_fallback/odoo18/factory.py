"""Local public TRAIN runtime configuration and trusted fixture RPC only."""
from pathlib import Path
import os,xmlrpc.client
CODE_DIR=Path(__file__).resolve().parent
if not os.environ.get('ENVLOOP_ODOO_WORKER_DIR'):raise RuntimeError('public_worker_scope_required_before_import')
HERE=Path(os.environ['ENVLOOP_ODOO_WORKER_DIR']).resolve()
PRIVATE=HERE/'private'
def local_config():
 p=HERE/'.env'
 if p.is_symlink() or not p.is_file() or p.stat().st_mode & 0o077:raise RuntimeError('private_local_config_required')
 return dict(line.split('=',1) for line in p.read_text().splitlines() if '=' in line)
class OdooRPC:
 def __init__(self,base_url=None):
  cfg=local_config();base_url=base_url or 'http://127.0.0.1:'+cfg['ODOO_PORT'];self.password=cfg['ODOO_ADMIN_PASSWORD']
  common=xmlrpc.client.ServerProxy(base_url+'/xmlrpc/2/common',allow_none=True)
  self.uid=common.authenticate('bench','admin',self.password,{})
  if self.uid!=2:raise RuntimeError('fresh_builtin_admin_authentication_required')
  self.models=xmlrpc.client.ServerProxy(base_url+'/xmlrpc/2/object',allow_none=True)
 def call(self,model,method,*args,**kwargs):
  return self.models.execute_kw('bench',self.uid,self.password,model,method,list(args),kwargs)
