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
            self.assertTrue(r.register('one','h1','one.json',100,summary([1,0,0]),historical_import=True)['promoted'])
            self.assertFalse(r.register('two','h2','two.json',100,summary([1,0,0]),historical_import=True)['promoted'])
            self.assertFalse(r.register('three','h3','three.json',100,summary([0,1,1]),historical_import=True)['promoted'])
            invalid=summary([1,1,1]);invalid['status']='infrastructure_error'
            self.assertFalse(r.register('four','h4','four.json',100,invalid,historical_import=True)['promoted'])
            self.assertEqual(r.freeze_selection('budget end')['candidate'],'one')
    def test_final_cannot_change_selection_or_precede_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.registry(tmp);r.set_baseline(summary([0,0,0]));r.register('one','h1','one.json',100,summary([1,0,0]),historical_import=True)
            with self.assertRaises(ValueError):r.record_final('early',summary([1,1,1],('x','y','z')),time.time())
            chosen=r.freeze_selection('search complete')
            with self.assertRaises(ValueError):r.record_final('earlier',summary([1,1,1],('x','y','z')),chosen['frozen_at']-1)
            r.record_final('valid',summary([0,0,0],('x','y','z')),time.time())
            self.assertEqual(r.snapshot()['selected'],'one')
            with self.assertRaises(ValueError):r.register('two','h2','two.json',100,summary([1,1,1]))
    def test_budget_dataset_and_protocol_guards(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.registry(tmp);r.set_baseline(summary([0,0,0]));r.register('one','same','one.json',900,summary([0,0,0]),historical_import=True)
            with self.assertRaises(ValueError):r.register('two','same','two.json',1,summary([1,1,1]))
            with self.assertRaises(ValueError):r.register('two','new','two.json',101,summary([1,1,1]))
            with self.assertRaises(ValueError):CampaignRegistry(r.path,{'selection_tasks':['a'],'final_tasks':['x']})

    def test_rejected_submission_is_an_unscored_attempt_without_training(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.registry(tmp);r.set_baseline(summary([0,0,0]))
            r.record_submission_rejection('one','h1',{'accepted':False,'max_sequence':17000})
            state=r.snapshot()
            self.assertEqual(state['used_training_tokens'],0)
            self.assertIsNone(state['attempts'][0]['evaluation']['score'])
            self.assertEqual(state['attempts'][0]['evaluation']['status'],'submission_rejected')
            with self.assertRaisesRegex(ValueError,'duplicate'):r.record_submission_rejection('one','h1',{'accepted':False})
            self.assertEqual(r.freeze_selection('search complete')['candidate'],'base')

    def test_reservation_prevents_parallel_overspend_and_survives_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.registry(tmp);r.set_baseline(summary([0,0,0]))
            with self.assertRaisesRegex(ValueError,'reservation required'):
                r.register('unreserved','x','x.json',100,summary([1,0,0]))
            r.reserve_training('one','h1',600)
            restarted=CampaignRegistry(r.path);restarted.reserve_training('one','h1',600)
            with self.assertRaisesRegex(ValueError,'before execution'):restarted.reserve_training('two','h2',401)
            with self.assertRaisesRegex(ValueError,'pending'):r.freeze_selection('too early')
            r.register('one','h1','one.json',400,summary([1,0,0]))
            r.reserve_training('two','h2',600)
            r.record_training_failure('two','controller interrupted')
            self.assertEqual(r.snapshot()['used_training_tokens'],1000)
            self.assertEqual(r.freeze_selection('budget end')['candidate'],'one')
