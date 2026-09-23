import json,tempfile,unittest
from pathlib import Path
from cursibench.factory_results import summarize,selection_feedback

class FactoryResultTests(unittest.TestCase):
    def write(self,tmp,errors=False,duplicate=False):
        p=Path(tmp)/'harbor/checkpoint-browser';p.mkdir(parents=True)
        (p/'result.json').write_text(json.dumps({'finished_at':'finished'}))
        for i,task in enumerate(('selection-direct-01','selection-rank-01','selection-allocation-01')):
            d=p/f'trial-{i}';d.mkdir()
            (d/'result.json').write_text(json.dumps({'task_name':'selection-direct-01' if duplicate else task,
                'verifier_result':{'rewards':{'reward':1 if i==0 else 0}},
                'exception_info':{'exception_type':'TimeoutException'} if errors and i==2 else None}))
        return ('selection-direct-01','selection-rank-01','selection-allocation-01')
    def test_complete_comparison_and_no_false_zero_for_infra(self):
        with tempfile.TemporaryDirectory() as tmp:
            names=self.write(tmp);r=summarize(tmp,names);self.assertEqual(r['score'],1/3)
            self.assertEqual(selection_feedback(r)['by_task_family'][0]['family'],'direct')
        with tempfile.TemporaryDirectory() as tmp:
            names=self.write(tmp,errors=True);r=summarize(tmp,names);self.assertIsNone(r['score']);self.assertEqual(r['status'],'infrastructure_error')
    def test_duplicate_or_missing_task_cannot_create_an_average(self):
        with tempfile.TemporaryDirectory() as tmp:
            names=self.write(tmp,duplicate=True);self.assertIsNone(summarize(tmp,names)['score'])
