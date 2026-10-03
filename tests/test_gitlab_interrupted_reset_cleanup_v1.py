"""An interruption must release only a positively claimed partial boot."""
import asyncio
from pathlib import Path
import unittest
from unittest.mock import patch
from gitlab_world import v066_uniform_task_runtime_v14 as original
from gitlab_world import v066_interrupted_reset_cleanup_v1 as repair


class Backend:
    def __init__(self, failure, owned):
        self.failure, self.claim = failure, owned
        self.owned_cycles, self.calls = set(), []

    def boot(self, index):
        self.calls.append(('boot', index))
        if self.claim:
            self.owned_cycles.add(index)
        raise self.failure

    def teardown(self, index):
        if index not in self.owned_cycles:
            raise AssertionError('Must not adopt an unknown resource')
        self.calls.append(('teardown', index))
        self.owned_cycles.remove(index)


class InterruptionTests(unittest.TestCase):
    def world(self, backend):
        value = repair.InterruptionSafeTaskWorld(
            Path('plan'), Path('permit'), Path('artifacts'), phase='full-study')
        value.backend = backend
        return value

    def test_keyboard_interrupt_cancel_and_system_exit_cleanup_claimed_boot_once(self):
        for failure in (KeyboardInterrupt(), asyncio.CancelledError(), SystemExit(2),
                        RuntimeError('cold boot failed')):
            with self.subTest(exception=type(failure).__name__):
                backend = Backend(failure, True)
                world = self.world(backend)
                with self.assertRaises(type(failure)) as caught:
                    world.reset()
                self.assertIs(caught.exception, failure)
                self.assertEqual(backend.calls, [('boot', 0), ('teardown', 0)])
                self.assertEqual(world.generation, 0)
                self.assertIsNone(world.active_index)
                self.assertFalse(backend.owned_cycles)

    def test_interrupted_unclaimed_boot_never_deletes_or_restarts(self):
        backend = Backend(KeyboardInterrupt(), False)
        with self.assertRaises(KeyboardInterrupt):
            self.world(backend).reset()
        self.assertEqual(backend.calls, [('boot', 0)])

    def test_original_exception_only_cleanup_misses_keyboard_interrupt(self):
        backend = Backend(KeyboardInterrupt(), True)
        world = self.world(backend)
        with self.assertRaises(KeyboardInterrupt):
            original.TaskWorld.reset(world)
        self.assertEqual(backend.calls, [('boot', 0)])
        self.assertEqual(backend.owned_cycles, {0})

    def test_cleanup_failure_is_not_success_and_cannot_start_second_boot(self):
        backend = Backend(KeyboardInterrupt(), True)
        with patch.object(backend, 'teardown', side_effect=ValueError('Cleanup failed')):
            with self.assertRaisesRegex(ValueError, 'Cleanup failed'):
                self.world(backend).reset()
        self.assertEqual(backend.calls, [('boot', 0)])

    def test_old_runtime_and_all_other_methods_are_unchanged(self):
        source = Path(original.__file__).read_bytes()
        original_reset = original.TaskWorld.reset
        repair.interruption_safe_reset()
        self.assertEqual(Path(original.__file__).read_bytes(), source)
        self.assertIs(original.TaskWorld.reset, original_reset)
        for name in ('open', '_open_guarded', '_scope', '_permit'):
            self.assertIs(getattr(repair.InterruptionSafeTaskWorld, name),
                          getattr(original.TaskWorld, name))


if __name__ == '__main__':
    unittest.main()
