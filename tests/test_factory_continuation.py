"""Operational checkpoints retain training charges without starting evaluation."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import run_factory_round
from resume_factory_round import recovery_path
from cursibench.factory_campaign import CampaignRegistry


class ContinuationTests(unittest.TestCase):
    def test_stop_before_evaluation_preserves_reservation_and_never_launches_eval(self):
        with tempfile.TemporaryDirectory() as tmp:
            study = Path(tmp)
            factory = study / 'factory'
            factory.mkdir()
            (study / 'round-1').mkdir()
            (factory / 'result.json').write_text(json.dumps({'complete': True}))
            (factory / 'train_messages.jsonl').write_text('preserved input\n')
            registry = CampaignRegistry(study / 'sol6-campaign.json', {
                'selection_tasks': ['s'], 'final_tasks': ['f'], 'max_attempts': 5,
                'training_token_budget': 1000, 'promotion': 'no_regression',
                'selection_manifest_sha256': 'frozen-selection'})
            registry.set_baseline({'status': 'scored', 'score': 0.0,
                'tasks': [{'task': 's', 'score': 0, 'error_type': None}]})
            def training_only(command, work, label):
                self.assertEqual(label, 'sol6-training')
                self.assertIn('--steps', command)
                self.assertEqual(command[command.index('--steps') + 1], '32')
                training = work / 'train-sol6'
                training.mkdir()
                (training / 'training.json').write_text(json.dumps({
                    'verified_training_and_sampling': True,
                    'scheduled_tokens': 42, 'data_sha256': 'verified-data'}))
            with patch.object(run_factory_round, 'preflight', return_value={
                    'data_sha256': 'verified-data', 'scheduled_tokens': 42}), \
                    patch.object(run_factory_round, 'child', side_effect=training_only) as child, \
                    patch.object(run_factory_round, 'summarize') as summarize, \
                    contextlib.redirect_stdout(io.StringIO()):
                result = run_factory_round.finish_submission(study, 'sol6', 1, factory, stop_before_evaluation=True)
            self.assertEqual(child.call_count, 1)
            summarize.assert_not_called()
            self.assertEqual(result['status'], 'awaiting_evaluation')
            state = registry.snapshot()
            self.assertEqual(state['reservations']['round-1']['token_bound'], 42)
            self.assertEqual(state['attempts'], [])
            self.assertEqual(state['selected'], 'base')
            self.assertFalse((study / 'round-1/eval-sol6').exists())
            with self.assertRaisesRegex(ValueError, 'pending'):
                registry.freeze_selection('not ready')

    def test_recovery_ids_preserve_first_directory_and_reject_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = recovery_path(tmp, 'sol6', 2)
            first.mkdir(parents=True)
            (first / 'evidence').write_text('immutable first recovery')
            second = recovery_path(tmp, 'sol6', 2, 'attempt-2')
            second.mkdir()
            self.assertNotEqual(first, second)
            self.assertEqual((first / 'evidence').read_text(), 'immutable first recovery')
            with self.assertRaises(ValueError):
                recovery_path(tmp, 'sol6', 2, '../overwrite')


if __name__ == '__main__':
    unittest.main()
