"""Prospective ownership correction derived from the actual v23b diagnostic.

The original v23 file remains pinned. X11 account equality stays mandatory.
A typed LibreOffice class must match the document application and the actual
soffice executable bytes from the attested guest. This source grants no native
qualification; GI/focus/target availability still requires a new real probe.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
from types import ModuleType

PIN='fd7663808d3ad48b6999d949fe65e46026a12db7dca42e69dea389fb1155edb8'
# Actual root-attested v23d process executable. A different guest image requires
# a new independently attested source binding, never an arbitrary CLI override.
ATTESTED_EXE_SHA='65bab645455ca7fe2f38e61f5d36b84dc02c229594d6c0598b5078a819d4f43a'
SCHEMA='cua-native-desktop-accessibility-probe-v24'
CLASS_BY_EXTENSION={'.xlsx':'libreoffice-calc','.pptx':'libreoffice-impress','.docx':'libreoffice-writer'}
OBSERVED_NATIVE_CLASSES=['libreoffice-calc']

def sha(raw):return hashlib.sha256(raw).hexdigest()
def ownership(first,filename):
 expected=CLASS_BY_EXTENSION.get(Path(filename).suffix);match=re.fullmatch(r'WM_CLASS\(STRING\)\s*=\s*"([^"\n]+)",\s*"([^"\n]+)"',first['wm_class'])
 if expected not in OBSERVED_NATIVE_CLASSES:return False
 if first['uid']!=first['probe_uid'] or match is None or match[1]!='libreoffice' or match[2]!=expected:return False
 try:
  executable=Path(os.readlink(Path('/proc')/str(first['pid'])/'exe'))
  return str(executable)=='/usr/lib/libreoffice/program/soffice.bin' and sha(executable.read_bytes())==ATTESTED_EXE_SHA
 except OSError:return False

def load():
 path=Path(__file__).with_name('native_accessibility_probe_v23.py');raw=path.read_bytes()
 if sha(raw)!=PIN:raise ValueError('frozen_v23_probe_source_changed')
 source=raw.decode();before="require(first['uid']==first['probe_uid'] and 'soffice' in first['wm_class'].lower(),'native_application_account_not_owned')"
 after="require(ownership(first,filename),'native_application_account_not_owned')"
 if source.count(before)!=1:raise ValueError('native_ownership_patch_not_exactly_once')
 source=source.replace(before,after);module=ModuleType('envloop_native_probe_v24_bound');module.__file__=__file__;module.__dict__['ownership']=ownership
 exec(compile(source,'envloop-native-probe-v24-bound','exec'),module.__dict__);module.SCHEMA=SCHEMA;return module


def probe(*,filename,viewport):
 result=load().probe(filename=filename,viewport=viewport)
 result['native_ownership_policy']='exact-libreoffice-instance-and-typed-class-attested-soffice-exe-same-uid'
 result['observed_native_classes']=OBSERVED_NATIVE_CLASSES
 return result

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--filename',required=True);parser.add_argument('--width',type=int,default=1280);parser.add_argument('--height',type=int,default=800);args=parser.parse_args()
 try:value=probe(filename=args.filename,viewport=[args.width,args.height])
 except Exception as error:value={'schema':SCHEMA,'status':'unavailable_or_unsafe','error_class':type(error).__name__,'error_code':str(error)[:100] if isinstance(error,ValueError) else 'native_api_unavailable','native_mutations':0,'raster_equality_used':False}
 print(json.dumps(value,sort_keys=True,separators=(',',':')))

if __name__=='__main__':main()
