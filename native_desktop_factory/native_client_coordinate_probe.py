"""Paired owned native point facts with X11 absolute client coordinates."""
import hashlib,importlib.util,json,re
from pathlib import Path
from types import FunctionType

BASE_SHA='f1dbec68fa68f6c33e4b82a4adf2728354c034b7654938653aabae949d98bd86'

def absolute_client_geometry(frozen,x11):
 raw=frozen.command(['xwininfo','-id',x11['window_id']]);fields={}
 window=re.search(r'Window id:\s*(0x[0-9a-fA-F]+)',raw)
 if window is None or int(window[1],16)!=int(x11['window_id']):raise ValueError('Actual X11 queried client window differs')
 for key,pattern in [('X',r'Absolute upper-left X:\s*(-?[0-9]+)'),('Y',r'Absolute upper-left Y:\s*(-?[0-9]+)'),('WIDTH',r'Width:\s*([0-9]+)'),('HEIGHT',r'Height:\s*([0-9]+)')]:
  match=re.search(pattern,raw)
  if match is None:raise ValueError('Actual X11 absolute client geometry unavailable')
  fields[key]=int(match[1])
 if fields['WIDTH']<=0 or fields['HEIGHT']<=0:raise ValueError('Actual X11 absolute client geometry invalid')
 return {'WINDOW':int(x11['window_id']),**fields,'source':'xwininfo_absolute_client_origin','actual_raw_metadata_sha256':hashlib.sha256(raw.encode()).hexdigest()}

def main():
 path=Path(__file__).with_name('native_coordinate_probe.py')
 if hashlib.sha256(path.read_bytes()).hexdigest()!=BASE_SHA:raise ValueError('Frozen coordinate probe source changed')
 spec=importlib.util.spec_from_file_location('envloop_client_coordinate_base',path);base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
 scope={**vars(base),'x11_geometry':absolute_client_geometry}
 run=FunctionType(base.run.__code__,scope,base.run.__name__,base.run.__defaults__,base.run.__closure__)
 import argparse
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--filename',required=True);args=parser.parse_args()
 print(json.dumps(run(filename=args.filename,points=[[52,170],[258,767],[648,414]]),sort_keys=True,separators=(',',':')))

if __name__=='__main__':main()
