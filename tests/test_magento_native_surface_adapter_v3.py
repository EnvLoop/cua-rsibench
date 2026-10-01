"""Exercise the production V3 observation and V1 dispatch, with a fake page only."""
import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from enterprise_fallback.odoo18.odoo_native_surface_evidence_v6 import EvidenceStore
from magento_catalog_factory import native_surface_adapter_v3 as current
from magento_catalog_factory.native_surface_guard_v1 import GuardHardStop
from native_desktop_factory.actor_deadline_future_v21 import ActorDeadlineReached
from playwright.async_api import Error
from tests.test_magento_native_surface_guard_v1 import Page, Boundary


class ObservationBudgetTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.root.chmod(0o700)
        self.page = Page()
        self.boundary = Boundary(self.page, EvidenceStore(self.root))
        self.adapter = current.NativeAdapter(
            page=self.page, task_id='synthetic-v3-owned-task', package_sha256='e' * 64,
            instruction='Repair the visible synthetic price', root=self.root,
            lease_boundary=self.boundary,
        )
        self.adapter.clock = lambda: self.page.tick
        self.timer = patch('time.monotonic', lambda: self.page.tick)
        self.timer.start()
        self.addCleanup(self.timer.stop)
        asyncio.get_running_loop().set_debug(False)

    def read_results(self):
        return [json.loads(p.read_text()) for p in sorted(self.root.glob('guard/observation-read-*-result.private.json'))]

    async def test_same_read_can_settle_after_six_seconds_without_resubmission(self):
        evaluate = self.page.evaluate
        count = 0
        async def delayed(script, points):
            nonlocal count
            count += 1
            if count == 1:
                self.page.tick += 7
            return await evaluate(script, points)
        self.page.evaluate = delayed
        observation, _ = await self.adapter.observe()
        self.assertEqual(count, 3)  # Two readiness reads and one fresh frame read.
        self.assertEqual(observation.step, 0)
        self.assertGreater(self.read_results()[0]['returned_monotonic'] - self.read_results()[0]['started_monotonic'], 6)
        self.assertEqual(self.page.calls, [])

    async def test_loading_mask_reads_share_one_total_thirty_second_deadline(self):
        evaluate = self.page.evaluate
        self.page.busy = True
        async def delayed(script, points):
            self.page.tick += 8
            return await evaluate(script, points)
        self.page.evaluate = delayed
        with self.assertRaisesRegex(GuardHardStop, 'readiness_timeout'):
            await self.adapter.observe()
        intents = [json.loads(p.read_text()) for p in self.root.glob('guard/observation-read-*-intent.private.json')]
        self.assertEqual(len(intents), 4)
        self.assertEqual(len({v['readiness_deadline_monotonic'] for v in intents}), 1)
        self.assertEqual(self.page.calls, [])
        self.assertTrue(self.adapter.quarantined)
        self.assertIsNone(self.adapter.latest)

    async def test_timeout_records_unavailable_read_and_no_nonce_or_driver(self):
        async def unavailable(_script, _points):
            raise TimeoutError('Synthetic read unavailable')
        self.page.evaluate = unavailable
        with self.assertRaisesRegex(GuardHardStop, 'readiness_timeout'):
            await self.adapter.observe()
        result = self.read_results()[0]
        self.assertEqual(result['status'], 'read_unavailable')
        self.assertEqual(result['error_type'], 'TimeoutError')
        self.assertFalse(result['gui_driver_called'])
        self.assertFalse(result['native_io_replayed'])
        self.assertFalse(result['nonce_issued_for_failed_read'])
        self.assertFalse(list(self.root.glob('guard/turn-*/intent.private.json')))
        self.assertFalse(list(self.root.glob('paid/*')))
        with self.assertRaisesRegex(GuardHardStop, 'quarantined'):
            await self.adapter.observe()

    async def test_actor_expiry_during_observation_is_typed_and_no_driver(self):
        evaluate = self.page.evaluate
        self.page.tick = self.adapter.actor.deadline - .5
        async def delayed(script, points):
            self.page.tick += .5
            return await evaluate(script, points)
        self.page.evaluate = delayed
        with self.assertRaises(ActorDeadlineReached):
            await self.adapter.observe()
        self.assertEqual(self.page.calls, [])
        self.assertFalse(list(self.root.glob('guard/turn-*/intent.private.json')))
        self.assertTrue(list(self.root.glob('actor-clock/stop-*.private.json')))

    async def test_navigation_context_loss_resamples_read_only(self):
        evaluate = self.page.evaluate
        count = 0
        async def replaced(script, points):
            nonlocal count
            count += 1
            if count == 1:
                raise Error('Execution context was destroyed')
            return await evaluate(script, points)
        self.page.evaluate = replaced
        async def advance(duration):
            self.page.tick += duration
        with patch.object(current.asyncio, 'sleep', advance):
            await self.adapter.observe()
        self.assertEqual(count, 4)
        self.assertEqual(self.read_results()[0]['status'], 'context_destroyed')
        self.assertEqual(self.page.calls, [])

    async def test_predispatch_context_loss_is_terminal_without_read_retry(self):
        await self.adapter.observe()
        count = 0
        async def replaced(_script, _points):
            nonlocal count
            count += 1
            raise Error('Execution context was destroyed')
        self.page.evaluate = replaced
        with self.assertRaises(Error):
            await self.adapter.dispatch('{"type":"click","target":{"x":50,"y":50}}')
        self.assertEqual(count, 1)
        self.assertEqual(self.page.calls, [])
        self.assertFalse(list(self.root.glob('guard/turn-*/intent.private.json')))

    async def test_keyboard_focus_context_loss_has_one_click_and_no_typing_or_retry(self):
        await self.adapter.observe()
        evaluate = self.page.evaluate
        count = 0
        async def replaced(script, points):
            nonlocal count
            count += 1
            if count == 2:
                raise Error('Execution context was destroyed')
            return await evaluate(script, points)
        self.page.evaluate = replaced
        with self.assertRaises(Error):
            await self.adapter.dispatch('{"type":"type","target":{"x":50,"y":50},"mode":"fill","text":"9.25"}')
        self.assertEqual(count, 2)
        self.assertEqual(self.page.calls, [('click', 50, 50)])
        self.assertTrue(self.adapter.quarantined)
        self.assertTrue((self.root / 'guard/turn-000/uncertain.private.json').exists())
        self.assertFalse((self.root / 'guard/turn-000/receipt.private.json').exists())

    async def test_closed_browser_is_not_resampled(self):
        count = 0
        async def closed(_script, _points):
            nonlocal count
            count += 1
            raise Error('Target page, context or browser has been closed')
        self.page.evaluate = closed
        with self.assertRaises(Error):
            await self.adapter.observe()
        self.assertEqual(count, 1)
        self.assertEqual(self.page.calls, [])

    async def test_common_actor_imports_new_adapter_and_binding_covers_both_epochs(self):
        from magento_catalog_factory import native_surface_actor_v1 as actor, native_surface_workers_v1 as workers
        self.assertIs(actor.NativeAdapter, current.NativeAdapter)
        binding = workers.public_binding()
        self.assertTrue(binding['all_teacher_control_base_and_four_checkpoint_slots_same_source'])
        self.assertEqual((binding['max_actions'], binding['actor_seconds'], binding['owned_lifecycle_seconds']), (90, 720, 1200))
        for name in ['native_surface_adapter_v2.py', 'native_surface_adapter_v3.py']:
            self.assertIn('magento_catalog_factory/' + name, binding['source_sha256s'])


if __name__ == '__main__':
    unittest.main()
