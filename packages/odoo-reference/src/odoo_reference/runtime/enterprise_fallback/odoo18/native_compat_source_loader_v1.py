"""Public package source loader, verified against bundled source-lock.json."""
from pathlib import Path
from types import ModuleType
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[2]
def load_source(relative,name,expected_sha256,substitutions=()):
 p=ROOT/relative;lock=json.loads((ROOT/'source-lock.json').read_text())
 if p.is_symlink() or not p.is_file() or lock.get(relative)!=expected_sha256 or hashlib.sha256(p.read_bytes()).hexdigest()!=expected_sha256:raise RuntimeError('public_runtime_source_binding_changed')
 source=p.read_text()
 for before,after,count in substitutions:
  if source.count(before)!=count:raise RuntimeError('public_runtime_substitution_mismatch')
  source=source.replace(before,after)
 identity=hashlib.sha256(source.encode()).hexdigest();prior=sys.modules.get(name)
 if prior is not None:
  if prior._native_compat_source_sha256!=identity:raise RuntimeError('public_runtime_namespace_conflict')
  return prior
 m=ModuleType(name);m.__file__=str(p);m.__package__=name.rsplit('.',1)[0];m._native_compat_source_sha256=identity;sys.modules[name]=m
 try:exec(compile(source,str(p),'exec'),m.__dict__)
 except BaseException:sys.modules.pop(name,None);raise
 return m
