"""Real final gate/controller fixtures; no native or provider call."""
import copy
import json
import unittest
from pathlib import Path
from cursibench import full_study_final_dispatch_v1 as old
from cursibench import full_study_final_performance_v2 as new
from cursibench import full_study_runtime_v2 as runtime
from tests import test_full_study_final_dispatch_v1 as fixtures
from tests import v22_policy_runtime_fixture as v2


class Worker(fixtures.FakeTrustedWorker):
    def __init__(self,cell,*,unknown=False,broken=None,**kw):
        super().__init__(cell,**kw);self.unknown=unknown;self.broken=broken
    def run_once(self,command,out):
        value=super().run_once(command,out)
        value.update(lifecycle_wall_time_ms=900000,budget_performance=None)
        value['actor_clock']=fixtures.write(out/'clock.json',{
            'schema':'cua-full-study-final-actor-clock-v2','attempt_id':command['attempt_id'],
            'max_actions':90,'actor_seconds_limit':720,'lease_seconds_limit':1200,
            'actor_wall_time_ms':value['wall_time_ms'],'lifecycle_wall_time_ms':900000,
            'native_actions_after_deadline':0,'evaluation_outside_actor_clock':True})
        if self.unknown:
            intent=fixtures.write(out/'consumed.json',{'attempt_id':command['attempt_id']+'-sample-000',
                'same_intent_replay_authorized':False})
            result=fixtures.write(out/'model.json',{'status':'completed'})
            usage={'schema':'cua-full-study-authentic-unknown-usage-v2','attempt_id':command['attempt_id'],
                'cost_basis':'authentic_usage_unknown','cost_usd':None,'input_tokens':None,'image_tokens':None,
                'output_tokens':None,'provider_billed_tokens':None,'provider_invoice_sha256':None,
                'paid_calls':[{'attempt_id':command['attempt_id']+'-sample-000','kind':'sample','intent':intent,'result':result}]}
            value['usage']=fixtures.write(out/'unknown-usage.json',usage)
            value['cost_basis']='authentic_usage_unknown';value['cost_usd']=None
        else:
            usage=json.loads((out/'usage.json').read_bytes());usage['cost_usd']='50000';usage['cost_basis']='provider_billed';usage['provider_invoice_sha256']='a'*64
            (out/'usage.json').write_bytes(old.canonical(usage))
            value['usage']=old.reference(out,out/'usage.json');value['cost_usd']='50000';value['cost_basis']='provider_billed'
        if self.broken=='saved':(out/'state.bin').unlink()
        if self.broken=='reset':(out/'reset.json').unlink()
        if self.broken=='private_hash':(out/'state.bin').write_bytes(b'changed')
        if self.broken=='unknown_response':
            usage=json.loads((out/'unknown-usage.json').read_bytes());usage['paid_calls'][0]['result']=None
            (out/'unknown-usage.json').write_bytes(old.canonical(usage));value['usage']=old.reference(out,out/'unknown-usage.json')
        return value


class FinalControllerTests(unittest.TestCase):
    def fixture(self,**kw):
        f=fixtures.FullStudyFinalDispatchTests();f.setUp();self.addCleanup(f.tearDown)
        gate,_,_=v2.final_gate(f)
        workers={c:Worker(next(r for r in gate.plan['cells'] if r['cell_id']==c),**kw) for c in runtime.matrix.CELLS}
        # New plan hash is bound in a fresh sampler witness, never overwritten
        # in the historical fixture namespace.
        sampler=json.loads(f.sampler_path.read_bytes());sampler['matrix_plan_sha256']=gate.plan_sha256
        path=f.work/'sampler-v2.private.json';old.private_write_new(path,old.canonical(sampler))
        controller=new.FinalController(gate,workers=workers,sampler_bindings_path=path,output_dir=f.work/'final-output-v2')
        return f,gate,controller,workers

    def test_real_controller_all_slots_use_90_720_and_high_known_charge_no_longer_overruns_quote(self):
        f,gate,controller,workers=self.fixture()
        self.assertTrue(all(slot['execution']['max_actions_per_task']==90 and slot['execution']['max_wall_seconds_per_task']==720
            for cell in gate.plan['cells'] for slot in [cell['base'],*cell['researcher_plans'].values()]))
        cell=runtime.matrix.CELLS[0];task=controller._task_order(cell,'shared-base')[0]
        result=controller.run_task(cell,'shared-base',task['task_id'])
        self.assertEqual(result['score'],1)
        state=gate.budget.owner_attempts(cell+':shared-base')
        self.assertEqual(next(iter(state.values()))['actual_usd'],'50000')
        self.assertFalse(gate.budget.snapshot()['paid_dispatch_frozen'])
        self.assertEqual(workers[cell].commands[0]['max_wall_seconds'],720)
        self.assertEqual(controller.run_task(cell,'shared-base',task['task_id']),result)
        self.assertEqual(len(workers[cell].commands),1)

    def test_real_controller_unknown_authentic_cost_stays_null_and_performance_scored(self):
        f,gate,controller,_=self.fixture(unknown=True)
        cell=runtime.matrix.CELLS[0];task=controller._task_order(cell,'shared-base')[0]
        result=controller.run_task(cell,'shared-base',task['task_id'])
        self.assertEqual(result['score'],1)
        state=next(iter(gate.budget.owner_attempts(cell+':shared-base').values()))
        self.assertIsNone(state['actual_usd']);self.assertEqual(state['status'],'dispatched')
        rows=controller.journal.rows();proof=[r for r in rows if r.get('kind')=='authentic_usage_unknown_v2'][0]['data']
        self.assertEqual(proof['completed_model_response_count'],1);self.assertEqual(proof['model_completion_unknown_count'],0)
        path=controller.output_dir/result['attempts'][0]['attempt_id']/'attempt-receipt.private.json'
        self.assertIsNone(json.loads(path.read_bytes())['cost_usd'])

    def test_missing_saved_no_reset_changed_private_hash_and_unproved_unknown_never_score(self):
        for failure in ['saved','reset','private_hash','unknown_response']:
            with self.subTest(failure=failure):
                _,gate,controller,workers=self.fixture(unknown=True,broken=failure)
                cell=runtime.matrix.CELLS[0];task=controller._task_order(cell,'shared-base')[0]
                with self.assertRaises(ValueError):controller.run_task(cell,'shared-base',task['task_id'])
                self.assertFalse(any(r.get('kind')=='task_result' for r in controller.journal.rows()))
                with self.assertRaises(ValueError):controller.run_task(cell,'shared-base',task['task_id'])
                self.assertEqual(len(workers[cell].commands),1)

    def test_earlier_infrastructure_invalid_with_unknown_usage_is_not_scored_or_retried(self):
        _,gate,controller,workers=self.fixture(unknown=True,first_invalid=True)
        cell=runtime.matrix.CELLS[0];task=controller._task_order(cell,'shared-base')[0]
        result=controller.run_task(cell,'shared-base',task['task_id'])
        self.assertEqual(result['status'],'invalid_usage_unknown_no_retry')
        self.assertFalse(any(r.get('kind')=='task_result' for r in controller.journal.rows()))
        with self.assertRaises(ValueError):controller.run_task(cell,'shared-base',task['task_id'])
        self.assertEqual(len(workers[cell].commands),1)
