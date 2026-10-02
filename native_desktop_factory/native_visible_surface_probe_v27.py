"""Prospective native Collection surface reader; no full tree enumeration.

Read-only VISIBLE/SHOWING and FOCUSED native queries use finite limits. Native
point lookup validates actual ownership and ancestors. Missing/overflow/unknown
states never become an enabled static canvas. Source-only until native proof.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

SCHEMA='cua-native-visible-surface-probe-v27'
OWNER_SHA='cc04307c4317397054f98ecedc780687df83e764f5d2a75c6cb4ed305b6238c7'
MAX_VISIBLE=128
MAX_ANCESTORS=32

def sha(raw):return hashlib.sha256(raw).hexdigest()
def require(ok,code):
 if not ok:raise ValueError(code)
def owner_module():
 path=Path(__file__).with_name('native_accessibility_probe_v24.py');raw=path.read_bytes();require(sha(raw)==OWNER_SHA,'Exact owned-window source required')
 spec=importlib.util.spec_from_file_location('envloop_visible_surface_owner_v24',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def owned_window(owner,filename):
 frozen=owner.load();x11=frozen.x11();require(owner.ownership(x11,filename),'native_application_account_not_owned')
 api=frozen.native_api();desktop=api.desktop();require(desktop.childCount<=64,'native_desktop_application_count_unbounded');matched=[]
 for app in desktop:
  require(app.childCount<=64,'native_application_window_count_unbounded')
  for window in app:
   if window.getState().contains(api.STATE_ACTIVE) and window.name==x11['title'] and window.pid==x11['pid']:matched.append(window)
 require(len(matched)==1,'native_active_window_ambiguous');return frozen,x11,matched[0]

def match_rule(Atspi,states):
 # Parameter order confirmed in the official Ubuntu 2.44.0 GIR; ANY empty
 # attributes/roles/interfaces do not inspect names or values.
 return Atspi.MatchRule.new(Atspi.StateSet.new(states),Atspi.CollectionMatchType.ALL,{},Atspi.CollectionMatchType.ANY,[],Atspi.CollectionMatchType.ANY,[],Atspi.CollectionMatchType.ANY,False)

def collection_queries(Atspi,window,*,limit=MAX_VISIBLE):
 collection=window.get_collection_iface();require(collection is not None,'Actual native Collection interface required')
 visible=collection.get_matches(match_rule(Atspi,[Atspi.StateType.VISIBLE,Atspi.StateType.SHOWING]),Atspi.CollectionSortOrder.CANONICAL,limit+1,True)
 require(len(visible)<=limit,'native_visible_collection_overflow')
 focused=collection.get_matches(match_rule(Atspi,[Atspi.StateType.FOCUSED]),Atspi.CollectionSortOrder.CANONICAL,2,True)
 require(len(focused)<=1,'native_focus_ambiguous')
 return visible,focused[0] if focused else None

def ancestors(node,window):
 result=[];cursor=node
 for _ in range(MAX_ANCESTORS):
  require(cursor is not None,'Native object not in owned window ancestry');result.append(cursor)
  if cursor==window:return result
  cursor=cursor.get_parent()
 raise ValueError('Native ancestor path unbounded')

def native_record(Atspi,node,window,*,pid,uid,viewport):
 chain=ancestors(node,window);require(node.get_process_id()==pid,'Native object process ownership changed')
 state=node.get_state_set();component=node.get_component_iface();require(component is not None,'Native component geometry required');box=component.get_extents(Atspi.CoordType.SCREEN)
 left,top=max(0,box.x),max(0,box.y);right,bottom=min(viewport[0],box.x+box.width),min(viewport[1],box.y+box.height);require(right>left and bottom>top,'Native object outside observed viewport')
 path=[n.get_index_in_parent() for n in reversed(chain[:-1])];role=node.get_role_name();enabled=state.contains(Atspi.StateType.ENABLED) and state.contains(Atspi.StateType.SENSITIVE)
 showing=state.contains(Atspi.StateType.VISIBLE) and state.contains(Atspi.StateType.SHOWING);editable=state.contains(Atspi.StateType.EDITABLE)
 hit=window.get_component_iface().get_accessible_at_point(int((left+right)/2),int((top+bottom)/2),Atspi.CoordType.SCREEN)
 hit_chain=ancestors(hit,window) if hit is not None else [];unobscured=node in hit_chain
 # Administrative UI labels may exclude exports/navigation; cells/text data
 # are never read. Only exact native role categories use control names.
 name=node.get_name() if role in ['menu item','push button','link','check menu item','radio menu item'] else ''
 import re
 unsafe=role=='link' or bool(re.match(r'^(open|new|print|export|send|share|delete|close|quit|account)\b',name,re.I))
 record={'ref':'ax-'+sha(json.dumps(path,separators=(',',':')).encode())[:24],'bounds':[left,top,right-left,bottom-top],'visible':showing,'enabled':enabled and not unsafe,'obscured':not unobscured,
  'keyboard':editable and showing and enabled and not unsafe,'actions':[] if unsafe else ['click','double_click','scroll','drag']+(['type','key'] if editable else [])}
 return record,{'native_uid':uid,'native_pid':pid,'role':role,'ancestor_indices_sha256':sha(json.dumps(path).encode()),'enabled_flag_observed':state.contains(Atspi.StateType.ENABLED),'sensitive_flag_observed':state.contains(Atspi.StateType.SENSITIVE),'point_hit_ownership_checked':True}

def run(*,filename,viewport,point=None):
 owner=owner_module();frozen,x11,wrapped=owned_window(owner,filename);window=wrapped.value
 import gi
 gi.require_version('Atspi','2.0');from gi.repository import Atspi
 visible,focus=collection_queries(Atspi,window);targets=[];facts=[]
 for node in visible:
  try:record,fact=native_record(Atspi,node,window,pid=x11['pid'],uid=x11['uid'],viewport=viewport)
  except ValueError as error:
   if str(error)=='Native object outside observed viewport':continue
   raise
  targets.append(record);facts.append(fact)
 focus_ref=None
 if focus is not None:
  f,_=native_record(Atspi,focus,window,pid=x11['pid'],uid=x11['uid'],viewport=viewport);focus_ref=f['ref']
 point_fact=None
 if point is not None:
  require(0<=point[0]<viewport[0] and 0<=point[1]<viewport[1],'Requested point outside current frame')
  hit=window.get_component_iface().get_accessible_at_point(point[0],point[1],Atspi.CoordType.SCREEN);require(hit is not None,'Actual requested native point hit unavailable')
  record,fact=native_record(Atspi,hit,window,pid=x11['pid'],uid=x11['uid'],viewport=viewport);point_fact={'requested_point':point,'actual_hit':record,'actual_native':fact}
 require(frozen.x11()==x11,'Native window changed during visible query')
 return {'schema':SCHEMA,'status':'prospective_visible_native_observed_not_qualified','probe_source_sha256':sha(Path(__file__).read_bytes()),'ownership_source_sha256':OWNER_SHA,
  'native_uid':x11['uid'],'native_pid':x11['pid'],'viewport':viewport,'window_id_sha256':sha(x11['window_id'].encode()),'window_title_sha256':sha(x11['title'].encode()),
  'native_collection_count':len(visible),'targets':targets,'native_facts':facts,'focus_id':focus_ref,'requested_point_fact':point_fact,
  'full_virtual_tree_enumerated':False,'task_values_read':False,'native_mutations':0,'native_qualification_passed':False}

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--filename',required=True);parser.add_argument('--width',type=int,default=1280);parser.add_argument('--height',type=int,default=800);parser.add_argument('--point-x',type=int);parser.add_argument('--point-y',type=int);args=parser.parse_args()
 try:
  require((args.point_x is None)==(args.point_y is None),'Both requested coordinates required');value=run(filename=args.filename,viewport=[args.width,args.height],point=None if args.point_x is None else [args.point_x,args.point_y])
 except Exception as error:value={'schema':SCHEMA,'status':'native_visible_unavailable_or_unsafe','error_class':type(error).__name__,'error_code':str(error)[:100] if isinstance(error,ValueError) else 'native_api_unavailable','native_mutations':0,'native_qualification_passed':False}
 print(json.dumps(value,sort_keys=True,separators=(',',':')))

if __name__=='__main__':main()
