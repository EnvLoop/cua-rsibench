"""Offline continuation admission and provenance tests; no native or model calls."""
import copy
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from magento_catalog_factory import native_selection_reference_continuation_v1 as m


def save(path, value):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_bytes(m.original.workers.final.canonical(value)); path.chmod(0o600)
    return m._sha(path)


def identities():
    return [{'task_id': f'fixture-{ordinal:02d}', 'package_sha256': f'{ordinal+1:064x}'}
            for ordinal in range(20)]


def fixture(root):
    root = root.resolve(); old = root/'original.private'; output = root/'continuation.private'
    native = m.original.workers.public_binding(); loaded = []
    case = {'target_variants': [{'target_price': 1}], 'untouched_comparators': [{'price': 2}]}
    def load(identity, split):
        loaded.append((identity, split)); return case
    inputs = SimpleNamespace(binding=native, roster={'splits': {'selection': identities()}},
        load=load, runtime=lambda: 'offline-runtime', username=lambda: 'offline-admin')
    binding = {'binding_sha256': 'a'*64}
    owner = {'schema': 'magento-continuation-owned-host-run-v1', 'pid': os.getpid(),
        'started_monotonic': 1, 'continuation_binding_sha256': binding['binding_sha256'],
        'automatic_restart_authorized': False, 'root_review_ref': {}}
    save(output/'continuation-run-owner.private.json', owner)
    tasks = []
    for ordinal, identity in enumerate(identities()):
        base = old if ordinal < 11 else output/'fresh-controls.private'
        trio = {}
        for mode, score in m.MODES:
            folder = base/f'attempt-{ordinal:03d}'/mode
            row = {**identity, 'score': score, 'native_source_binding_sha256': native['binding_sha256'],
                'samples': [{'paid_attempt_id': None, 'status': 'control_action',
                             'raw_result': {'model_call_performed': False}}],
                'actor_wall_time_ms': 1, 'lifecycle_wall_time_ms': 2}
            digest = save(folder/'native-row.private.json', row)
            save(folder/'guard/held-lease.private.json', {'owned_operation':
                 {'pid': owner['pid'], 'started_monotonic': 2}})
            trio[mode] = {'score': score, 'episode_root': str(folder), 'native_row_sha256': digest}
        tasks.append({**identity, 'ordinal': ordinal,
            'origin': 'original_completed_whole_trio' if ordinal < 11 else 'fresh_remaining_whole_trio',
            'trio': trio})
    ignored = old/'attempt-011/baseline/native-row.private.json'
    save(ignored, {**identities()[11], 'score': 0})
    contract = {'source_binding': binding, 'original_output_root': str(old), 'output_root': str(output),
        'selection_tasks': identities(), 'reused_whole_trios': tasks[:11],
        'fresh_original_ordinals': list(range(11,20)), 'interruption_audit_ref': {'sha256': 'b'*64},
        'discarded_partial_baseline_ref': m._ref(ignored)}
    manifest = {'schema': 'magento-selection20-continuation-controls-v1',
        'continuation_binding_sha256': binding['binding_sha256'], 'selection_identities': identities(),
        'task_count': 20, 'mode_count': 60, 'tasks': tasks, 'model_calls': 0, 'tinker_calls': 0,
        'old_partial_mode_credit': 0, 'formal_registration_performed': False,
        'fresh_run_owner_ref': m._ref(output/'continuation-run-owner.private.json')}
    return inputs, contract, manifest, loaded


def audited(folder, row, **kwargs):
    if kwargs['provider_close_required'] is not False: raise AssertionError('reference-only required')
    return {'score': row['score'], 'actions': ['offline-action'], 'frames': ['offline-frame']}


