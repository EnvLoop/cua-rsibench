"""Configurable public TRAIN-only, fresh-project review contract."""
from dataclasses import dataclass,asdict
from pathlib import Path
import hashlib,json,re,secrets,socket
@dataclass(frozen=True)
class Config:
 workspace:str
 project:str
 port:int
 docker_context:str=''
 schema:str='public-odoo-reference-train-demo-v2'
 actor_seconds:int=720
 actor_actions:int=90
 def validate(self):
  path=Path(self.workspace)
  if not path.is_absolute() or path.exists() or path.is_symlink():raise ValueError('workspace must be a new absolute directory')
  if not re.fullmatch(r'odoo-ref-demo-[a-z0-9-]{8,48}',self.project):raise ValueError('fresh public project prefix required')
  if self.schema!='public-odoo-reference-train-demo-v2' or type(self.port) is not int or type(self.actor_seconds) is not int or type(self.actor_actions) is not int or type(self.docker_context) is not str:raise ValueError('public config schema invalid')
  if not 1024<=self.port<=65535 or (self.actor_seconds,self.actor_actions)!=(720,90):raise ValueError('fixed guard budgets or port invalid')
  return self
 def public(self):return asdict(self)
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False,ensure_ascii=False).encode()
def digest(value):return hashlib.sha256(canonical(value)).hexdigest()
def fresh(workspace,port,docker_context=''):
 return Config(str(Path(workspace).absolute()),'odoo-ref-demo-'+secrets.token_hex(8),port,docker_context).validate()
