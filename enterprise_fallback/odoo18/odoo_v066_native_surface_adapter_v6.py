"""One owned-surface policy for Odoo controls, teachers and every checkpoint."""
from __future__ import annotations
from dataclasses import replace
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import time
from urllib.parse import urlsplit
from cursibench import native_surface_guard_policy_v1 as policy
from cursibench.scale_action_contract import ContractError,make_observation
from cursibench.scale_action_contract_v066 import validate_action,public_receipt
from cursibench.scale_action_output_v066 import normalize_model_action,render_for_model
from .odoo_native_adapter import OdooNativeAdapter,VIEWPORT,VISIBLE_CONTROLS_JS,WALL_SECONDS
from .odoo_v066_train_adapter import OdooV066TrainAdapter
from .odoo_native_surface_evidence_v6 import EvidenceStore,OdooLeaseEvidence,require

PROFILE='native-owned-surface-safety-envelope-v6'
NATIVE_CONTEXT_JS=r"""(points) => {
 const visible=el=>{const r=el.getBoundingClientRect(),s=getComputedStyle(el);return r.width>0&&r.height>0&&r.right>0&&r.bottom>0&&r.left<innerWidth&&r.top<innerHeight&&s.display!=='none'&&s.visibility!=='hidden';};
 const bounds=el=>{const r=el.getBoundingClientRect(),l=Math.max(0,Math.floor(r.left)),t=Math.max(0,Math.floor(r.top));return [l,t,Math.min(innerWidth,Math.ceil(r.right))-l,Math.min(innerHeight,Math.ceil(r.bottom))-t];};
 const unsafe=el=>!!el.closest('.o_user_menu,.o_switch_company_menu')||((el.closest('a')||{}).target==='_blank')||(()=>{const a=el.closest('a[href]');if(!a)return false;const h=a.getAttribute('href');if(!h||h==='#')return false;try{const u=new URL(h,location.href);return u.origin!==location.origin||!/^\/(odoo(?:\/|$)|web\/content|web\/image)/.test(u.pathname);}catch{return true;}})();
 const keyboard=el=>['INPUT','TEXTAREA'].includes(el.tagName)&&!el.disabled&&!el.readOnly||el.isContentEditable;
 const active=document.activeElement;
 const nodes=Array.from(document.querySelectorAll('[data-envloop-ref]')).filter(visible);
 const target=el=>{const b=bounds(el),x=b[0]+b[2]/2,y=b[1]+b[3]/2,hit=document.elementFromPoint(x,y);return {ref:el.getAttribute('data-envloop-ref')||'body',bounds:b,visible:true,enabled:!el.disabled&&!unsafe(el),obscured:!!hit&&hit!==el&&!el.contains(hit),keyboard:keyboard(el),actions:keyboard(el)?['click','double_click','type','key','scroll','drag']:['click','double_click','scroll','drag'],tag:el.tagName.toLowerCase(),type:el.type||'',name:el.getAttribute('name')||'',value:typeof el.value==='string'?el.value:null};};
 const targets=nodes.map(target).filter(t=>t.bounds[2]>0&&t.bounds[3]>0);
 const modals=Array.from(document.querySelectorAll('.modal.show,.o_dialog,[role="dialog"],dialog[open],[aria-modal="true"]')).filter(visible).map(el=>({tag:el.tagName.toLowerCase(),role:el.getAttribute('role')||'',class_name:el.className,bounds:bounds(el)}));
 const avatars=Array.from(document.querySelectorAll('.o_main_navbar .o_user_menu img.o_user_avatar')).filter(visible);
 let uid='';if(avatars.length===1){try{const u=new URL(avatars[0].currentSrc||avatars[0].src,location.href);if(u.searchParams.get('model')==='res.users')uid=u.searchParams.get('id')||'';else{const m=u.pathname.match(/\/web\/image\/res.users\/(\d+)\//);uid=m?m[1]:'';}}catch{}}
 const focus=active&&visible(active)?{ref:active.getAttribute('data-envloop-ref')||'body',tag:active.tagName.toLowerCase(),type:active.type||'',name:active.getAttribute('name')||'',editable:keyboard(active),bounds:bounds(active),value:typeof active.value==='string'?active.value:null}:null;
 const hits=(points||[]).map((p,i)=>{const hit=document.elementFromPoint(p.x,p.y);if(!hit)return {ref:'point-'+i,bounds:[p.x,p.y,1,1],visible:false,enabled:false,obscured:true,keyboard:false,actions:['click']};const el=hit.closest('[data-envloop-ref]')||hit;return {ref:'point-'+i,bounds:[p.x,p.y,1,1],visible:visible(el),enabled:!el.disabled&&!unsafe(el),obscured:false,keyboard:keyboard(el),actions:keyboard(el)?['click','double_click','type','key','scroll','drag']:['click','double_click','scroll','drag']};});
 return {schema:'odoo-current-native-surface-v6',visible:document.visibilityState==='visible',top_window:window===window.top,app_shell:!!document.querySelector('.o_web_client,.o_main_navbar'),account_uid:uid,route_path:location.pathname,viewport:[innerWidth,innerHeight],focus,modals,targets,hits};
}"""


