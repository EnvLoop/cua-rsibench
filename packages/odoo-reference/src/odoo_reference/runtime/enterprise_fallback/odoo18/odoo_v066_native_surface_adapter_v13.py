"""Fresh v13 principal witness/readiness; preserved v6 safety and action rules."""
from hashlib import sha256
import json
from pathlib import Path
from .native_compat_source_loader_v1 import load_source
from . import odoo_native_principal_witness_v7 as witness
from .odoo_actor_clock_v1 import ActorClock,ActorDeadlineReached

# Task-independent request/DOM readiness. Disabled controls are deliberately
# absent: a permanently disabled control remains ordinary rejected behavior.
READINESS_POLL_MS=250
READINESS_QUIET_SECONDS=0.5
READINESS_MAX_SAMPLES=24
READINESS_REQUEST_TYPES=('document','xhr','fetch')
BUSY_JS=r"""() => {
 const visible=el=>{const r=el.getBoundingClientRect(),s=getComputedStyle(el);return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden';};
 const nodes=Array.from(document.querySelectorAll('[aria-busy="true"],.o_blockUI,.o_block_ui,.o_loading,.o_field_loading,[inert],[aria-label]')).filter(visible).filter(el=>el.matches('[aria-busy="true"],.o_blockUI,.o_block_ui,.o_loading,.o_field_loading,[inert]')||/loading/i.test(el.getAttribute('aria-label')||''));
 return {schema:'odoo-generic-native-loading-v13',document_ready:document.readyState==='complete',action_view_count:document.querySelectorAll('.o_action,.o_action_manager').length,busy:nodes.map(el=>({tag:el.tagName.toLowerCase(),class_name:typeof el.className==='string'?el.className:'',aria_busy:el.getAttribute('aria-busy'),aria_label:el.getAttribute('aria-label'),inert:el.hasAttribute('inert')}))};
}"""

_impl=load_source('enterprise_fallback/odoo18/odoo_v066_native_surface_adapter_v6.py',
 'enterprise_fallback.odoo18._native_surface_adapter_v13',
 'a7bc3f6edcd4cd0ab031edafd5f549164b37cdf5e8d903123ea88eb1f90dc119',(
 ('odoo_native_surface_evidence_v6','odoo_native_surface_evidence_v13',2),
 ('native-owned-surface-safety-envelope-v6','native-owned-surface-safety-envelope-v13',1),
 ('odoo-current-native-surface-v6','odoo-current-native-surface-v13',2),
 ('odoo-native-surface-capsule-v6','odoo-native-surface-capsule-v13',2),
 ('odoo-native-held-lease-evidence-v6','odoo-native-held-lease-evidence-v13',1),
 ('native_avatar_uid','native_avatar_principal',1),('account_uid','account_principal',5),
 ('odoo_v066_native_surface_adapter_v6.py','odoo_v066_native_surface_adapter_v13.py',1),
 ('envloop-odoo-native-surface-common-binding-v6','envloop-odoo-native-surface-common-binding-v13',1),
 ("from .odoo_native_surface_evidence_v13 import EvidenceStore,OdooLeaseEvidence,require","from .odoo_native_surface_evidence_v13 import EvidenceStore,OdooLeaseEvidence,require\nfrom .odoo_actor_clock_v1 import ActorDeadlineReached",1),
 ("                        row={'operation':name,'arguments_sha256':policy.digest([args,kwargs]),'started_at':adapter.clock()}","                        adapter.actor_clock.before_io(name)\n                        row={'operation':name,'arguments_sha256':policy.digest([args,kwargs]),'started_at':adapter.clock()}",1),
 ('                        returned=value(*args,**kwargs)',
  '                        try:returned=value(*args,**kwargs)\n                        except BaseException:\n                            adapter.actor_clock.after_io(name,returned=False);raise\n                        adapter.actor_clock.after_io(name,returned=True)',1),
 ('            except BaseException as error:\n                self._quarantined=True;',
  '            except ActorDeadlineReached:\n                self._quarantined=True;raise\n            except BaseException as error:\n                self._quarantined=True;',1),

 ))
