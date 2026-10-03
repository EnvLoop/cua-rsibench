"""Same native compatibility predicates with conservatively bounded evidence."""
import hashlib
from pathlib import Path
from types import FunctionType
if __package__:
 from . import native_editor_reader_v45 as original
 from . import native_editor_evidence_v47 as evidence
else:
 import native_editor_reader_v45 as original
 import native_editor_evidence_v47 as evidence
BASE_SHA='e7fd487ff736392e19c302004ffc375abe7430bb9dd0ae42c032016592209173'
SCHEMA='cua-native-editor-capability-probe-v47'
if hashlib.sha256(Path(original.__file__).read_bytes()).hexdigest()!=BASE_SHA:raise ValueError('Frozen V45 reader changed')
current_evidence=FunctionType(original.current_evidence.__code__,{**original.current_evidence.__globals__,'evidence':evidence},original.current_evidence.__name__,original.current_evidence.__defaults__,original.current_evidence.__closure__)

def scoped_reader():
 fn=original.scoped_reader
 namespace={**fn.__globals__,'__file__':__file__,'SCHEMA':SCHEMA,'current_evidence':current_evidence}
 return FunctionType(fn.__code__,namespace,fn.__name__,fn.__defaults__,fn.__closure__)()

if __name__=='__main__':scoped_reader()[1]()