class ContinuationTests(unittest.TestCase):
    def test_full_aggregate_reaudits_sixty_modes_without_new_load_or_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); inputs, contract, manifest, loaded = fixture(root)
            path = root/'manifest.private.json'; digest = save(path, manifest)
            with patch.object(m.original.audit, 'audit_episode', side_effect=audited) as audit:
                result = m.aggregate_saved_audit(inputs, contract, path, digest)
            self.assertEqual(audit.call_count, 60); self.assertEqual(result['mode_count'], 60)
            self.assertEqual(result['actions'], 60); self.assertEqual(result['frames'], 60)
            self.assertEqual(result['actor_wall_time_ms'], 60); self.assertEqual(loaded, [])

    def test_manifest_refuses_partial_missing_reordered_substituted_reindexed_or_paid_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); inputs, contract, manifest, _ = fixture(root)
            variants = []
            bad = copy.deepcopy(manifest); bad['tasks'][11]['trio'].pop('positive'); variants.append(bad)
            bad = copy.deepcopy(manifest); bad['tasks'][11]['ordinal'] = 0; variants.append(bad)
            bad = copy.deepcopy(manifest); bad['tasks'].reverse(); variants.append(bad)
            bad = copy.deepcopy(manifest); bad['tasks'][11]['package_sha256'] = 'f'*64; variants.append(bad)
            bad = copy.deepcopy(manifest); bad['tasks'][11]['trio']['baseline']['episode_root'] = str(root/'original.private/attempt-011/baseline'); variants.append(bad)
            bad = copy.deepcopy(manifest); bad['old_partial_mode_credit'] = 1; variants.append(bad)
            bad = copy.deepcopy(manifest); bad['model_calls'] = False; variants.append(bad)
            bad = copy.deepcopy(manifest); bad['tasks'][0]['origin'] = 'fresh_remaining_whole_trio'; variants.append(bad)
            bad = copy.deepcopy(manifest); bad['tasks'][11]['origin'] = 'original_completed_whole_trio'; variants.append(bad)
            with patch.object(m.original.audit, 'audit_episode', side_effect=audited):
                for bad in variants:
                    path = root/'manifest.private.json'; digest = save(path, bad)
                    with self.assertRaises(Exception): m.aggregate_saved_audit(inputs, contract, path, digest)

    def test_reference_samples_refuse_completed_model_calls_paid_ids_and_boolean_scores(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); inputs, contract, manifest, _ = fixture(root)
            task = manifest['tasks'][11]; folder = Path(task['trio']['positive']['episode_root'])
            original = json.loads((folder/'native-row.private.json').read_text())
            variants = []
            bad = copy.deepcopy(original); bad['samples'][0]['status'] = 'completed'; variants.append(bad)
            bad = copy.deepcopy(original); bad['samples'][0]['paid_attempt_id'] = 'paid'; variants.append(bad)
            bad = copy.deepcopy(original); bad['samples'][0]['raw_result']['model_call_performed'] = True; variants.append(bad)
            bad = copy.deepcopy(original); bad['score'] = True; variants.append(bad)
            bad = copy.deepcopy(original); bad['native_source_binding_sha256'] = 'f'*64; variants.append(bad)
            with patch.object(m.original.audit, 'audit_episode', side_effect=audited):
                for bad in variants:
                    task['trio']['positive']['native_row_sha256'] = save(folder/'native-row.private.json', bad)
                    path = root/'manifest.private.json'; digest = save(path, manifest)
                    with self.assertRaises(Exception): m.aggregate_saved_audit(inputs, contract, path, digest)

    def test_copied_old_native_episode_cannot_be_promoted_as_fresh(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); inputs, contract, manifest, _ = fixture(root)
            folder = Path(manifest['tasks'][11]['trio']['baseline']['episode_root'])
            save(folder/'guard/held-lease.private.json', {'owned_operation':
                 {'pid': os.getpid(), 'started_monotonic': 0.5}})
            path = root/'manifest.private.json'; digest = save(path, manifest)
            with patch.object(m.original.audit, 'audit_episode', side_effect=audited):
                with self.assertRaises(Exception): m.aggregate_saved_audit(inputs, contract, path, digest)

    def test_original_prefix_digest_or_independent_reset_failure_stops_aggregate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); inputs, contract, manifest, _ = fixture(root)
            path = root/'manifest.private.json'; digest = save(path, manifest)
            with patch.object(m.original.audit, 'audit_episode', side_effect=ValueError('reset failed')):
                with self.assertRaises(Exception): m.aggregate_saved_audit(inputs, contract, path, digest)
            row = Path(manifest['tasks'][0]['trio']['baseline']['episode_root'])/'native-row.private.json'
            save(row, {'changed': True})
            with patch.object(m.original.audit, 'audit_episode', side_effect=audited):
                with self.assertRaises(Exception): m.aggregate_saved_audit(inputs, contract, path, digest)

    def test_fresh_run_dispatches_exact_twenty_seven_calls_original_ordinals_and_never_reuses_partial(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); inputs, contract, _, loaded = fixture(root)
            output = root/'new-continuation.private'; contract['output_root'] = str(output)
            review = root/'review.private.json'; review_sha = save(review, contract); seen = []
            async def task(**args):
                ordinal = 11+len(seen)//3; mode = m.MODES[len(seen)%3][0]
                self.assertEqual(args['task'], identities()[ordinal]); self.assertEqual(args['sampler'].mode, mode)
                self.assertEqual(args['paid_attempt_id'], None)
                self.assertIn(f'attempt-{ordinal:03d}', str(args['output']))
                self.assertEqual(args['attempt_id'], f'continuation-control-{ordinal:03d}-{mode}')
                owner = json.loads((output/'continuation-run-owner.private.json').read_text())
                save(args['output']/'guard/held-lease.private.json', {'owned_operation':
                     {'pid': owner['pid'], 'started_monotonic': owner['started_monotonic']+1}})
                seen.append((ordinal, mode))
                return {**args['task'], 'score': int(mode == 'positive'),
                    'native_source_binding_sha256': inputs.binding['binding_sha256'],
                    'samples': [{'paid_attempt_id': None, 'status': 'control_action',
                                 'raw_result': {'model_call_performed': False}}],
                    'actor_wall_time_ms': 1, 'lifecycle_wall_time_ms': 2}
            with patch.object(m, '_prepare', return_value=(inputs, contract, {})), \
                 patch.object(m, 'source_binding', return_value=contract['source_binding']), \
                 patch.object(m, '_authority_root', return_value=root/'authority.private'), \
                 patch.object(m.original.facade._impl, 'run_task', AsyncMock(side_effect=task)) as runner, \
                 patch.object(m.original.audit, 'audit_episode', side_effect=audited):
                result = m.run(root_review_path=review, root_review_sha256=review_sha, execute=True, output=output)
                self.assertEqual(result['saved_audit']['mode_count'], 60)
                self.assertEqual(runner.await_count, 27)
                self.assertEqual(loaded, [(identity, 'selection') for identity in identities()[11:]])
                self.assertEqual(seen, [(ordinal, mode) for ordinal in range(11,20) for mode, _ in m.MODES])
                self.assertEqual(m.saved_audit(root_review_path=review, root_review_sha256=review_sha, output=output), result)
                changed = copy.deepcopy(result); changed['failure_costs_preserved_separately'] = False
                save(output/'continuation-result.private.json', changed)
                with self.assertRaises(Exception): m.saved_audit(root_review_path=review, root_review_sha256=review_sha, output=output)
                changed = copy.deepcopy(result); changed['schema'] = 'different'
                save(output/'continuation-result.private.json', changed)
                with self.assertRaises(Exception): m.saved_audit(root_review_path=review, root_review_sha256=review_sha, output=output)
                save(output/'continuation-result.private.json', result)
                with self.assertRaises(Exception): m.run(root_review_path=review, root_review_sha256=review_sha, execute=True, output=output)
                self.assertEqual(runner.await_count, 27)

    def test_failure_consumes_fixed_authority_and_no_next_mode_or_replay_after_output_delete(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); inputs, contract, _, loaded = fixture(root)
            output = root/'failed-new.private'; contract['output_root'] = str(output)
            review = root/'review.private.json'; digest = save(review, contract)
            with patch.object(m, '_prepare', return_value=(inputs, contract, {})), \
                 patch.object(m, 'source_binding', return_value=contract['source_binding']), \
                 patch.object(m, '_authority_root', return_value=root/'authority.private'), \
                 patch.object(m.original.facade._impl, 'run_task', AsyncMock(side_effect=RuntimeError('native failed'))) as runner:
                with self.assertRaises(Exception): m.run(root_review_path=review, root_review_sha256=digest, execute=True, output=output)
                self.assertEqual(runner.await_count, 1); self.assertTrue((output/'failure.private.json').exists())
                import shutil
                shutil.rmtree(output)
                with self.assertRaises(Exception): m.run(root_review_path=review, root_review_sha256=digest, execute=True, output=output)
                self.assertEqual(runner.await_count, 1)
                self.assertEqual(loaded, [(identities()[11], 'selection')])

    def test_changed_review_or_prerequisites_refuse_before_new_task_load(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); inputs, contract, _, loaded = fixture(root)
            output = root/'fresh.private'; contract['output_root'] = str(output)
            review = root/'review.private.json'; digest = save(review, {'changed': True})
            with patch.object(m, '_prepare', return_value=(inputs, contract, {})):
                with self.assertRaises(Exception): m.run(root_review_path=review, root_review_sha256=digest, execute=True, output=output)
            digest = save(review, contract)
            with patch.object(m, '_prepare', side_effect=[(inputs, contract, {}), (inputs, {'changed': True}, {})]), \
                 patch.object(m, '_authority_root', return_value=root/'authority.private'):
                with self.assertRaises(Exception): m.run(root_review_path=review, root_review_sha256=digest, execute=True, output=output)
            self.assertEqual(loaded, [])

    def test_symlink_output_ancestry_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); (root/'link').symlink_to(root, target_is_directory=True)
            with self.assertRaises(Exception): m._safe_output(root/'link/output.private')

    def test_original_partial_and_failure_artifacts_are_rehashed_not_trusted_from_flags(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); source = root/'original.private'
            artifact = source/'selection-controls.private/partial.private.json'; save(artifact, {'partial': True})
            relative = str(artifact.relative_to(source)); size = artifact.stat().st_size
            manifest = {'source_root': str(source), 'file_count': 1, 'total_bytes': size, 'symlinks': [],
                'rows': [{'path': relative, 'bytes': size, 'sha256': m._sha(artifact)}]}
            path = root/'preservation.private.json'; save(path, manifest)
            historical = {'preserved_files': 1, 'preserved_bytes': size, 'references':
                {'original-artifact-preservation-manifest.private.json': m._ref(path)}}
            self.assertEqual(m._preserved_original(source/'selection-controls.private', historical), m._ref(path))
            save(artifact, {'partial': False})
            with self.assertRaises(Exception): m._preserved_original(source/'selection-controls.private', historical)

    def test_source_drift_between_modes_stops_before_second_native_call(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); inputs, contract, _, _ = fixture(root)
            output = root/'source-drift.private'; contract['output_root'] = str(output)
            review = root/'review.private.json'; digest = save(review, contract)
            async def baseline(**args):
                return {**args['task'], 'score': 0, 'native_source_binding_sha256': inputs.binding['binding_sha256'],
                    'samples': [{'paid_attempt_id': None, 'status': 'control_action',
                                 'raw_result': {'model_call_performed': False}}]}
            with patch.object(m, '_prepare', return_value=(inputs, contract, {})), \
                 patch.object(m, 'source_binding', side_effect=[contract['source_binding'], {'changed': True}]), \
                 patch.object(m, '_authority_root', return_value=root/'authority.private'), \
                 patch.object(m.original.facade._impl, 'run_task', AsyncMock(side_effect=baseline)) as runner, \
                 patch.object(m.original.audit, 'audit_episode', side_effect=audited):
                with self.assertRaises(Exception): m.run(root_review_path=review, root_review_sha256=digest, execute=True, output=output)
                self.assertEqual(runner.await_count, 1)
                self.assertTrue((output/'failure.private.json').exists())

    def test_execution_is_explicit_and_frozen_native_binding_is_unchanged(self):
        with self.assertRaises(Exception): m.run(execute=False)
        self.assertEqual(m.original.workers.public_binding()['binding_sha256'],
                         '3796a86891553f2dae6092a9a8e548356467d6a312352a1768f5d7de9597b23a')
        self.assertIs(m.original.facade._impl.run_task, m.original.workers.run_task)
        self.assertEqual(m.source_binding()['original_reference_binding'], m.original.source_binding())


if __name__ == '__main__': unittest.main()