_start=_impl.NATIVE_CONTEXT_JS.index(' const avatars=')
_end=_impl.NATIVE_CONTEXT_JS.index(' const focus=',_start)
_impl.NATIVE_CONTEXT_JS=(_impl.NATIVE_CONTEXT_JS[:_start]+witness.PRINCIPAL_JS+_impl.NATIVE_CONTEXT_JS[_end:]).replace(
 'account_principal:uid,','account_principal:principal,principal_witness:principalWitness,')


# Native semantic interactive controls include DIV/SPAN role buttons, menus
# and options. The owned-surface gate still filters unsafe account/navigation
# and obscured controls; selectors never depend on task answers or filenames.
_CONTROL_SELECTOR = 'button,a,input,textarea,[role="tab"],td[name]'
_EXPANDED_CONTROL_SELECTOR = _CONTROL_SELECTOR + ',[role="button"],[role="menuitem"],[role="option"],[class*="Attachment"]'
assert _impl.VISIBLE_CONTROLS_JS.count(_CONTROL_SELECTOR) == 1
_impl.VISIBLE_CONTROLS_JS = _impl.VISIBLE_CONTROLS_JS.replace(_CONTROL_SELECTOR, _EXPANDED_CONTROL_SELECTOR)
_MODAL_SELECTOR = '.modal.show,.o_dialog,[role="dialog"],dialog[open],[aria-modal="true"]'
assert _impl.NATIVE_CONTEXT_JS.count(_MODAL_SELECTOR) == 1
_impl.NATIVE_CONTEXT_JS = _impl.NATIVE_CONTEXT_JS.replace(_MODAL_SELECTOR, _MODAL_SELECTOR + ',.o-FileViewer')


# The current dialog is a native interaction surface. Underlying controls
# remain in full metadata but cannot compete with its painted target geometry.
# Disabled/unsafe controls inside the dialog are retained and still rejected.
_MODAL_SCOPE_JS = r"""
  const modalNodes = Array.from(document.querySelectorAll('.modal.show,.o_dialog,[role="dialog"],dialog[open],[aria-modal="true"],.o-FileViewer')).filter(el => {
    const r=el.getBoundingClientRect(),s=getComputedStyle(el);
    return r.width>0&&r.height>0&&r.right>0&&r.bottom>0&&r.left<innerWidth&&r.top<innerHeight&&s.display!=='none'&&s.visibility!=='hidden';
  });
  const activeModal=modalNodes.length?modalNodes[modalNodes.length-1]:null;
"""
assert _impl.VISIBLE_CONTROLS_JS.count('  return filtered.map(') == 1
_impl.VISIBLE_CONTROLS_JS = _impl.VISIBLE_CONTROLS_JS.replace('  return filtered.map(', _MODAL_SCOPE_JS+'  return filtered.map(')
_old_targets=' const targets=nodes.map(target).filter(t=>t.bounds[2]>0&&t.bounds[3]>0);'
assert _impl.NATIVE_CONTEXT_JS.count(_old_targets)==1
_impl.NATIVE_CONTEXT_JS=_impl.NATIVE_CONTEXT_JS.replace(_old_targets,_MODAL_SCOPE_JS+r"""
 const allTargets=nodes.map(target).filter(t=>t.bounds[2]>0&&t.bounds[3]>0);
 const outside_modal_targets=activeModal?allTargets.filter(t=>{
   const el=nodes.find(n=>n.getAttribute('data-envloop-ref')===t.ref);return !el||!activeModal.contains(el);
 }):[];
 const targets=activeModal?allTargets.filter(t=>{
   const el=nodes.find(n=>n.getAttribute('data-envloop-ref')===t.ref);return !!el&&activeModal.contains(el);
 }):allTargets;
""")
_impl.NATIVE_CONTEXT_JS=_impl.NATIVE_CONTEXT_JS.replace('focus,modals,targets,hits','focus,modals,targets,hits,outside_modal_targets')

