"""No-Docker checks for clean Magento v3 runtime, guard, pilot and freeze."""

from __future__ import annotations

import asyncio
import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tools import magento_clean_100_v3 as v3
from tools import magento_v3_runtime as runtime
from tools import magento_v3_guard_train_pilot as pilot
from tools import qualify_magento_original_catalog_v3 as gui
from tools import sweep_magento_original_gui_controls_v3 as sweep


class _Modal:
    def __init__(self, page, *, label="A new Magento release notification is available"):
        self.page = page
        self.label = label

    async def count(self):
        return 1 if self.page.phase == 'modal' else 0

    async def inner_text(self):
        return self.label

    def locator(self, _selector):
        return self

    async def is_visible(self):
        return self.page.phase == 'modal'

    async def click(self, *, timeout):
        assert timeout == 5000
        self.page.phase = 'clear'


class _Mask:
    def __init__(self, page):
        self.page = page

    async def count(self):
        return 1 if self.page.phase == 'mask' else 0


class _Page:
    def __init__(self, *, label="A new Magento release notification is available"):
        self.phase = 'mask'
        self.modal = _Modal(self, label=label)
        self.mask = _Mask(self)

    def locator(self, selector):
        return self.mask if 'loading-mask' in selector else self.modal

    async def wait_for_timeout(self, _ms):
        if self.phase == 'mask':
            self.phase = 'modal'


