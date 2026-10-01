"""Fresh v9 principal witness/readiness; preserved v6 safety and action rules."""
from hashlib import sha256
import json
from pathlib import Path
from .native_compat_source_loader_v1 import load_source
from . import odoo_native_principal_witness_v7 as witness

# Task-independent request/DOM readiness. Disabled controls are deliberately
# absent: a permanently disabled control remains ordinary rejected behavior.
READINESS_POLL_MS=250
READINESS_QUIET_SECONDS=0.5
READINESS_MAX_SAMPLES=24
READINESS_REQUEST_TYPES=('document','xhr','fetch')
BUSY_JS=r"""() => {
 const visible=el=>{const r=el.getBoundingClientRect(),s=getComputedStyle(el);return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden';};
 const nodes=Array.from(document.querySelectorAll('[aria-busy="true"],.o_blockUI,.o_block_ui,.o_loading,.o_field_loading,[inert],[aria-label]')).filter(visible).filter(el=>el.matches('[aria-busy="true"],.o_blockUI,.o_block_ui,.o_loading,.o_field_loading,[inert]')||/loading/i.test(el.getAttribute('aria-label')||''));
 return {schema:'odoo-generic-native-loading-v9',document_ready:document.readyState==='complete',action_view_count:document.querySelectorAll('.o_action,.o_action_manager').length,busy:nodes.map(el=>({tag:el.tagName.toLowerCase(),class_name:typeof el.className==='string'?el.className:'',aria_busy:el.getAttribute('aria-busy'),aria_label:el.getAttribute('aria-label'),inert:el.hasAttribute('inert')}))};
}"""