_control_end='  });\n}'
assert _impl.VISIBLE_CONTROLS_JS.count(_control_end)==1
_impl.VISIBLE_CONTROLS_JS=_impl.VISIBLE_CONTROLS_JS.replace(_control_end,'  }).filter(row => !activeModal || activeModal.querySelector(\'[data-envloop-ref="\'+row.ref+\'" ]\'));\n}')
# Give the active dialog the same bounded 128-control observation capacity;
# a large underlying form must not exhaust the list before its controls.
assert _impl.VISIBLE_CONTROLS_JS.count(_MODAL_SCOPE_JS)==1
_impl.VISIBLE_CONTROLS_JS=_impl.VISIBLE_CONTROLS_JS.replace(_MODAL_SCOPE_JS,'')
_impl.VISIBLE_CONTROLS_JS=_impl.VISIBLE_CONTROLS_JS.replace('  const nodes =',_MODAL_SCOPE_JS+'  const nodes =')
_limit='  }).slice(0, 128);'
assert _impl.VISIBLE_CONTROLS_JS.count(_limit)==1
_impl.VISIBLE_CONTROLS_JS=_impl.VISIBLE_CONTROLS_JS.replace(_limit,
 '  }).sort((a,b)=>Number(!!activeModal&&activeModal.contains(b))-Number(!!activeModal&&activeModal.contains(a))).slice(0, 128);')

# Current native focus has a stable document/element witness even when the
# generic list is capped. Body, canvas and selection ranges are not fallback.
FOCUS_REF_JS = r"""
 const focusEligible=el=>!!el&&el.ownerDocument===document&&el.isConnected&&el.getRootNode()===document&&!['BODY','HTML'].includes(el.tagName);
 if(!window.__envloopNativeFocusV13)window.__envloopNativeFocusV13={counter:0,refs:new WeakMap()};
 const focusRef=el=>{const state=window.__envloopNativeFocusV13;if(!state.refs.has(el))state.refs.set(el,'nf'+String(++state.counter).padStart(6,'0'));const id=state.refs.get(el);el.setAttribute('data-envloop-ref',id);return id;};
"""
_impl.NATIVE_CONTEXT_JS=_impl.NATIVE_CONTEXT_JS.replace(' const active=document.activeElement;',FOCUS_REF_JS+'''
 const active=document.activeElement;
 if(focusEligible(active))focusRef(active);
''',1)
assert _impl.VISIBLE_CONTROLS_JS.count('  const nodes =')==1
_impl.VISIBLE_CONTROLS_JS=_impl.VISIBLE_CONTROLS_JS.replace('  const nodes =',FOCUS_REF_JS+'''
  const currentFocus=document.activeElement;
  const nodes =''',1)
_sort='  }).sort((a,b)=>Number(!!activeModal&&activeModal.contains(b))-Number(!!activeModal&&activeModal.contains(a))).slice(0, 128);'
assert _impl.VISIBLE_CONTROLS_JS.count(_sort)==1
_impl.VISIBLE_CONTROLS_JS=_impl.VISIBLE_CONTROLS_JS.replace(_sort,
 '  }).sort((a,b)=>(Number(!!activeModal&&activeModal.contains(b))-Number(!!activeModal&&activeModal.contains(a)))||Number(b===currentFocus)-Number(a===currentFocus)).slice(0, 128);')
_assign="    const ref = 'c' + String(index).padStart(3, '0');"
assert _impl.VISIBLE_CONTROLS_JS.count(_assign)==1
_impl.VISIBLE_CONTROLS_JS=_impl.VISIBLE_CONTROLS_JS.replace(_assign,
 "    const ref = el===currentFocus&&focusEligible(el)?focusRef(el):'c'+String(index).padStart(3,'0');")
