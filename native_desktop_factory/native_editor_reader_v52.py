"""Scoped complete-document focused-leaf projection; raw flags remain unchanged."""
import hashlib
from pathlib import Path
from types import FunctionType,SimpleNamespace
if __package__:
 from . import native_editor_reader_v51 as previous
 from . import native_impress_focus_v52 as focus
else:
 import native_editor_reader_v51 as previous
 import native_impress_focus_v52 as focus
SCHEMA='cua-native-Impress-focused-leaf-probe-v52'
BASE_SHA='20d2d872114a57947c72af0e5ffba1aff2458a6ab9d0e2f6272d59ab24509512'
if hashlib.sha256(Path(previous.__file__).read_bytes()).hexdigest()!=BASE_SHA:raise ValueError('Frozen V51 reader changed')
base41=previous.previous.base41
def finalise_source(source):
 source=previous.previous.finalise_source(source)
 marker=" exec(compile(walk_source.replace(original,replacement).replace(cap,bounded).replace('seen=[]','seen=set()'),__file__,'exec'),namespace)"
 replacement=" import native_impress_focus_v52 as focus\n namespace['resolve_focus']=lambda focused,nodes,A,window,pid,uid,viewport,ancestry,seen:focus.resolve_focus(reader,A,window,pid=pid,uid=uid,viewport=viewport,ancestry=ancestry,focused=focused,focus_nodes=nodes,seen=seen)\n built=walk_source.replace(original,replacement).replace(cap,bounded).replace('seen=[]','seen=set()')\n exec(compile(focus.walk_source(built),__file__,'exec'),namespace)"
 proof="'native_cache_current_receipt':state['cache'],"
 start=" peer=load();reader=peer.load('native_visible_surface_probe_v31.py',peer.V31_SHA)"
 if source.count(marker)!=1 or source.count(proof)!=1 or source.count(start)!=1:raise ValueError('Frozen focus integration source changed')
 return source.replace(start," import time\n query_started=time.monotonic()\n"+start+"\n reader._v52_query_started=query_started").replace(marker,replacement).replace(proof,proof+"\n  'Impress_focus_resolution':getattr(reader,'_v52_focus_evidence',None),")
scoped_base=SimpleNamespace(**{**vars(base41),'finalise_source':finalise_source})
fn=base41.scoped_reader
scoped_base.scoped_reader=FunctionType(fn.__code__,{**fn.__globals__,'finalise_source':finalise_source},fn.__name__,fn.__defaults__,fn.__closure__)
def scoped_reader():
 fn=previous.previous.previous.old.original.scoped_reader
 namespace={**fn.__globals__,'__file__':__file__,'SCHEMA':SCHEMA,'base':scoped_base,'current_evidence':previous.previous.previous.old.current_evidence,'compatible_record':previous.compatible_record}
 run,main=FunctionType(fn.__code__,namespace,fn.__name__,fn.__defaults__,fn.__closure__)()
 def guarded_run(**kwargs):return previous.capability.actionable_metadata(run(**kwargs))
 main.__globals__['guarded_run']=guarded_run
 return guarded_run,main
if __name__=='__main__':scoped_reader()[1]()
