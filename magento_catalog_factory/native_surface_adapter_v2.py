"""Bounded read resampling while navigation replaces an observation context."""
import asyncio
from playwright.async_api import Error
from .native_surface_guard_v1 import NativeAdapter as OriginalNativeAdapter


class NativeAdapter(OriginalNativeAdapter):
    async def observe(self, memory=''):
        self._observing_native = True
        try:
            return await super().observe(memory)
        finally:
            self._observing_native = False

    async def meta(self, points=None):
        if not getattr(self, '_observing_native', False):
            return await super().meta(points)
        deadline = min(self.actor.deadline, self.clock() + 6)
        sequence = getattr(self, '_observation_read_sequence', 0)
        self._observation_read_sequence = sequence + 1
        count = 0
        while True:
            self.actor.check('before_observation_context_read')
            remaining = deadline - self.clock()
            if remaining <= 0:
                raise Error('Native observation navigation did not settle within six seconds')
            try:
                return await asyncio.wait_for(super().meta(points), timeout=remaining)
            except Error as error:
                if 'Execution context was destroyed' not in str(error) and 'Cannot find context with specified id' not in str(error):
                    raise
                self.store.json(f'guard/navigation-read-{self.step:03d}-{sequence:03d}-{count:03d}.private.json', {
                    'schema': 'magento-native-observation-context-loss-v2',
                    'phase': 'observation_before_intent', 'step': self.step,
                    'read_attempt': count, 'native_io_replayed': False,
                    'gui_driver_called': False, 'nonce_issued_for_failed_read': False,
                }, 'native_observation_envelope')
                count += 1
                await asyncio.sleep(min(.1, max(0, deadline - self.clock())))
