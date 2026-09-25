"""Paid dispatch cannot outrun an immutable, reconciled dollar reservation."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from cursibench import full_study_budget_v1 as budget  # noqa: E402
from cursibench import full_study_matrix_v1 as matrix  # noqa: E402
from cursibench import full_study_pre_campaign_v1 as pre_campaign  # noqa: E402
from cursibench import scale_final_v06 as cell_final  # noqa: E402


def sha(value: str) -> str:
    return cell_final.digest(value.encode())


def plan_fixture() -> dict:
    cells = [{'cell_id': cell_id,
              'selected_final_cost_upper_bound_usd': '100'}
             for cell_id in matrix.CELLS]
    intents = [{
        'cell_id': cell_id, 'researcher_id': researcher,
        'tinker_usd_cap': '500',
        'researcher_inference_usd_cap': '100',
        'teacher_rollout_usd_cap': '25',
        'e2b_usd_cap': '20',
        'storage_application_usd_cap': '5',
        'all_in_ceiling_usd': '750',
    } for cell_id in matrix.CELLS for researcher in matrix.RESEARCHERS]
    return {'schema': pre_campaign.PLAN_SCHEMA, 'campaign_count': 24,
            'distinct_official_task_identities': 600,
            'declared_all_in_cost_upper_bound_usd': '18600',
            'cells': cells, 'campaign_intents': intents}


class FullStudyBudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cua-study-budget-test-')
        self.path = Path(self.temp.name) / 'budget.jsonl'
        self.plan = plan_fixture()
        self.ledger = budget.StudyBudgetLedger(self.path, self.plan)
        self.owner = f'{matrix.CELLS[0]}:astra'

    def tearDown(self):
        self.temp.cleanup()

    def test_uncertain_dispatch_retains_envelope_until_provider_usage_reconciles(self):
        work = sha('one Tinker optimizer step')
        reserved = self.ledger.reserve('sft-001', self.owner, 'tinker',
                                       '0.01422412', work)
        self.assertEqual(reserved['status'], 'pending')
        self.ledger.mark_dispatched('sft-001', sha('exact paid request'))
        self.ledger.mark_uncertain('sft-001', 'transport')
        self.assertEqual(self.ledger.snapshot()['uncertain_attempts'], 1)
        with self.assertRaisesRegex(ValueError, 'same work already'):
            self.ledger.reserve('sft-002', self.owner, 'tinker',
                                '0.01422412', work)
        settled = self.ledger.settle('sft-001', '0.013766822',
                                     sha('hourly provider usage'))
        self.assertEqual(settled['status'], 'settled')
        self.assertEqual(self.ledger.snapshot()['global_reserved_or_spent_usd'],
                         '0.013766822')
        self.assertEqual(self.ledger.settle('sft-001', '0.013766822',
                                            sha('hourly provider usage')),
                         settled)
        reopened = budget.StudyBudgetLedger(self.path, self.plan)
        self.assertEqual(reopened.snapshot()['settled_attempts'], 1)
        with self.assertRaisesRegex(ValueError, 'already dispatched or closed'):
            reopened.reserve('sft-001', self.owner, 'tinker',
                             '0.01422412', work)

    def test_category_and_campaign_ceiling_reject_extra_reservations(self):
        self.ledger.reserve('large', self.owner, 'tinker', '500', sha('large'))
        with self.assertRaisesRegex(ValueError, 'category cap exhausted'):
            self.ledger.reserve('extra', self.owner, 'tinker',
                                '0.000000001', sha('extra'))
        self.ledger.reserve('researcher', self.owner, 'researcher_inference',
                            '100', sha('researcher'))
        self.ledger.reserve('teacher', self.owner, 'teacher_rollout',
                            '25', sha('teacher'))
        self.ledger.reserve('e2b', self.owner, 'e2b', '20', sha('e2b'))
        self.ledger.reserve('storage', self.owner, 'storage_application',
                            '5', sha('storage'))
        self.ledger.reserve('selected', self.owner, 'selected_final',
                            '100', sha('selected'))
        self.assertEqual(self.ledger.snapshot()['owner_totals_usd'][self.owner],
                         '750')
        with self.assertRaisesRegex(ValueError, 'all-in cap exhausted'):
            self.ledger.reserve('extra-final', self.owner, 'selected_final',
                                '1', sha('another-final'))

    def test_cancel_requires_no_charge_evidence_and_hash_chain_detects_tamper(self):
        work = sha('cancelled provider request')
        self.ledger.reserve('first', self.owner, 'tinker', '1.5', work)
        with self.assertRaisesRegex(ValueError, 'SHA-256 required'):
            self.ledger.cancel_with_no_charge('first', 'unproven')
        self.ledger.mark_dispatched('first', sha('request'))
        self.ledger.cancel_with_no_charge('first', sha('provider no-charge proof'))
        self.assertEqual(self.ledger.snapshot()['global_reserved_or_spent_usd'], '0')
        self.ledger.reserve('second', self.owner, 'tinker', '1.5', work)
        rows = self.path.read_text().splitlines()
        rows[-1] = rows[-1].replace('1.5', '1.6')
        self.path.write_text('\n'.join(rows) + '\n')
        with self.assertRaisesRegex(ValueError, 'hash chain broken'):
            self.ledger.snapshot()

    def test_provider_overrun_is_recorded_and_freezes_new_paid_work(self):
        self.ledger.reserve('first', self.owner, 'tinker', '0.01', sha('work'))
        self.ledger.mark_dispatched('first', sha('request'))
        overrun = self.ledger.settle('first', '0.02', sha('provider actual usage'))
        self.assertEqual(overrun['status'], 'overrun')
        snapshot = self.ledger.snapshot()
        self.assertEqual(snapshot['global_reserved_or_spent_usd'], '0.02')
        self.assertEqual(snapshot['provider_overrun_attempts'], 1)
        self.assertTrue(snapshot['paid_dispatch_frozen'])
        with self.assertRaisesRegex(ValueError, 'overrun freezes'):
            self.ledger.reserve('next', self.owner, 'tinker', '0.01', sha('new work'))


if __name__ == '__main__':
    unittest.main()
