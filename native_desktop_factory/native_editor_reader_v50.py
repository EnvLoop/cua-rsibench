"""Uniform bounded observation coverage for known writable Writer paragraphs."""
import hashlib
from pathlib import Path
from types import FunctionType,SimpleNamespace
if __package__:
 from . import native_editor_reader_v49 as previous
else:
 import native_editor_reader_v49 as previous
SCHEMA='cua-native-Writer-visible-inventory-probe-v50'
BASE_SHA='a7358e1be2fe9ab0c2cd79dcc2b4601c225f7659f8f0a0340d3839a32a595dc0'
if hashlib.sha256(Path(previous.__file__).read_bytes()).hexdigest()!=BASE_SHA:raise ValueError('Frozen V49 reader changed')
base41=previous.old.original.base

def finalise_source(source):
 source=base41.finalise_source(source)
 marker=' import inspect,textwrap\n walk_source=breadth_first_source(reader.previous.bounded_surface)'
 replacement=" import inspect,textwrap\n import native_writer_inventory_v50 as writer_inventory\n namespace['writer_document_count']=lambda A,node,window,pid,uid,ancestry,role,flags:writer_inventory.current_document_count(reader,A,node,window,pid=pid,uid=uid,ancestry=ancestry,role=role,flags=flags)\n walk_source=writer_inventory.breadth_first_source(reader.previous.bounded_surface)"
 if source.count(marker)!=1:raise ValueError('Frozen inventory source hook changed')
 return source.replace(marker,replacement)

scoped_base=SimpleNamespace(**{**vars(base41),'finalise_source':finalise_source})
fn=base41.scoped_reader
scoped_base.scoped_reader=FunctionType(fn.__code__,{**fn.__globals__,'finalise_source':finalise_source},fn.__name__,fn.__defaults__,fn.__closure__)

def scoped_reader():
 fn=previous.old.original.scoped_reader
 namespace={**fn.__globals__,'__file__':__file__,'SCHEMA':SCHEMA,'base':scoped_base,'current_evidence':previous.old.current_evidence,'compatible_record':previous.compatible_record}
 return FunctionType(fn.__code__,namespace,fn.__name__,fn.__defaults__,fn.__closure__)()
if __name__=='__main__':scoped_reader()[1]()
