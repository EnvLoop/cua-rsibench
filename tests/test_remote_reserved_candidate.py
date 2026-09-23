"""Initial remote evaluations must be bound to an untouched trained reservation."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import run_cloud_chain_remote as launcher


class ReservedCandidateTests(unittest.TestCase):
    def fixture(self, temporary):
        study = Path(temporary)
        work = study / 'round-2'
        training = work / 'train-sol6/training.json'
        training.parent.mkdir(parents=True)
        factory = study / 'factories/factory-sol6-02'
        factory.mkdir(parents=True)
        data = b'{"record_id":"verified-example"}\n'
        (factory / 'train_messages.jsonl').write_bytes(data)
        (factory / 'result.json').write_text(json.dumps({'complete': True,
            'submission': {'validated': True, 'records': 1}}))
        selected = {'verified_training_and_sampling': True, 'data_sha256': launcher.sha(data),
            'scheduled_tokens': 42, 'record_count': 1, 'covered_records': 1,
            'training_profile': 'factory-v1', 'steps_requested': 32, 'batch_size': 2,
            'events': [{'step': step} for step in range(1, 33)]}
        training.write_text(json.dumps(selected))
        preflight = {'accepted': True, 'data_sha256': launcher.sha(data), 'scheduled_tokens': 42, 'records': 1}
        (work / 'sol6-preflight.json').write_text(json.dumps(preflight))
        state = {'attempts': [{'attempt_id': 'round-1'}], 'final_selection': None,
            'baseline': {'status': 'scored'},
            'protocol': {'max_attempts': 5, 'factory_directory': 'factories',
                         'selection_manifest_sha256': 'selection-frozen'},
            'reservations': {'round-2': {'dataset_hash': launcher.sha(data), 'token_bound': 42, 'reserved_at': 100}}}
        pending = {'status': 'awaiting_evaluation', 'researcher': 'sol6', 'attempt': 'round-2',
            'evaluation_started': False, 'training_reservation_retained': True,
            'training_manifest': 'round-2/train-sol6/training.json',
            'training_manifest_sha256': launcher.sha(training.read_bytes()),
            'data_sha256': launcher.sha(data), 'scheduled_tokens': 42,
            'selection_manifest_sha256': 'selection-frozen', 'created_at': 200}
        (work / 'sol6-evaluation-pending.json').write_text(json.dumps(pending))
        return study, state, training, selected, pending

    def bind(self, fixture):
        study, state, training, selected, _ = fixture
        return launcher.reserved_candidate_binding(study, state, 'sol6', training, selected, 'round-2')

    def test_initial_evaluation_needs_no_prior_execution_wrapper(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self.fixture(tmp)
            before = copy.deepcopy(fixture[1])
            record, provenance = self.bind(fixture)
            self.assertEqual(record['attempt_id'], 'round-2')
            self.assertEqual(record['training_tokens'], 42)
            self.assertTrue(provenance['local_evaluation_absent_at_preparation'])
            self.assertIn('pending_evaluation_receipt_sha256', provenance)
            self.assertEqual(fixture[1], before)
            self.assertFalse((Path(tmp) / 'round-2/eval-sol6').exists())

    def test_missing_pending_receipt_or_existing_evaluation_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self.fixture(tmp)
            receipt = Path(tmp) / 'round-2/sol6-evaluation-pending.json'
            original = receipt.read_bytes()
            receipt.unlink()
            with self.assertRaisesRegex(ValueError, 'receipt required'):
                self.bind(fixture)
            receipt.write_bytes(original)
            (Path(tmp) / 'round-2/eval-sol6').mkdir()
            with self.assertRaisesRegex(ValueError, 'recovery path'):
                self.bind(fixture)

    def test_mutated_dataset_and_nonexact_token_reservation_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self.fixture(tmp)
            path = Path(tmp) / 'factories/factory-sol6-02/train_messages.jsonl'
            original = path.read_bytes()
            path.write_bytes(original + b'\n')
            with self.assertRaisesRegex(ValueError, 'provenance mismatch'):
                self.bind(fixture)
            path.write_bytes(original)
            fixture[1]['reservations']['round-2']['token_bound'] = 43
            with self.assertRaisesRegex(ValueError, 'provenance mismatch'):
                self.bind(fixture)

    def test_pending_receipt_cannot_switch_checkpoint_or_selection_suite(self):
        for field, value in [('training_manifest_sha256', 'different-weights'),
                             ('selection_manifest_sha256', 'different-tasks'),
                             ('researcher', 'luna6'), ('evaluation_started', True)]:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                fixture = self.fixture(tmp)
                fixture[4][field] = value
                (Path(tmp) / 'round-2/sol6-evaluation-pending.json').write_text(json.dumps(fixture[4]))
                with self.assertRaisesRegex(ValueError, 'receipt differs'):
                    self.bind(fixture)

    def test_duplicate_updates_and_closed_search_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self.fixture(tmp)
            fixture[3]['events'][-1]['step'] = 31
            with self.assertRaisesRegex(ValueError, '32 verified updates'):
                self.bind(fixture)
            fixture[1]['final_selection'] = {'candidate': 'base'}
            with self.assertRaisesRegex(ValueError, 'next open'):
                self.bind(fixture)


if __name__ == '__main__':
    unittest.main()
