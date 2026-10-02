"""Checked all-app principal scope for the frozen current inventory reader."""
from __future__ import annotations
import hashlib,importlib.util,os,re
from pathlib import Path
from types import FunctionType,SimpleNamespace

V39_SHA='d60af7a40bcdfc492cd7e53ddcca842e8be689bf404025b10a9062cd2888b6c3'
SCHEMA='cua-native-business-current-probe-v40'
EXE_PATH='/usr/lib/libreoffice/program/soffice.bin'
EXE_SHA='65bab645455ca7fe2f38e61f5d36b84dc02c229594d6c0598b5078a819d4f43a'
CLASSES={'.xlsx':'libreoffice-calc','.docx':'libreoffice-writer','.pptx':'libreoffice-impress'}

def executable_reader(pid):
 path=Path(os.readlink(Path('/proc')/str(pid)/'exe'))
 return str(path),hashlib.sha256(path.read_bytes()).hexdigest()

def ownership(first,filename,*,executable_reader=executable_reader):
 expected=CLASSES.get(Path(filename).suffix)
 match=re.fullmatch(r'WM_CLASS\(STRING\)\s*=\s*"([^"\n]+)",\s*"([^"\n]+)"',first.get('wm_class',''))
 if (expected is None or type(first.get('pid')) is not int or first['pid']<=0 or
  type(first.get('uid')) is not int or first['uid']!=first.get('probe_uid') or
  match is None or match[1]!='libreoffice' or match[2]!=expected):return False
 try:return executable_reader(first['pid'])==(EXE_PATH,EXE_SHA)
 except OSError:return False

def load_current():
 path=Path(__file__).with_name('native_current_inventory.py')
 if hashlib.sha256(path.read_bytes()).hexdigest()!=V39_SHA:raise ValueError('Frozen V39 native reader changed')
 spec=importlib.util.spec_from_file_location('envloop_business_v40_current',path);current=importlib.util.module_from_spec(spec);spec.loader.exec_module(current);return current

def scoped_reader():
 current=load_current();old_load=current.load_base;principal_checks=[]
 def load_base():
  base=old_load();original_load=base.load
  def load():
   peer=original_load();peer_load=peer.load
   def checked_peer_load(name,expected):
    result=peer_load(name,expected)
    if name=='native_visible_surface_probe_v31.py':
     original_peer=result.namespace['peer']
     def scoped_peer():
      owner_peer=original_peer();original_owner=owner_peer.owner_module()
      def checked(first,filename):
       accepted=ownership(first,filename)
       if accepted:principal_checks.append({'actual_native_class':CLASSES[Path(filename).suffix],
        'native_pid':first['pid'],'native_uid':first['uid'],'probe_uid':first['probe_uid'],
        'wm_class_sha256':hashlib.sha256(first['wm_class'].encode()).hexdigest(),
        'actual_process_executable_sha256':EXE_SHA,'same_uid_and_exact_executable_checked':True})
       return accepted
      owner=SimpleNamespace(load=original_owner.load,ownership=checked)
      return SimpleNamespace(owner_module=lambda:owner,owned_window=owner_peer.owned_window,
       ancestors=owner_peer.ancestors,OWNER_SHA=owner_peer.OWNER_SHA)
     result.namespace['peer']=scoped_peer
    return result
   peer.load=checked_peer_load;return peer
  base.load=load;return base
 namespace={**vars(current),'__file__':__file__,'SCHEMA':SCHEMA,'load_base':load_base}
 original=current.scoped_reader
 scoped=FunctionType(original.__code__,namespace,original.__name__,original.__defaults__,original.__closure__)
 run,main=scoped()
 def guarded_run(**kwargs):
  result=run(**kwargs)
  return {**result,'native_principal_checks':list(principal_checks),
   'native_principal_policy':'fresh_same_uid_exact_typed_class_attested_soffice_executable'}
 main.__globals__['guarded_run']=guarded_run
 return guarded_run,main

if __name__=='__main__':scoped_reader()[1]()
