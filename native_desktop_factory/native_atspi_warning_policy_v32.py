"""Narrow AT-SPI getter deprecation classification, never native success proof.

The complete stderr remains private. Only the known Python warning form, fixed
native helper locations, explicitly supported AT-SPI getters and exact pinned
source line are informational. Any other stderr is a failure.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
import re

SCHEMA='cua-native-atspi-stderr-classification-v32'
GETTERS=frozenset({'get_collection_iface','get_component_iface'})
PREFIXES=('/tmp/envloop-native-ownership-v24/','/tmp/envloop-native-common-v31/')
FILES=frozenset({'native_accessibility_probe_v23.py','native_accessibility_probe_v24.py','native_visible_surface_probe_v27.py','native_visible_surface_probe_v30.py','native_visible_surface_probe_v31.py'})
HEADER=re.compile(r'(?P<path>/tmp/[A-Za-z0-9_./-]+):(?P<line>[1-9][0-9]*): DeprecationWarning: Atspi\.Accessible\.(?P<method>get_collection_iface|get_component_iface) is deprecated\n\Z')

def classify(stderr,*,source_root,source_sha256s):
 if type(stderr) is not str or len(stderr.encode())>32768:raise ValueError('Native stderr type or bound changed')
 sha=hashlib.sha256(stderr.encode()).hexdigest()
 if stderr=='':return {'schema':SCHEMA,'status':'empty','stderr_sha256':sha,'warning_blocks':0,'methods':[],'native_success_inferred':False}
 lines=stderr.splitlines(keepends=True)
 if len(lines)%2 or not 0<len(lines)<=16:raise ValueError('Unrecognized native stderr block shape')
 methods=[]
 for index in range(0,len(lines),2):
  match=HEADER.fullmatch(lines[index])
  if match is None:raise ValueError('Unrecognized native stderr warning header')
  path=match['path'];name=Path(path).name;method=match['method']
  if name not in FILES or path not in [prefix+name for prefix in PREFIXES] or method not in GETTERS:raise ValueError('Unrecognized native stderr warning source')
  relative='native_desktop_factory/'+name;local=Path(source_root)/relative;raw=local.read_bytes()
  if hashlib.sha256(raw).hexdigest()!=source_sha256s.get(relative):raise ValueError('Native warning source differs from frozen manifest')
  source_lines=raw.decode().splitlines();line=int(match['line'])
  if line>len(source_lines):raise ValueError('Native warning source line invalid')
  actual=source_lines[line-1].strip()
  if '.'+method+'(' not in actual or lines[index+1]!='  '+actual+'\n':raise ValueError('Native warning continuation differs from exact source')
  methods.append(method)
 return {'schema':SCHEMA,'status':'known_atspi_getter_deprecations','stderr_sha256':sha,'warning_blocks':len(methods),'methods':methods,'native_success_inferred':False}
