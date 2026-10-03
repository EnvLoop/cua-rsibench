"""Conservative proof expiry; frozen V45 evidence and native predicates remain."""
import hashlib, inspect, json, math, textwrap
from pathlib import Path
if __package__:
 from . import native_editor_evidence_v45 as original
else:
 import native_editor_evidence_v45 as original
BASE_SHA='89947c4f4d554ba6aa3157bccf91b97bddd9c1aeef9170b725caa2a19841c2e8'
if hashlib.sha256(Path(original.__file__).read_bytes()).hexdigest()!=BASE_SHA:raise ValueError('Frozen V45 evidence changed')

def bounded_expiry(observed_at):
 """Shorten by one float step so addition cannot overstate the ten-second cap."""
 return math.nextafter(observed_at+10,-math.inf)

def scoped_function(fn,old,new,namespace):
 source=textwrap.dedent(inspect.getsource(fn))
 if source.count(old)!=1:raise ValueError('Frozen proof clock producer changed')
 scope={**fn.__globals__,**namespace}
 exec(compile(source.replace(old,new),__file__,'exec'),scope)
 return scope[fn.__name__]

CurrentEvidence=type('ConservativeCurrentEvidence',(original.CurrentEvidence,),{
 'refresh':scoped_function(original.CurrentEvidence.refresh,'expires_at=now+10','expires_at=bounded_expiry(now)',{'bounded_expiry':bounded_expiry})})
evidence=scoped_function(original.evidence,"'expires_at':now+10","'expires_at':bounded_expiry(now)",{'bounded_expiry':bounded_expiry,'CurrentEvidence':CurrentEvidence})
SEED=original.SEED

if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('--filename',required=True);parser.add_argument('--bootstrap',action='store_true');parser.add_argument('--pipe');args=parser.parse_args()
 if args.bootstrap:
  node,binding,x11=original.native_menu_state(args.filename,bootstrap=True)
  result={**node,'document_binding_sha256':binding,'visible_initial_native_proof':node['visible'] and node['showing'],'pipe_name':args.pipe}
 else:result=evidence(args.filename)
 print(json.dumps(result,sort_keys=True,separators=(',',':')))
