"""Real candidate-probe fake native page; pure local data and O_EXCL store."""
from pathlib import Path
from types import SimpleNamespace
from contextlib import ExitStack
from unittest.mock import patch
import copy,hashlib,json,os,struct,zlib,subprocess
from odoo_reference import observer as q
from odoo_reference.config import canonical
def file_sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
from odoo_reference import observer_audit as auditor

def png():
 def chunk(kind,raw):return struct.pack('>I',len(raw))+kind+raw+struct.pack('>I',zlib.crc32(kind+raw)&0xffffffff)
 return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b'\0\xff\xff\xff'))+chunk(b'IEND',b'')
class Store:
 def __init__(self,root):self.root=root;self.names=[];self.page=None
 def write(self,name,raw,kind):
  assert name not in self.names;self.names.append(name)
  if self.page is not None and name.endswith('-context-before.png'):self.page.probe_stem=name
  p=self.root/name;p.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
  fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
  with os.fdopen(fd,'wb') as f:f.write(raw)
  return {'schema':'native-guard-artifact-ref-v1','path':name,'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw),'kind':kind}
class Handle:
 def __init__(self,page,kind,index=0,name=None):self.page=page;self.kind=kind;self.index=index;self.name=name
 def dispose(self):pass
 def is_visible(self):return self.kind=='button' and self.index==0 and self.page.conflict()
 def evaluate(self,source):
  if 'buttons_count:b.length' in source:return {'kind':'form','url':self.page.url,'connected_current_document':True,
   'root_visible':True,'buttons_count':1,'invisible_class':True,'buttons_visible':False,'invalid_visible':False}
  alpha='0' if self.kind in ('button','buttons') else '1'
  return {'document_url':self.page.url,'connected':True,'same_document':True,'tag':'BUTTON' if self.kind=='button' else 'DIV',
   'role':'button' if self.kind=='button' else None,'element_id':self.kind+str(self.index),
   'native_path':[{'tag':self.kind,'index':self.index,'id':self.kind+str(self.index)}],
   'inside_current_form':True,'native_V5_chain_visible':alpha!='0','rect':{'x':0,'y':0,'width':10,'height':10},
   'full_ancestor_style_chain':[{'tag':'DIV','id':'fixture','class':'fixture','display':'block','visibility':'visible','opacity':alpha,
    'hidden':False,'inert':False,'aria_hidden':None}]}
class Locator:
 def __init__(self,page,kind,name=None,visible=False):self.page=page;self.kind=kind;self.name=name;self.visible=visible
 def filter(self,visible=False):return Locator(self.page,self.kind,self.name,visible)
 def element_handles(self):
  items=[Handle(self.page,self.kind,i,self.name) for i in range(2 if self.kind=='button' else 1)]
  return [h for h in items if h.is_visible()] if self.visible else items
class Page:
 def __init__(self,clock,mode):self.clock=clock;self.mode=mode;self.context=object();self.url='http://127.0.0.1/odoo/actual-probe-fixture';self.probe_stem=''
 def conflict(self):return self.mode=='persistent' or self.mode=='transient' and self.clock[0]<.21 or self.mode=='finalconflict' and '-conditional-final-capture-000-' in self.probe_stem
 def locator(self,selector):return Locator(self,'buttons' if 'indicator_buttons' in selector else 'indicator')
 def get_by_role(self,role,name,exact):assert role=='button' and exact;return Locator(self,'button',name)
 def evaluate(self,source):return {'document_url':self.url,'document_visible':'visible','document_has_focus':True,'top_window':True,'focused_tag':'BODY','focused_id':''}
 def screenshot(self,**_):return png()
 def wait_for_timeout(self,ms):self.clock[0]+=ms/1000

def exercise(root,mode='transient'):
 root=Path(root);root.mkdir(mode=0o700,parents=True,exist_ok=True);store=Store(root);clock=[0.0];page=Page(clock,mode);store.page=page
 lock=canonical({'pid':42});lock_path=root/'held.lock';lock_path.write_bytes(lock);lock_path.chmod(0o600)
 credential=root/'held.creds';credential.write_bytes(b'local-fake-credential');credential.chmod(0o600)
 lease={'issued_at':0,'expires_at':1200};window='f'*64
 held=SimpleNamespace(page=page,private=root,lock=lock,lock_path=lock_path,credentials_path=credential,
  credentials_sha=file_sha(credential),lease=lease,window_sha=window,module=SimpleNamespace(require_worker_lease=lambda **_:None),owns=lambda p,m:p is page)
 def meta():return {'visible':True,'top_window':True,'app_shell':True,'focus_owned_app':True,'physical_url':page.url,
  'native_window_sha256':window,'native_capture_monotonic':clock[0]}
 adapter=SimpleNamespace(boundary=held,actor_clock=SimpleNamespace(deadline=720,check=lambda _:None),limits=SimpleNamespace(frame_ttl_seconds=270),store=store,_meta=meta)
 journal=SimpleNamespace(adapter=adapter,trace=[{}],out=root);observer=q.instrumented_observer()
 with ExitStack() as stack:
  stack.enter_context(patch.object(observer.time,'monotonic',side_effect=lambda:clock[0]))
  stack.enter_context(patch.object(q.time,'monotonic',side_effect=lambda:clock[0]))
  stack.enter_context(patch.object(observer.os,'getpid',return_value=42))
  stack.enter_context(patch.object(subprocess,'Popen',side_effect=AssertionError('native_ctor_forbidden')))
  try:result=observer.wait_positive_priority_autosave(page,journal,'positive');error=None
  except BaseException as caught:result=None;error=caught
 names=[p.name for p in root.iterdir() if p.is_file()]
 assert len(names)==len(set(names))
 pair_paths=sorted(root.glob('*-pair.private.json'))
 assert pair_paths
 # Original native metadata needed by the existing saved-only provenance verifier.
 for path,value in [('surface-guard/lease-boundary.private.json',{'lock_sha256':hashlib.sha256(lock).hexdigest(),
   'credential_file_sha256':file_sha(credential),'window_sha256':window,'lock_owner':{'pid':42}}),
   ('surface-guard/turn-000/observation-envelope.private.json',{'lease':lease}),
   ('actor-clock/start.private.json',{'actor_deadline_monotonic':720})]:
  target=root/path;target.parent.mkdir(mode=0o700,parents=True,exist_ok=True);target.write_bytes(canonical(value));target.chmod(0o600)
 checked=[]
 for path in pair_paths:
  read=auditor.ImmutableSavedReader();checked.append(auditor._pair(read,root,path,hashlib.sha256(page.url.encode()).hexdigest(),1));read.unchanged()
 if mode in ('transient','finalconflict'):assert result and result['conflict_count']>0 and result['ended_monotonic']-result['stable_since_monotonic']>=.25
 if mode=='persistent':assert result is None and error is not None and 'timeout' in str(error) and clock[0]<=30.00001
 if mode=='finalconflict':assert len(list(root.glob('*conditional-final-capture-*-pair.private.json')))==2
 return {'mode':mode,'pair_count':len(pair_paths),'all_real_pair_files_reconstructable':True,'diagnostic_names_unique':True,
  'real_control_records':sum(x['real_control_count'] for x in checked),'native_dispatches':0,'success':result is not None}
