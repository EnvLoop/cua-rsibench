"""Uniform original-Magento native safety envelope; no whole-raster equality."""
from __future__ import annotations
from dataclasses import replace
from hashlib import sha256
import json
import os
import time
from urllib.parse import urlsplit
from cursibench import native_surface_guard_policy_v1 as policy
from cursibench.scale_action_contract import ContractLimits,make_observation
from cursibench.scale_action_contract_v066 import validate_action,public_receipt
from cursibench.scale_action_output_v066 import normalize_model_action,render_for_model
from enterprise_fallback.odoo18.odoo_native_surface_evidence_v6 import EvidenceStore
from enterprise_fallback.odoo18.odoo_actor_clock_v1 import ActorClock

PROFILE='magento-owned-native-surface-v1'
VIEWPORT={'width':1440,'height':1000}

NATIVE_JS=r"""(points)=>{
 const visible=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&r.right>0&&r.bottom>0&&r.left<innerWidth&&r.top<innerHeight&&s.display!=='none'&&s.visibility!=='hidden';};
 const bounds=e=>{const r=e.getBoundingClientRect(),x=Math.max(0,Math.floor(r.left)),y=Math.max(0,Math.floor(r.top));return [x,y,Math.min(innerWidth,Math.ceil(r.right))-x,Math.min(innerHeight,Math.ceil(r.bottom))-y];};
 const keyboard=e=>['INPUT','TEXTAREA'].includes(e.tagName)&&!e.disabled&&!e.readOnly||e.isContentEditable;
 const unsafe=e=>!!e.closest('.admin-user')||(()=>{const a=e.closest('a[href]');if(!a)return false;try{const u=new URL(a.href,location.href);return a.target==='_blank'||u.origin!==location.origin||!/^\/admin(?:\/|$)/.test(u.pathname)||/\/(?:logout|system_account)(?:\/|$)/.test(u.pathname);}catch{return true;}})();
 const enabled=e=>{const c=e.closest('button,input,textarea,select,[aria-disabled="true"],[inert]');return !!e&&!(c&&(c.disabled||c.getAttribute('aria-disabled')==='true'||c.hasAttribute('inert')))&&!unsafe(e);};
 const modalNodes=Array.from(document.querySelectorAll('.modal-popup._show,.modal-slide._show,[aria-modal="true"],[role="dialog"],dialog[open]')).filter(visible);
 const modal=modalNodes.length?modalNodes[modalNodes.length-1]:null;
 const nodes=Array.from(document.querySelectorAll('button,a,input,textarea,select,[role="button"],[role="menuitem"],[role="option"],[role="tab"],[contenteditable="true"]')).filter(visible).sort((a,b)=>Number(!!modal&&modal.contains(b))-Number(!!modal&&modal.contains(a))).slice(0,128);
 nodes.forEach((e,i)=>e.setAttribute('data-envloop-ref','m'+String(i).padStart(3,'0')));
 const target=e=>{const b=bounds(e),hit=document.elementFromPoint(b[0]+b[2]/2,b[1]+b[3]/2),edit=keyboard(e);return {ref:e.getAttribute('data-envloop-ref')||'body',bounds:b,visible:true,enabled:enabled(e),obscured:!!hit&&hit!==e&&!e.contains(hit),keyboard:edit,actions:edit?['click','double_click','type','key','scroll','drag']:['click','double_click','scroll','drag'],role:e.getAttribute('role')||e.tagName.toLowerCase(),label:(e.getAttribute('aria-label')||e.getAttribute('title')||e.getAttribute('placeholder')||e.innerText||e.name||'').trim().replace(/\s+/g,' ').slice(0,220)};};
 const all=nodes.map(target),targets=modal?all.filter((t,i)=>modal.contains(nodes[i])):all;
 const account=Array.from(document.querySelectorAll('.admin-user .admin-user-account-text')).filter(visible);
 const active=document.activeElement;
 const focus=active&&visible(active)?{ref:active.getAttribute('data-envloop-ref')||'body',editable:keyboard(active)}:null;
 const hits=(points||[]).map((p,i)=>{const e=document.elementFromPoint(p.x,p.y);return {ref:'point-'+i,bounds:[p.x,p.y,1,1],visible:!!e&&visible(e),enabled:!!e&&enabled(e)&&(!modal||modal.contains(e)),obscured:!e,keyboard:!!e&&keyboard(e),actions:e&&keyboard(e)?['click','double_click','type','key','scroll','drag']:['click','double_click','scroll','drag']};});
 const busy=Array.from(document.querySelectorAll('.admin__form-loading-mask,.loading-mask,[aria-busy="true"],[inert]')).filter(visible).map(e=>({tag:e.tagName.toLowerCase(),class_name:e.className,aria_busy:e.getAttribute('aria-busy')}));
 return {schema:'magento-native-context-v1',physical_url:location.href,viewport:[innerWidth,innerHeight],visible:document.visibilityState==='visible',top_window:window===window.top,app_shell:!!document.querySelector('.page-wrapper .page-header,.admin-user'),native_username:account.length===1?account[0].textContent.trim():'',account_witness:{selector:'.admin-user .admin-user-account-text',visible_count:account.length,username:account.length===1?account[0].textContent.trim():null},focus,modals:modalNodes.map(e=>({bounds:bounds(e),class_name:e.className})),targets,hits,outside_modal_targets:modal?all.filter((t,i)=>!modal.contains(nodes[i])):[],busy,document_ready:document.readyState==='complete'};
}"""