_focus=" const focus=active&&visible(active)?{ref:active.getAttribute('data-envloop-ref')||'body',tag:active.tagName.toLowerCase(),type:active.type||'',name:active.getAttribute('name')||'',editable:keyboard(active),bounds:bounds(active),value:typeof active.value==='string'?active.value:null}:null;"
assert _impl.NATIVE_CONTEXT_JS.count(_focus)==1
_impl.NATIVE_CONTEXT_JS=_impl.NATIVE_CONTEXT_JS.replace(_focus,r"""
 const focus=active&&visible(active)?{ref:focusEligible(active)?focusRef(active):'body',tag:active.tagName.toLowerCase(),type:active.type||'',name:active.getAttribute('name')||'',editable:keyboard(active),bounds:bounds(active),value:typeof active.value==='string'?active.value:null}:null;
 const focus_owned_app=focusEligible(active)&&!!active.closest('.o_web_client,.o_action,.o_action_manager,.o_main_navbar,.modal.show,.o_dialog,[role="dialog"],dialog[open],[aria-modal="true"],.o-FileViewer');
 let focused_target=null;
 if(focusEligible(active)&&visible(active)){
  focused_target=target(active);
  focused_target.enabled=focused_target.enabled&&focus_owned_app&&(!activeModal||activeModal.contains(active));
  const existing=targets.findIndex(t=>t.ref===focused_target.ref);
  if(existing>=0)targets[existing]=focused_target;else targets.push(focused_target);
 }
""")
_impl.NATIVE_CONTEXT_JS=_impl.NATIVE_CONTEXT_JS.replace('focus,modals,targets,hits,outside_modal_targets',
 'focus,modals,targets,hits,outside_modal_targets,focused_target,focus_owned_app')
_keyboard=" const keyboard=el=>['INPUT','TEXTAREA'].includes(el.tagName)&&!el.disabled&&!el.readOnly||el.isContentEditable;"
assert _impl.NATIVE_CONTEXT_JS.count(_keyboard)==1
_impl.NATIVE_CONTEXT_JS=_impl.NATIVE_CONTEXT_JS.replace(_keyboard,r"""
 const disabled=el=>!!el.closest('[aria-disabled="true"],[inert],button:disabled,input:disabled,textarea:disabled,select:disabled,fieldset:disabled');
 const keyboard=el=>!disabled(el)&&(['INPUT','TEXTAREA'].includes(el.tagName)&&!el.readOnly&&!['hidden','password','file','submit','button','checkbox','radio'].includes(el.type)||el.isContentEditable);
""").replace('enabled:!el.disabled&&!unsafe(el)','enabled:!disabled(el)&&!unsafe(el)')
_old_targets=_impl.OdooV066NativeSurfaceAdapter._targets

def _focused_targets(self,meta,action=None):
    rows=_old_targets(self,meta,action)
    for row in rows:
        if row['ref'] in ('body','workspace'):
            row['keyboard']=False
            row['actions']=[kind for kind in row['actions'] if kind not in ('key','type')]
    return rows

_impl.OdooV066NativeSurfaceAdapter._targets=_focused_targets


