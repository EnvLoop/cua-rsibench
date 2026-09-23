import tempfile,time,unittest
from pathlib import Path
from cursibench.factory_campaign import CampaignRegistry


def summary(values,names=('a','b','c')):
    return {'status':'scored','score':sum(values)/len(values),'tasks':[{'task':n,'score':s,'error_type':None} for n,s in zip(names,values)]}

class CampaignRegistryTests(unittest.TestCase):
    def registry(self,tmp):return CampaignRegistry(Path(tmp)/'state.json',{'selection_tasks':['a','b','c'],'final_tasks':['x','y','z'],'max_attempts':5,'training_token_budget':1000,'promotion':'no_regression'})
    def test_best_is_preserved_across_ties_regression_and_invalid_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.registry(tmp);r.set_baseline(summary([0,0,0]))
            self.assertTrue(r.register('one','h1','one.json',100,summary([1,0,0]))['promoted'])
            self.assertFalse(r.register('two','h2','two.json',100,summary([1,0,0]))['promoted'])
            self.assertFalse(r.register('three','h3','three.json',100,summary([0,1,1]))['promoted'])
            invalid=summary([1,1,1]);invalid['status']='infrastructure_error'
            self.assertFalse(r.register('four','h4','four.json',100,invalid)['promoted'])
            self.assertEqual(r.freeze_selection('budget end')['candidate'],'one')
    def test_final_cannot_change_selection_or_precede_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.registry(tmp);r.set_baseline(summary([0,0,0]));r.register('one','h1','one.json',100,summary([1,0,0]))
            with self.assertRaises(ValueError):r.record_final('early',summary([1,1,1],('x','y','z')),time.time())
            chosen=r.freeze_selection('search complete')
            with self.assertRaises(ValueError):r.record_final('earlier',summary([1,1,1],('x','y','z')),chosen['frozen_at']-1)
            r.record_final('valid',summary([0,0,0],('x','y','z')),time.time())
            self.assertEqual(r.snapshot()['selected'],'one')
            with self.assertRaises(ValueError):r.register('two','h2','two.json',100,summary([1,1,1]))
    def test_budget_dataset_and_protocol_guards(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.registry(tmp);r.set_baseline(summary([0,0,0]));r.register('one','same','one.json',900,summary([0,0,0]))
            with self.assertRaises(ValueError):r.register('two','same','two.json',1,summary([1,1,1]))
            with self.assertRaises(ValueError):r.register('two','new','two.json',101,summary([1,1,1]))
            with self.assertRaises(ValueError):CampaignRegistry(r.path,{'selection_tasks':['a'],'final_tasks':['x']})
