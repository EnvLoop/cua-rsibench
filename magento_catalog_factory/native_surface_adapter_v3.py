"""One bounded readiness window for observation-only native metadata reads.

Original V1 safety and V2 loading-mask/context-loss behavior remain unchanged.
Reads after action intent (predispatch and keyboard focus) are never resampled.
"""
import asyncio

from playwright.async_api import Error

from .native_surface_adapter_v2 import (
    NativeAdapter as PreviousNativeAdapter, _meta_current, _observe_current,
)
from .native_surface_guard_v1 import GuardHardStop

OBSERVATION_SECONDS = 30


class NativeAdapter(PreviousNativeAdapter):
    async def observe(self, memory=''):
        self.actor.check('before_bounded_native_observation')
        self._observation_deadline = min(self.actor.deadline, self.clock() + OBSERVATION_SECONDS)
        self._observing_native = True
        try:
            result = await asyncio.wait_for(
                _observe_current(self, memory),
                timeout=self._observation_deadline - self.clock(),
            )
            self.actor.check('after_bounded_native_observation')
            if self.clock() >= self._observation_deadline:
                raise TimeoutError('Observation returned after readiness deadline')
            return result
        except TimeoutError:
            self.store.json(f'guard/observation-timeout-{self.step:03d}.private.json', {
                'schema': 'magento-native-observation-timeout-v3',
                'phase': 'observation_before_intent', 'step': self.step,
                'readiness_deadline_monotonic': self._observation_deadline,
                'observed_monotonic': self.clock(),
                'actor_deadline_monotonic': self.actor.deadline,
                'observation_seconds_limit': OBSERVATION_SECONDS,
                'gui_driver_called': False, 'native_io_replayed': False,
                'nonce_issued_for_failed_read': False,
                'saved_score_not_inferred': True,
            }, 'native_observation_envelope')
            self.quarantined = True
            self.latest = None
            self.observed = None
            # Absolute actor expiry is a typed budget stop, not an infrastructure
            # timeout. A renderer that does not settle earlier remains terminal.
            self.actor.check('after_bounded_native_observation_timeout')
            raise GuardHardStop('native_observation_readiness_timeout_no_replay')
        finally:
            self._observing_native = False
            self._observation_deadline = None

    async def meta(self, points=None):
        if not getattr(self, '_observing_native', False):
            return await _meta_current(self, points)
        sequence = getattr(self, '_observation_read_sequence', 0)
        self._observation_read_sequence = sequence + 1
        deadline = self._observation_deadline
        count = 0
        while True:
            self.actor.check('before_observation_context_read')
            remaining = deadline - self.clock()
            if remaining <= 0:
                raise TimeoutError('Observation readiness window expired')
            prefix = f'guard/observation-read-{self.step:03d}-{sequence:03d}-{count:03d}'
            started = self.clock()
            self.store.json(prefix + '-intent.private.json', {
                'schema': 'magento-native-observation-read-intent-v3',
                'phase': 'observation_before_intent', 'step': self.step,
                'read_attempt': count, 'started_monotonic': started,
                'readiness_deadline_monotonic': deadline,
                'actor_deadline_monotonic': self.actor.deadline,
                'gui_driver_called': False, 'native_io_replayed': False,
                'nonce_issued_for_failed_read': False,
            }, 'native_observation_envelope')
            try:
                value = await asyncio.wait_for(_meta_current(self, points), timeout=remaining)
            except BaseException as error:
                context_lost = isinstance(error, Error) and (
                    'Execution context was destroyed' in str(error) or
                    'Cannot find context with specified id' in str(error)
                )
                self.store.json(prefix + '-result.private.json', {
                    'schema': 'magento-native-observation-read-result-v3',
                    'phase': 'observation_before_intent', 'step': self.step,
                    'read_attempt': count, 'started_monotonic': started,
                    'returned_monotonic': self.clock(),
                    'status': 'context_destroyed' if context_lost else 'read_unavailable',
                    'error_type': type(error).__name__, 'actual_error_text': str(error),
                    'gui_driver_called': False, 'native_io_replayed': False,
                    'nonce_issued_for_failed_read': False,
                }, 'native_observation_envelope')
                if not context_lost:
                    raise
                count += 1
                await asyncio.sleep(min(.1, max(0, deadline - self.clock())))
                continue
            self.store.json(prefix + '-result.private.json', {
                'schema': 'magento-native-observation-read-result-v3',
                'phase': 'observation_before_intent', 'step': self.step,
                'read_attempt': count, 'started_monotonic': started,
                'returned_monotonic': self.clock(), 'status': 'returned',
                'gui_driver_called': False, 'native_io_replayed': False,
                'nonce_issued_for_failed_read': False,
            }, 'native_observation_envelope')
            self.actor.check('after_observation_context_read')
            if self.clock() >= deadline:
                raise TimeoutError('Observation metadata returned after readiness deadline')
            return value
