"""One native ownership/target gate for GitLab teacher, students and controls.

Safety metadata never consumes task answers or compares document values.
Raw images, envelopes, lease checks, nonce/intent and driver result are durable.
"""
from __future__ import annotations
from dataclasses import asdict,replace
import fcntl,json,math,os,time
from pathlib import Path
from urllib.parse import urlsplit
from cursibench import native_surface_guard_policy_v1 as policy
from cursibench.scale_action_contract import ContractError,ContractLimits,make_observation
from cursibench.scale_action_contract_v066 import validate_action
from . import vision_actor as prior,runtime,operators

META_JS=r"""({project,points})=>{
 const visible=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&r.bottom>0&&r.right>0&&r.top<innerHeight&&r.left<innerWidth&&s.visibility!=='hidden'&&s.display!=='none'};
 const bounds=e=>{const r=e.getBoundingClientRect(),l=Math.max(0,Math.floor(r.left)),t=Math.max(0,Math.floor(r.top));return[l,t,Math.min(innerWidth,Math.ceil(r.right))-l,Math.min(innerHeight,Math.ceil(r.bottom))-t]};
 if(!window.__envloopNative){window.__envloopNative={document:crypto.randomUUID(),counter:0,map:new WeakMap()}}
 const ref=e=>{if(!window.__envloopNative.map.has(e))window.__envloopNative.map.set(e,'g'+(++window.__envloopNative.counter));let r=window.__envloopNative.map.get(e);e.setAttribute('data-envloop-native-ref',r);return r};
 const editable=e=>e.isContentEditable||['INPUT','TEXTAREA'].includes(e.tagName)&&!e.readOnly&&!['password','hidden','submit','button','checkbox','radio','file'].includes(e.type);
 const keyboard=e=>editable(e)||e.tagName==='SELECT';
 const owned=e=>{const a=e.closest('a[href]');if(a){try{let u=new URL(a.href,location.href);if(u.origin!==location.origin||!u.pathname.startsWith(project+'/')&&u.pathname!==project)return false}catch{return false}}
  if(e.closest('header,.super-sidebar,.user-menu,[data-testid="user-menu"],[data-testid="super-sidebar"]'))return false;
  return !!e.closest('main,[role="main"],.content-wrapper,.page-content,[role="dialog"],.modal.show')};
 const row=e=>{const editor=e.closest('.monaco-editor'),proxy=editor&&e===document.activeElement&&editable(e)?editor:e;let b=bounds(proxy),hit=document.elementFromPoint(b[0]+b[2]/2,b[1]+b[3]/2),key=keyboard(e),safe=owned(e);return{ref:ref(e),bounds:b,visible:visible(proxy),enabled:!e.disabled&&safe,obscured:!hit||hit!==e&&!e.contains(hit)&&!proxy.contains(hit),keyboard:key,
 actions:['click','double_click','scroll','drag'].concat(key?['key']:[]).concat(editable(e)?['type']:[]),role:e.getAttribute('role')||({INPUT:'textbox',TEXTAREA:'textbox',BUTTON:'button',A:'link',SELECT:'combobox'}[e.tagName]||'control'),label:(e.getAttribute('aria-label')||e.innerText||e.title||e.getAttribute('placeholder')||'').replace(/\s+/g,' ').slice(0,200)}};
 const elements=Array.from(document.querySelectorAll('a,button,input,select,textarea,[role="button"],[role="link"],[role="menuitem"],[role="option"],[contenteditable="true"]')).filter(visible).slice(0,300);
 const targets=elements.map(row).filter(r=>r.bounds[2]>0&&r.bounds[3]>0);
 const main=document.querySelector('main,[role="main"],.content-wrapper,.page-content');if(main&&visible(main))targets.unshift({ref:'workspace',bounds:bounds(main),visible:true,enabled:true,obscured:false,keyboard:false,actions:['click','double_click','scroll','drag']});
 const active=document.activeElement,focus=active&&(visible(active)||active.closest('.monaco-editor')&&editable(active))?row(active):null;if(focus&&!targets.some(t=>t.ref===focus.ref))targets.push(focus);
 const modals=Array.from(document.querySelectorAll('[role="dialog"],[aria-modal="true"],.modal.show,dialog[open]')).filter(visible).map(ref);
 const hits=(points||[]).map((p,i)=>{let e=document.elementFromPoint(p.x,p.y);if(!e)return{ref:'point-'+i,bounds:[p.x,p.y,1,1],visible:false,enabled:false,obscured:true,keyboard:false,actions:['click']};let t=e.closest('a,button,input,textarea,select,[role="button"],[contenteditable="true"]')||e,r=row(t);return{...r,native_ref:r.ref,ref:'point-'+i,bounds:[p.x,p.y,1,1]}});
 const gon=window.gon||{};const uid=gon.current_user_id||gon.user_id||(gon.current_user||{}).id||document.body.getAttribute('data-user-id')||'';
 return{schema:'gitlab-native-surface-v12',top:window===window.top,visible:document.visibilityState==='visible',account_uid:String(uid),document_id:window.__envloopNative.document,
 path:location.pathname,viewport:[innerWidth,innerHeight],targets,focus,modals,hits};
}"""

