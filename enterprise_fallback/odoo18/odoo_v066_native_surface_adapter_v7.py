"""Fresh v7 principal witness/readiness; preserved v6 safety and action rules."""
from hashlib import sha256
import json
from pathlib import Path
from .native_compat_source_loader_v1 import load_source
from . import odoo_native_principal_witness_v7 as witness

_impl=load_source('enterprise_fallback/odoo18/odoo_v066_native_surface_adapter_v6.py',
 'enterprise_fallback.odoo18._native_surface_adapter_v7',
 'a7bc3f6edcd4cd0ab031edafd5f549164b37cdf5e8d903123ea88eb1f90dc119',(
 ('odoo_native_surface_evidence_v6','odoo_native_surface_evidence_v7',2),
 ('native-owned-surface-safety-envelope-v6','native-owned-surface-safety-envelope-v7',1),
 ('odoo-current-native-surface-v6','odoo-current-native-surface-v7',2),
 ('odoo-native-surface-capsule-v6','odoo-native-surface-capsule-v7',2),
 ('odoo-native-held-lease-evidence-v6','odoo-native-held-lease-evidence-v7',1),
 ('native_avatar_uid','native_avatar_principal',1),('account_uid','account_principal',5),
 ('odoo_v066_native_surface_adapter_v6.py','odoo_v066_native_surface_adapter_v7.py',1),
 ('envloop-odoo-native-surface-common-binding-v6','envloop-odoo-native-surface-common-binding-v7',1),
 ))
_start=_impl.NATIVE_CONTEXT_JS.index(' const avatars=')
_end=_impl.NATIVE_CONTEXT_JS.index(' const focus=',_start)
_impl.NATIVE_CONTEXT_JS=(_impl.NATIVE_CONTEXT_JS[:_start]+witness.PRINCIPAL_JS+_impl.NATIVE_CONTEXT_JS[_end:]).replace(
 'account_principal:uid,','account_principal:principal,principal_witness:principalWitness,')


class OdooV066NativeSurfaceAdapter(_impl.OdooV066NativeSurfaceAdapter):
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
    return {**value,'principal_identity':'native_typed_avatar_resource_after_trusted_login',
        'principal_readiness_delays_ms':list(witness.READINESS_DELAYS_MS),'principal_missing_fails_closed':True,
        'bindings_sha256':bindings,'binding_sha256':sha256(_impl.policy.canonical(bindings)).hexdigest()}


def __getattr__(name):return getattr(_impl,name)
