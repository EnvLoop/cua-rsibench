"""Bounded actual native branch facts before v23 traversal cap rejection.

No text/name/value, selection or focus mutation is performed. This diagnostic
never returns safe targets or qualifies a partial/virtual accessibility tree.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

SCHEMA='cua-native-accessibility-branch-diagnostic-v26'
V24_SHA='cc04307c4317397054f98ecedc780687df83e764f5d2a75c6cb4ed305b6238c7'
MAX_RECORDS=256
MAX_CHILDREN=512
MAX_DEPTH=32

def sha(raw):return hashlib.sha256(raw).hexdigest()
def load_owner():
 path=Path(__file__).with_name('native_accessibility_probe_v24.py');raw=path.read_bytes()
 if sha(raw)!=V24_SHA:raise ValueError('owned_native_v24_probe_changed')
 spec=importlib.util.spec_from_file_location('envloop_native_v24_diagnostic',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def branches(api,window,*,native_uid,native_pid,limit=MAX_RECORDS):
 records=[];rejections=[]
 def walk(node,path,ancestors,depth):
  if len(records)>=limit:
   rejections.append({'reason':'diagnostic_record_bound','path_sha256':sha(path.encode())});return False
  if depth>MAX_DEPTH:
   rejections.append({'reason':'diagnostic_depth_bound','path_sha256':sha(path.encode())});return False
  state=node.getState();role=node.getRoleName();count=node.childCount
  record={'path_sha256':sha(path.encode()),'ancestor_path_sha256s':[sha(p.encode()) for p in ancestors],'depth':depth,'native_uid':native_uid,'native_pid':native_pid,'role':role,
   'child_count':count,'visible':state.contains(api.STATE_VISIBLE),'showing':state.contains(api.STATE_SHOWING),'focused':state.contains(api.STATE_FOCUSED),'bounds':None,
   'has_table_interface':False,'has_collection_interface':False,'native_mutations':0}
  try:
   r=node.queryComponent().getExtents(api.XY_SCREEN);record['bounds']=[r.x,r.y,r.width,r.height]
  except NotImplementedError:record['component_unavailable']=True
  # Mandatory raw structural facts precede optional interfaces. Unsupported
  # GI table/collection methods must never erase an actual oversized branch.
  records.append(record)
  value=getattr(node,'value',None)
  if value is not None:
   table=None
   try:table=value.get_table_iface();record['has_table_interface']=table is not None
   except Exception as error:record['table_interface_error_class']=type(error).__name__
   try:collection=value.get_collection_iface();record['has_collection_interface']=collection is not None
   except Exception as error:record['collection_interface_error_class']=type(error).__name__
   if table is not None:
    try:record['table_rows']=table.get_n_rows()
    except Exception as error:record['table_rows_error_class']=type(error).__name__
    try:record['table_columns']=table.get_n_columns()
    except Exception as error:record['table_columns_error_class']=type(error).__name__
  if count>MAX_CHILDREN:
   rejections.append({'reason':'existing_child_count_cap','path_sha256':record['path_sha256'],'role':role,'child_count':count,'bounds':record['bounds']});return True
  if not record['visible'] or not record['showing']:
   record['not_traversed']='not_showing_visible';return True
  for index in range(count):
   if not walk(node[index],path+'/'+str(index),ancestors+[path],depth+1):return False
  return True
 walk(window,'window',[],0)
 return {'records':records,'cap_rejections':rejections,'record_count':len(records),'original_caps_unchanged':True,'safe_target_metadata_produced':False,'partial_tree_qualified':False}

def run(*,filename):
 owner=load_owner();frozen=owner.load();first=frozen.x11()
 if not owner.ownership(first,filename):raise ValueError('native_application_account_not_owned')
 api=frozen.native_api();desktop=api.desktop();matches=[]
 if desktop.childCount>64:raise ValueError('native_desktop_application_count_unbounded')
 for app in desktop:
  if app.childCount>64:raise ValueError('native_application_window_count_unbounded')
  for window in app:
   if window.getState().contains(api.STATE_ACTIVE) and window.name==first['title'] and window.pid==first['pid']:matches.append(window)
 if len(matches)!=1:raise ValueError('native_active_accessibility_window_ambiguous')
 result=branches(api,matches[0],native_uid=first['uid'],native_pid=first['pid'])
 if frozen.x11()!=first:raise ValueError('native_window_changed_during_diagnostic')
 return {'schema':SCHEMA,'status':'actual_branch_diagnostic_no_activation','source_sha256':sha(Path(__file__).read_bytes()),'ownership_probe_sha256':V24_SHA,
  'native_uid':first['uid'],'native_pid':first['pid'],'window_title_sha256':sha(first['title'].encode()),'native_mutations':0,'task_text_read':False,**result}

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--filename',required=True);args=parser.parse_args()
 try:value=run(filename=args.filename)
 except Exception as error:value={'schema':SCHEMA,'status':'diagnostic_unavailable','error_class':type(error).__name__,'error_code':str(error)[:100] if isinstance(error,ValueError) else 'native_api_unavailable','native_mutations':0,'safe_target_metadata_produced':False}
 print(json.dumps(value,sort_keys=True,separators=(',',':')))

if __name__=='__main__':main()