class GuardHardStop(policy.GuardError):pass
class GuardIOUncertain(policy.GuardError):pass


class NativeAdapter:
    def __init__(self,*,page,task_id,package_sha256,instruction,root,lease_boundary):
        self.page=page;self.task_id=task_id;self.package_sha256=package_sha256;self.instruction=instruction
        self.store=EvidenceStore(root);self.boundary=lease_boundary;self.step=0;self.latest=None
        self.observed=None;self.previous=None;self.quarantined=False;self.clock=time.monotonic
        self.actor=ActorClock(task_id=task_id,package_sha256=package_sha256,started=self.boundary.lease['issued_at'],clock=lambda:self.clock())
        self.actor.bind(self.store);self.limits=ContractLimits(max_step=90)

    async def meta(self,points=None):
        value=await self.page.evaluate(NATIVE_JS,points or [])
        if type(value) is not dict or value.get('schema')!='magento-native-context-v1':raise GuardHardStop('native_context_missing')
        value['native_window_sha256']=policy.digest({'pid':os.getpid(),'page_object':id(self.page)})
        return value

    def targets(self,meta):
        keys=('ref','bounds','visible','enabled','obscured','keyboard','actions')
        rows=[{k:r[k] for k in keys} for r in meta['targets']+meta['hits']]
        focus=(meta['focus'] or {}).get('ref','body');body=focus=='body'
        rows.insert(0,{'ref':'body' if body else 'workspace','bounds':[0,0,*meta['viewport']],
            'visible':True,'enabled':True,'obscured':False,'keyboard':False,
            'actions':['click','double_click','scroll','drag']})
        return rows

    async def envelope(self,observation,meta,image,phase):
        self.actor.check('before_native_surface_envelope')
        tick=self.clock();owned=await self.boundary.owns(self.page,meta)
        raw=self.store.json(f'guard/turn-{observation.step:03d}/{phase}-native.private.json',meta,'native_'+phase+'_envelope')
        focus=(meta['focus'] or {}).get('ref','body')
        value={'schema':'native-surface-envelope-v1','policy_sha256':policy.POLICY_SHA,'phase':phase,
            'lease':self.boundary.lease,'task_id':self.task_id,'task_binding_sha256':self.package_sha256,
            'frame_id':observation.frame_id,'step':observation.step,'captured_at':tick,
            'expires_at':observation.expires_at if phase=='observation' else min(tick+self.limits.frame_ttl_seconds,self.actor.deadline),
            'viewport':meta['viewport'],'view_id':'magento-owned-admin','context_id':policy.digest(meta['physical_url']),
            'modal_id':'owned-dialog' if meta['modals'] else 'none','focus_id':focus,
            'allowed_views':['magento-owned-admin'],'allowed_modals':['none','owned-dialog'],
            'allowed_focus':self.observed['allowed_focus'] if self.observed else list(dict.fromkeys([focus]+[r['ref'] for r in self.targets(meta) if r['keyboard']])),
            'owned_surface':owned,'targets':self.targets(meta),'raw_image':image,'raw_envelope':raw}
        policy.validate_envelope(value)
        self.store.json(f'guard/turn-{observation.step:03d}/{phase}-envelope.private.json',value,'native_'+phase+'_envelope')
        return value

    async def observe(self,memory=''):
        if self.quarantined:raise GuardHardStop('quarantined_no_replay')
        self.actor.check('before_native_observation')
        for index in range(24):
            self.actor.check('native_readiness')
            await self.page.wait_for_timeout(250)
            meta=await self.meta();image=self.store.write(f'guard/readiness-{self.step:03d}-{index:02d}.png',await self.page.screenshot(type='png'),'raw_observation_image')
            check=await self.boundary.check(self.store)
            self.store.json(f'guard/readiness-{self.step:03d}-{index:02d}.private.json',{'native':meta,'lease_check':check,'image':image,'driver_called':False},'native_observation_envelope')
            if not await self.boundary.owns(self.page,meta) or check['status']!='active':self.quarantined=True;raise GuardHardStop('ownership_or_lease_lost')
            if index>=1 and meta['document_ready'] and not meta['busy']:break
        else:self.quarantined=True;raise GuardHardStop('native_busy_timeout_no_replay')
        raw=await self.page.screenshot(type='png');meta=await self.meta()
        controls=[{'ref':r['ref'],'role':r['role'],'label':r['label'],'visible':r['visible'],'enabled':r['enabled']} for r in meta['targets']]
        observation=make_observation(task_id=self.task_id,task_binding_sha256=self.package_sha256,
            instruction=self.instruction,step=self.step,screenshot_bytes=raw,controls=controls,
            previous_action_result=None if self.step==0 else {'status':'rejected','code':'invalid_action'} if self.previous else {'status':'applied','code':'ok'},
            memory=memory,limits=self.limits)
        observation=replace(observation,expires_at=min(observation.expires_at,self.actor.deadline))
        if self.previous is not None:observation=replace(observation,previous_action_result=self.previous)
        image=self.store.write(f'guard/turn-{self.step:03d}/observation.png',raw,'raw_observation_image')
        self.observed=None;self.observed=await self.envelope(observation,meta,image,'observation');self.latest=observation
        return observation,render_for_model(observation)

    def parse(self,raw):
        if self.latest is None:raise GuardHardStop('observation_missing')
        syntax=replace(self.latest,issued_at=self.clock(),expires_at=self.clock()+self.limits.frame_ttl_seconds)
        return normalize_model_action(raw,syntax,current_frame_id=syntax.frame_id)

    async def dispatch(self,raw):
        self.actor.check('before_native_dispatch')
        if self.quarantined or self.latest is None:raise GuardHardStop('quarantined_or_consumed_nonce')
        observation=self.latest;action=self.parse(raw)
        points=[action[k] for k in ('target','from','to') if k in action and set(action[k])=={'x','y'}]
        prefix=f'guard/turn-{self.step:03d}';image=self.store.write(prefix+'/predispatch.png',await self.page.screenshot(type='png'),'raw_predispatch_image')
        meta=await self.meta(points);current=await self.envelope(observation,meta,image,'predispatch')
        check=await self.boundary.check(self.store);tick=self.clock()
        self.store.json(prefix+'/lease-check.private.json',check,'lease_check')
        decided=policy.decision(self.observed,current,action,lease_check=lambda _lease:check,now=tick)
        decision=self.store.json(prefix+'/decision.private.json',decided,'dispatch_receipt')
        consumed=self.store.json(prefix+'/nonce.private.json',{'frame_id':observation.frame_id,'step':self.step,'action_sha256':policy.digest(action)},'action_intent')
        receipt={'schema':'native-surface-dispatch-receipt-v1','policy_sha256':policy.POLICY_SHA,
            'decision_sha256':policy.digest(decided),'action_sha256':policy.digest(action),'frame_id':observation.frame_id,'step':self.step,
            'status':decided['status'],'reason':decided['reason'],'turn_consumed':True,'nonce_invalidated':True,
            'intent':None,'driver_result':'not_attempted','driver_evidence':None}
        calls=[]
        if decided['status']=='accepted':
            receipt['intent']=self.store.json(prefix+'/intent.private.json',{'action':action,'decision':decision,'driver_not_yet_called':True},'action_intent')
            async def call(operation,fn,*args,**kwargs):
                self.actor.before_io(operation)
                try:value=await fn(*args,**kwargs)
                except BaseException:self.actor.after_io(operation,returned=False);raise
                self.actor.after_io(operation,returned=True);calls.append(operation);return value
            async def point(target):
                if set(target)=={'x','y'}:return target['x'],target['y']
                rows=[r for r in current['targets'] if r['ref']==target['ref']]
                if len(rows)!=1:raise GuardHardStop('native_target_ref_changed')
                x,y,w,h=rows[0]['bounds'];return x+w/2,y+h/2
            try:
                kind=action['type']
                if kind in ('click','double_click'):
                    x,y=await point(action['target']);await call('mouse.'+kind,self.page.mouse.dblclick if kind=='double_click' else self.page.mouse.click,x,y)
                elif kind in ('type','key'):
                    if 'target' in action:
                        x,y=await point(action['target']);await call('mouse.click',self.page.mouse.click,x,y)
                        focused=await self.meta();fresh=await self.boundary.check(self.store)
                        if not await self.boundary.owns(self.page,focused) or not (focused['focus'] or {}).get('editable') or fresh['status']!='active':raise GuardHardStop('native_keyboard_focus_unsafe')
                    if kind=='type':
                        if action['mode']=='fill':await call('keyboard.press',self.page.keyboard.press,'ControlOrMeta+A')
                        await call('keyboard.insert_text',self.page.keyboard.insert_text,action['text'])
                    else:await call('keyboard.press',self.page.keyboard.press,action['key'])
                elif kind=='scroll':
                    if 'target' in action:
                        x,y=await point(action['target']);await call('mouse.move',self.page.mouse.move,x,y)
                    await call('mouse.wheel',self.page.mouse.wheel,action['dx'],action['dy'])
                elif kind=='drag':
                    x,y=await point(action['from']);tx,ty=await point(action['to'])
                    await call('mouse.move',self.page.mouse.move,x,y);await call('mouse.down',self.page.mouse.down)
                    await call('mouse.move',self.page.mouse.move,tx,ty,steps=8);await call('mouse.up',self.page.mouse.up)
                elif kind=='wait':await call('page.wait_for_timeout',self.page.wait_for_timeout,action['duration_ms'])
                receipt['status']='applied' if calls else 'accepted';receipt['driver_result']='succeeded' if calls else 'not_attempted'
                if calls:receipt['driver_evidence']=self.store.json(prefix+'/driver.private.json',{'actual_calls':calls,'returned':True},'driver_result')
            except BaseException:
                self.quarantined=True
                self.store.json(prefix+'/uncertain.private.json',{'actual_completed_calls':calls,'applied_inferred':False},'driver_result')
                raise
        policy.validate_receipt(receipt)
        capsule=self.store.json(prefix+'/receipt.private.json',{'schema':'magento-native-capsule-v1','profile':PROFILE,
            'observed':self.observed,'current':current,'action':action,'audit_clock':tick,'decision':decided,
            'receipt':receipt,'lease_check':check,'nonce_consumption':consumed},'dispatch_receipt')
        contract=public_receipt(observation,action=action);contract['native_surface_guard']=capsule
        self.latest=None;self.observed=None;self.step+=1
        if decided['status']=='hard_stop':self.quarantined=True;raise GuardHardStop(decided['reason'])
        if decided['status']=='rejected':
            feedback=policy.rejection_feedback(decided);self.previous={'status':'rejected','code':feedback['code']}
            return {'status':'rejected','action':action,'contract':contract,'finished':False}
        self.previous=None
        return {'status':'finished' if action['type']=='finish' else 'applied','action':action,'contract':contract,'finished':action['type']=='finish'}
