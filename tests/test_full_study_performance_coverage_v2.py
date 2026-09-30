import copy
import unittest
from cursibench import full_study_selection_paid_coverage_v1 as old
from cursibench import full_study_performance_coverage_v2 as new
from cursibench import full_study_policy_amendment_v2 as policy
from tests.test_full_study_policy_unlimited_budget_v2 import qualified_plan,amendment


class PerformanceCoverageTests(unittest.TestCase):
    def fixture(self):
        plan=qualified_plan();amend=amendment(plan);attempt='matched-v2';checkpoint='b'*64
        tasks=[{'task_id':'task'+str(i),'package_sha256':'c'*64} for i in range(20)]
        calls=[]
        for i,task in enumerate(tasks):
            request={'selection_attempt':attempt,'cell_id':'desktop-native','checkpoint_path_sha256':checkpoint,**task}
            calls.extend([{'attempt_id':attempt+'-model-'+str(i),'category':'tinker','request':request,
                'result_present':True,'result_status':'completed'},
                {'attempt_id':attempt+'-environment-'+str(i),'category':'e2b','request':request,
                'result_present':True,'result_status':'active'}])
        uncertain_id=attempt+'-uncertain-budget'
        calls.append({'attempt_id':uncertain_id,'category':'tinker','request':calls[0]['request'],
                      'result_present':False,'result_status':None})
        receipt={'schema':'cua-verified-budget-performance-with-unknown-billing-v22',
            'amendment_sha256':policy.validate(amend,plan),'sample_paid_attempt_id':uncertain_id,
            **tasks[0],'owner_slot':'shared-base','checkpoint_sha256':checkpoint,
            'performance_coverage_eligible':True,'provider_close_acknowledged':True,
            'performance':{'status':'independently_saved_scored_and_reset','score':0},
            'inference':{'unknown_response_is_completed':False,'request_replayed':False},
            'billing':{'actual_usd':None},'formal_registration_performed':False,
            'evidence_sha256':{name:'d'*64 for name in ['saved-state.private.json','verifier.private.json','reset.private.json',
                'actor-clock.private.json','actor-budget-stop.private.json','task.private.json']}}
        return dict(plan=plan,amendment=amend,cell_id='desktop-native',owner_slot='shared-base',attempt_id=attempt,checkpoint_sha256=checkpoint,
            selection_tasks=tasks,paid_calls=calls,related_paid_attempt_ids={v['attempt_id'] for v in calls},
            budget_performance_receipts=[receipt])

    def test_actual_old_gate_rejects_uncertain_final_sample_new_performance_gate_keeps_unknown(self):
        args=self.fixture()
        with self.assertRaises(ValueError):
            old.validate(**{k:args[k] for k in ['cell_id','attempt_id','checkpoint_sha256','selection_tasks','paid_calls','related_paid_attempt_ids']},
                selection_identities_sha256=policy.sha(policy.canonical(args['selection_tasks'])))
        value=new.validate(**args)
        self.assertTrue(value['performance_coverage_complete']);self.assertFalse(value['inference_completion_complete'])
        self.assertEqual(value['completed_model_response_count'],20)
        self.assertEqual(value['verified_budget_ended_unknown_response_count'],1)
        self.assertIsNone(value['actual_cost_usd']);self.assertFalse(value['formal_registration_performed'])

    def test_no_deadline_evidence_no_close_no_reset_or_earlier_provider_fault_is_rejected(self):
        for field in ['budget_receipt','close_ack','reset','earlier_provider_fault']:
            with self.subTest(field=field):
                args=self.fixture();receipt=args['budget_performance_receipts'][0]
                if field=='budget_receipt':args['budget_performance_receipts']=[]
                if field=='close_ack':receipt['provider_close_acknowledged']=False
                if field=='reset':del receipt['evidence_sha256']['reset.private.json']
                if field=='earlier_provider_fault':receipt['performance']['status']='infrastructure_invalid'
                with self.assertRaises(ValueError):new.validate(**args)

    def test_cannot_omit_paid_intent_invent_zero_bill_or_change_checkpoint(self):
        for field in ['paid_set','bill','checkpoint']:
            with self.subTest(field=field):
                args=self.fixture()
                if field=='paid_set':args['related_paid_attempt_ids'].add('unretained-request')
                if field=='bill':args['budget_performance_receipts'][0]['billing']['actual_usd']='0'
                if field=='checkpoint':args['budget_performance_receipts'][0]['checkpoint_sha256']='e'*64
                with self.assertRaises(ValueError):new.validate(**args)
