"""Verified client-relative native geometry with original action predicates."""
import hashlib,inspect,textwrap
from pathlib import Path
from types import FunctionType
if __package__:
 from . import native_business_reader as business
 from .native_client_coordinate_probe import absolute_client_geometry
else:
 import native_business_reader as business
 from native_client_coordinate_probe import absolute_client_geometry

BASE_SHA='f716c7d132dc7b6569fa445d12a993f516598286fab5e62934101973f955d9dc'
SCHEMA='cua-native-window-current-probe-v41'
if hashlib.sha256(Path(business.__file__).read_bytes()).hexdigest()!=BASE_SHA:raise ValueError('Frozen V40 business reader changed')
STRUCTURAL_RECORD=business.load_current().load_base().structural_record

def root_projection(reader,Atspi,window,client):
 component=window.get_component_iface();screen=component.get_extents(Atspi.CoordType.SCREEN);local=component.get_extents(Atspi.CoordType.WINDOW)
 raw=[screen.x,screen.y,screen.width,screen.height];converted=[local.x+client['X'],local.y+client['Y'],local.width,local.height]
 reader.require(raw==converted and client['WIDTH']>0 and client['HEIGHT']>0,'Native root client-coordinate mapping differs')
 return {'coordinate_api':'WINDOW','physical_pixels_retargeted':False,'actual_x11_client':client,
  'native_root_screen_extents':raw,'native_root_window_extents':[local.x,local.y,local.width,local.height],
  'native_root_projection_equal':True}

def install_coordinate_scope(reader,state):
 def geometry(Atspi,node,viewport):
  component=node.get_component_iface()
  if component is None:return None
  box=component.get_extents(Atspi.CoordType.WINDOW);client=state['client']
  left,top=max(0,int(box.x+client['X'])),max(0,int(box.y+client['Y']))
  right,bottom=min(viewport[0],int(box.x+client['X']+box.width)),min(viewport[1],int(box.y+client['Y']+box.height))
  return [left,top,right-left,bottom-top] if right>left and bottom>top else None
 original=reader.physical_hit;source=textwrap.dedent(inspect.getsource(original))
 call='get_accessible_at_point(point[0],point[1],Atspi.CoordType.SCREEN)'
 reader.require(source.count(call)==1,'Frozen physical coordinate query changed')
 source=source.replace(call,"get_accessible_at_point(point[0]-client_state['client']['X'],point[1]-client_state['client']['Y'],Atspi.CoordType.WINDOW)")
 ns={**original.__globals__,'geometry':geometry,'client_state':state}
 exec(compile('\n'*(original.__code__.co_firstlineno-1)+source,original.__code__.co_filename,'exec'),ns)
 physical=ns['physical_hit']
 record=FunctionType(reader.native_record.__code__,{**reader.native_record.__globals__,'geometry':geometry,'physical_hit':physical},reader.native_record.__name__,reader.native_record.__defaults__,reader.native_record.__closure__)
 reader.geometry=geometry;reader.physical_hit=physical;reader.native_record=record
 reader.namespace.update(geometry=geometry,physical_hit=physical,native_record=record)
 return reader

def editable_record(reader,Atspi,node,window,*,pid,uid,viewport,ancestry):
 flags=reader.state_flags(Atspi,node)
 if flags['EDITABLE']:
  try:return reader.native_record(Atspi,node,window,pid=pid,uid=uid,viewport=viewport,ancestry=ancestry)
  except ValueError as error:
   if str(error) not in ('Native terminal point is not a proved leaf','Native deferred point hit unavailable','Native root point hit unavailable'):raise
 # A failed proof stays inventory only; the actor point predicate is unchanged.
 return STRUCTURAL_RECORD(reader,Atspi,node,window,pid=pid,uid=uid,viewport=viewport,ancestry=ancestry)

def finalise_source(source):
 start="writer=bounded_runtime_journal(diag,facts_path);reader=instrument(reader,identity,writer)\n old=reader.namespace['peer']();state={}"
 new="writer=bounded_runtime_journal(diag,facts_path);state={}\n reader=install_coordinate_scope(reader,state);reader=instrument(reader,identity,writer)\n old=reader.namespace['peer']()"
 resolver="  state['resolver']=RecordedPaths(wrapped.value,x11['pid'],identity)"
 projection="  state['client']=absolute_client_geometry(result[0],x11)\n  state['projection']=root_projection(reader,Atspi,wrapped.value,state['client'])\n"+resolver
 proof="'native_cache_current_receipt':state['cache'],"
 for text in (start,resolver,proof):
  if source.count(text)!=1:raise ValueError('Frozen owned coordinate integration changed')
 return source.replace(start,new).replace(resolver,projection).replace(proof,proof+"\n  'native_coordinate_projection':state['projection'],")

def scoped_reader():
 original_current=business.load_current
 def load_current():
  current=original_current();ns={**vars(current),'__file__':__file__,'SCHEMA':SCHEMA,
   'install_coordinate_scope':install_coordinate_scope,'root_projection':root_projection,
   'absolute_client_geometry':absolute_client_geometry,'editable_record':editable_record,'finalise_source':finalise_source}
  source=textwrap.dedent(inspect.getsource(current.scoped_reader))
  marker=" namespace['SCHEMA']=SCHEMA"
  if source.count(marker)!=1:raise ValueError('Frozen scoped reader construction changed')
  source=source.replace(marker,marker+"\n namespace.update(install_coordinate_scope=install_coordinate_scope,root_projection=root_projection,absolute_client_geometry=absolute_client_geometry,structural_record=editable_record)\n source=finalise_source(source)")
  exec(compile(source,__file__,'exec'),ns);current.scoped_reader=ns['scoped_reader']
  current.install_coordinate_scope=install_coordinate_scope;current.root_projection=root_projection
  current.absolute_client_geometry=absolute_client_geometry;current.editable_record=editable_record;current.finalise_source=finalise_source
  return current
 original=business.scoped_reader
 scope={**vars(business),'__file__':__file__,'SCHEMA':SCHEMA,'load_current':load_current}
 return FunctionType(original.__code__,scope,original.__name__,original.__defaults__,original.__closure__)()

if __name__=='__main__':scoped_reader()[1]()