class GuardHardStop(policy.GuardError):pass
class GuardDriverUncertain(policy.GuardError):pass


def _previous(value):
    if value is not None and value.get('status')=='rejected' and value.get('code') not in ('invalid_action','target_not_found','target_disabled','target_obscured'):
        return {'status':'rejected','code':'invalid_action'}
    return value


def _metadata_valid(meta):
    return (type(meta) is dict and meta.get('schema')=='odoo-current-native-surface-v6' and
        all(type(meta.get(k)) is bool for k in ('visible','top_window','app_shell')) and
        type(meta.get('account_uid')) is str and type(meta.get('route_path')) is str and
        type(meta.get('viewport')) is list and len(meta['viewport'])==2 and
        all(type(v) is int for v in meta['viewport']) and
        all(type(meta.get(k)) is list for k in ('targets','hits','modals')) and
        (meta.get('focus') is None or type(meta['focus']) is dict))


class OdooV066NativeSurfaceAdapter(OdooNativeAdapter):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.clock=time.monotonic;self.store=None;self.boundary=None;self._native_page=self.page
        self.frame_guard_sink=None;self.frame_guard_samples=[];self._observed=None;self._armed=False
        self._quarantined=False;self._dispatch_number=0

    def _meta(self,points=None):
        value=self.page.evaluate(NATIVE_CONTEXT_JS,points or [])
        require(_metadata_valid(value),'guard_native_surface_invalid')
        parsed=urlsplit(self.page.url)
        value['physical_url']=self.page.url
        value['native_window_sha256']=policy.digest({'pid':os.getpid(),'page_object':id(self.page),
            'origin':parsed.scheme+'://'+parsed.netloc})
        value['native_capture_monotonic']=self.clock()
        return value

    def bind_guard(self,root,worker_private):
        require(self.store is None and self.latest is None,'guard_boundary_already_bound')
        self.store=EvidenceStore(root);meta=self._meta()
        self.boundary=OdooLeaseEvidence(store=self.store,worker_private=worker_private,page=self.page,
            account_uid=meta['account_uid'],started=self.started,expires=self.started+WALL_SECONDS,clock=self.clock)
        require(self.boundary.owns(self.page,meta),'guard_initial_surface_not_owned')

    def _within_budget(self):
        if self._quarantined:raise GuardHardStop('guard_quarantined_no_replay')
        super()._within_budget()

    def current_frame_id(self):
        return self.latest.frame_id if self.latest is not None and self.page is self._native_page and self.clock()<=self.latest.expires_at and not self._quarantined else 'stale'

    def _targets(self,meta,action=None):
        keys=('ref','bounds','visible','enabled','obscured','keyboard','actions')
        rows=[{key:row[key] for key in keys} for row in meta['targets']]
        focus=meta['focus']
        body_focus=focus is not None and focus['ref']=='body'
        body_keyboard=body_focus and (action is None or action.get('type')!='key' or
            action.get('key') in ('Escape','Tab','Shift+Tab','ArrowUp','ArrowDown','ArrowLeft','ArrowRight','Home','End','PageUp','PageDown','Control+F','Control+H','Control+End','Shift+End'))
        rows.insert(0,{'ref':'body' if body_focus else 'workspace','bounds':[0,0,*meta['viewport']],'visible':True,'enabled':True,'obscured':False,
            'keyboard':body_keyboard,'actions':['click','double_click','scroll','drag']+(['key'] if body_keyboard else [])})
        for hit in meta['hits']:rows.append({key:hit[key] for key in keys})
        return rows

    def _envelope(self,observation,meta,image_ref,phase,action=None):
        tick=self.clock();prefix=f'surface-guard/turn-{observation.step:03d}/{phase}'
        raw_ref=self.store.json(prefix+'-native.private.json',meta,'native_'+phase+'_envelope')
        focus=(meta['focus'] or {}).get('ref','body')
        modal='none' if not meta['modals'] else 'owned-dialog'
        # Document values/labels and route/record IDs never decide correctness.
        value={'schema':'native-surface-envelope-v1','policy_sha256':policy.POLICY_SHA,'phase':phase,
            'lease':self.boundary.lease,'task_id':observation.task_id,'task_binding_sha256':observation.task_binding_sha256,
            'frame_id':observation.frame_id,'step':observation.step,'captured_at':tick,
            'expires_at':observation.expires_at if phase=='observation' else min(tick+self.limits.frame_ttl_seconds,self.boundary.lease['expires_at']),
            'viewport':meta['viewport'],'view_id':'odoo-workspace','context_id':policy.digest(meta['physical_url']),
            'modal_id':modal,'focus_id':focus,
            'allowed_views':['odoo-workspace'],'allowed_modals':['none','owned-dialog'],
            'allowed_focus':self._observed['allowed_focus'] if self._observed else list(dict.fromkeys([focus]+[r['ref'] for r in self._targets(meta) if r['keyboard']])),
            'owned_surface':self.boundary.owns(self.page,meta),'targets':self._targets(meta,action),
            'raw_image':image_ref,'raw_envelope':raw_ref}
        policy.validate_envelope(value)
        self.store.json(prefix+'-envelope.private.json',value,'native_'+phase+'_envelope')
        return value

    def observe_for_model(self,*,memory=''):
        self._within_budget();require(self.store is not None and self.boundary is not None,'guard_boundary_not_bound')
        controls=self.page.evaluate(VISIBLE_CONTROLS_JS);meta=self._meta();raw=self.page.screenshot(type='png')
        require(self.boundary.owns(self.page,meta),'guard_observation_outside_workspace')
        previous=self.previous_result
        observation=make_observation(task_id=self.task_id,task_binding_sha256=self.task_binding_sha256,
            instruction=self.instruction,step=self.step,screenshot_bytes=raw,
            a11y_text='\n'.join(f"{c['role']}: {c['label']}" for c in controls if c['label'])[:12000],
            controls=controls,previous_action_result=_previous(previous),memory=memory,limits=self.limits)
        # The base helper's enum projection is truthful rejection, never
        # applied/ok. The real versioned feedback is what the model receives.
        if previous is not None:observation=replace(observation,previous_action_result=previous)
        self._observed=None
        image=self.store.write(f'surface-guard/turn-{self.step:03d}/observation.png',raw,'raw_observation_image')
        self._observed=self._envelope(observation,meta,image,'observation')
        self.latest=observation;self.latest_url=self.page.url
        return observation,render_for_model(observation)

    def parse_current_action(self,raw):
        self._within_budget();observation=self.latest
        if observation is None:raise ContractError('stale_frame')
        if type(raw) is dict:
            return validate_action(raw,observation,current_frame_id=observation.frame_id,now=observation.issued_at)
        # Parsing checks the original nonce/task/step/targets. A temporary
        # clock projection only bypasses the legacy normalizer's early TTL
        # check; the original observation/expiry remains the dispatch input.
        tick=self.clock();syntax_frame=replace(observation,issued_at=tick,expires_at=tick+self.limits.frame_ttl_seconds)
        return normalize_model_action(raw,syntax_frame,current_frame_id=observation.frame_id)

    def _frame_current(self,observation,*,stage):
        return self._armed and stage=='dispatch' and self.latest is observation and self.page is self._native_page

    def dispatch(self,raw_action):
        self._within_budget();observation=self.latest
        if observation is None:raise ContractError('stale_frame')
        action=self.parse_current_action(raw_action)
        endpoints=[action[k] for k in ('target','from','to') if k in action]
        points=[endpoint for endpoint in endpoints if set(endpoint)=={'x','y'} and
                0<=endpoint['x']<VIEWPORT['width'] and 0<=endpoint['y']<VIEWPORT['height']]
        raw=self.page.screenshot(type='png');meta=self._meta(points)
        prefix=f'surface-guard/turn-{self.step:03d}'
        image=self.store.write(prefix+'/predispatch.png',raw,'raw_predispatch_image')
        current=self._envelope(observation,meta,image,'predispatch',action)
        checked_lease=self.boundary.check(policy.validate_lease(current['lease']))
        decision_clock=self.clock()
        decided=policy.decision(self._observed,current,action,lease_check=lambda _lease:checked_lease,now=decision_clock)
        decision_ref=self.store.json(prefix+'/decision.private.json',decided,'dispatch_receipt')
        consumed=self.store.json('surface-guard/nonces/'+observation.frame_id+'.consumed.private.json',{
            'frame_id':observation.frame_id,'step':self.step,'action_sha256':policy.digest(action),'decision_ref':decision_ref},'action_intent')
        result={'schema':'native-surface-dispatch-receipt-v1','policy_sha256':policy.POLICY_SHA,
            'decision_sha256':policy.digest(decided),'action_sha256':policy.digest(action),'frame_id':observation.frame_id,'step':self.step,
            'status':decided['status'],'reason':decided['reason'],'turn_consumed':True,'nonce_invalidated':True,
            'intent':None,'driver_result':'not_attempted','driver_evidence':None}
        applied=None;calls=[]
        if decided['status']=='accepted':
            intent=self.store.json(prefix+'/intent.private.json',{'action':action,'decision':decision_ref,
                'frame_id':observation.frame_id,'driver_not_yet_called':True},'action_intent');result['intent']=intent
            original=self.page
            adapter=self
            class Driver:
                def __init__(self,target):self.target=target
                def __getattr__(self,name):
                    value=getattr(self.target,name)
                    if not callable(value):return value
                    def call(*args,**kwargs):
                        if name in ('insert_text','press') and 'target' in action:
                            proxy=adapter.page;adapter.page=original
                            try:live=adapter._meta()
                            finally:adapter.page=proxy
                            focus=live.get('focus') or {}
                            require(adapter.boundary.owns(original,live) and focus.get('editable') is True,
                                    'guard_targeted_keyboard_focus_unsafe')
                            if set(action['target'])=={'ref'}:
                                require(focus.get('ref')==action['target']['ref'],'guard_targeted_keyboard_focus_ref_changed')
                            keyboard_lease=policy.validate_lease_check(
                                adapter.boundary.check(policy.validate_lease(current['lease'])),policy.validate_lease(current['lease']))
                            require(keyboard_lease['status']=='active','guard_targeted_keyboard_lease_lost')
                            live['post_target_lease_check']=json.loads(policy.canonical(keyboard_lease))
                            ref=adapter.store.json(prefix+f'/keyboard-scope-{len(calls):03d}.private.json',live,
                                'native_predispatch_envelope')
                        row={'operation':name,'arguments_sha256':policy.digest([args,kwargs]),'started_at':adapter.clock()}
                        if name in ('insert_text','press') and 'target' in action:row['keyboard_scope']=ref
                        started=adapter.store.json(prefix+f'/driver-call-{len(calls):03d}.private.json',row,'driver_result')
                        row['started_evidence']=started
                        calls.append(row)
                        returned=value(*args,**kwargs)
                        completion=adapter.store.json(prefix+f'/driver-call-{len(calls)-1:03d}-returned.private.json',
                            {'operation':name,'returned':True,'completed_at':adapter.clock()},'driver_result')
                        row['completed']=True;row['completion']=completion
                        return returned
                    return call
            class Page:
                mouse=Driver(original.mouse);keyboard=Driver(original.keyboard)
                def __getattr__(self,name):return getattr(original,name)
                def wait_for_timeout(self,duration):return Driver(original).wait_for_timeout(duration)
            try:
                self._armed=True;self.page=Page()
                # The exact preserved mechanics invoke _frame_current on this
                # proxy. Its owned native target remains the original page.
                self._native_page=self.page
                applied=OdooV066TrainAdapter.dispatch(self,action)
                result['status']='applied' if calls else 'accepted'
                if calls:
                    result['driver_result']='succeeded'
                    result['driver_evidence']=self.store.json(prefix+'/driver-result.private.json',{
                        'status':'succeeded','calls':calls,'actual_driver_returned':True},'driver_result')
            except BaseException as error:
                self._quarantined=True;result['status']='failed'
                result['driver_result']='unknown' if any(not row.get('completed') for row in calls) else 'failed'
                result['driver_evidence']=self.store.json(prefix+'/driver-result.private.json',{
                    'status':result['driver_result'],'calls':calls,'error_type':type(error).__name__,'applied_inferred':False},'driver_result')
            finally:self.page=original;self._native_page=original;self._armed=False
        policy.validate_receipt(result)
        capsule={'schema':'odoo-native-surface-capsule-v6','profile':PROFILE,'policy_sha256':policy.POLICY_SHA,'audit_clock':decision_clock,
            'observed':self._observed,'current':current,'action':action,'decision':decided,'receipt':result,
            'nonce_consumption':consumed}
        reference=self.store.json(prefix+'/receipt.private.json',capsule,'dispatch_receipt')
        contract=public_receipt(observation,action=action)
        contract.update(native_surface_guard=reference,native_adapter_profile=PROFILE,dispatch_status=result['status'])
        self.latest=None;self.latest_url=None;self._observed=None
        self.step=observation.step+1
        if result['status']=='failed':raise GuardDriverUncertain('guard_driver_unknown_no_replay') if result['driver_result']=='unknown' else GuardHardStop('guard_driver_failed_no_replay')
        if decided['status']=='hard_stop':self._quarantined=True;raise GuardHardStop(decided['reason'])
        if decided['status']=='rejected':
            feedback=policy.rejection_feedback(decided);self.previous_result={'status':'rejected','code':feedback['code']}
            return {'status':'rejected','code':feedback['code'],'action':action,'public_contract_receipt':contract,'finished':False}
        self.previous_result=None if action['type']=='finish' else {'status':'applied','code':'ok'}
        return {**applied,'status':'finished' if action['type']=='finish' else 'applied','code':'ok','public_contract_receipt':contract}


