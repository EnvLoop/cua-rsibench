import json,tempfile,unittest
from pathlib import Path
from cursibench.cloud_launch import model_input

class LaunchTests(unittest.TestCase):
    def test_base_needs_no_private_training_history(self):
        result=model_input(base=True)
        self.assertEqual(result['checkpoint'],'Qwen/Qwen3.5-4B')
        self.assertEqual(result['inference_kind'],'base')
        self.assertNotIn('verified_training_and_sampling',result)
    def test_checkpoint_requires_real_training_evidence(self):
        with self.assertRaises(ValueError):model_input()
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'training.json';p.write_text(json.dumps({'model':'base','checkpoint':'saved'}))
            with self.assertRaises(ValueError):model_input(p)
            p.write_text(json.dumps({'model':'base','checkpoint':'saved','verified_training_and_sampling':True}))
            self.assertEqual(model_input(p)['checkpoint'],'saved')
            with self.assertRaises(ValueError):model_input(p,model='different')
