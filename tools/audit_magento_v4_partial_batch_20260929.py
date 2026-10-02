"""Read-only, source-bound audit of the first Magento v4 two-case chunk.

The private run remains in the operator's ignored ``work/`` tree. This audit
reopens source/plan/journal/receipts and replays scores from raw saved-state
snapshots. Only a field-limited public summary is written on explicit request.
No Docker mutation, GUI action, task dispatch, or model call is possible here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from magento_catalog_factory.plan import SCHEMA as PLAN_SCHEMA, digest
from magento_catalog_factory.seed import CONTEXT
from magento_catalog_factory.verify import check_baseline, score_saved_state
from tools import audit_magento_original_fresh_reset_v1 as reset_verifier
from tools import magento_clean_100_v4 as v4
from tools import magento_v4_preconfig_startup_amendment_20260929 as recovery
from tools import sweep_magento_original_gui_controls_v3 as sweep


SCHEMA = 'envloop-magento-v4-partial-two-case-independent-audit-public-v1'
PLAN_REL = Path('work/magento-original/candidate-plan-v2.private.json')
SOURCE_REL = Path('work/webarena-source')
CRON_FREEZE_REL = Path('work/magento-original/cron-freeze-20260928.private.json')
V4_FREEZE_REL = Path('work/magento-original/clean-v4-freeze-20260929.private.json')
RUN_REL = Path('work/magento-original/clean-v4-100-20260929')
ORIGINAL_STEPS = (
    'positive-prepare', 'positive-seed', 'positive-neutral',
    'positive-finalize', 'positive-runtime', 'positive-gui',
    'negative-prepare', 'negative-seed', 'negative-neutral',
    'negative-finalize', 'negative-runtime', 'fresh-reset', 'negative-gui',
)


class AuditError(ValueError):
    """A private input cannot support the public partial-batch claim."""


def must(condition: bool, message: str) -> None:
    if not condition:
        raise AuditError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=False, allow_nan=False) + '\n').encode()


def read_json(path: Path) -> tuple[dict, str]:
    must(path.is_file() and not path.is_symlink(), 'missing or linked private evidence')
    raw = path.read_bytes()
    result = json.loads(raw)
    must(isinstance(result, dict), 'private evidence must be an object')
    return result, sha(raw)


def read_journal_prefix(path: Path) -> tuple[list[dict], bytes]:
    must(path.is_file() and not path.is_symlink(), 'missing private journal')
    raw = path.read_bytes()
    must(raw.endswith(b'\n'), 'truncated private journal')
    rows = []
    prior = '0' * 64
    for number, line in enumerate(raw.splitlines(keepends=True)):
        row = json.loads(line)
        must(isinstance(row, dict) and line == canonical(row) and
             row.get('schema') == v4.JOURNAL_SCHEMA and
             row.get('sequence') == number and
             row.get('previous_line_sha256') == prior,
             'noncanonical or broken append-only journal chain')
        rows.append(row)
        prior = sha(line)
    must(len(rows) == 79 and rows[-1].get('event') == 'chunk_completed',
         'first bounded two-case chunk is not the entire current journal')
    return rows, raw


def check_chunk(rows: list[dict], cases: list[dict], freeze: dict,
                freeze_sha: str) -> dict:
    must(len(cases) == 100 and len(rows) == 79, 'not the frozen first 2 of 100')
    header, dispatch, chunk = rows[0], rows[1], rows[-1]
    must(header.get('event') == 'run_started' and
         header.get('freeze_v4_sha256') == freeze_sha and
         header.get('plan_sha256') == freeze['plan_sha256'] and
         header.get('ordered_task_identity_sha256') ==
         freeze['ordered_task_identity_sha256'] and
         header.get('source_commit') == freeze['source_commit'] and
         header.get('model_calls') == header.get('official_final_admitted') == 0,
         'run header is not bound to frozen source and ordered plan')
    must(dispatch.get('event') == 'dispatch_started' and
         dispatch.get('max_cases') == 2 and
         dispatch.get('completed_before_dispatch') == 0 and
         dispatch.get('freeze_v4_sha256') == freeze_sha and
         dispatch.get('model_calls') ==
         dispatch.get('official_final_admitted') == 0,
         'dispatch is not the first bounded two-case chunk')
    starts = [r for r in rows if r.get('event') == 'case_attempt_started']
    stopped = [r for r in rows if r.get('event') == 'attempt_stopped']
    reconciled = [r for r in rows if r.get('event') == 'attempt_reconciled']
    completed = [r for r in rows if r.get('event') == 'case_completed']
    must([(r.get('index'), r.get('attempt')) for r in starts] ==
         [(0, 0), (0, 1), (1, 0)] and
         [(r.get('index'), r.get('attempt')) for r in stopped] == [(0, 0)] and
         [(r.get('index'), r.get('attempt')) for r in reconciled] == [(0, 0)] and
         [(r.get('index'), r.get('attempt')) for r in completed] ==
         [(0, 1), (1, 0)] and
         all(r.get('task_id') == cases[r['index']]['task_id'] and
             r.get('package_sha256') == cases[r['index']]['package_sha256']
             for r in starts) and
         all(r.get('model_calls') == r.get('official_final_admitted') == 0
             for r in starts + stopped + reconciled + completed),
         'case order, one same-ID retry, or zero-model boundary changed')
    prior = rows[:-1]
    receipts = [r['calibration_sha256'] for r in completed]
    must(chunk.get('max_cases') == 2 and
         chunk.get('dispatch_sequence') == dispatch['sequence'] and
         chunk.get('freeze_v4_sha256') == freeze_sha and
         chunk.get('parent_v3_freeze_sha256') ==
         freeze['parent_v3_freeze_sha256'] and
         chunk.get('completed_distinct_cases') == 2 and
         chunk.get('newly_completed_this_dispatch') == 2 and
         chunk.get('ordered_completed_task_identity_sha256') ==
         v4.case_identity_digest(cases[:2]) and
         chunk.get('completed_calibration_receipts_sha256') ==
         sha(('\n'.join(receipts) + '\n').encode()) and
         chunk.get('journal_prefix_sha256') ==
         sha(b''.join(canonical(r) for r in prior)) and
         chunk.get('infrastructure_retries') == 1 and
         chunk.get('model_calls') == chunk.get('official_final_admitted') == 0,
         'two-case chunk receipt or journal prefix hash changed')
    return {'starts': starts, 'stopped': stopped,
            'reconciled': reconciled, 'completed': completed}


def check_preconfig_retry(root: Path, run: Path, rows: list[dict],
                          case: dict, freeze_sha: str) -> dict:
    paths = recovery._paths(root)
    must(paths['run'] == run and
         sha((root / PLAN_REL).read_bytes()) == recovery.PLAN_SHA and
         freeze_sha == recovery.FREEZE_SHA,
         'preconfig supplement targets another campaign or plan')
    supplement_sha = recovery._validate_source_freeze(paths)
    supplement, _ = read_json(paths['source_freeze'])
    must(supplement.get('classification') == recovery.CLASSIFICATION and
         supplement.get('original_journal_sha256') ==
         recovery.ORIGINAL_JOURNAL_SHA and
         supplement.get('one_same_id_whole_case_retry_only') is True,
         'source-frozen preconfig supplement changed')
    journal_prefix = b''.join(canonical(r) for r in rows[:6])
    must(len(journal_prefix) == recovery.ORIGINAL_JOURNAL_LENGTH and
         sha(journal_prefix) == recovery.ORIGINAL_JOURNAL_SHA and
         [r.get('event') for r in rows[:6]] == list(recovery.STOP_EVENTS) and
         rows[4].get('exit_code') == 1 and
         rows[5].get('error_type') == 'ValueError',
         'original before-seed startup stop changed')
    process, process_sha = read_json(paths['process'])
    stderr = paths['stderr'].read_bytes()
    must(process_sha == recovery.PROCESS_SHA and
         sha(stderr) == recovery.STDERR_SHA and
         process.get('exit_code') == 1 and
         process.get('stderr_sha256') == recovery.STDERR_SHA and
         b'TimeoutError: Magento HTTP did not become ready' in stderr and
         not (run / recovery.CASE_REL / 'prepare.private.json').exists() and
         not (run / recovery.CASE_REL / 'seed.private.json').exists() and
         not (run / recovery.CASE_REL / 'gui-positive').exists(),
         'invalid first attempt was not strictly preconfig, preseed and pre-GUI')
    audit, audit_sha = read_json(paths['audit'])
    intent, intent_sha = read_json(paths['intent'])
    receipt, receipt_sha = read_json(paths['receipt'])
    witness = audit.get('material_witness', {})
    containers = witness.get('containers', [])
    must(len(containers) == 2 and
         [r.get('name') for r in containers] == [sweep.APP, sweep.SEARCH] and
         all(isinstance(r.get('container_id_sha256'), str) and
             len(r['container_id_sha256']) == 64 for r in containers),
         'preconfig pair identity missing')
    must(audit.get('schema') == 'envloop-magento-clean-attempt-audit-private-v4' and
         intent.get('schema') == 'envloop-magento-clean-cleanup-intent-private-v4' and
         receipt.get('schema') == 'envloop-magento-clean-cleanup-private-v4' and
         all(r.get('task_id') == case['task_id'] and
             r.get('case_index') == r.get('attempt') == 0 and
             r.get('model_calls') == r.get('official_final_admitted') == 0
             for r in (audit, intent, receipt)) and
         audit.get('package_sha256') == receipt.get('package_sha256') ==
         case['package_sha256'] and
         audit.get('plan_sha256') == receipt.get('plan_sha256') ==
         recovery.PLAN_SHA and
         audit.get('freeze_v4_sha256') == receipt.get('freeze_v4_sha256') ==
         freeze_sha and
         audit.get('preconfig_amendment_freeze_sha256') ==
         intent.get('preconfig_amendment_freeze_sha256') ==
         receipt.get('preconfig_amendment_freeze_sha256') == supplement_sha and
         intent.get('audit_sha256') == receipt.get('audit_sha256') == audit_sha and
         receipt.get('cleanup_intent_sha256') == intent_sha and
         witness == intent.get('material_witness') ==
         receipt.get('material_witness') and
         receipt.get('both_containers_absent') is True and
         witness.get('task_seeded') is False and
         witness.get('quote_pages') == 0 and
         witness.get('native_sidecar_index_count') == 0 and
         witness.get('cron_stopped') is True and
         witness.get('embedded_search_stopped') is True and
         witness.get('price_changed_rows') == 0 and
         witness.get('price_key_sets_equal') is True,
         'failed-attempt audit/cleanup does not preserve exact material lineage')
    scoped = rows[6:16]
    must(scoped[0].get('event') == 'reconciliation_cleanup_intent' and
         scoped[0].get('intent_sha256') == intent_sha and
         scoped[0].get('audit_sha256') == audit_sha and
         scoped[-1].get('event') == 'attempt_reconciled' and
         scoped[-1].get('classification') == recovery.CLASSIFICATION and
         scoped[-1].get('reconciliation_sha256') == receipt_sha and
         scoped[-1].get('audit_sha256') == audit_sha and
         scoped[-1].get('both_containers_absent') is True,
         'supplemental cleanup journal does not bind the exact retry')
    expected_cleanup = [(item['name'], item['container_id_sha256'], action)
                        for item in containers for action in ('stop', 'rm')]
    actual_intents = [(r.get('name'), r.get('container_id_sha256'), r.get('action'))
                      for r in scoped if r.get('event') == 'cleanup_step_intent']
    actual_finishes = [(r.get('name'), r.get('container_id_sha256'), r.get('action'))
                       for r in scoped if r.get('event') == 'cleanup_step_finished']
    must(actual_intents == actual_finishes == expected_cleanup and
         all(r.get('stdout_sha256') ==
             sha((r['name'] + '\n').encode()) and
             r.get('stderr_sha256') == sha(b'') for r in scoped
             if r.get('event') == 'cleanup_step_finished'),
         'exact disposable pair cleanup was not completed')
    return {'supplement_sha256': supplement_sha,
            'reconciliation_sha256': receipt_sha,
            'classification': recovery.CLASSIFICATION}


def check_successful_case(run: Path, rows: list[dict], index: int,
                          attempt: int, case: dict, runtime_sha: str) -> str:
    scoped = [r for r in rows if r.get('index') == index and
              r.get('attempt') == attempt]
    intents = [r.get('step') for r in scoped if r.get('event') == 'step_intent']
    finishes = [r for r in scoped if r.get('event') == 'step_finished']
    must(intents == [r.get('step') for r in finishes] ==
         list(ORIGINAL_STEPS) and
         all(r.get('exit_code') == 0 for r in finishes) and
         [r.get('pair') for r in scoped if r.get('event') ==
          'pair_cleanup_verified'] == ['positive', 'negative'] and
         len([r for r in scoped if r.get('event') ==
              'task_gui_calibrated']) == 1,
         'completed candidate lacks full positive/negative GUI process and cleanup')
    base = run / 'attempts' / f'case-{index:03d}-attempt-{attempt}' / f'case-{index:03d}'
    calibration, calibration_sha = read_json(base / 'calibration.private.json')
    must(calibration.get('schema') ==
         'envloop-magento-original-gui-case-calibration-v3' and
         calibration.get('task_id') == case['task_id'] and
         calibration.get('package_sha256') == case['package_sha256'] and
         calibration.get('split') == 'official_candidate' and
         calibration.get('positive_score') == 1.0 and
         calibration.get('wrong_variant_score') == 0.0 and
         calibration.get('fresh_reset_passed') is True and
         calibration.get('cellwide_cron_runtime_fingerprint_sha256') == runtime_sha and
         calibration.get('model_calls') == 0 and
         calibration.get('official_final_admitted') is False and
         [r for r in scoped if r.get('event') == 'task_gui_calibrated'][0].get(
             'receipt_sha256') == calibration_sha and
         [r for r in scoped if r.get('event') == 'case_completed'][0].get(
             'calibration_sha256') == calibration_sha,
         'calibration receipt is not bound to the exact completed task')
    for pair in ('positive', 'negative'):
        for part in ('prepare', 'seed', 'baseline', 'finalization', 'runtime'):
            filename = ('normalized-baseline.private.json' if part == 'baseline'
                        else f'{part}.private.json')
            _, digest = read_json(base / pair / filename)
            must(calibration['receipt_sha256'].get(f'{pair}_{part}') == digest,
                 'calibration input receipt bytes changed')
    for pair, mode, expected in (
            ('positive', 'neutral', 0.0),
            ('positive', 'gui-positive', 1.0),
            ('negative', 'neutral', 0.0),
            ('negative', 'gui-wrong-variant', 0.0)):
        folder = base / pair / mode
        result, _ = read_json(folder / 'result.json')
        before, before_sha = read_json(folder / 'private-before.json')
        after, after_sha = read_json(folder / 'private-after.json')
        pre_edit, pre_edit_sha = read_json(folder / 'private-pre-edit.json')
        if mode == 'neutral':
            check_baseline(case, before)
        must(result.get('schema') == 'envloop-magento-original-gui-control-v3' and
             result.get('task_id') == case['task_id'] and
             result.get('package_sha256') == case['package_sha256'] and
             result.get('before_sha256') == before_sha and
             result.get('after_sha256') == after_sha and
             result.get('pre_edit_sha256') == pre_edit_sha and
             before == pre_edit and
             result.get('model_calls') ==
             result.get('official_final_tasks_admitted') == 0 and
             result.get('external_requests_blocked') == 0 and
             result.get('quote', {}).get('release_modal_guard', {}).get(
                 'obstruction_clear_before_business_edit') is True and
             result.get('quote', {}).get('quote_visible_in_native_cms') is True,
             'GUI snapshot/quote/guard/evaluation boundary changed')
        replay = score_saved_state(case, before, after)
        must(replay == result.get('score') and replay['score'] == expected and
             replay['independent_saved_state'] is True,
             'saved SQL/search snapshot replay disagrees with GUI score')
        saved = result.get('saved')
        must(isinstance(saved, list) and len(saved) >= 1 and
             all(row.get('native_save_status') in (200, 302) and
                 sha((folder / f"private-save-{row['entity_id']}.png").read_bytes()) ==
                 row.get('screenshot_sha256') for row in saved) and
             sha((folder / 'private-quote-page.png').read_bytes()) ==
             result['quote'].get('screenshot_sha256'),
             'native GUI save/quote screenshot bytes changed')
    reset, _ = read_json(base / 'negative/fresh-reset.private.json')
    sources = {
        'first_before': base / 'positive/gui-positive/private-before.json',
        'second_before': base / 'negative/gui-wrong-variant/private-before.json',
        'first_seed': base / 'positive/seed.private.json',
        'second_seed': base / 'negative/seed.private.json',
        'first_runtime': base / 'positive/runtime.private.json',
        'second_runtime': base / 'negative/runtime.private.json',
        'first_finalization': base / 'positive/finalization.private.json',
        'second_finalization': base / 'negative/finalization.private.json',
    }
    values = []
    for key, path in sources.items():
        value, digest = read_json(path)
        must(reset.get('input_sha256', {}).get(key) == digest,
             'fresh reset evidence input bytes changed')
        values.append(value)
    replay = reset_verifier.audit(case, *values)
    must(reset == {**replay, 'input_sha256': reset['input_sha256']} and
         reset.get('official_final_tasks_admitted') == 0,
         'fresh clone reset cannot be reproduced from saved native state')
    return calibration_sha


def assert_disposable_pair_absent() -> bool:
    """Read-only Docker inspect; failure to contact Docker is not absence."""
    for name in (sweep.APP, sweep.SEARCH):
        result = subprocess.run(
            ['docker', '--context', CONTEXT, 'container', 'inspect', name],
            capture_output=True, text=True, timeout=30)
        must(result.returncode == 1 and result.stdout.strip() == '[]' and
             result.stderr.strip() in (
                 f'Error response from daemon: No such container: {name}',
                 f'Error response from daemon: No such object: {name}'),
             'disposable application or native-search container is present, '
             'or Docker absence could not be verified')
    return True


def validate_source_bindings(root: Path, plan: Path, source: Path,
                             cron: Path, freeze_file: Path) -> tuple[dict, dict, str]:
    """Recompute hashes against the root source without root-bound globals."""
    freeze, freeze_sha = read_json(freeze_file)
    v3, v3_sha = read_json(
        root / 'work/magento-original/clean-v3-freeze-20260928.private.json')
    old, old_sha = read_json(cron)
    public, _ = read_json(
        root / 'docs/evidence/magento-clean-100-v4-freeze-2026-09-29.json')
    must(freeze_sha == recovery.FREEZE_SHA and
         sha(plan.read_bytes()) == recovery.PLAN_SHA and
         freeze.get('schema') == v4.SCHEMA and
         freeze.get('status') == 'pre_result_chunked_evaluator_controls_only' and
         freeze.get('ordered_case_count') == 100 and
         freeze.get('max_cases_per_dispatch') == 5 and
         freeze.get('whole_case_retry_cap_per_id') == 1 and
         freeze.get('study_wide_infrastructure_retry_cap') == 20 and
         freeze.get('historical_v3_controls_reused') == 0 and
         freeze.get('model_calls') == freeze.get('official_final_admitted') == 0 and
         freeze.get('plan_sha256') == recovery.PLAN_SHA and
         freeze.get('parent_v3_freeze_sha256') == v3_sha and
         freeze.get('parent_cron_freeze_sha256') == old_sha and
         freeze.get('parent_runtime_fingerprint_sha256') ==
         old.get('runtime_fingerprint_sha256') and
         v3.get('ordered_task_identity_sha256') ==
         freeze.get('ordered_task_identity_sha256') and
         public.get('schema') == 'envloop-magento-clean-100-freeze-public-v4' and
         public.get('private_freeze_sha256') == freeze_sha and
         public.get('parent_v3_freeze_sha256') == v3_sha and
         public.get('plan_sha256') == recovery.PLAN_SHA and
         public.get('ordered_task_identity_sha256') ==
         freeze.get('ordered_task_identity_sha256') and
         public.get('runtime_fingerprint_sha256') ==
         old.get('runtime_fingerprint_sha256') and
         public.get('model_calls') == public.get('official_final_admitted') == 0,
         'v4 freeze, parent runtime, ordered plan, or published receipt changed')
    must(set(freeze.get('code_sha256', {})) == set(v4.CODE_FILES) and
         all(sha((root / name).read_bytes()) == digest
             for name, digest in freeze['code_sha256'].items()),
         'frozen Magento evaluator source bytes changed')
    must(sha((root / 'tools/magento_clean_100_v4.py').read_bytes()) ==
         sha(Path(v4.__file__).read_bytes()) and
         sha((root / 'tools/magento_v4_preconfig_startup_amendment_20260929.py')
             .read_bytes()) == sha(Path(recovery.__file__).read_bytes()),
         'loaded read-only validator differs from frozen repository source')
    revision = subprocess.run(
        ['git', '-C', str(source), 'rev-parse', 'HEAD'],
        check=True, capture_output=True, text=True, timeout=15).stdout.strip()
    must(revision == freeze.get('source_commit') and
         revision == v3.get('source_commit'),
         'original Magento source checkout changed')
    return freeze, old, freeze_sha


def validate_plan(plan: Path, expected_sha: str) -> list[dict]:
    raw = plan.read_bytes()
    value = json.loads(raw)
    must(sha(raw) == expected_sha and
         value.get('schema') == PLAN_SCHEMA and
         value.get('status') == 'offline_candidates_not_gui_admitted' and
         value.get('official_final_admitted_count') == 0,
         'candidate plan bytes or unadmitted status changed')
    cells = value.get('cases', {})
    must({key: len(value) for key, value in cells.items()} ==
         {'train': 20, 'selection': 20, 'official_candidate': 100},
         'candidate plan split sizes changed')
    all_cases = [case for group in cells.values() for case in group]
    cases = cells['official_candidate']
    must(len({row['task_id'] for row in all_cases}) == 140 and
         len({row['package_sha256'] for row in all_cases}) == 140 and
         all(row['package_sha256'] == digest(
             {key: val for key, val in row.items()
              if key != 'package_sha256'}) and
             row['quote_page_body_sha256'] ==
             sha(row['quote_page_body'].encode()) and
             len(row['target_variants']) == 5 and
             row.get('split') == 'official_candidate' for row in cases),
         'distinct task package or quote-body digest changed')
    return cases


def audit_partial(repo_root: Path, run_dir: Path, *, check_containers=True) -> dict:
    root, run = repo_root.resolve(), run_dir.resolve()
    must(run == root / RUN_REL and run.is_dir() and not run_dir.is_symlink(),
         'read-only audit requires the exact original v4 run directory')
    plan, source, cron, freeze_file = (
        root / PLAN_REL, root / SOURCE_REL, root / CRON_FREEZE_REL,
        root / V4_FREEZE_REL)
    must(sha(plan.read_bytes()) == recovery.PLAN_SHA and
         sha(freeze_file.read_bytes()) == recovery.FREEZE_SHA,
         'exact frozen plan or v4 source bytes changed')
    freeze, old, freeze_sha = validate_source_bindings(
        root, plan, source, cron, freeze_file)
    cases = validate_plan(plan, recovery.PLAN_SHA)
    must(v4.case_identity_digest(cases) ==
         freeze['ordered_task_identity_sha256'],
         'ordered candidate identity changed')
    rows, journal_raw = read_journal_prefix(run / 'journal.private.jsonl')
    check_chunk(rows, cases, freeze, freeze_sha)
    # The frozen runner validators are an additional cross-check. The
    # independent checks above and saved-state replays below are decisive.
    v4.validate_run_header(rows, freeze_sha, freeze)
    v4.validate_case_sequence(rows, cases)
    v4.validate_chunk_boundaries(rows, cases, freeze, freeze_sha)
    v4.validate_attempt_inventory(run, rows)
    retry = check_preconfig_retry(root, run, rows, cases[0], freeze_sha)
    receipts = [check_successful_case(
        run, rows, index, attempt, cases[index],
        old['runtime_fingerprint_sha256']) for index, attempt in ((0, 1), (1, 0))]
    must([r['calibration_sha256'] for r in rows if r.get('event') ==
          'case_completed'] == receipts,
         'completed receipt order differs from independent replay')
    absent = assert_disposable_pair_absent() if check_containers else False
    must(absent, 'live container absence was not independently verified')
    chunk = rows[-1]
    report = {
        'schema': SCHEMA,
        'date': '2026-09-29',
        'status': 'first_v4_chunk_independently_audited_no_final_admissions',
        'independent_auditor_source_sha256': sha(Path(__file__).read_bytes()),
        'source_freeze_sha256': freeze_sha,
        'source_commit': freeze['source_commit'],
        'plan_sha256': recovery.PLAN_SHA,
        'ordered_task_identity_sha256': freeze['ordered_task_identity_sha256'],
        'preconfig_amendment_freeze_sha256': retry['supplement_sha256'],
        'preconfig_cleanup_receipt_sha256': retry['reconciliation_sha256'],
        'journal_sha256': sha(journal_raw),
        'chunk_receipt_sha256': sha(canonical(chunk)),
        'completed_calibration_receipts_sha256':
            chunk['completed_calibration_receipts_sha256'],
        'planned_distinct_candidate_controls': 100,
        'completed_distinct_candidate_controls': 2,
        'positive_saved_state_pass': 2,
        'wrong_variant_saved_state_rejected': 2,
        'fresh_clone_material_reset_pass': 2,
        'failed_preconfig_infrastructure_attempts': 1,
        'reconciled_same_id_infrastructure_retries': 1,
        'invalid_attempts_by_classification': {retry['classification']: 1},
        'disposable_app_and_native_search_containers_absent': True,
        'historical_v2_v3_controls_reused': 0,
        'model_calls': 0,
        'official_final_admitted': 0,
    }
    must(set(report) == PUBLIC_FIELDS, 'public output field allowlist changed')
    return report


PUBLIC_FIELDS = {
    'schema', 'date', 'status', 'independent_auditor_source_sha256',
    'source_freeze_sha256', 'source_commit',
    'plan_sha256', 'ordered_task_identity_sha256',
    'preconfig_amendment_freeze_sha256', 'preconfig_cleanup_receipt_sha256',
    'journal_sha256', 'chunk_receipt_sha256',
    'completed_calibration_receipts_sha256',
    'planned_distinct_candidate_controls', 'completed_distinct_candidate_controls',
    'positive_saved_state_pass', 'wrong_variant_saved_state_rejected',
    'fresh_clone_material_reset_pass', 'failed_preconfig_infrastructure_attempts',
    'reconciled_same_id_infrastructure_retries',
    'invalid_attempts_by_classification',
    'disposable_app_and_native_search_containers_absent',
    'historical_v2_v3_controls_reused', 'model_calls', 'official_final_admitted',
}


def render_markdown(report: dict) -> str:
    must(set(report) == PUBLIC_FIELDS, 'unexpected public report fields')
    return (
        '# Magento v4: independent audit of the first two controls\n\n'
        'The first bounded chunk contains **2 of 100** planned, ordered '
        'original-Magento evaluator GUI controls. Both saved-state positives '
        'score 1, both wrong-variant negatives score 0, and both fresh-clone '
        'material resets pass after independent replay of retained SQL/search '
        'snapshots. This is evaluator calibration only: **0 model calls and '
        '0 official final tasks admitted**.\n\n'
        'One first-case infrastructure attempt failed before task seeding or '
        'GUI action when the unconfigured Magento HTTP endpoint did not become '
        'ready. The frozen supplemental audit established the unchanged '
        'unseeded SQL/search/cron state; an exact disposable app/search pair '
        'was retired and the same task was retried once. The journal, source '
        'freeze, ordered plan, supplemental freeze, cleanup receipt, and '
        'two-case chunk receipt are bound by hashes in the adjacent JSON. '
        'A read-only live Docker query found both disposable container names '
        'absent at audit time.\n\n'
        'Historical v2/v3 partial controls contribute zero to this v4 count. '
        'The remaining 98 cases, per-task admission, researcher campaigns, '
        'and final model outcomes are not established by this evidence. '
        'Raw task and saved-state files remain in private evaluator storage; '
        'authorized reviewers can rerun the source-bound auditor against '
        'those files.\n'
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, required=True)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--public-json', type=Path)
    parser.add_argument('--public-md', type=Path)
    args = parser.parse_args()
    must((args.public_json is None) == (args.public_md is None),
         'JSON and Markdown public outputs must be requested together')
    report = audit_partial(args.repo_root, args.run_dir)
    if args.public_json is not None:
        public_dir = (Path(__file__).resolve().parents[1] /
                      'docs/evidence').resolve()
        for target in (args.public_json, args.public_md):
            target = target.resolve()
            must(target.is_relative_to(public_dir) and
                 not target.exists(),
                 'new public output must be under auditor checkout docs/evidence')
        args.public_json.parent.mkdir(parents=True, exist_ok=True)
        args.public_json.write_text(json.dumps(report, indent=2, sort_keys=True) +
                                    '\n', encoding='utf-8')
        args.public_md.write_text(render_markdown(report), encoding='utf-8')
    print(json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    main()
