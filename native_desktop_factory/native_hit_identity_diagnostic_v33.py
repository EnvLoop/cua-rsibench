"""Bounded native hit identity/parent facts; original V31 refusal preserved.

Only process ID, role, component geometry and documented AT-SPI Object.path /
Object.app.bus_name fields are read. Names, cell/text/value interfaces, child
enumeration and GUI actions are unused. Missing native identity remains unknown.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re

SCHEMA='cua-native-hit-identity-diagnostic-v33'
V31_SHA='55f0c01a57afa4795b5c8c6b02ba25892266f6963cb4d60ccba873627b48d8fa'
MAX_ANCESTORS=32
PRIVATE_FACTS_PATH=Path('/tmp/envloop-native-hit-v33-facts.private.jsonl')
BUS=re.compile(r':[0-9]+\.[0-9]+\Z')
PATH=re.compile(r'/(?:[A-Za-z0-9_]+(?:/[A-Za-z0-9_]+)*)?\Z')

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':')).encode()
def sha(raw):return hashlib.sha256(raw).hexdigest()
def load():
 path=Path(__file__).with_name('native_visible_surface_probe_v31.py')
 if sha(path.read_bytes())!=V31_SHA:raise ValueError('Pinned V31 reader changed')
 spec=importlib.util.spec_from_file_location('envloop_native_hit_identity_v33_bound',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def identity(node):
 result={'kind':'atspi_bus_and_object_path','available':False,'identity_sha256':None,'bus_name_sha256':None,'object_path_sha256':None,'field_errors':{}}
 try:path=node.path
 except Exception as error:result['field_errors']['path']=type(error).__name__;path=None
 try:bus=node.app.bus_name
 except Exception as error:result['field_errors']['app.bus_name']=type(error).__name__;bus=None
 if type(path) is str and len(path)<=1024 and PATH.fullmatch(path):result['object_path_sha256']=sha(path.encode())
 elif path is not None:result['field_errors']['path']='InvalidNativeObjectPath'
 if type(bus) is str and len(bus)<=255 and BUS.fullmatch(bus):result['bus_name_sha256']=sha(bus.encode())
 elif bus is not None:result['field_errors']['app.bus_name']='InvalidNativeUniqueBusName'
 if result['object_path_sha256'] is not None and result['bus_name_sha256'] is not None:
  result.update(available=True,identity_sha256=sha(canonical({'bus_name':bus,'object_path':path})))
 return result

def structural_facts(node,owned_window,Atspi,*,sink=None):
 # Mandatory identity/process/role facts survive an optional geometry error.
 row={'identity':identity(node),'wrapper_instance_sha256':sha(str(id(node)).encode()),'native_pid':None,'native_role':None,'geometry':None,'proxy_equals_owned_window':None,'field_errors':{}}
 for field,read in [('native_pid',lambda:node.get_process_id()),('native_role',lambda:node.get_role_name()),('proxy_equals_owned_window',lambda:bool(node==owned_window))]:
  try:row[field]=read()
  except Exception as error:row['field_errors'][field]=type(error).__name__
  if sink is not None:sink({'stage':'native_structural_field','field':field,'facts':row})
 try:
  component=node.get_component_iface()
  if component is not None:
   box=component.get_extents(Atspi.CoordType.SCREEN);row['geometry']=[int(box.x),int(box.y),int(box.width),int(box.height)]
 except Exception as error:row['field_errors']['geometry']=type(error).__name__
 if sink is not None:sink({'stage':'native_structural_geometry','facts':row})
 return row

def parent_diagnostic(node,owned_window,Atspi,*,limit=MAX_ANCESTORS,sink=None):
 if type(limit) is not int or not 1<=limit<=MAX_ANCESTORS:raise ValueError('Existing native ancestor bound required')
 owned=structural_facts(owned_window,owned_window,Atspi,sink=sink);rows=[];cursor=node;seen=set();status='cap_refused';native_match=False;proxy_mismatch=False
 for ordinal in range(limit):
  if cursor is None:status='missing_parent';break
  row=structural_facts(cursor,owned_window,Atspi,sink=sink);row['ordinal']=ordinal;rows.append(row)
  current=row['identity'];native_match=bool(current['available'] and owned['identity']['available'] and current['identity_sha256']==owned['identity']['identity_sha256'])
  row['native_identity_matches_owned_window']=native_match
  if native_match:
   proxy_mismatch=row['proxy_equals_owned_window'] is False;status='native_owned_identity_observed_proxy_mismatch' if proxy_mismatch else 'native_owned_identity_observed';break
  token=('native',current['identity_sha256']) if current['available'] else ('wrapper',row['wrapper_instance_sha256'])
  if token in seen:status='cycle_refused';break
  seen.add(token)
  if ordinal+1==limit:status='cap_refused';break
  try:cursor=cursor.get_parent()
  except Exception as error:row['field_errors']['parent']=type(error).__name__;status='parent_query_failed';break
 window_roles={'frame','window','dialog','alert'}
 foreign=[r for r in rows if r['native_role'] in window_roles and r['identity']['available'] and owned['identity']['available'] and r['identity']['identity_sha256']!=owned['identity']['identity_sha256']]
 return {'schema':'cua-native-parent-identity-facts-v33','status':status,'owned_window':owned,'parent_chain':rows,'existing_ancestor_limit':limit,'native_owned_identity_in_chain':native_match,'proxy_identity_mismatch_observed':proxy_mismatch,
  'different_native_window_identity_observed':bool(foreign),'same_pid_is_ownership_proof':False,'original_guard_refusal_preserved':True,'native_action_authorized':False,'diagnostic_node_names_or_values_read':False}

class PrivateFacts:
 def __init__(self,path):
  self.path=Path(path);self.count=0;self.bytes=0;self.closed=False
  self.file=os.fdopen(os.open(self.path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb')
 def append(self,row):
  raw=canonical(row)+b'\n'
  if self.closed or self.count>=192 or self.bytes+len(raw)>131072:raise ValueError('Native private structural journal bound exceeded')
  self.file.write(raw);self.file.flush();os.fsync(self.file.fileno());self.count+=1;self.bytes+=len(raw)
 def close(self):
  if not self.closed:self.file.close();self.closed=True
 def reference(self):
  raw=self.path.read_bytes();return {'sha256':sha(raw),'bytes':len(raw),'records':self.count,'mode':0o600,'raw_task_text_present':False,'actor_access_authorized':False}

def run(*,filename,viewport,loader=load,facts_path=PRIVATE_FACTS_PATH):
 reader=loader();old=reader.namespace['peer']();owner=old.owner_module();frozen,x11,wrapped=old.owned_window(owner,filename);window=wrapped.value
 import gi
 gi.require_version('Atspi','2.0');from gi.repository import Atspi
 box=reader.geometry(Atspi,window,viewport)
 if box is None:raise ValueError('Actual owned window geometry unavailable')
 point=[box[0]+box[2]//2,box[1]+box[3]//2];facts=None
 writer=PrivateFacts(facts_path)
 def original_ancestry_with_capture(node,owned):
  nonlocal facts
  try:return old.ancestors(node,owned)
  except Exception as original_error:
   if facts is None:
    try:facts=parent_diagnostic(node,owned,Atspi,sink=writer.append)
    except Exception as diagnostic_error:facts={'status':'structural_capture_failed','error_class':type(diagnostic_error).__name__,'original_guard_refusal_preserved':True,'native_action_authorized':False}
   raise original_error
 try:
  hit,depth=reader.physical_hit(Atspi,window,point,pid=x11['pid'],viewport=viewport,ancestry=original_ancestry_with_capture)
  status='original_native_hit_returned_unqualified';failure=None
  # The diagnostic still does not enable the returned hit or grant credit.
  facts=parent_diagnostic(hit,window,Atspi,sink=writer.append) if facts is None else facts
 except Exception as error:
  status='original_native_hit_refused_unqualified';failure={'class':type(error).__name__,'message_sha256':sha(str(error).encode())}
  if facts is None:facts={'status':'failure_before_ancestor_capture','owned_window':structural_facts(window,window,Atspi),'original_guard_refusal_preserved':True,'native_action_authorized':False}
 writer.close()
 if frozen.x11()!=x11:raise ValueError('Owned native window changed during identity diagnostic')
 return {'schema':SCHEMA,'status':status,'diagnostic_source_sha256':sha(Path(__file__).read_bytes()),'pinned_reader_v31_sha256':V31_SHA,'physical_point_from_owned_window_geometry':point,'native_pid':x11['pid'],'native_uid':x11['uid'],
  'window_id_sha256':sha(x11['window_id'].encode()),'window_title_sha256':sha(x11['title'].encode()),'failure':failure,'native_structural_facts':facts,'private_facts_file':writer.reference(),'existing_owned_window_title_comparison_used':True,'native_qualification_passed':False,'native_mutations':0,'actor_actions':0,'model_calls':0,'diagnostic_node_names_or_values_read':False}

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--filename',required=True);parser.add_argument('--width',type=int,default=1280);parser.add_argument('--height',type=int,default=800);args=parser.parse_args()
 try:value=run(filename=args.filename,viewport=[args.width,args.height])
 except Exception as error:value={'schema':SCHEMA,'status':'identity_diagnostic_unavailable_unqualified','error_class':type(error).__name__,'error_message_sha256':sha(str(error).encode()),'native_mutations':0,'native_qualification_passed':False}
 print(json.dumps(value,sort_keys=True,separators=(',',':')))

if __name__=='__main__':main()
