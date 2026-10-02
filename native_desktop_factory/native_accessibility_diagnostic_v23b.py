"""Additive read-only X11 diagnostics before the frozen v23 ownership guard.

This helper never accepts a different class/UID and never invents safe native
metadata. It reports bounded native facts even when the original guard fails.
Window titles are hashed; environment, command line and document text are not
read. The original v23 probe must be copied beside this exact helper.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess

SCHEMA='cua-native-desktop-accessibility-diagnostic-v23b'
FROZEN_SOURCE='native_accessibility_probe_v23.py'
FROZEN_SHA='fd7663808d3ad48b6999d949fe65e46026a12db7dca42e69dea389fb1155edb8'

def sha(raw):return hashlib.sha256(raw).hexdigest()
def load_frozen():
 path=Path(__file__).with_name(FROZEN_SOURCE);raw=path.read_bytes()
 if sha(raw)!=FROZEN_SHA:raise ValueError('frozen_v23_probe_source_changed')
 spec=importlib.util.spec_from_file_location('envloop_frozen_native_probe_v23',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def diagnostic_x11(*,runner=subprocess.run,proc_root=Path('/proc'),probe_uid=None):
 result={'schema':'cua-native-x11-observed-details-v23b','probe_uid':os.getuid() if probe_uid is None else probe_uid,'queries':[],'process_observed':False}
 def query(label,args,*,raw_allowed=True):
  try:
   completed=runner(args,capture_output=True,text=True,timeout=5);out=completed.stdout;err=completed.stderr
   record={'query':label,'returncode':completed.returncode,'stdout_bytes':len(out.encode()),'stderr_bytes':len(err.encode()),'stdout_sha256':sha(out.encode()),'stderr_sha256':sha(err.encode())}
   if len(out.encode())>8192 or len(err.encode())>8192:record['status']='unbounded';result['queries'].append(record);raise ValueError('native_diagnostic_query_unbounded')
   record['status']='completed' if completed.returncode==0 else 'failed'
   if raw_allowed:record['stdout']=out;record['stderr']=err
   result['queries'].append(record)
   if completed.returncode!=0:raise ValueError('native_diagnostic_query_failed')
   return out.strip()
  except Exception as error:
   if not result['queries'] or result['queries'][-1].get('query')!=label:result['queries'].append({'query':label,'status':'exception','error_class':type(error).__name__})
   raise
 try:
  window=query('active_window',['xdotool','getactivewindow']);result['window_id']=window
  if not re.fullmatch(r'\d+',window):raise ValueError('native_window_id_invalid')
  pid=query('window_pid',['xdotool','getwindowpid',window]);result['pid_observed_raw']=pid
  if not re.fullmatch(r'\d+',pid):raise ValueError('native_window_pid_invalid')
  result['native_pid']=int(pid)
  title=query('window_title',['xdotool','getwindowname',window],raw_allowed=False);result['window_title_sha256']=sha(title.encode())
  klass=query('window_class',['xprop','-id',window,'WM_CLASS']);result['wm_class_raw']=klass
  status=(Path(proc_root)/pid/'status').read_bytes();result['process_status_sha256']=sha(status)
  uid=re.search(rb'^Uid:\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$',status,re.M)
  if uid is None:raise ValueError('native_process_uid_unavailable')
  result['native_process_uids']={'real':int(uid[1]),'effective':int(uid[2]),'saved':int(uid[3]),'filesystem':int(uid[4])}
  result['native_uid']=int(uid[1]);result['uid_matches_probe']=result['native_uid']==result['probe_uid']
  executable=Path(os.readlink(Path(proc_root)/pid/'exe'));result['process_exe_path']=str(executable);result['process_exe_basename']=executable.name
  executable_raw=executable.read_bytes();result['process_exe_sha256']=sha(executable_raw);result['process_exe_bytes']=len(executable_raw)
  result['process_observed']=True;result['status']='observed'
 except Exception as error:result['status']='partial_or_unavailable';result['error_class']=type(error).__name__;result['error_code']=str(error) if isinstance(error,ValueError) else 'native_process_query_unavailable'
 return result

def run(*,filename,viewport,x11_reader=diagnostic_x11,frozen_loader=load_frozen):
 details=x11_reader();value={'schema':SCHEMA,'diagnostic_source_sha256':sha(Path(__file__).read_bytes()),'frozen_probe_sha256':FROZEN_SHA,
  'native_mutations':0,'guard_relaxed':False,'task_text_read':False,'x11_details':details}
 try:
  frozen=frozen_loader();value['frozen_probe_result']=frozen.probe(filename=filename,viewport=viewport)
 except Exception as error:value['frozen_probe_result']={'schema':'cua-native-desktop-accessibility-probe-v23','status':'unavailable_or_unsafe','error_class':type(error).__name__,'error_code':str(error)[:100] if isinstance(error,ValueError) else 'native_api_unavailable','native_mutations':0,'raster_equality_used':False}
 value['status']='diagnostic_observed_no_activation';return value

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--filename',required=True);parser.add_argument('--width',type=int,default=1280);parser.add_argument('--height',type=int,default=800);args=parser.parse_args()
 print(json.dumps(run(filename=args.filename,viewport=[args.width,args.height]),sort_keys=True,separators=(',',':')))

if __name__=='__main__':main()
