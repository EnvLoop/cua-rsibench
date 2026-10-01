"""Synthetic selection packets only; no Docker, browser or paid API calls."""
import copy
import json
from pathlib import Path
import re
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from enterprise_fallback.odoo18 import twenty_task_trial_selection_v1 as subject
from tests.test_odoo_twenty_task_trial_evaluator_v1 import save


class TrialSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plan = {'native_binding_sha256': 'a'*64, 'reference_binding_sha256': 'b'*64}
        self.identities = [{'task_id': f'SYNTHETIC-SEL-{i:02d}', 'package_sha256': subject.digest(str(i).encode())} for i in range(20)]
        self.control = {'schema': subject.controls.SCHEMA, 'status': subject.controls.STATUS, 'split': 'selection',
            'qualified_control_case_count': 20, 'native_worker_binding_sha256': 'a'*64, 'reference_binding_sha256': 'b'*64,
            'finalizer_source_sha256': subject.digest(Path(subject.controls.__file__).read_bytes()),
            'all_saved_audits_independently_rederived': True, 'all_source_and_packages_equivalent': True,
            'originals_preserved': True, 'formal_task_registration_count': 0, 'formal_registration_performed': False,
            'model_calls': 0, 'provider_calls': 0, 'native_calls': 0,
            'rows': [{**task, 'independent_scores': [0.0, 1.0, 0.0], 'source_visual_review_verified': True,
                      'source_attachment_readback': True} for task in self.identities]}
        self.audit_calls = []
        self.selection = SimpleNamespace(campaign=SimpleNamespace(TINKER_PATH=re.compile(r'tinker://[^ ]+')),
            vision_digest=lambda value: subject.digest(json.dumps(value).encode()),
            _audit_task_artifacts=lambda episode, task, row: self.audit_calls.append((str(episode), task['task_id'])))

    def check_control(self, value=None):
        ref = save(self.root/'control.private.json', self.control if value is None else value)
        return subject.checked_control(ref['path'], ref['sha256'], self.plan, self.identities)

    def test_current_twenty_controls_required_and_old_formal_authority_rejected(self):
        self.assertEqual(len(self.check_control()['rows']), 20)
        for key, value in [('qualified_control_case_count', 100), ('split', 'official_hidden'),
            ('native_worker_binding_sha256', '0'*64), ('reference_binding_sha256', '0'*64),
            ('formal_registration_performed', True), ('model_calls', 1), ('finalizer_source_sha256', '0'*64),
            ('schema', 'cua-full-study-ratification-v1')]:
            changed = copy.deepcopy(self.control)
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(subject.legacy.OdooFinalWorkerError): self.check_control(changed)

    def test_control_roster_order_and_three_independent_scores_are_checked(self):
        for kind in ('wrong_score', 'duplicate', 'reorder', 'unreviewed', 'nineteen'):
            value = copy.deepcopy(self.control)
            rows = value['rows']
            if kind == 'wrong_score': rows[0]['independent_scores'] = [0, 1, 1]
            if kind == 'duplicate': rows[1] = rows[0]
            if kind == 'reorder': rows.reverse()
            if kind == 'unreviewed': rows[0]['source_visual_review_verified'] = False
            if kind == 'nineteen': rows.pop()
            with self.subTest(kind=kind), self.assertRaises(subject.legacy.OdooFinalWorkerError): self.check_control(value)

    def packet(self, base):
        path = subject.MODEL if base else 'tinker://SYNTHETIC/sampler_weights/checkpoint'
        entries, scores = [], []
        for index, task in enumerate(self.identities):
            episode = self.root/f'{"base" if base else "checkpoint"}-{index}'
            episode.mkdir(mode=0o700)
            relative = lambda ref: {'path': Path(ref['path']).name, 'sha256': ref['sha256']}
            refs = {}
            values = {
                'actor_clock_ref': {'native_actions_after_deadline': 0, 'evaluation_outside_actor_clock': True, 'actor_elapsed_seconds': 3},
                'owned_complete_lifecycle_ref': {'saved_readback_reset_and_provider_close_complete': True, 'started_monotonic': 1, 'ended_monotonic': 4},
                'provider_close_ref': {'status': 'acknowledged', 'real_close_call_returned': True}}
            for key, value in values.items(): refs[key] = relative(save(episode/(key+'.private.json'), value))
            score = index%2
            row = relative(save(episode/'row.private.json', {**task, 'score': score, **refs}))
            setup = relative(save(episode/'setup.private.json', {'status': 'ready', 'actual_backend_identity': {
                'sampling_kind': 'base' if base else 'checkpoint', 'checkpoint_sha256': self.selection.vision_digest(path)}}))
            entries.append({'task': task, 'episode_root': str(episode), 'native_row': row, 'paid_setup_result': setup})
            scores.append({'task': task, 'score': score})
        control_ref = save(self.root/'control.private.json', self.control)
        return {'schema': 'envloop-odoo20-selection-complete-v1', 'status': 'twenty_saved_scores_reset_and_closed',
            'trial_plan_sha256': 'c'*64, 'source_binding': subject.source_binding(),
            'selection_control_ref': control_ref, 'selection_control_sha256': control_ref['sha256'],
            'model': subject.MODEL, 'checkpoint_path': path, 'checkpoint_sha256': subject.digest(path.encode()),
            'base_mode': base, 'selection_tasks': entries, 'scores': scores, 'actual_cost_usd': None,
            'formal_large_study_credit': 0, 'hidden_final_outcomes_used': False}

    def freeze(self, baseline, selected):
        baseline_ref = save(self.root/'baseline-result.private.json', baseline)
        selected_ref = save(self.root/'selected-result.private.json', selected)
        with patch.object(subject.evaluator, 'checked_trial', return_value=(self.plan, [])), \
             patch.object(subject.workers, '_model_modules', return_value=(None, self.selection)):
            return subject.freeze_checkpoint(plan_path='', plan_sha='c'*64, baseline_result_ref=baseline_ref,
                selected_result_ref=selected_ref, output_path=self.root/'freeze.private.json')

    def test_freeze_reopens_all_actual_selection_artifacts_and_matches_final_schema(self):
        baseline, selected = self.packet(True), self.packet(False)
        ref = self.freeze(baseline, selected)
        freeze = subject.evaluator.read_ref(ref)
        self.assertEqual(freeze['schema'], 'envloop-odoo20-selection-checkpoint-freeze-v1')
        self.assertEqual(freeze['checkpoint_path'], selected['checkpoint_path'])
        self.assertEqual(freeze['formal_large_study_credit'], 0)
        self.assertEqual(len(self.audit_calls), 60)
        self.assertTrue((self.root/'freeze.private.json.selection-lineage.private.json').exists())

    def test_freeze_rejects_changed_raw_score_or_provider_close(self):
        packet = self.packet(False)
        packet['scores'][0]['score'] = 1
        with self.assertRaisesRegex(subject.legacy.OdooFinalWorkerError, 'raw_score'):
            subject.audit_selection_result(packet, self.selection)
        packet['scores'][0]['score'] = 0
        entry = packet['selection_tasks'][0]
        episode = Path(entry['episode_root'])
        row = json.loads((episode/'row.private.json').read_bytes())
        close = json.loads((episode/'provider_close_ref.private.json').read_bytes())
        close['real_close_call_returned'] = False
        ref = save(episode/'provider_close_ref.private.json', close)
        row['provider_close_ref']['sha256'] = ref['sha256']
        ref = save(episode/'row.private.json', row)
        entry['native_row']['sha256'] = ref['sha256']
        with self.assertRaisesRegex(subject.legacy.OdooFinalWorkerError, 'lifecycle_unproved'):
            subject.audit_selection_result(packet, self.selection)

    def test_freeze_rejects_cross_epoch_and_hidden_tuning(self):
        baseline, selected = self.packet(True), self.packet(False)
        for key, value in [('trial_plan_sha256', '0'*64), ('hidden_final_outcomes_used', True),
                           ('formal_large_study_credit', 1), ('checkpoint_sha256', '0'*64)]:
            changed = copy.deepcopy(selected)
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(subject.legacy.OdooFinalWorkerError): self.freeze(baseline, changed)

    def test_no_regression_is_computed_from_raw_selection_scores(self):
        baseline, selected = self.packet(True), self.packet(False)
        entry = selected['selection_tasks'][1]
        episode = Path(entry['episode_root'])
        row = json.loads((episode/'row.private.json').read_bytes())
        row['score'] = 0
        ref = save(episode/'row.private.json', row)
        entry['native_row']['sha256'] = ref['sha256']
        selected['scores'][1]['score'] = 0
        with self.assertRaisesRegex(subject.legacy.OdooFinalWorkerError, 'no_regression'):
            self.freeze(baseline, selected)
        self.assertFalse((self.root/'freeze.private.json').exists())

    def test_exact_partition_bridge_rejects_hundred_before_opening_any_body(self):
        worker = self.root/'selection'
        (worker/'private').mkdir(parents=True, mode=0o700)
        save(worker/'private/task_set_manifest.json', {'selection': self.identities*5})
        class Base:
            ROUTES = {name: '' for name in subject.evaluator.FAMILIES}
            def __init__(self, worker): self.worker_dir = worker
        fake_selection = SimpleNamespace(RealOdooSelectionEnvironment=Base)
        fake_factory = SimpleNamespace(PRIVATE=worker/'private')
        with patch.object(subject, 'modules', return_value=[fake_factory, None, None, None, None]):
            environment = subject.selection_environment(fake_selection, worker, self.identities, {})
            with self.assertRaisesRegex(subject.legacy.OdooFinalWorkerError, 'sealed_native_roster_changed'):
                environment.load_command_task(self.identities[0], self.root)
        self.assertFalse((worker/'private/partition_cases.json').exists())

    def test_explicit_dispatch_is_required_before_native_or_provider_work(self):
        args = dict(plan_path='', plan_sha='', native_binding_path='', native_binding_sha='', train_control_path='',
            train_control_sha='', selection_control_path='', selection_control_sha='', local_cost_authority_path='',
            local_cost_authority_sha='', worker_dir='', checkpoint_path='', output_root='', root_review_path='', root_review_sha='')
        with patch.object(subject, 'run_owned_task') as native:
            with self.assertRaisesRegex(subject.legacy.OdooFinalWorkerError, 'explicit_selection_dispatch'):
                subject.run(**args)
            native.assert_not_called()


if __name__ == '__main__': unittest.main()
