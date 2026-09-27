"""Evidence gate for cell-wide Magento cron-free GUI requalification.

The freeze is private and permits only evaluator GUI controls. It does not
admit a final task, score a model, or pool the earlier 35 historical controls.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from magento_catalog_factory.plan import require
from magento_catalog_factory.seed import IMAGE
from magento_catalog_factory.verify import NATIVE_SEARCH_IMAGE


SEARCH_SHA = '54ca1d8ef5cb82ed879338e6740a589a930e50cd8a54f495c234c5f5b0acf6fb'
POLICY = 'cron_autostart_disabled_before_supervisor'
STAGES = frozenset(('after_cron_policy_and_http_ready', 'after_config_cache',
                    'after_search_reindex', 'after_idle_60_seconds'))
HISTORICAL = (
    'docs/evidence/magento-original-preseed-index-drift-2026-09-27.json',
    'docs/evidence/magento-original-cellwide-index-drift-stop-2026-09-27.json',
)
PUBLIC_PROBE = 'docs/evidence/magento-cron-never-autostart-train-probe-2026-09-27.json'
TRAIN_FAILURE_PUBLIC = 'docs/evidence/magento-cron-train-gui-interruption-2026-09-28.json'
TRAIN_FAILURE_DIR = 'work/magento-original/train-cron-never-autostart-gui-v1'
TRAIN_RETRY_DIR = 'work/magento-original/train-cron-never-autostart-gui-retry1'
TRAIN_PLAN = 'work/magento-original/train-policy-development-four.private.json'
FINAL_PLAN = 'work/magento-original/candidate-plan-v2.private.json'
CODE_FILES = (
    'tools/magento_cron_runtime_contract_v1.py',
    'tools/freeze_magento_cron_runtime_v1.py',
    'tools/sweep_magento_original_gui_controls_v1.py',
    'tools/start_magento_native_sidecar_clone_v1.py',
    'tools/capture_magento_native_runtime_v1.py',
    'tools/qualify_magento_original_catalog_v1.py',
    'tools/audit_magento_original_fresh_reset_v1.py',
    'magento_catalog_factory/plan.py',
    'magento_catalog_factory/seed.py',
    'magento_catalog_factory/verify.py',
)
STEPS = (
    'positive-prepare', 'positive-seed', 'positive-neutral',
    'positive-finalize', 'positive-runtime', 'positive-gui',
    'negative-prepare', 'negative-seed', 'negative-neutral',
    'negative-finalize', 'negative-runtime', 'fresh-reset', 'negative-gui',
)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    return json.loads(raw), sha(raw)


def validate_prepared(prepared: dict, *, config_sha256: str) -> None:
    clone = prepared.get('application_clone', {})
    cron = prepared.get('train_probe_cron', {})
    stages = prepared.get('train_probe_price_stages', {})
    require(prepared.get('schema') == 'envloop-magento-native-sidecar-clone-preparation-v1' and
            prepared.get('status') == 'clone_and_sidecar_prepared_no_task_seeded' and
            prepared.get('search_document_count') == 181 and
            prepared.get('search_documents_sha256') == SEARCH_SHA and
            prepared.get('search_sidecar_image_sha256') == NATIVE_SEARCH_IMAGE and
            clone.get('image_sha256') == IMAGE and clone.get('mount_count') == 0 and
            cron.get('policy') == POLICY and cron.get('config_sha256') == config_sha256 and
            set(stages) == STAGES and
            all(row.get('price_rows') == 8156 and
                    row.get('price_key_sets_equal') is True and
                    row.get('price_changed_rows') == 0 and
                    row.get('live_price_sha256') == row.get('replica_price_sha256')
                    for row in stages.values()) and
            prepared.get('official_final_tasks_admitted') == 0,
            'prepared pair differs from cron-free training probe')


def validate_history(root: Path) -> dict:
    first, first_sha = read(root / HISTORICAL[0])
    second, second_sha = read(root / HISTORICAL[1])
    require(first['schema'] == 'envloop-magento-preseed-search-drift-public-v1' and
            second['schema'] == 'envloop-magento-cellwide-index-drift-stop-v1' and
            first['ordinal'] == 31 and second['current_attempt_ordinal'] == 35 and
            second['candidate_gui_controls_passed_before_stop'] == 35 and
            first['live_price_index_rows'] == second['live_price_index_rows'] == 8156 and
            first['live_price_index_rows_with_derived_field_drift'] ==
            second['derived_price_rows_differing_from_replica'] == 2776 and
            first['observed_search_sha256'] == second['observed_search_sha256'] and
            first['frozen_search_sha256'] == second['frozen_search_sha256'] == SEARCH_SHA and
            first['task_seeded'] is second['task_seeded'] is False and
            first['model_calls'] == second['model_calls'] == 0 and
            first['official_final_admitted'] == second['official_final_admitted'] == 0 and
            second['further_per_case_retry_allowed'] is False,
            'historical two-failure cell stop changed')
    return {'historical_controls': 35, 'preseed_drift_failures': 2,
            'failure_receipt_sha256': [first_sha, second_sha]}


def validate_probe(root: Path, probe_dir: Path) -> tuple[dict, dict]:
    public, public_sha = read(root / PUBLIC_PROBE)
    startup, startup_sha = read(probe_dir / 'startup.private.json')
    audit, audit_sha = read(probe_dir / 'probe-pair-audit.private.json')
    cleanup, cleanup_sha = read(probe_dir / 'probe-pair-cleanup.private.json')
    require(public['schema'] == 'envloop-magento-cron-never-autostart-train-success-public-v1' and
            public['status'] == 'unseeded_training_startup_and_60_second_idle_passed' and
            public['cron_policy'] == POLICY and
            public['app_image_sha256'] == IMAGE and
            public['search_image_sha256'] == NATIVE_SEARCH_IMAGE and
            public['app_mount_count'] == 0 and
            public['search_documents'] == 181 and
            public['search_documents_sha256'] == SEARCH_SHA and
            public['private_receipt_sha256'] == startup_sha and
            public['private_pair_audit_sha256'] == audit_sha and
            public['task_seeded'] is False and
            public['model_calls'] == public['official_final_admitted'] == 0 and
            set(public['price_changed_rows_by_stage']) == STAGES and
            all(value == 0 for value in public['price_changed_rows_by_stage'].values()),
            'public startup probe changed')
    require(startup.get('schema') ==
            'envloop-magento-cron-never-autostart-train-probe-v2' and
            startup.get('split') == 'train_only' and
            startup.get('model_calls') == 0,
            'private startup probe is not the bounded training-only v2 attempt')
    validate_prepared({**startup,
                       'schema': 'envloop-magento-native-sidecar-clone-preparation-v1'},
                      config_sha256=public['cron_config_sha256'])
    require(audit['schema'] == 'envloop-magento-cron-v2-pair-audit-private-v1' and
            cleanup['schema'] == 'envloop-magento-cron-v2-pair-cleanup-private-v1' and
            audit['source_receipt_sha256'] == startup_sha and
            audit['price_changed_rows'] == 0 and
            audit['cron_config_sha256'] == public['cron_config_sha256'] and
            audit['search_documents_sha256'] == SEARCH_SHA and
            audit['app_container_id_sha256'] == public['app_container_id_sha256'] and
            audit['search_container_id_sha256'] == public['search_container_id_sha256'] and
            cleanup['audit_sha256'] == audit_sha and
            cleanup['both_containers_cleaned'] is True and
            audit['task_seeded'] is cleanup['task_seeded'] is False and
            audit['model_calls'] == cleanup['model_calls'] == 0 and
            audit['official_final_admitted'] == cleanup['official_final_admitted'] == 0,
            'startup pair has no exact cleanup')
    return public, {'public_sha256': public_sha, 'private_sha256': startup_sha,
                    'cleanup_sha256': cleanup_sha}


def validate_train_recovery(root: Path) -> tuple[str, dict]:
    public, public_sha = read(root / TRAIN_FAILURE_PUBLIC)
    failed_dir = root / TRAIN_FAILURE_DIR
    journal_raw = (failed_dir / 'events.private.jsonl').read_bytes()
    lines = journal_raw.splitlines(keepends=True)
    events = [json.loads(line) for line in lines]
    require(public['schema'] == 'envloop-magento-cron-train-gui-interruption-public-v1' and
            public['status'] == 'train_negative_neutral_stopped_before_gui_edit' and
            public['fresh_clone_retry_cap'] == 1 and
            public['saved_positive_score'] == 1.0 and
            public['negative_gui_attempted'] is False and
            public['model_calls'] == public['official_final_admitted'] == 0 and
            len(events) >= 3 and
            sha(b''.join(lines[:-2])) == public['stopped_journal_sha256'] and
            events[-3].get('event') == 'sweep_stopped' and
            events[-2].get('event') == 'operator_cron_train_gui_cleanup_intent' and
            events[-1].get('event') ==
            'operator_reconciled_cron_train_gui_interruption' and
            events[-1].get('index') == 0 and
            events[-1].get('both_containers_cleaned') is True and
            events[-1].get('negative_gui_attempted') is False,
            'original failed training trio and exact reconciliation must remain')
    audit, audit_sha = read(failed_dir /
                            'case-000/negative/train-interruption-audit.private.json')
    cleanup, cleanup_sha = read(failed_dir /
                                'case-000/negative/train-interruption-cleanup.private.json')
    require(audit['schema'] == 'envloop-magento-cron-train-gui-audit-private-v1' and
            cleanup['schema'] == 'envloop-magento-cron-train-gui-cleanup-private-v1' and
            audit['public_failure_receipt_sha256'] == public_sha and
            audit['original_stopped_journal_sha256'] ==
            cleanup['original_stopped_journal_sha256'] ==
            public['stopped_journal_sha256'] and
            cleanup['audit_sha256'] == events[-2].get('audit_sha256') ==
            events[-1].get('audit_sha256') == audit_sha and
            events[-1].get('cleanup_receipt_sha256') == cleanup_sha and
            cleanup['plan_sha256'] == public['train_plan_sha256'] and
            audit['material_state_unchanged'] is True and
            cleanup['material_state_unchanged'] is True and
            cleanup['both_containers_cleaned'] is True and
            cleanup['negative_gui_attempted'] is False and
            audit['model_calls'] == cleanup['model_calls'] == 0 and
            audit['official_final_admitted'] ==
            cleanup['official_final_admitted'] == 0,
            'failed training pair was not exactly audited and cleaned')
    return sha(journal_raw), {'original_failure_public_sha256': public_sha,
                              'original_failure_journal_sha256':
                              public['stopped_journal_sha256'],
                              'reconciled_journal_sha256': sha(journal_raw),
                              'audit_sha256': audit_sha,
                              'cleanup_sha256': cleanup_sha}


def validate_train_gui(train_dir: Path, config_sha256: str,
                       plan_sha256: str, recovery_sha256: str) -> dict:
    journal_raw = (train_dir / 'events.private.jsonl').read_bytes()
    events = [json.loads(line) for line in journal_raw.splitlines()]
    require(bool(events) and events[0].get('event') == 'sweep_started' and
            events[0].get('split') == 'train_policy_development' and
            events[0].get('plan_sha256') == plan_sha256 and
            events[0].get('start_index') == 0 and events[0].get('limit') == 1 and
            events[0].get('recovery_of_private_journal_sha256') == recovery_sha256 and
            events[0].get('recovery_kind') ==
            'cron_train_negative_neutral_once' and
            events[0].get('train_cron_never_autostart') is True and
            events[0].get('model_calls') == 0 and
            events[0].get('official_final_admitted') is False and
            events[-1].get('event') == 'sweep_completed' and
            events[-1].get('passed') == events[-1].get('requested') == 1 and
            events[-1].get('official_final_admitted') == 0 and
            not any(row.get('event') in ('sweep_stopped', 'step_timeout_uncertain')
                    for row in events),
            'uninterrupted one-case training GUI run required')
    intents = tuple(row['step'] for row in events if row.get('event') == 'step_intent')
    finishes = tuple(row['step'] for row in events if row.get('event') == 'step_finished'
                     and row.get('exit_code') == 0)
    require(intents == finishes == STEPS and
            len([row for row in events if row.get('event') == 'step_finished']) == len(STEPS) and
            [(row.get('index'), row.get('pair')) for row in events
             if row.get('event') == 'pair_cleanup_verified'] ==
            [(0, 'positive'), (0, 'negative')],
            'training GUI steps or pair cleanup changed')
    case = train_dir / 'case-000'
    calibration, calibration_sha = read(case / 'calibration.private.json')
    require(calibration['schema'] == 'envloop-magento-original-gui-case-calibration-v1' and
            calibration['split'] == 'train_policy_development' and
            calibration['positive_score'] == 1.0 and
            calibration['wrong_variant_score'] == 0.0 and
            calibration['fresh_reset_passed'] is True and
            calibration['model_calls'] == 0 and
            calibration['official_final_admitted'] is False and
            [row.get('receipt_sha256') for row in events
             if row.get('event') == 'task_gui_calibrated'] == [calibration_sha],
            'training GUI calibration not 1/0/reset')
    for pair, mode, score in (('positive', 'gui-positive', 1.0),
                              ('negative', 'gui-wrong-variant', 0.0)):
        prepared, _ = read(case / pair / 'prepare.private.json')
        validate_prepared(prepared, config_sha256=config_sha256)
        runtime, runtime_sha = read(case / pair / 'runtime.private.json')
        require(runtime['app'] == prepared['application_clone'] and
                runtime['sidecar_id_sha256'] == prepared['search_sidecar_id_sha256'] and
                calibration['receipt_sha256'][f'{pair}_runtime'] == runtime_sha,
                'train GUI clone identity differs from prepared pair')
        result, _ = read(case / pair / mode / 'result.json')
        require(result.get('model_calls') == result.get('official_final_tasks_admitted') == 0 and
                result.get('score', {}).get('independent_saved_state') is True and
                result['score']['score'] == score and
                result['score']['task_id'] == calibration['task_id'],
                'independent train GUI saved-state score changed')
    reset, reset_sha = read(case / 'negative/fresh-reset.private.json')
    require(reset['fresh_clone_reset_passed'] is True and
            reset['material_monitored_sql_and_search_state'] is True and
            reset['different_container_ids'] is True and
            reset['different_search_container_ids'] is True and
            reset['official_final_tasks_admitted'] == 0,
            'training GUI fresh reset failed')
    return {'journal_sha256': sha(journal_raw),
            'calibration_sha256': calibration_sha,
            'reset_sha256': reset_sha,
            'positive_score': 1.0, 'wrong_variant_score': 0.0,
            'fresh_reset_passed': True}


def build_freeze(root: Path, probe_dir: Path, train_dir: Path,
                 train_plan_sha256: str, final_plan_sha256: str) -> dict:
    require(train_dir.resolve() == (root / TRAIN_RETRY_DIR).resolve() and
            sha((root / TRAIN_PLAN).read_bytes()) == train_plan_sha256 and
            sha((root / FINAL_PLAN).read_bytes()) == final_plan_sha256 and
            len(json.loads((root / TRAIN_PLAN).read_bytes())['cases']
                ['train_policy_development']) == 4 and
            len(json.loads((root / FINAL_PLAN).read_bytes())['cases']
                ['official_candidate']) == 100,
            'unchanged separate train and final candidate plans required')
    history = validate_history(root)
    probe, probe_hashes = validate_probe(root, probe_dir)
    recovery_sha, failure = validate_train_recovery(root)
    train = validate_train_gui(train_dir, probe['cron_config_sha256'],
                               train_plan_sha256, recovery_sha)
    runtime = {'application_image_sha256': IMAGE,
               'native_search_image_sha256': NATIVE_SEARCH_IMAGE,
               'source_search_sha256': SEARCH_SHA,
               'source_commit': '6473f72db5dcefc97b5725b59e734504edc28a21',
               'cron_policy': POLICY,
               'cron_config_sha256': probe['cron_config_sha256'],
               'mount_count': 0, 'search_documents': 181,
               'loopback_admin_port': 7794, 'loopback_control_port': 7795,
               'code_sha256': {name: sha((root / name).read_bytes())
                               for name in CODE_FILES}}
    fingerprint = sha((json.dumps(runtime, sort_keys=True, separators=(',', ':')) + '\n').encode())
    return {'schema': 'envloop-magento-cellwide-cron-runtime-freeze-v1',
            'status': 'qualified_for_100_fresh_gui_controls_only',
            'runtime_fingerprint_sha256': fingerprint,
            'runtime': runtime, 'history': history,
            'startup_probe': probe_hashes, 'training_gui': train,
            'failed_training_attempt': failure,
            'training_plan_sha256': train_plan_sha256,
            'final_candidate_plan_sha256': final_plan_sha256,
            'required_fresh_final_candidate_controls': 100,
            'historical_controls_eligible_for_revised_runtime': 0,
            'model_calls': 0, 'official_final_admitted': 0}


def validate_freeze(path: Path, root: Path, probe_dir: Path,
                    train_dir: Path) -> tuple[dict, str]:
    frozen, digest = read(path)
    require(frozen.get('schema') == 'envloop-magento-cellwide-cron-runtime-freeze-v1' and
            frozen.get('status') == 'qualified_for_100_fresh_gui_controls_only' and
            frozen.get('model_calls') == frozen.get('official_final_admitted') == 0,
            'non-scoring cell-wide runtime freeze required')
    require(frozen == build_freeze(root, probe_dir, train_dir,
                                   frozen['training_plan_sha256'],
                                   frozen['final_candidate_plan_sha256']),
            'source, code, probe, or train GUI evidence changed after freeze')
    return frozen, digest