_impl=load_source('enterprise_fallback/odoo18/odoo_v066_native_surface_adapter_v6.py',
 'enterprise_fallback.odoo18._native_surface_adapter_v9',
 'a7bc3f6edcd4cd0ab031edafd5f549164b37cdf5e8d903123ea88eb1f90dc119',(
 ('odoo_native_surface_evidence_v6','odoo_native_surface_evidence_v9',2),
 ('native-owned-surface-safety-envelope-v6','native-owned-surface-safety-envelope-v9',1),
 ('odoo-current-native-surface-v6','odoo-current-native-surface-v9',2),
 ('odoo-native-surface-capsule-v6','odoo-native-surface-capsule-v9',2),
 ('odoo-native-held-lease-evidence-v6','odoo-native-held-lease-evidence-v9',1),
 ('native_avatar_uid','native_avatar_principal',1),('account_uid','account_principal',5),
 ('odoo_v066_native_surface_adapter_v6.py','odoo_v066_native_surface_adapter_v9.py',1),
 ('envloop-odoo-native-surface-common-binding-v6','envloop-odoo-native-surface-common-binding-v9',1),
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


class OdooV066NativeSurfaceAdapter(_impl.OdooV066NativeSurfaceAdapter):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self._pending_requests={};self._last_native_request=self.clock();self._failure_number=0
        # Do not retain request URLs/bodies or filter business endpoints.
        # Websocket/eventsource streams are not document/xhr/fetch resources.
        self.page.on('request',self._request_started)
        self.page.on('requestfinished',self._request_finished)
        self.page.on('requestfailed',self._request_finished)

    def _request_started(self,request):
        if request.resource_type in READINESS_REQUEST_TYPES:
            # Keep the public Request alive until its completion event; Python
            # object IDs cannot be reused while an in-flight entry is retained.
            self._pending_requests[id(request)]=(request,request.resource_type)
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
            self.store.json(prefix+'-native.private.json',{'native':meta,'loading':loading,
                'image':image,'pending_request_types':pending,'gui_driver_called':False},'native_observation_envelope')
            lease=_impl.policy.validate_lease(self.boundary.lease)
            check=_impl.policy.validate_lease_check(self.boundary.check(lease),lease)
            tick=self.clock();quiet=tick-max(since,self._last_native_request)
            self.store.json(prefix+'.private.json',{'schema':'odoo-native-readiness-sample-v9',
                'task_id':self.task_id,'step':self.step,'sample':index,'native':meta,'loading':loading,
                'pending_request_types':pending,'request_quiet_seconds':quiet,'lease_check':check,
                'image':image,'gui_driver_called':False},'native_observation_envelope')
            if check['status']!='active' or not self.boundary.owns(self.page,meta):
                self._quarantined=True
                raise GuardHardStop('guard_readiness_lease_or_owned_surface_lost')
            _impl.require(type(loading) is dict and loading.get('schema')=='odoo-generic-native-loading-v9'
                and type(loading.get('busy')) is list,'guard_readiness_metadata_invalid')
            if not pending and quiet>=READINESS_QUIET_SECONDS and loading.get('document_ready') is True and loading.get('action_view_count',0)>0 and not loading['busy']:
                return
        self._quarantined=True
        raise GuardHardStop('guard_native_loading_timeout_no_replay')

    def observe_for_model(self,*,memory=''):
        try:self._ready_before_observation()
        except BaseException as error:
            if self.store is not None:
                self.store.json(f'surface-guard/readiness-failure-{self.step:03d}-{self._failure_number:03d}.private.json',{
                    'schema':'odoo-native-readiness-failure-v9','error_type':type(error).__name__,
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
                    'schema':'odoo-native-dispatch-failure-v9','error_type':type(error).__name__,
                    'error_message':str(error),'error_code':getattr(error,'code',None),
                    'step_after_failure':self.step,'applied_inferred':False},'dispatch_receipt')
                self._failure_number+=1
            raise
        if result['status']=='rejected':
            self.store.json(f'surface-guard/rejected-turn-{self.step-1:03d}.private.json',{
                'schema':'odoo-native-rejected-turn-v9','status':'rejected','reason':result['code'],
                'turn_consumed':True,'nonce_invalidated':True,'gui_driver_called':False,
                'contract_receipt':result['public_contract_receipt'],'action':result['action'],
                'trusted_control_must_stop':True},'dispatch_receipt')
        return result


_impl.OdooV066NativeSurfaceAdapter=OdooV066NativeSurfaceAdapter
PROFILE,VIEWPORT,NATIVE_CONTEXT_JS,VISIBLE_CONTROLS_JS=_impl.PROFILE,_impl.VIEWPORT,_impl.NATIVE_CONTEXT_JS,_impl.VISIBLE_CONTROLS_JS
GuardHardStop,GuardDriverUncertain,audit_guard=_impl.GuardHardStop,_impl.GuardDriverUncertain,_impl.audit_guard


def public_binding():
    value=_impl.public_binding();root=Path(__file__).resolve().parents[2]
    names=('enterprise_fallback/odoo18/odoo_native_principal_witness_v7.py',
        'enterprise_fallback/odoo18/odoo_v066_native_surface_adapter_v6.py',
        'enterprise_fallback/odoo18/odoo_native_surface_evidence_v6.py',
        'enterprise_fallback/odoo18/native_compat_source_loader_v1.py')
    bindings={**value['bindings_sha256'],**{name:sha256((root/name).read_bytes()).hexdigest() for name in names}}
    return {**value,'semantic_role_controls': ['button','menuitem','option'],
        'file_viewer_modal_recognized': True,
        'principal_identity':'native_typed_avatar_resource_after_trusted_login',
        'principal_readiness_delays_ms':list(witness.READINESS_DELAYS_MS),'principal_missing_fails_closed':True,
        'native_readiness':{'poll_ms':READINESS_POLL_MS,'quiet_seconds':READINESS_QUIET_SECONDS,
            'max_samples':READINESS_MAX_SAMPLES,'request_types':list(READINESS_REQUEST_TYPES),
            'disabled_targets_are_not_loading':True,'no_task_or_action_specific_wait':True,
            'wall_budget_retained':True,'all_samples_raw_and_lease_checked':True},
        'bindings_sha256':bindings,'binding_sha256':sha256(_impl.policy.canonical(bindings)).hexdigest()}


def __getattr__(name):return getattr(_impl,name)
