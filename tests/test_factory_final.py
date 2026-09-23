import json
import tempfile
import unittest
from pathlib import Path
from cursibench.factory_campaign import digest
from cursibench.factory_final import combine, package_hash, checkpoint_binding, verify_execution


def summary(task, score=1):
    return {'status': 'scored', 'score': score,
            'tasks': [{'task': task, 'score': score, 'error_type': None}]}


class FinalProtocolTests(unittest.TestCase):
    def test_final_aggregate_rejects_missing_duplicate_or_invalid_trials(self):
        self.assertEqual(combine([summary('a'), summary('b', 0)], ['a', 'b'])['score'], .5)
        self.assertIsNone(combine([summary('a')], ['a', 'b'])['score'])
        self.assertIsNone(combine([summary('a'), summary('a')], ['a', 'b'])['score'])
        bad=summary('b');bad.update(status='infrastructure_error', score=None)
        self.assertIsNone(combine([summary('a'),bad],['a','b'])['score'])

    def test_task_target_and_instruction_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'environment').mkdir();(p/'tests').mkdir()
            case={'instruction':'Edit the permitted task','provenance':{'source_split':'final'},'targets':[1]}
            (p/'environment/scenario.json').write_text(json.dumps({k:v for k,v in case.items() if k!='targets'}))
            (p/'tests/targets.json').write_text('[1]')
            (p/'instruction.md').write_text(case['instruction'])
            (p/'contract.json').write_text(json.dumps({'case_sha256':digest(case),'source_partition':'final'}))
            original=package_hash(p,digest(case),'final')
            (p/'tests/grader.py').write_text('changed grader')
            self.assertNotEqual(package_hash(p,digest(case),'final'),original)
            (p/'tests/targets.json').write_text('[2]')
            with self.assertRaisesRegex(ValueError,'sealed case'):package_hash(p,digest(case),'final')
            (p/'tests/targets.json').write_text('[1]');(p/'instruction.md').write_text('Other task')
            with self.assertRaisesRegex(ValueError,'instruction'):package_hash(p,digest(case),'final')

    def test_frozen_selection_required_even_for_base(self):
        with self.assertRaisesRegex(ValueError,'freeze'):
            checkpoint_binding({'final_selection':None},{'student':'student'},'base')

    def test_wrong_checkpoint_cannot_be_registered_as_selected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);plan={'binding':{'candidate':'round-1','checkpoint_sha256':digest('chosen'),'model':'student'}}
            result={'training_checkpoint':'other','training_model':'student','inference_kind':'checkpoint',
                'environment':'journal','factory_contract':True,'concurrency':3,'harbor_exit':0,'proxy_destroyed':True}
            (p/'result.json').write_text(json.dumps(result))
            with self.assertRaisesRegex(ValueError,'binding'):verify_execution(p,plan)
            result['training_checkpoint']='chosen';(p/'result.json').write_text(json.dumps(result))
            self.assertTrue(verify_execution(p,plan))
            result['error_type']='TimeoutExpired';(p/'result.json').write_text(json.dumps(result))
            self.assertFalse(verify_execution(p,plan))