class OdooV066NativeSurfaceAdapter(_impl.OdooV066NativeSurfaceAdapter):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.actor_clock=ActorClock(task_id=self.task_id,package_sha256=self.task_binding_sha256,started=self.started,clock=lambda:self.clock())
        self._pending_requests={};self._last_native_request=self.clock();self._failure_number=0
        # Do not retain request URLs/bodies or filter business endpoints.
        # Websocket/eventsource streams are not document/xhr/fetch resources.
        self.page.on('request',self._request_started)
        self.page.on('requestfinished',self._request_finished)
        self.page.on('requestfailed',self._request_finished)

    def _within_budget(self):
        self.actor_clock.check('before_native_observation_or_dispatch')
        return super()._within_budget()

    def current_frame_id(self):
        if self.actor_clock.ended is not None or self.clock()>=self.actor_clock.deadline:return 'stale'
        return super().current_frame_id()

    def _request_started(self,request):
        if request.resource_type in READINESS_REQUEST_TYPES:
            # Keep the public Request alive until its completion event; Python
            # object IDs cannot be reused while an in-flight entry is retained.
            self._pending_requests[id(request)]=(request,request.resource_type,self.clock())
            self._last_native_request=self.clock()

    def _request_finished(self,request):
        if self._pending_requests.pop(id(request),None) is not None:
            self._last_native_request=self.clock()

    def bind_guard(self,root,worker_private):
        _impl.require(self.store is None and self.latest is None,'guard_boundary_already_bound')
        self.store=_impl.EvidenceStore(root)
        meta=None
        for index,delay in enumerate(witness.READINESS_DELAYS_MS):
            if delay:self.page.wait_for_timeout(delay)
            meta=self._meta()
            # Retain the actual selector/resource metadata before rejection.
            self.store.json(f'surface-guard/principal-readiness-{index:02d}.private.json',meta,
                'native_observation_envelope')
            expected_origin=self.page.url.split('/odoo',1)[0]
            parsed=witness.principal_from_witness(meta.get('principal_witness'),expected_origin)
            if parsed is not None and parsed==meta['account_principal'] and meta['app_shell'] and meta['visible'] and meta['top_window']:break
        else:raise _impl.policy.GuardError('guard_native_account_binding_missing')
        self.boundary=_impl.OdooLeaseEvidence(store=self.store,worker_private=worker_private,page=self.page,
            account_principal=parsed,started=self.started,expires=self.started+_impl.WALL_SECONDS,clock=self.clock)
        _impl.require(self.boundary.owns(self.page,meta),'guard_initial_surface_not_owned')
        self.actor_clock.bind(self.store)

    def _ready_before_observation(self):
        self._within_budget()
        _impl.require(self.store is not None and self.boundary is not None,'guard_boundary_not_bound')
        # Every observation has a fresh quiet interval, including initial route
        # hydration whose requests may predate construction. No GUI is replayed.
        since=self.clock()
        for index in range(READINESS_MAX_SAMPLES):
            self._within_budget()
            self.page.wait_for_timeout(READINESS_POLL_MS)
            self._within_budget()
            prefix=f'surface-guard/readiness-turn-{self.step:03d}-{index:02d}'
            image=self.store.write(prefix+'.png',self.page.screenshot(type='png'),'raw_observation_image')
            meta=self._meta();loading=self.page.evaluate(BUSY_JS)
            pending=[row[1] for row in self._pending_requests.values()]
            pending_ages=[max(0.0,self.clock()-row[2]) for row in self._pending_requests.values()]
            self.store.json(prefix+'-native.private.json',{'native':meta,'loading':loading,
                'image':image,'pending_request_types':pending,'pending_request_ages_seconds':pending_ages,'gui_driver_called':False},'native_observation_envelope')
            lease=_impl.policy.validate_lease(self.boundary.lease)
            check=_impl.policy.validate_lease_check(self.boundary.check(lease),lease)
            tick=self.clock();quiet=tick-max(since,self._last_native_request)
            self.store.json(prefix+'.private.json',{'schema':'odoo-native-readiness-sample-v13',
                'task_id':self.task_id,'step':self.step,'sample':index,'native':meta,'loading':loading,
                'pending_request_types':pending,'pending_request_ages_seconds':pending_ages,'request_quiet_seconds':quiet,'lease_check':check,
                'image':image,'gui_driver_called':False},'native_observation_envelope')
            if check['status']!='active' or not self.boundary.owns(self.page,meta):
                self._quarantined=True
                raise GuardHardStop('guard_readiness_lease_or_owned_surface_lost')
            _impl.require(type(loading) is dict and loading.get('schema')=='odoo-generic-native-loading-v13'
                and type(loading.get('busy')) is list,'guard_readiness_metadata_invalid')
            if quiet>=READINESS_QUIET_SECONDS and loading.get('document_ready') is True and loading.get('action_view_count',0)>0 and not loading['busy']:
                return
        self._quarantined=True
        raise GuardHardStop('guard_native_loading_timeout_no_replay')

    def observe_for_model(self,*,memory=''):
        try:self._ready_before_observation()
        except BaseException as error:
            if self.store is not None:
                self.store.json(f'surface-guard/readiness-failure-{self.step:03d}-{self._failure_number:03d}.private.json',{
                    'schema':'odoo-native-readiness-failure-v13','error_type':type(error).__name__,
                    'error_message':str(error),'error_code':getattr(error,'code',None),
                    'step':self.step,'nonce_issued':False,'gui_driver_called':False,
                    'applied_inferred':False},'native_observation_envelope')
                self._failure_number+=1
            raise
        return super().observe_for_model(memory=memory)

    def dispatch(self,raw_action):
        try:
            result=super().dispatch(raw_action)
        except BaseException as error:
            if self.store is not None:
                self.store.json(f'surface-guard/dispatch-failure-{self.step:03d}-{self._failure_number:03d}.private.json',{
                    'schema':'odoo-native-dispatch-failure-v13','error_type':type(error).__name__,
                    'error_message':str(error),'error_code':getattr(error,'code',None),
                    'step_after_failure':self.step,'applied_inferred':False},'dispatch_receipt')
                self._failure_number+=1
            raise
        if result['status']=='rejected':
            self.store.json(f'surface-guard/rejected-turn-{self.step-1:03d}.private.json',{
                'schema':'odoo-native-rejected-turn-v13','status':'rejected','reason':result['code'],
                'turn_consumed':True,'nonce_invalidated':True,'gui_driver_called':False,
                'contract_receipt':result['public_contract_receipt'],'action':result['action'],
                'trusted_control_must_stop':True},'dispatch_receipt')
        return result