def audit_guard(guard,observed_png,read_ref,action=None):
    require(type(guard) is dict,'guard_capsule_ref_missing')
    capsule=json.loads(read_ref(guard));require(capsule.get('schema')=='odoo-native-surface-capsule-v6' and capsule.get('profile')==PROFILE and capsule.get('action')==action,'guard_capsule_binding_changed')
    observed,current=capsule['observed'],capsule['current']
    lease_proof=json.loads(read_ref(observed['lease']['evidence']))
    require(lease_proof.get('schema')=='odoo-native-held-lease-evidence-v6','guard_held_lease_evidence_schema_missing')
    from PIL import Image
    from io import BytesIO
    for envelope in (observed,current):
        policy.validate_envelope(envelope)
        for field in ('raw_image','raw_envelope'):
            reference=envelope[field];raw=read_ref(reference)
            require(sha256(raw).hexdigest()==reference['sha256'] and len(raw)==reference['size'],'guard_raw_evidence_changed')
        meta=json.loads(read_ref(envelope['raw_envelope']))
        require(_metadata_valid(meta) and envelope['viewport']==meta['viewport'] and
            envelope['context_id']==policy.digest(meta['physical_url']) and
            envelope['focus_id']==(meta['focus'] or {}).get('ref','body') and
            envelope['modal_id']==('none' if not meta['modals'] else 'owned-dialog') and
            envelope['targets']==OdooV066NativeSurfaceAdapter._targets(None,meta,action if envelope['phase']=='predispatch' else None),
            'guard_native_envelope_not_rederived')
        with Image.open(BytesIO(read_ref(envelope['raw_image']))) as image:
            require(list(image.size)==envelope['viewport'],'guard_image_viewport_changed')
        parsed=urlsplit(meta['physical_url'])
        owned=(parsed.scheme+'://'+parsed.netloc==lease_proof['origin'] and
            (parsed.path=='/odoo' or parsed.path.startswith('/odoo/')) and meta['visible'] and meta['top_window'] and meta['app_shell'] and
            meta['account_uid']==lease_proof['native_avatar_uid'] and meta['native_window_sha256']==lease_proof['window_sha256'])
        require(envelope['owned_surface']==owned,'guard_owned_surface_not_rederived')
    require(read_ref(observed['raw_image'])==observed_png,'guard_observed_image_changed')
    check=capsule['decision']['lease_check']
    if check is not None:read_ref(check['evidence'])
    read_ref(observed['lease']['evidence'])
    rederived=policy.decision(observed,current,action,lease_check=lambda _lease:check,now=capsule['audit_clock'])
    require(rederived==capsule['decision'],'guard_decision_changed')
    receipt=policy.validate_receipt(capsule['receipt'])
    for field in ('intent','driver_evidence'):
        if capsule['receipt'][field] is not None:read_ref(capsule['receipt'][field])
    consumed=json.loads(read_ref(capsule['nonce_consumption']))
    require(consumed['frame_id']==action['frame_id'] and consumed['step']==action['step'] and
        consumed['action_sha256']==policy.digest(action) and json.loads(read_ref(consumed['decision_ref']))==rederived,
        'guard_nonce_consumption_not_bound')
    if capsule['receipt']['intent'] is not None:
        intent=json.loads(read_ref(capsule['receipt']['intent']))
        require(intent['action']==action and json.loads(read_ref(intent['decision']))==rederived and
            intent['driver_not_yet_called'] is True,'guard_intent_not_before_driver')
    if capsule['receipt']['driver_evidence'] is not None:
        driver=json.loads(read_ref(capsule['receipt']['driver_evidence']))
        require(driver['status']==receipt['driver_result'] and type(driver['calls']) is list,'guard_driver_result_changed')
        if receipt['status']=='applied':require(bool(driver['calls']) and driver.get('actual_driver_returned') is True,'guard_applied_without_driver')
        for call in driver['calls']:
            started=json.loads(read_ref(call['started_evidence']))
            require(started['operation']==call['operation'] and started['arguments_sha256']==call['arguments_sha256'] and
                started['started_at']==call['started_at'],'guard_native_call_not_reopened')
            if call.get('completed'):
                completed=json.loads(read_ref(call['completion']))
                require(completed['operation']==call['operation'] and completed['returned'] is True and
                    completed['completed_at']>=call['started_at'],'guard_native_return_not_reopened')
            elif receipt['status']=='applied':raise policy.GuardError('guard_applied_without_native_return')
            if call.get('keyboard_scope'):
                keyboard=json.loads(read_ref(call['keyboard_scope']))
                require((keyboard.get('focus') or {}).get('editable') is True,'guard_keyboard_focus_not_reopened')
                keyboard_lease=policy.validate_lease_check(keyboard['post_target_lease_check'],policy.validate_lease(current['lease']))
                require(keyboard_lease['status']=='active','guard_keyboard_lease_not_reopened')
                read_ref(keyboard['post_target_lease_check']['evidence'])
    require(receipt['action_sha256']==policy.digest(action) and receipt['decision_sha256']==policy.digest(rederived),'guard_dispatch_binding_changed')
    return {'profile':PROFILE,'status':'verified','decision_status':rederived['status'],'dispatch_status':receipt['status'],
        'raw_observation_images_reopened':1,'raw_predispatch_images_reopened':1,'native_targets_reopened':len(current['targets']),
        'dispatch_status':'finished' if action['type']=='finish' and receipt['status']=='accepted' and receipt['driver_result']=='not_attempted' else receipt['status']}