class EvidenceStore:
 def __init__(self,root):
  self.root=Path(root);self.root.mkdir(parents=True,mode=0o700,exist_ok=True)
  if self.root.is_symlink() or self.root.stat().st_mode&0o077:raise policy.GuardError('unsafe_native_artifact_root')
 def put(self,name,raw,kind):
  path=self.root/name;path.parent.mkdir(parents=True,mode=0o700,exist_ok=True)
  if path.exists() or path.is_symlink():raise policy.GuardError('native_artifact_replay')
  fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
  with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
  return {'schema':'native-guard-artifact-ref-v1','path':name,'sha256':prior.hashlib.sha256(raw).hexdigest(),'size':len(raw),'kind':kind}
 def json(self,name,value,kind):return self.put(name,policy.canonical(value),kind)

class NativeGuard:
 def __init__(self,active,root,*,account_uid,partition):
  self.active=active;self.page=active.page;self.project=active.project_path;self.partition=partition
  self.store=EvidenceStore(root);self.clock=time.monotonic;self.expected_uid=str(account_uid);self.observed=None;self.quarantined=False
  self.last_result=None;self.last_decision=None;self.consumed=set();self.lease_fd=None;self.lease=None
 def bind(self):
  self.lease_fd=os.open(self.store.root/'owned-native-surface.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
  fcntl.flock(self.lease_fd,fcntl.LOCK_EX|fcntl.LOCK_NB);tick=self.clock()
  evidence=self.store.json('lease.private.json',{'pid':os.getpid(),'lock_inode':os.fstat(self.lease_fd).st_ino,
   'expected_account_uid_sha256':policy.digest(self.expected_uid),'project_path_sha256':policy.digest(self.project),'page_object':id(self.page)},'lease_evidence')
  self.lease={'schema':'native-surface-lease-v1','lease_id':'gitlab-'+str(os.getpid())+'-'+str(id(self)), 'cell_id':'gitlab',
   'account_sha256':policy.digest(self.expected_uid),'workspace_sha256':policy.digest(self.project),'window_sha256':policy.digest(id(self.page)),
   'owner_sha256':policy.digest(os.getpid()),'issued_at':tick,'expires_at':tick+720,'evidence':evidence}
  policy.validate_lease(self.lease)
 def close(self):
  if self.lease_fd is not None:fcntl.flock(self.lease_fd,fcntl.LOCK_UN);os.close(self.lease_fd);self.lease_fd=None
 async def meta(self,points=None):
  meta=await self.page.evaluate(META_JS,{'project':self.project,'points':points or []})
  if meta.get('schema')!='gitlab-native-surface-v12':raise policy.GuardError('invalid_native_surface')
  meta['url']=self.page.url;return meta
 def owned(self,meta):
  url=urlsplit(meta['url'])
  return(self.page is self.active.page and self.active._scoped_url() and url.port==8018 and meta['top'] is True and meta['visible'] is True and
   meta['account_uid']==self.expected_uid and bool(self.expected_uid))
 async def image(self):return await self.page.screenshot(type='png',full_page=False,animations='disabled',mask=[self.page.locator('input[type="password"]')])
 def envelope(self,obs,meta,image,phase,action=None):
  prefix=f'turn-{obs.step:03d}/{phase}';image_ref=self.store.put(prefix+'.png',image,'raw_'+phase+'_image')
  raw_ref=self.store.json(prefix+'-native.private.json',meta,'native_'+phase+'_envelope')
  keys=('ref','bounds','visible','enabled','obscured','keyboard','actions');targets=[{k:r[k] for k in keys} for r in meta['targets']+meta['hits']]
  focus=(meta['focus'] or {}).get('ref','body');modal='none' if not meta['modals'] else 'owned-dialog'
  value={'schema':'native-surface-envelope-v1','policy_sha256':policy.POLICY_SHA,'phase':phase,'lease':self.lease,
   'task_id':obs.task_id,'task_binding_sha256':obs.task_binding_sha256,'frame_id':obs.frame_id,'step':obs.step,
   'captured_at':self.clock(),'expires_at':obs.expires_at,'viewport':meta['viewport'],'view_id':'gitlab-project',
   'context_id':policy.digest({'url':meta['url'],'document':meta['document_id'],'modals':meta['modals']}),
   'modal_id':modal,'focus_id':focus,'allowed_views':['gitlab-project'],'allowed_modals':['none','owned-dialog'],
   'allowed_focus':self.observed['allowed_focus'] if self.observed else list(dict.fromkeys([focus]+[r['ref'] for r in targets if r['keyboard']])),
   'owned_surface':self.owned(meta),'targets':targets,'raw_image':image_ref,'raw_envelope':raw_ref}
  policy.validate_envelope(value);self.store.json(prefix+'-envelope.private.json',value,'native_'+phase+'_envelope');return value
 def lease_check(self,lease):
  tick=self.clock();active=self.lease_fd is not None
  if active:
   try:fcntl.flock(self.lease_fd,fcntl.LOCK_EX|fcntl.LOCK_NB);active=os.fstat(self.lease_fd).st_ino==(self.store.root/'owned-native-surface.lock').stat().st_ino
   except (OSError,BlockingIOError):active=False
  evidence=self.store.json(f'turn-{self.active.step:03d}/lease-check.private.json',{'kernel_lock_active':active,'pid':os.getpid(),'checked_at':tick},'lease_check')
  return {'schema':'native-surface-lease-check-v1','lease_sha256':policy.digest(lease),'status':'active' if active else 'inactive',
   'checked_at':tick,'expires_at':min(tick+5,self.lease['expires_at']),'evidence':evidence}
 async def observe(self,memory):
  if self.quarantined:raise policy.GuardError('native_guard_quarantined')
  meta=await self.meta();image=await self.image();controls=[{k:r[k] for k in ['ref','role','label','visible','enabled']} for r in meta['targets'] if r.get('label')][:120]
  previous=self.last_result
  if previous is not None and previous['status']=='rejected':previous={'status':'rejected','code':'invalid_action'}
  obs=make_observation(task_id=self.active.task['task_id'],task_binding_sha256=self.active.task['package_sha256'],instruction=self.active.task['visible_instruction'],
   step=self.active.step,screenshot_bytes=image,controls=controls,previous_action_result=previous,memory=memory,limits=ContractLimits(max_step=90))
  if self.last_decision is not None and self.last_decision['status']=='rejected':obs=replace(obs,previous_action_result=policy.rejection_feedback(self.last_decision))
  self.observed=None;self.observed=self.envelope(obs,meta,image,'observation');handles={}
  frame=prior.Frame(obs,handles,self.page.url);self.active.latest=frame;return frame
 async def dispatch(self,action):
  if self.observed is None or self.quarantined:raise policy.GuardError('native_observation_missing')
  obs=self.active.latest.observation;checked=validate_action(action,obs,current_frame_id=obs.frame_id)
  points=[checked[k] for k in ['target','from','to'] if k in checked and set(checked[k])=={'x','y'}]
  resolutions=[];self._resolved_handles={}
  for target in [checked[k] for k in ['target','from','to'] if k in checked and 'ref' in checked[k]]:
   ref=target['ref'];handles=await self.page.locator('[data-envloop-native-ref="'+ref+'"]').element_handles()
   native={'found_count':len(handles),'connected':False,'ref':ref}
   if len(handles)==1:
    native.update(await handles[0].evaluate('(el)=>({connected:el.isConnected,ref:el.getAttribute("data-envloop-native-ref"),document_id:(window.__envloopNative||{}).document||null})'))
    if native['connected'] and native['ref']==ref:self._resolved_handles[ref]=handles[0]
   resolutions.append(native)
  self.store.json(f'turn-{obs.step:03d}/target-resolution.private.json',{'requested_refs':resolutions,'nonwaiting':True,'gui_driver_called':False},'native_predispatch_envelope')
  meta=await self.meta(points)
  for native in resolutions:
   if native['found_count']!=1 or not native['connected'] or native['ref'] not in self._resolved_handles or native.get('document_id')!=meta['document_id']:
    for row in meta['targets']:
     if row['ref']==native['ref']:row['enabled']=False
  image=await self.image();current=self.envelope(obs,meta,image,'predispatch',checked)
  decision=policy.decision(self.observed,current,checked,lease_check=self.lease_check)
  self.last_decision=decision
  self.store.json(f'turn-{obs.step:03d}/decision.private.json',decision,'dispatch_receipt')
  if obs.frame_id in self.consumed:raise policy.GuardError('native_nonce_replay')
  self.consumed.add(obs.frame_id);self.store.json(f'turn-{obs.step:03d}/nonce.private.json',{'frame_id':obs.frame_id,'consumed':True},'dispatch_receipt')
  accepted=decision['status']=='accepted';intent=None;driver_ref=None;driver_result='not_attempted';status=decision['status'];reason=decision['reason']
  if accepted:
   self._approved_meta=meta
   intent=self.store.json(f'turn-{obs.step:03d}/intent.private.json',{'action':checked,'decision_sha256':policy.digest(decision)},'action_intent')
   try:await self.drive(checked);driver_result='succeeded';status='applied';reason='native_driver_succeeded'
   except BaseException as error:driver_result='unknown';status='failed';reason='native_driver_uncertain';self.quarantined=True
   driver_ref=self.store.json(f'turn-{obs.step:03d}/driver.private.json',{'result':driver_result},'driver_result')
  elif status=='hard_stop':self.quarantined=True
  receipt={'schema':'native-surface-dispatch-receipt-v1','policy_sha256':policy.POLICY_SHA,'decision_sha256':policy.digest(decision),
   'action_sha256':policy.digest(checked),'frame_id':obs.frame_id,'step':obs.step,'status':status,'reason':reason,'turn_consumed':True,'nonce_invalidated':True,
   'intent':intent,'driver_result':driver_result,'driver_evidence':driver_ref}
  policy.validate_receipt(receipt);self.store.json(f'turn-{obs.step:03d}/receipt.private.json',receipt,'dispatch_receipt')
  self.last_result={'status':'applied','code':'ok'} if status=='applied' else {'status':'rejected','code':'invalid_action'}
  self.active.step+=1;self.active.latest=None;self.observed=None
  if status=='applied' and checked['type']=='finish':self.active.finished=True
  if status in ['failed','hard_stop']:raise policy.GuardError(reason)
  return self.last_result
 async def drive(self,action):
  kind=action['type'];frame=self.active.latest
  async def point(target):
   if 'ref' in target:return self._resolved_handles[target['ref']]
   return None
  if kind=='wait':await self.page.wait_for_timeout(action['duration_ms']);return
  if kind=='finish':return
  if kind in ['click','double_click']:
   handle=await point(action['target'])
   if handle is not None:await (handle.dblclick(timeout=15000) if kind=='double_click' else handle.click(timeout=15000))
   else:await (self.page.mouse.dblclick(action['target']['x'],action['target']['y']) if kind=='double_click' else self.page.mouse.click(action['target']['x'],action['target']['y']))
  elif kind in ['type','key']:
   target=action.get('target');handle=await point(target) if target else None
   if target:
    if handle is not None:await handle.focus()
    else:await self.page.mouse.click(target['x'],target['y'])
   meta=await self.meta();focus=meta['focus']
   if not self.owned(meta) or not focus or not focus['keyboard'] or not focus['enabled'] or focus['obscured']:raise policy.GuardError('editable_focus_changed_or_unsafe')
   if target and 'ref' in target and focus['ref']!=target['ref']:raise policy.GuardError('editable_focus_changed_or_unsafe')
   if target and 'x' in target and focus['ref']!=self._approved_meta['hits'][0].get('native_ref'):raise policy.GuardError('editable_focus_changed_or_unsafe')
   if not target and focus['ref']!=self.observed['focus_id']:raise policy.GuardError('editable_focus_changed_or_unsafe')
   self.store.json(f'turn-{frame.observation.step:03d}/focus.private.json',meta,'driver_result')
   if kind=='key':await self.page.keyboard.press(action['key'])
   else:
    if action['mode']=='fill':await self.page.keyboard.press('ControlOrMeta+A')
    await self.page.keyboard.insert_text(action['text'])
  elif kind=='scroll':await self.page.mouse.wheel(action['dx'],action['dy'])
  elif kind=='drag':
   points=[]
   for key in ['from','to']:
    target=action[key];handle=await point(target)
    if handle is not None:
     box=await handle.bounding_box();points.append((box['x']+box['width']/2,box['y']+box['height']/2))
    else:points.append((target['x'],target['y']))
   await self.page.mouse.move(*points[0]);await self.page.mouse.down();await self.page.mouse.move(*points[1],steps=8);await self.page.mouse.up()
  else:raise policy.GuardError('invalid_action')

class GuardedSession:
 def __init__(self,active,guard):self.active,self.guard=active,guard
 def __getattr__(self,key):return getattr(self.active,key)
 def observe(self,*,memory):return self.active.loop.call(self.guard.observe(memory)).observation
 def current_frame_id(self):
  frame=self.active.latest
  return frame.observation.frame_id if frame and not self.guard.quarantined and self.guard.clock()<=frame.observation.expires_at else 'stale'
 def dispatch(self,action):return self.active.loop.call(self.guard.dispatch(action))
 def read_saved_state(self):return self.active.read_saved_state()
