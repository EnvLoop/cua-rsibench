"""Synthetic six-cell tests never dispatch a real provider or hidden task."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tests'))

from cursibench import full_study_campaign_dispatch_v1 as dispatch  # noqa: E402
from cursibench import full_study_matrix_v1 as matrix  # noqa: E402
from cursibench import full_study_pre_campaign_v1 as pre_campaign  # noqa: E402
from cursibench import scale_final_v06 as cell_final  # noqa: E402
from native_desktop_factory import qwen_v066_adapter  # noqa: E402
from native_desktop_factory.v066_final_freeze import source_hashes  # noqa: E402
import test_full_study_matrix_v1 as matrix_fixture  # noqa: E402


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class FullStudyDispatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='cua-study-dispatch-test-')
        self.root = Path(self.temp.name)
        matrix_fixture.FullStudyMatrixTests.root = self.root
        matrix_fixture.FullStudyMatrixTests.build_fixture()
        self.manifest_path = self.root / 'pre-campaign-protocol.json'
        self.prepared = self.root / 'prepared'
        pre_campaign.prepare(self.manifest_path, self.prepared)
        self.plan = json.loads((self.prepared / 'campaign-plan.json').read_bytes())
        self.ratification_path = self.root / 'ratification.private.json'
        common = source_hashes()
        profiles = {cell_id: {
            'common_source_sha256s': common,
            'adapter_sha256': ('a' * 64 if cell_id != 'desktop-native' else
                               sha(Path(qwen_v066_adapter.__file__).read_bytes())),
        } for cell_id in matrix.CELLS}
        self.ratification_path.write_bytes(cell_final.json_bytes({
            'schema': 'cua-six-cell-action-profile-v066-ratification-v1',
            'status': 'ratified_pre_result',
            'ratified_utc': datetime.now(timezone.utc).isoformat(),
            'action_profile': 'scale-action-profile-v0.6.6',
            'common_source_sha256s': common, 'cell_profiles': profiles,
            'base_and_selected_identical': True,
            'hidden_final_model_attempts_before_ratification': 0,
        }))
        self.ratification_sha = sha(self.ratification_path.read_bytes())
        self.commit = 'b' * 40
        self.witness = {
            'schema': dispatch.WITNESS_SCHEMA,
            'status': 'frozen_before_campaign_dispatch',
            'study_id': self.plan['study_id'],
            'protocol_manifest_sha256': sha(self.manifest_path.read_bytes()),
            'campaign_plan_sha256': sha((self.prepared / 'campaign-plan.json').read_bytes()),
            'ratification_sha256': self.ratification_sha,
            'action_contract_sha256_by_cell': {
                row['cell_id']: row['matched_bindings']['action_contract']
                for row in self.plan['cells']},
            'campaign_count': 24,
            'admitted_final_task_identities': 600,
            'hidden_final_model_attempts_before_freeze': 0,
        }
        self.clock = [1_800_000_000]

    def tearDown(self):
        self.temp.cleanup()

    def frozen(self, witness=None):
        witness = self.witness if witness is None else witness
        return dispatch.FrozenStudy(
            repo_root=self.root, manifest_path=self.manifest_path,
            prepared_dir=self.prepared,
            ratification_path=self.ratification_path,
            public_commit_sha1=self.commit,
            witness_fetcher=lambda _url: cell_final.json_bytes(witness))

    def campaign(self):
        frozen = self.frozen()
        session = frozen.open_campaign(
            self.root / 'work' / 'campaign-astra',
            cell_id=matrix.CELLS[0], researcher_id='astra',
            now=lambda: self.clock[0])
        return frozen, session

    def test_current_missing_real_manifest_refuses_before_fetch_or_provider(self):
        calls = []
        with self.assertRaisesRegex(ValueError, 'pre_campaign_manifest_missing'):
            dispatch.FrozenStudy(
                repo_root=ROOT,
                manifest_path=ROOT / 'work' / 'full-study' / 'absent.json',
                prepared_dir=self.prepared,
                ratification_path=self.ratification_path,
                public_commit_sha1=self.commit,
                witness_fetcher=lambda url: calls.append(url))
        self.assertEqual(calls, [])

    def test_synthetic_freeze_binds_24_intents_and_hides_final_view(self):
        frozen = self.frozen()
        self.assertEqual(len(frozen.intents), 24)
        views = frozen.task_views(matrix.CELLS[0])
        self.assertEqual(len(views['selection']), 20)
        self.assertEqual(len(views['train']), 1)
        self.assertEqual(set(views), {'train', 'selection'})
        _, session = self.campaign()
        self.assertEqual(session.snapshot()['paid_attempt_count'], 0)

    def test_changed_prepared_plan_or_public_witness_fails_closed(self):
        plan_path = self.prepared / 'campaign-plan.json'
        original = plan_path.read_bytes()
        plan_path.write_bytes(original.replace(b'"campaign_count": 24',
                                               b'"campaign_count": 23'))
        with self.assertRaisesRegex(ValueError, 'prepared_campaign_plan_changed'):
            self.frozen()
        plan_path.write_bytes(original)
        wrong = dict(self.witness, ratification_sha256='0' * 64)
        with self.assertRaisesRegex(ValueError, 'public_witness_does_not_bind'):
            self.frozen(wrong)
        wrong = dict(self.witness, admitted_final_task_identities=599)
        with self.assertRaisesRegex(ValueError, 'public_witness_does_not_bind'):
            self.frozen(wrong)

    def test_paid_fake_provider_one_dispatch_private_resume_and_reconciliation(self):
        frozen, session = self.campaign()
        called = []
        result = session.dispatch_paid(
            attempt_id='researcher-001', category='researcher_inference',
            work={'round': 1}, request={'prompt': 'train sources only'},
            reserve_usd='1', resource_reservation={'researcher_calls': '1'},
            provider=lambda request: called.append(request) or {'text': 'proposal'})
        self.assertEqual(len(called), 1)
        self.assertEqual(result['billing_state'],
                         'awaiting_provider_usage_reconciliation')
        self.assertEqual(session.snapshot()['resource_reserved']['researcher_calls'], '1')
        self.assertEqual((session.directory / 'researcher-001.request.private.json').stat().st_mode & 0o077, 0)
        with self.assertRaisesRegex(ValueError, 'attempt_already_recorded'):
            session.dispatch_paid(
                attempt_id='researcher-001', category='researcher_inference',
                work={'round': 1}, request={'prompt': 'train sources only'},
                reserve_usd='1', resource_reservation={'researcher_calls': '1'},
                provider=lambda _: called.append('duplicate'))
        self.assertEqual(len(called), 1)
        reopened = frozen.open_campaign(
            session.directory, cell_id=matrix.CELLS[0],
            researcher_id='astra', now=lambda: self.clock[0])
        self.assertEqual(reopened.snapshot()['provider_result_count'], 1)
        record = reopened.reconcile_paid('researcher-001', actual_usd='0.5',
                                         provider_usage_sha256=sha(b'billed provider usage'))
        self.assertEqual(record['status'], 'settled')
        with self.assertRaisesRegex(ValueError, 'already_reconciled'):
            reopened.reconcile_paid('researcher-001', actual_usd='0.5',
                                    provider_usage_sha256=sha(b'billed provider usage'))

    def test_uncertain_failure_blocks_next_call_until_usage_reconciled(self):
        _, session = self.campaign()
        def timeout(_):
            raise TimeoutError('provider body may have been accepted')
        with self.assertRaisesRegex(ValueError, 'paid_response_uncertain'):
            session.dispatch_paid(
                attempt_id='researcher-001', category='researcher_inference',
                work={'round': 1}, request={'prompt': 'train sources only'},
                reserve_usd='1', resource_reservation={'researcher_calls': '1'},
                provider=timeout)
        self.assertTrue(session.snapshot()['uncertain_unreconciled'])
        with self.assertRaisesRegex(ValueError, 'paid_call_unreconciled'):
            session.dispatch_paid(
                attempt_id='researcher-002', category='researcher_inference',
                work={'round': 2}, request={'prompt': 'different train query'},
                reserve_usd='1', resource_reservation={'researcher_calls': '1'},
                provider=lambda _: {'text': 'must not run'})
        session.reconcile_paid('researcher-001', actual_usd=None,
                               provider_no_charge_sha256=sha(b'provider no charge'))
        self.assertFalse(session.snapshot()['uncertain_unreconciled'])
        with self.assertRaisesRegex(ValueError, 'same_work_already_recorded'):
            session.dispatch_paid(
                attempt_id='researcher-002', category='researcher_inference',
                work={'round': 1}, request={'prompt': 'train sources only'},
                reserve_usd='1', resource_reservation={'researcher_calls': '1'},
                provider=lambda _: {'text': 'must not run'})

    def test_time_limit_and_journal_tamper_stop_resumption(self):
        frozen, session = self.campaign()
        self.clock[0] += 16 * 3600 + 1
        with self.assertRaisesRegex(ValueError, 'sixteen_hour_limit'):
            session.dispatch_paid(
                attempt_id='late', category='researcher_inference',
                work={'round': 1}, request={'prompt': 'too late'},
                reserve_usd='1', resource_reservation={'researcher_calls': '1'},
                provider=lambda _: {'text': 'must not run'})
        self.clock[0] -= 16 * 3600 + 1
        journal = session.directory / 'campaign.jsonl'
        journal.write_bytes(journal.read_bytes().replace(b'campaign_started',
                                                         b'campaign_changed'))
        with self.assertRaisesRegex(ValueError, 'journal_hash_chain_broken'):
            frozen.open_campaign(session.directory, cell_id=matrix.CELLS[0],
                                 researcher_id='astra', now=lambda: self.clock[0])

    def test_orphan_budget_reservation_from_pre_journal_crash_blocks_dispatch(self):
        _, session = self.campaign()
        session.budget.reserve('orphan-001', session.owner,
                               'researcher_inference', '1', sha(b'orphan work'))
        self.assertEqual(session.snapshot()['orphan_budget_attempts'], ['orphan-001'])
        with self.assertRaisesRegex(ValueError, 'paid_call_unreconciled'):
            session.dispatch_paid(
                attempt_id='researcher-001', category='researcher_inference',
                work={'round': 1}, request={'prompt': 'train only'},
                reserve_usd='1', resource_reservation={'researcher_calls': '1'},
                provider=lambda _: {'text': 'must not run'})
        session.reconcile_orphan_reservation(
            'orphan-001', provider_no_charge_sha256=sha(b'provider no charge'))
        self.assertEqual(session.snapshot()['orphan_budget_attempts'], [])

    def test_researcher_call_cannot_omit_matched_call_counter(self):
        _, session = self.campaign()
        with self.assertRaisesRegex(ValueError, 'researcher_call_counter_required'):
            session.dispatch_paid(
                attempt_id='researcher-001', category='researcher_inference',
                work={'round': 1}, request={'prompt': 'train only'},
                reserve_usd='1', resource_reservation={},
                provider=lambda _: {'text': 'must not run'})
        self.assertEqual(session.snapshot()['paid_attempt_count'], 0)


if __name__ == '__main__':
    unittest.main()
