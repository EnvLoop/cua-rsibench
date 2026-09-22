import copy
import unittest
from dataclasses import replace
from cursibench.tasks import make_tasks
from cursibench.verifier import verify
from cursibench.benchmark import run_benchmark
from cursibench.protocol import BenchmarkSpec, validate_spec

class IntegrityTests(unittest.TestCase):
    def test_extra_fields_fail(self):
        task=make_tasks()[0]
        state=copy.deepcopy(task.expected)
        state['injected']='unexpected'
        self.assertEqual(verify(task,state)[0],0)
    def test_duplicate_object_fails(self):
        task=make_tasks()[0]
        state=copy.deepcopy(task.expected)
        state['slides'][1]=copy.deepcopy(state['slides'][0])
        self.assertEqual(verify(task,state)[0],0)
    def test_wrong_object_fails_even_when_target_correct(self):
        task=make_tasks()[0]
        state=copy.deepcopy(task.expected)
        state['slides'][1]['note']='tampered'
        self.assertEqual(verify(task,state)[0],0)
    def test_all_rounds_and_ties_rejected(self):
        result=run_benchmark(5)
        self.assertEqual(len(result['rounds']),5)
        self.assertEqual([r['accepted'] for r in result['rounds']],[True,False,False,False,False])
        self.assertFalse(result['official_submission_eligible'])
    def test_test_visibility_rejected(self):
        with self.assertRaises(ValueError):
            validate_spec(replace(BenchmarkSpec(),test_visible_to_improver=True))
    def test_invalid_and_reordered_states_fail(self):
        task=make_tasks()[0]
        for state in (None, {}, {'slides':list(reversed(task.expected['slides'])), 'metadata':task.expected['metadata']}):
            self.assertEqual(verify(task,state)[0],0)
