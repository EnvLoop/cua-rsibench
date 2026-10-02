"""Read-only Linux X11/AT-SPI projection; no task text or GUI mutation.

This file is copied to a reviewed fresh owned guest by the evaluator. Missing
native APIs, ownership ambiguity, truncated accessibility traversal or unknown
hit/focus state fail closed. No static canvas substitutes for native states.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

SCHEMA='cua-native-desktop-accessibility-probe-v23'
MAX_NODES=2048
MAX_TARGETS=128

def digest(raw):return hashlib.sha256(raw).hexdigest()
def require(ok,code):
 if not ok:raise ValueError(code)
def command(args):
 result=subprocess.run(args,capture_output=True,text=True,timeout=5)
 require(result.returncode==0 and len(result.stdout)<=8192,'native_os_query_failed')
 return result.stdout.strip()
def x11():
 window=command(['xdotool','getactivewindow']);require(re.fullmatch(r'\d+',window),'native_window_id_invalid')
 pid=command(['xdotool','getwindowpid',window]);require(re.fullmatch(r'\d+',pid),'native_window_pid_invalid')
 title=command(['xdotool','getwindowname',window]);klass=command(['xprop','-id',window,'WM_CLASS'])
 status=Path('/proc')/pid/'status';match=re.search(r'^Uid:\s+(\d+)\s+',status.read_text(),re.M);require(match is not None,'native_window_uid_unavailable')
 return {'window_id':window,'pid':int(pid),'uid':int(match[1]),'title':title,'wm_class':klass,'probe_uid':os.getuid()}

def native_api():
 # GObject introspection exposes the documented libatspi process-ID API.
 # No focus, scrolling, selection or text interface mutation is invoked.
 import gi
 gi.require_version('Atspi','2.0')
 from gi.repository import Atspi
 class Component:
  def __init__(self,value):self.value=value
  def getExtents(self,_):return self.value.get_extents(Atspi.CoordType.SCREEN)
  def getAccessibleAtPoint(self,x,y,_):
   value=self.value.get_accessible_at_point(x,y,Atspi.CoordType.SCREEN)
   return Node(value) if value is not None else None
 class Node:
  def __init__(self,value):self.value=value
  def __eq__(self,other):return isinstance(other,Node) and self.value==other.value
  @property
  def childCount(self):return self.value.get_child_count()
  @property
  def name(self):return self.value.get_name()
  @property
  def parent(self):
   value=self.value.get_parent();return Node(value) if value is not None else None
  @property
  def pid(self):return self.value.get_process_id()
  def __iter__(self):return (self[i] for i in range(self.childCount))
  def __getitem__(self,index):return Node(self.value.get_child_at_index(index))
  def getState(self):return self.value.get_state_set()
  def getRoleName(self):return self.value.get_role_name()
  def queryComponent(self):
   component=self.value.get_component_iface()
   if component is None:raise NotImplementedError()
   return Component(component)
 class Api:
  XY_SCREEN=Atspi.CoordType.SCREEN
  STATE_VISIBLE=Atspi.StateType.VISIBLE;STATE_SHOWING=Atspi.StateType.SHOWING
  STATE_ENABLED=Atspi.StateType.ENABLED;STATE_SENSITIVE=Atspi.StateType.SENSITIVE
  STATE_EDITABLE=Atspi.StateType.EDITABLE;STATE_FOCUSED=Atspi.StateType.FOCUSED;STATE_ACTIVE=Atspi.StateType.ACTIVE
  desktop=staticmethod(lambda:Node(Atspi.get_desktop(0)))
 return Api

def accessible_identity(node,path):
 # Actual native hierarchy identity is used; names/current task values are not.
 return 'ax-'+digest(path.encode())[:24]
def atspi_targets(api,window,*,viewport):
 candidates=[];focus=[];visited=0;truncated=False
 def walk(node,path,depth=0):
  nonlocal visited,truncated
  visited+=1
  if visited>MAX_NODES or depth>32:truncated=True;return
  state=node.getState();role=node.getRoleName()
  visible=state.contains(api.STATE_VISIBLE) and state.contains(api.STATE_SHOWING)
  if visible:
   try:
    component=node.queryComponent();r=component.getExtents(api.XY_SCREEN)
   except NotImplementedError:component=None
   if component is not None and r.width>0 and r.height>0:
    left,top=max(0,r.x),max(0,r.y);right,bottom=min(viewport[0],r.x+r.width),min(viewport[1],r.y+r.height)
    if right>left and bottom>top:
     enabled=state.contains(api.STATE_ENABLED) and state.contains(api.STATE_SENSITIVE)
     editable=state.contains(api.STATE_EDITABLE);focused=state.contains(api.STATE_FOCUSED)
     # Read administrative labels only to exclude navigation/exports. Text
     # entries, cells, paragraphs and shape values are never read or returned.
     administrative=role in ['menu item','push button','link']
     name=node.name if administrative else ''
     unsafe=role=='link' or bool(re.match(r'^(open|new|print|export|send|share|delete|close|quit|account)\b',name,re.I))
     try:hit=window.queryComponent().getAccessibleAtPoint(int((left+right)/2),int((top+bottom)/2),api.XY_SCREEN)
     except NotImplementedError:hit=None
     # A native point hit must resolve to this node or a native descendant.
     hit_ok=False;cursor=hit
     for _ in range(40):
      if cursor is None:break
      if cursor==node:hit_ok=True;break
      cursor=cursor.parent
     ref=accessible_identity(node,path)
     actions=[] if unsafe else ['click','double_click','scroll','drag']
     if editable and not unsafe:actions+=['type','key']
     record={'ref':ref,'bounds':[left,top,right-left,bottom-top],'visible':True,'enabled':enabled and not unsafe,'obscured':not hit_ok,
      'keyboard':editable and enabled and not unsafe,'actions':actions}
     candidates.append(record)
     if focused:focus.append((record,role))
  count=node.childCount
  # AT-SPI tables may expose huge offscreen sets. Do not assume a truncated
  # tree proves safe targets; report it and refuse paid/native dispatch.
  if count>512:truncated=True;return
  for index in range(count):
   if truncated:break
   walk(node[index],path+'/'+str(index),depth+1)
 walk(window,'window')
 require(not truncated and len(candidates)<=MAX_TARGETS,'native_accessibility_tree_unbounded')
 require(candidates and len(focus)<=1,'native_accessibility_focus_or_targets_ambiguous')
 return candidates,focus[0] if focus else None,visited

def probe(*,filename,viewport):
 require(re.fullmatch(r'[A-Za-z0-9_.-]{1,160}\.(xlsx|pptx|docx)',filename),'native_owned_filename_invalid')
 first=x11();require(first['uid']==first['probe_uid'] and 'soffice' in first['wm_class'].lower(),'native_application_account_not_owned')
 api=native_api()
 desktop=api.desktop();require(desktop.childCount<=64,'native_desktop_application_count_unbounded')
 matches=[]
 for app in desktop:
  require(app.childCount<=64,'native_application_window_count_unbounded')
  for window in app:
   state=window.getState()
   if state.contains(api.STATE_ACTIVE) and window.name==first['title'] and window.pid==first['pid']:matches.append(window)
 require(len(matches)==1,'native_active_accessibility_window_ambiguous')
 window=matches[0];role=window.getRoleName();owned_document=filename in first['title']
 # Unknown active dialogs stay unowned. A prospective native qualification
 # may add an independently observed typed save-format dialog schema later.
 modal='none' if role in ['frame','window'] else 'unknown-native-dialog'
 targets,focused,visited=atspi_targets(api,window,viewport=viewport)
 second=x11();require(first==second,'native_window_changed_during_probe')
 suffix=Path(filename).suffix;view={'.xlsx':'calc','.pptx':'impress','.docx':'writer'}[suffix]
 return {'schema':SCHEMA,'status':'observed','probe_source_sha256':digest(Path(__file__).read_bytes()),'native_api':'x11-and-gi-atspi',
  'window_id_sha256':digest(first['window_id'].encode()),'window_title_sha256':digest(first['title'].encode()),'native_pid':first['pid'],'native_uid':first['uid'],
  'account_sha256':digest(str(first['uid']).encode()),'owned_document_window':owned_document,'owned_native_application':True,'viewport':viewport,'view_id':view,
  'context_id':digest((first['window_id']+'|'+str(first['pid'])).encode()),'modal_id':modal,'focus_id':focused[0]['ref'] if focused else 'native-no-editable-focus',
  'focus_editable':bool(focused and focused[0]['keyboard']),'focus_fill_scope_verified':bool(focused and focused[0]['keyboard'] and focused[1] in ['text','entry','combo box','spin button']),'targets':targets,'visited_native_nodes':visited,'native_state_values_used':True,'task_values_read':False,
  'native_mutations':0,'raster_equality_used':False}

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--filename',required=True);parser.add_argument('--width',type=int,default=1280);parser.add_argument('--height',type=int,default=800);args=parser.parse_args()
 try:value=probe(filename=args.filename,viewport=[args.width,args.height])
 except Exception as error:value={'schema':SCHEMA,'status':'unavailable_or_unsafe','error_class':type(error).__name__,'error_code':str(error)[:100] if isinstance(error,ValueError) else 'native_api_unavailable','native_mutations':0,'raster_equality_used':False}
 print(json.dumps(value,sort_keys=True,separators=(',',':')))

if __name__=='__main__':main()
