"""Read-only SCREEN/WINDOW coordinate facts for an exactly owned native app.

This diagnostic cannot authorize an actor action or change a guard verdict.
"""
from __future__ import annotations
import argparse,json,re
from types import SimpleNamespace
if __package__:
 from . import native_business_reader as business
else:
 import native_business_reader as business

def point_chain(Atspi,window,point,coord_type,*,pid,identity,ancestry):
 rows=[];seen=set();cursor=window
 for depth in range(32):
  if cursor is None or cursor.get_process_id()!=pid:raise ValueError('Native coordinate process ownership changed')
  ancestry(cursor,window);current=identity(cursor)
  if current.get('available') is not True or current['identity_sha256'] in seen:raise ValueError('Native coordinate identity unavailable or cycle')
  seen.add(current['identity_sha256']);flags={name:bool(cursor.get_state_set().contains(getattr(Atspi.StateType,name))) for name in ('VISIBLE','SHOWING','ENABLED','SENSITIVE','EDITABLE','FOCUSED','DEFUNCT','STALE','MANAGES_DESCENDANTS')}
  if not flags['VISIBLE'] or not flags['SHOWING'] or flags['DEFUNCT'] or flags['STALE']:raise ValueError('Native coordinate state unsafe')
  component=cursor.get_component_iface()
  if component is None:raise ValueError('Native coordinate component unavailable')
  extents={}
  for name in ('SCREEN','WINDOW'):
   box=component.get_extents(getattr(Atspi.CoordType,name));extents[name]=[box.x,box.y,box.width,box.height]
  role=cursor.get_role_name();count=cursor.get_child_count()
  row={'depth':depth,'identity':current,'pid':pid,'role':role,'flags':flags,'actual_child_count':count,'extents':extents};rows.append(row)
  hit=component.get_accessible_at_point(point[0],point[1],coord_type)
  row['hit_identity']=identity(hit) if hit is not None else None
  if hit is None or row['hit_identity']['identity_sha256']==current['identity_sha256']:
   leaf=depth>0 and type(count) is int and count==0 and not flags['MANAGES_DESCENDANTS']
   return {'rows':rows,'terminal_kind':'none' if hit is None else 'same_native_identity','strict_leaf_shape_observed':leaf,
    'native_actions_authorized':False,'original_point_verdict_changed':False}
  cursor=hit
 return {'rows':rows,'terminal_kind':'native_depth_cap','strict_leaf_shape_observed':False,'native_actions_authorized':False,'original_point_verdict_changed':False}

def x11_geometry(frozen,x11):
 raw=frozen.command(['xdotool','getwindowgeometry','--shell',x11['window_id']]);values={}
 for line in raw.splitlines():
  match=re.fullmatch(r'(WINDOW|X|Y|WIDTH|HEIGHT|SCREEN)=(-?[0-9]+)',line)
  if match:values[match[1]]=int(match[2])
 if values.get('WINDOW')!=int(x11['window_id']) or not all(key in values for key in ('X','Y','WIDTH','HEIGHT')) or values['WIDTH']<=0 or values['HEIGHT']<=0:raise ValueError('Actual X11 client geometry unavailable')
 return values

def run(*,filename,points):
 current=business.load_current();base=current.load_base();peer=base.load();reader=peer.load('native_visible_surface_probe_v31.py',peer.V31_SHA)
 identity=peer.load('native_hit_identity_diagnostic_v33.py',peer.V33_SHA).identity
 old=reader.namespace['peer']();original_owner=old.owner_module();owner=SimpleNamespace(load=original_owner.load,ownership=business.ownership)
 frozen,x11,wrapped=old.owned_window(owner,filename);window=wrapped.value
 from gi.repository import Atspi
 cache=current.cache_owned_application(reader,Atspi,window,pid=x11['pid'],identity=identity)
 class Writer:
  def append(self,row):pass
 resolver=base.forward_owned_paths(peer,Writer())(window,x11['pid'],identity)
 geometry=x11_geometry(frozen,x11);facts=[]
 for point in points:
  converted=[point[0]-geometry['X'],point[1]-geometry['Y']]
  row={'original_screen_point':point,'x11_client_relative_point':converted}
  for name,coordinates in [('SCREEN',point),('WINDOW',converted)]:
   try:row[name]=point_chain(Atspi,window,coordinates,getattr(Atspi.CoordType,name),pid=x11['pid'],identity=identity,ancestry=resolver.ancestors)
   except Exception as error:row[name]={'error_class':type(error).__name__,'error':str(error),'native_actions_authorized':False}
  facts.append(row)
 if frozen.x11()!=x11 or x11_geometry(frozen,x11)!=geometry:raise ValueError('Native coordinate window changed during capture')
 return {'schema':'cua-native-readonly-coordinate-facts-v1','status':'captured','x11_client_geometry':geometry,'native_cache_receipt':cache,
  'facts':facts,'actual_native_forward_path_proofs':resolver.proofs,
  'native_mutations':0,'actor_actions':0,'model_calls':0,'native_qualification_passed':False,'native_actions_authorized':False}

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--filename',required=True);parser.add_argument('--points',default='[[52,170],[258,767],[648,414]]');args=parser.parse_args()
 points=json.loads(args.points)
 if type(points) is not list or len(points)>3 or any(type(p) is not list or len(p)!=2 or any(type(n) is not int for n in p) for p in points):raise ValueError('Diagnostic point bound')
 print(json.dumps(run(filename=args.filename,points=points),sort_keys=True,separators=(',',':')))