_impl.OdooV066NativeSurfaceAdapter=OdooV066NativeSurfaceAdapter
PROFILE,VIEWPORT,NATIVE_CONTEXT_JS,VISIBLE_CONTROLS_JS=_impl.PROFILE,_impl.VIEWPORT,_impl.NATIVE_CONTEXT_JS,_impl.VISIBLE_CONTROLS_JS
GuardHardStop,GuardDriverUncertain,audit_guard=_impl.GuardHardStop,_impl.GuardDriverUncertain,_impl.audit_guard


def public_binding():
    value=_impl.public_binding();root=Path(__file__).resolve().parents[2]
    names=('enterprise_fallback/odoo18/odoo_actor_clock_v1.py','native_desktop_factory/actor_deadline_future_v21.py',
        'enterprise_fallback/odoo18/odoo_native_principal_witness_v7.py',
        'enterprise_fallback/odoo18/odoo_v066_native_surface_adapter_v6.py',
        'enterprise_fallback/odoo18/odoo_native_surface_evidence_v6.py',
        'enterprise_fallback/odoo18/native_compat_source_loader_v1.py')
    bindings={**value['bindings_sha256'],**{name:sha256((root/name).read_bytes()).hexdigest() for name in names}}
    return {**value,'focused_native_element_always_retained':True,
        'focused_native_ref_policy':'stable_document_element_weakmap_no_body_or_selection_fallback',
        'uniform_focus_slots':['teacher','control','shared-base','selected-1','selected-2','selected-3','selected-4'],
        'semantic_role_controls': ['button','menuitem','option'],
        'file_viewer_modal_recognized': True,
        'active_modal_target_scope': 'native_topmost_visible_dialog_with_full_background_metadata',
        'principal_identity':'native_typed_avatar_resource_after_trusted_login',
        'principal_readiness_delays_ms':list(witness.READINESS_DELAYS_MS),'principal_missing_fails_closed':True,
        'native_readiness':{'poll_ms':READINESS_POLL_MS,'quiet_seconds':READINESS_QUIET_SECONDS,
            'max_samples':READINESS_MAX_SAMPLES,'request_types':list(READINESS_REQUEST_TYPES),
            'pending_requests_are_evidence_not_ui_loading_authority':True,
            'disabled_targets_are_not_loading':True,'no_task_or_action_specific_wait':True,
            'wall_budget_retained':True,'all_samples_raw_and_lease_checked':True},
        'bindings_sha256':bindings,'binding_sha256':sha256(_impl.policy.canonical(bindings)).hexdigest()}


def __getattr__(name):return getattr(_impl,name)