class MagentoClean100V3Tests(unittest.TestCase):
    def test_project_venv_and_playwright_import_gate_precede_browser(self):
        with patch.object(runtime.sys, 'executable', '/usr/bin/python3'):
            with self.assertRaisesRegex(ValueError, 'wrong_operator_python'):
                runtime.check_current(launch_browser=True)
        with patch.object(runtime.importlib.util, 'find_spec', return_value=None):
            with self.assertRaisesRegex(ValueError, 'playwright_async_api_not_importable'):
                runtime.check_current(launch_browser=True)

    def test_local_headless_preflight_is_source_bound_without_docker(self):
        async def fake_launch():
            return '153.0.8010.12'
        with patch.object(runtime, '_launch_headless', fake_launch):
            result = runtime.check_current(launch_browser=True)
        self.assertEqual(result['python_path'], str(runtime.PINNED_PYTHON))
        self.assertTrue(result['headless_launch_passed'])
        self.assertEqual(result['headless_revision'], '1243')
        self.assertEqual(result['docker_calls'], 0)

    def test_release_guard_waits_mask_and_closes_only_release_modal(self):
        page = _Page()
        result = asyncio.run(gui.settle_release_obstruction(page))
        self.assertEqual(result, {
            'release_mask_observed': True,
            'release_notification_modals_closed': 1,
            'obstruction_clear_before_business_edit': True})
        wrong = _Page(label='Delete this product permanently?')
        with self.assertRaisesRegex(ValueError, 'non-release'):
            asyncio.run(gui.settle_release_obstruction(wrong))

    def test_wrong_python_stops_sweep_before_any_clone_or_case_folder(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            with (patch.object(sweep.sys, 'executable', '/usr/bin/python3'),
                  patch.object(sweep, 'assert_absent') as absent):
                with self.assertRaisesRegex(ValueError, 'pinned project Python'):
                    sweep.task(0, {'task_id': 'train-only'}, Path('plan'), 'x',
                               Path('source'), root, root / 'journal')
                absent.assert_not_called()
                self.assertFalse((root / 'case-000').exists())

    def test_v3_freeze_requires_real_train_guard_exposure_and_keeps_old14_out(self):
        cases = [{'task_id': f'candidate-{i:03d}',
                  'package_sha256': f'{i + 1:064x}'} for i in range(100)]
        old = {'final_candidate_plan_sha256': 'p',
               'runtime_fingerprint_sha256': 'r'}
        train = {'release_obstruction_observed_in_train': False,
                 'all_four_pre_edit_states_exact': True,
                 'positive_saved_state_passed': True,
                 'wrong_variant_rejected': True,
                 'fresh_reset_passed': True}
        runtime_value = {'python_path': str(runtime.PINNED_PYTHON),
                         'headless_binary_sha256': 'h' * 64}
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            with (patch.object(v3, 'retired_v2_binding', return_value={
                    'v2_retirement_public_sha256': 'v' * 64,
                    'v2_partial_controls_excluded': 14}),
                  patch.object(v3.runtime_gate, 'validate_receipt',
                               return_value=(runtime_value, 'r' * 64)),
                  patch.object(v3.guard_pilot, 'validate_receipt',
                               return_value=(train, 't' * 64)),
                  patch.object(v3.old_contract, 'validate_freeze',
                               return_value=(old, 'o' * 64)),
                  patch.object(v3, 'validate_plan', return_value=cases),
                  patch.object(v3, 'source_revision', return_value='source'),
                  patch.object(v3, 'CODE_FILES', ())):
                with self.assertRaisesRegex(ValueError, 'real_train_gui_release_guard'):
                    v3.build_freeze(root, Path('old'), Path('plan'), 'p', Path('source'))
                train['release_obstruction_observed_in_train'] = True
                frozen = v3.build_freeze(root, Path('old'), Path('plan'), 'p', Path('source'))
        self.assertEqual(frozen['ordered_case_count'], 100)
        self.assertEqual(frozen['v2_partial_controls_excluded'], 14)
        self.assertEqual(frozen['pinned_python_runtime_sha256'], 'r' * 64)
        self.assertEqual(frozen['train_only_release_guard_pilot_sha256'], 't' * 64)
        self.assertEqual(frozen['official_final_admitted'], 0)

    def test_v3_runner_rejects_old_v2_directory_before_docker(self):
        with patch.object(v3.sweep_v3, 'assert_absent') as absent:
            with self.assertRaisesRegex(ValueError, 'own_exact_directory'):
                v3.run_campaign(Path('plan'), 'p', Path('source'), Path('parent'),
                                Path('freeze'), v3.V2_RUN, resume=False)
            absent.assert_not_called()

    def test_dispatch_does_not_parse_train_or_retired_v2_journals(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            parent = root / 'work/magento-original'
            for name in ('v3-release-guard-train-pilot-20260928',
                         'cron-resumable-100-v2'):
                folder = parent / name
                folder.mkdir(parents=True)
                (folder / 'journal.private.jsonl').write_bytes(b'{"legacy":true}\n')
            with patch.object(v3, 'ROOT', root):
                v3._check_single_dispatch(parent / 'clean-v3-100-20260928', 'f' * 64)
                duplicate = parent / 'clean-v3-another'
                duplicate.mkdir()
                v3.append_event(duplicate / 'journal.private.jsonl', {
                    'event': 'run_started', 'freeze_v3_sha256': 'f' * 64})
                with self.assertRaisesRegex(ValueError, 'already dispatched elsewhere'):
                    v3._check_single_dispatch(parent / 'clean-v3-100-20260928',
                                              'f' * 64)

    def test_train_pilot_requires_four_exact_pre_edit_states(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            base = root / 'case-000'
            task = {'task_id': 'train-only', 'package_sha256': 'a' * 64}
            def save(path, value):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value, sort_keys=True) + '\n')
            save(base / 'calibration.private.json', {
                'schema': 'envloop-magento-original-gui-case-calibration-v3',
                'split': 'train_policy_development',
                'task_id': task['task_id'],
                'package_sha256': task['package_sha256'],
                'positive_score': 1.0, 'wrong_variant_score': 0.0,
                'fresh_reset_passed': True,
                'model_calls': 0, 'official_final_admitted': False})
            save(base / 'negative/fresh-reset.private.json', {
                'fresh_clone_reset_passed': True,
                'material_monitored_sql_and_search_state': True,
                'different_container_ids': True,
                'different_search_container_ids': True,
                'official_final_tasks_admitted': 0})
            journal = []
            for step in pilot.old_contract.STEPS:
                journal.extend(({'event': 'step_intent', 'step': step},
                                {'event': 'step_finished', 'step': step,
                                 'exit_code': 0}))
            journal.extend(({'event': 'pair_cleanup_verified', 'pair': 'positive'},
                            {'event': 'pair_cleanup_verified', 'pair': 'negative'},
                            {'event': 'task_gui_calibrated',
                             'task_id': task['task_id'],
                             'receipt_sha256': pilot.sha(
                                 (base / 'calibration.private.json').read_bytes())}))
            (root / 'journal.private.jsonl').write_text(
                ''.join(json.dumps(row) + '\n' for row in journal))
            for pair, modes in (('positive', ('neutral', 'gui-positive')),
                                ('negative', ('neutral', 'gui-wrong-variant'))):
                for mode in modes:
                    folder = base / pair / mode
                    before = {'business': 'unchanged'}
                    save(folder / 'private-before.json', before)
                    save(folder / 'private-pre-edit.json', before)
                    result = {'task_id': task['task_id'],
                              'mode': ('wrong-variant' if mode == 'gui-wrong-variant'
                                       else 'positive' if mode == 'gui-positive'
                                       else 'neutral'),
                              'pre_edit_sha256': pilot.sha(
                                  (folder / 'private-pre-edit.json').read_bytes()),
                              'quote': {'release_modal_guard': {
                                  'obstruction_clear_before_business_edit': True,
                                  'release_mask_observed': pair == 'positive',
                                  'release_notification_modals_closed': 0}},
                              'model_calls': 0,
                              'official_final_tasks_admitted': 0}
                    save(folder / 'result.json', result)
            with patch.object(pilot, 'RUN_DIR', root):
                good = pilot._read_controls(task, 'plan-sha', 'runtime-sha', {})
                self.assertTrue(good['release_obstruction_observed_in_train'])
                self.assertTrue(good['all_four_pre_edit_states_exact'])
                bad_path = base / 'negative/gui-wrong-variant/private-pre-edit.json'
                save(bad_path, {'business': 'changed'})
                with self.assertRaisesRegex(ValueError, 'exact no-regression'):
                    pilot._read_controls(task, 'plan-sha', 'runtime-sha', {})


if __name__ == '__main__':
    unittest.main()
