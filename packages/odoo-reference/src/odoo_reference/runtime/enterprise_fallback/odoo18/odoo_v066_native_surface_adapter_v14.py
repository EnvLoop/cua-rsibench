"""Additive V14: frames expire within the actual actor and held lease clocks.

The exact V13 native principal, readiness, hit, focus and dispatch sources are
loaded in a fresh namespace. No V13 class or source is patched. The 720-second
actor budget, saved-state scorer and reset contract are unchanged.
"""
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

from .native_compat_source_loader_v1 import load_source

_PARENT = 'enterprise_fallback/odoo18/odoo_v066_native_surface_adapter_v13.py'
_PARENT_SHA = '1b4a8235950826f9e318cd72e0d9f31c39dfcb7177512f3e62d9fa0684b220cb'

# These edits apply only to the separately compiled V6 mechanics underlying
# our separately compiled V13 parent. Counted replacements fail on drift.
_CAPTURE_BOUNDARY = (
    ('        self._observed=None\n        image=self.store.write',
     '        observation=self._bounded_observation(observation)\n        self._observed=None\n        image=self.store.write', 1),
    ("        tick=self.clock();prefix=f'surface-guard/turn-{observation.step:03d}/{phase}'",
     "        self.actor_clock.check('before_'+phase+'_envelope_capture')\n"
     "        tick=self.clock();prefix=f'surface-guard/turn-{observation.step:03d}/{phase}'", 1),
    ("        raw_ref=self.store.json(prefix+'-native.private.json',meta,'native_'+phase+'_envelope')",
     "        raw_ref=self.store.json(prefix+'-native.private.json',meta,'native_'+phase+'_envelope')\n"
     "        self.actor_clock.check('after_'+phase+'_envelope_capture')", 1),
    ("'expires_at':observation.expires_at if phase=='observation' else min(tick+self.limits.frame_ttl_seconds,self.boundary.lease['expires_at']),",
     "'expires_at':min(observation.expires_at if phase=='observation' else tick+self.limits.frame_ttl_seconds,self.actor_clock.deadline,self.boundary.lease['expires_at']),", 1),
)

_parent = load_source(_PARENT, 'enterprise_fallback.odoo18._native_surface_adapter_v14_parent', _PARENT_SHA, (
    ('_impl=load_source(', '_V14_CAPTURE_BOUNDARY='+repr(_CAPTURE_BOUNDARY)+'\n\n_impl=load_source(', 1),
    (' ))\n_start=', ' )+_V14_CAPTURE_BOUNDARY)\n_start=', 1),
    ("'enterprise_fallback.odoo18._native_surface_adapter_v13'",
     "'enterprise_fallback.odoo18._native_surface_adapter_v14_base'", 1),
    ('native-owned-surface-safety-envelope-v13', 'native-owned-surface-safety-envelope-v14', 1),
    ('odoo-native-surface-capsule-v13', 'odoo-native-surface-capsule-v14', 1),
    ("('odoo_v066_native_surface_adapter_v6.py','odoo_v066_native_surface_adapter_v13.py',1)",
     "('odoo_v066_native_surface_adapter_v6.py','odoo_v066_native_surface_adapter_v14.py',1)", 1),
    ('envloop-odoo-native-surface-common-binding-v13', 'envloop-odoo-native-surface-common-binding-v14', 1),
))


class OdooV066NativeSurfaceAdapter(_parent.OdooV066NativeSurfaceAdapter):
    def _bounded_observation(self, observation):
        # This is after the actual screenshot and contract construction, before
        # any frame/envelope publication or teacher/student submission.
        self.actor_clock.check('after_native_observation_capture')
        expires = min(observation.expires_at, self.actor_clock.deadline,
                      self.boundary.lease['expires_at'])
        _parent._impl.require(observation.issued_at < expires,
                              'guard_observation_has_no_live_lease_interval')
        return replace(observation, expires_at=expires)

    def observe_for_model(self, *, memory=''):
        self.actor_clock.check('before_native_observation_capture')
        return super().observe_for_model(memory=memory)


# Only this fresh parent namespace exports the fresh subclass. Old V13 globals
# and its compiled V6 class remain untouched in a concurrent V13 process/import.
_parent._impl.OdooV066NativeSurfaceAdapter = OdooV066NativeSurfaceAdapter
_parent.OdooV066NativeSurfaceAdapter = OdooV066NativeSurfaceAdapter
PROFILE = _parent.PROFILE
VIEWPORT = _parent.VIEWPORT
NATIVE_CONTEXT_JS = _parent.NATIVE_CONTEXT_JS
VISIBLE_CONTROLS_JS = _parent.VISIBLE_CONTROLS_JS
GuardHardStop, GuardDriverUncertain, audit_guard = (
    _parent.GuardHardStop, _parent.GuardDriverUncertain, _parent.audit_guard)
EXPIRY_BOUNDARY = {
    'schema': 'odoo-uniform-frame-expiry-v14',
    'observation_expiry': 'min(actual_frame_expiry,actual_actor_deadline,held_lease_expiry)',
    'predispatch_expiry': 'min(current_capture_plus_ttl,actual_actor_deadline,held_lease_expiry)',
    'actual_observation_object_capped': True,
    'typed_actor_checks_before_and_after_capture': True,
    'actor_seconds': 720,
    'frame_ttl_seconds': 270,
    'actor_budget_extended': False,
    'guards_relaxed': False,
    'roles': ['teacher', 'control', 'shared-base', 'selection', 'selected-1', 'selected-2', 'selected-3', 'selected-4', 'final'],
    'old_control_credit': 0,
    'fresh_qualification_required': True,
}


def public_binding():
    value = _parent.public_binding()
    root = Path(__file__).resolve().parents[2]
    names = (_PARENT, 'enterprise_fallback/odoo18/odoo_v066_native_surface_adapter_v14.py',
             'enterprise_fallback/odoo18/odoo_native_surface_evidence_v13.py')
    bindings = {**value['bindings_sha256'], **{name:sha256((root/name).read_bytes()).hexdigest() for name in names}}
    return {**value, 'expiry_boundary':dict(EXPIRY_BOUNDARY), 'bindings_sha256':bindings,
            'binding_sha256':sha256(_parent._impl.policy.canonical({'sources':bindings,'expiry_boundary':EXPIRY_BOUNDARY})).hexdigest()}


def __getattr__(name):
    return getattr(_parent, name)