def public_binding():
    root=Path(__file__).resolve().parents[2]
    names=('enterprise_fallback/odoo18/odoo_v066_native_surface_adapter_v6.py','enterprise_fallback/odoo18/odoo_native_surface_evidence_v6.py',
        'enterprise_fallback/odoo18/odoo_native_adapter.py','enterprise_fallback/odoo18/odoo_v066_train_adapter.py',
        'enterprise_fallback/odoo18/worker_lease.py','src/cursibench/native_surface_guard_policy_v1.py',
        'src/cursibench/scale_action_contract.py','src/cursibench/scale_action_contract_v066.py','src/cursibench/scale_action_output_v066.py',
        'src/cursibench/scale_action_output_v065.py','src/cursibench/scale_action_output_v062.py')
    bindings={name:sha256((root/name).read_bytes()).hexdigest() for name in names}
    return {'schema':'envloop-odoo-native-surface-common-binding-v6','profile':PROFILE,'student_model':'Qwen/Qwen3.8-27B',
        'viewport':VIEWPORT,'max_actions':90,'wall_seconds':720,'policy_sha256':policy.POLICY_SHA,
        'raster_equality_required':False,'gold_directed_adapter_arguments':False,'bindings_sha256':bindings,
        'binding_sha256':sha256(policy.canonical(bindings)).hexdigest()}
