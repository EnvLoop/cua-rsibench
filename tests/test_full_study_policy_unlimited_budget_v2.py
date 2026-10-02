import copy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cursibench import full_study_budget_v1 as old
from cursibench import full_study_policy_amendment_v2 as policy
from cursibench import full_study_unlimited_budget_v2 as new
from tests.test_full_study_budget_v1 import plan_fixture,sha


def qualified_plan():
    value=plan_fixture()
    for intent in value['campaign_intents']:
        intent.update(campaign_hours_cap=16,e2b_sandbox_hours_cap='32',matched_count_caps={
            'researcher_calls_per_campaign':1000,'teacher_rollout_tokens_per_campaign':1000000,
            'teacher_rollout_calls_per_campaign':100,'e2b_peak_concurrency':1,
            'candidate_submissions_per_campaign':100,'selection_evaluations_per_campaign':100})
    return value


def amendment(plan):
    return policy.build(plan,user_authorization_sha256=sha('direct user no dollar limit'),
                        pre_result_review_sha256=sha('zero official model results scope review'))


class PolicyLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.plan=qualified_plan();self.amendment=amendment(self.plan)
        self.ledger=new.StudyBudgetLedger(self.root/'unlimited.private.jsonl',self.plan,self.amendment)
        self.owner=self.amendment['owners'][0]

    def test_explicit_pre_result_uniform_amendment_retains_all_compute_time_and_scope(self):
        self.assertEqual(len(self.amendment['owners']),30)
        self.assertEqual(len(self.amendment['configuration_slots']),5)
        self.assertEqual(self.amendment['retained_task_limits'],{'max_actions':90,'actor_seconds':720,'lease_seconds':1200})
        self.assertEqual(self.amendment['retained_task_scope']['initial_slot_task_results'],3000)
        for row in self.amendment['retained_campaign_compute_limits'].values():self.assertEqual(row['campaign_hours_cap'],16)
        self.assertIsNone(self.amendment['global_usd_ceiling'])

    def test_post_result_or_compute_policy_change_is_refused(self):
        with self.assertRaisesRegex(ValueError,'precede_official'):
            policy.build(self.plan,user_authorization_sha256=sha('auth'),pre_result_review_sha256=sha('review'),official_model_results_before=1)
        changed=copy.deepcopy(self.amendment);changed['retained_task_limits']['actor_seconds']=721
        with self.assertRaises(ValueError):policy.validate(changed,self.plan)

    def test_actual_old_500_category_gate_fails_while_new_ledger_has_no_dollar_gate(self):
        prior=old.StudyBudgetLedger(self.root/'legacy.private.jsonl',self.plan)
        owner='desktop-native:astra'
        prior.reserve('legacy-full',owner,'tinker','500',sha('old quote'))
        with self.assertRaisesRegex(ValueError,'category cap exhausted'):
            prior.reserve('legacy-next',owner,'tinker','1',sha('next quote'))
        self.ledger.reserve('authorized-large',owner,'tinker','50000',sha('new source work'))
        snapshot=self.ledger.snapshot()
        self.assertIsNone(snapshot['global_ceiling_usd']);self.assertIsNone(snapshot['actual_total_usd'])
        self.assertEqual(snapshot['unresolved_nominal_quote_usd'],'50000')

    def test_real_usage_above_nominal_quote_is_retained_and_does_not_create_a_new_cap(self):
        self.ledger.reserve('first',self.owner,'tinker','1',sha('first'))
        self.ledger.mark_dispatched('first',sha('request'))
        value=self.ledger.settle('first','5000.25',sha('authentic provider usage receipt'))
        self.assertEqual(value['status'],'settled');self.assertTrue(value['exceeded_nominal_quote'])
        self.ledger.reserve('next',self.owner,'tinker','2',sha('unrelated next work'))
        snapshot=self.ledger.snapshot();self.assertFalse(snapshot['paid_dispatch_frozen'])
        self.assertEqual(snapshot['known_observed_usd'],'5000.25');self.assertIsNone(snapshot['actual_total_usd'])

    def test_unknown_charge_stays_null_and_uncertain_request_cannot_resubmit(self):
        self.ledger.reserve('first',self.owner,'tinker','1',sha('same work'))
        self.ledger.mark_dispatched('first',sha('request'));self.ledger.mark_uncertain('first','provider')
        self.assertIsNone(self.ledger.owner_attempts(self.owner)['first']['actual_usd'])
        with self.assertRaises(ValueError):self.ledger.reserve('second',self.owner,'tinker','1',sha('same work'))
        with self.assertRaises(ValueError):self.ledger.settle('first','0','not evidence')
        self.assertEqual(self.ledger.snapshot()['uncertain_attempts'],1)

    def test_scope_and_hash_chain_remain_enforced(self):
        with self.assertRaises(ValueError):self.ledger.reserve('wrong','unknown:astra','tinker','1',sha('work'))
        self.ledger.reserve('first',self.owner,'tinker','1',sha('work'))
        raw=self.ledger.path.read_text();self.ledger.path.write_text(raw.replace('nominal_quote_usd":"1','nominal_quote_usd":"2'))
        with self.assertRaisesRegex(ValueError,'hash_chain'):self.ledger.snapshot()

    def test_reopened_ledger_requires_same_amendment_and_no_charge_evidence(self):
        self.ledger.reserve('first',self.owner,'tinker','1',sha('work'))
        with self.assertRaises(ValueError):self.ledger.cancel_with_no_charge('first','unknown')
        self.ledger.cancel_with_no_charge('first',sha('authentic no charge'))
        reopened=new.StudyBudgetLedger(self.ledger.path,self.plan,self.amendment)
        self.assertEqual(reopened.snapshot()['cancelled_attempts'],1)
        changed=copy.deepcopy(self.amendment);changed['user_authorization_sha256']=sha('different source authorization')
        with self.assertRaises(ValueError):new.StudyBudgetLedger(self.ledger.path,self.plan,changed)
