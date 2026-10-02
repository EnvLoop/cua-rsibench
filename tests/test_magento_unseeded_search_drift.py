"""The one stopped unseeded clone can be retired only on exact evidence."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
import unittest

from tools import reconcile_magento_unseeded_search_drift_v1 as drift
from tools import sweep_magento_original_gui_controls_v1 as sweep


class MagentoUnseededSearchDriftTests(unittest.TestCase):
    def test_sql_comparator_accepts_only_exact_derived_price_drift(self):
        stable = drift.STABLE_CATALOG + drift.STABLE_BUSINESS
        prior = {'database': {'hashes': {'full': {
            **{name: 'same-' + name for name in stable},
            'catalog_product_index_price': 'frozen-price'}}}}
        current = {'hashes': {
            **{name: 'same-' + name for name in stable},
            'catalog_product_index_price': 'drifted-price'},
            'price_rows': 8156, 'price_key_sets_equal': True,
            'price_changed_rows': 2776,
            'price_changed_fields': {'final_price': 2552,
                                     'min_price': 2776, 'max_price': 223}}
        result = drift.compare_sql_source(current, prior)
        self.assertEqual(result['price_changed_rows'], 2776)
        self.assertEqual(result['stable_catalog_tables_matched'], 8)
        self.assertEqual(result['stable_business_tables_matched'], 5)
        current['price_changed_fields']['price'] = 1
        with self.assertRaisesRegex(ValueError, 'beyond the observed'):
            drift.compare_sql_source(current, prior)
        del current['price_changed_fields']['price']
        current['hashes']['customer_entity'] = 'changed'
        with self.assertRaisesRegex(ValueError, 'beyond the observed'):
            drift.compare_sql_source(current, prior)

    def test_stopped_attempt_must_precede_seed_and_gui(self):
        events = [
            {'event': 'step_intent', 'index': 31, 'step': 'positive-prepare',
             'time': 10.0},
            {'event': 'step_finished', 'index': 31,
             'step': 'positive-prepare', 'exit_code': 1, 'time': 20.0},
            {'event': 'sweep_stopped', 'passed': 1,
             'official_final_admitted': 0},
        ]
        process = {'exit_code': 1, 'stdout_bytes': 0,
                   'stderr_sha256': drift.FAILED_STDERR_SHA}
        self.assertEqual(drift.validate_stopped_attempt(events, process),
                         (10.0, 20.0))
        events.insert(-1, {'event': 'step_intent', 'index': 31,
                           'step': 'positive-seed'})
        with self.assertRaisesRegex(ValueError, 'seeded'):
            drift.validate_stopped_attempt(events, process)

    def test_cleanup_refuses_changed_live_container_or_source(self):
        audit = {'app_container_id_sha256': 'a',
                 'search_container_id_sha256': 'b',
                 'observed_search_sha256': drift.OBSERVED_SEARCH_SHA}
        drift._require_same_audit(audit, dict(audit))
        with self.assertRaisesRegex(ValueError, 'changed after audit'):
            drift._require_same_audit(audit,
                {**audit, 'app_container_id_sha256': 'replacement'})

    def test_one_case_recovery_receipts_bind_original_journal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            previous = root / 'events.private.jsonl'
            case = root / 'case-031/positive'
            case.mkdir(parents=True)
            witness = {
                'schema': 'envloop-magento-preseed-search-drift-private-audit-v1',
                'case_index': 31,
                'original_journal_sha256': drift.ORIGINAL_JOURNAL_SHA,
                'observed_search_sha256': drift.OBSERVED_SEARCH_SHA,
                'frozen_search_sha256': sweep.SEARCH_SHA,
                'quote_pages': 0,
            }
            audit_raw = (json.dumps(witness) + '\n').encode()
            (case / 'index-drift-audit.private.json').write_bytes(audit_raw)
            record = {
                'schema': 'envloop-magento-preseed-search-drift-cleanup-private-v1',
                'case_index': 31,
                'original_journal_sha256': drift.ORIGINAL_JOURNAL_SHA,
                'audit_sha256': sweep.sha(audit_raw),
                'task_seeded': False,
                'both_containers_cleaned': True,
                'model_calls': 0,
                'official_final_admitted': 0,
            }
            cleanup_raw = (json.dumps(record) + '\n').encode()
            (case / 'index-drift-cleanup.private.json').write_bytes(cleanup_raw)
            last = {'audit_sha256': sweep.sha(audit_raw),
                    'cleanup_receipt_sha256': sweep.sha(cleanup_raw)}
            events = [{'event': 'step_finished', 'index': 31,
                       'step': 'positive-prepare', 'exit_code': 1}]
            sweep.validate_preseed_search_drift_recovery(previous, events, last)
            witness['observed_search_sha256'] = sweep.SEARCH_SHA
            changed_raw = (json.dumps(witness) + '\n').encode()
            (case / 'index-drift-audit.private.json').write_bytes(changed_raw)
            last['audit_sha256'] = sweep.sha(changed_raw)
            record['audit_sha256'] = last['audit_sha256']
            changed_cleanup = (json.dumps(record) + '\n').encode()
            (case / 'index-drift-cleanup.private.json').write_bytes(changed_cleanup)
            last['cleanup_receipt_sha256'] = sweep.sha(changed_cleanup)
            with self.assertRaisesRegex(ValueError, 'only the exact'):
                sweep.validate_preseed_search_drift_recovery(previous,
                                                               events, last)


if __name__ == '__main__':
    unittest.main()
