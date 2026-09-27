"""Run bounded, journaled evaluator-only Magento GUI admission controls.

One task uses two fresh app/search pairs: neutral fixture + positive; neutral
fixture + exact cold-reset audit + wrong-variant negative. A failed/uncertain
step stops the sweep and is never an automatic model zero or silent retry.
The output is private and does not grant official final admission by itself.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from magento_catalog_factory.plan import ROOT, require
from magento_catalog_factory.seed import load_case
from tools import magento_cron_runtime_contract_v1 as cron_contract


IMAGE_SOURCE_COMMIT = '6473f72db5dcefc97b5725b59e734504edc28a21'
SEARCH_SHA = '54ca1d8ef5cb82ed879338e6740a589a930e50cd8a54f495c234c5f5b0acf6fb'
APP = 'envloop-magento-original-control'
SEARCH = 'envloop-magento-native-es'
PLAN_CELLS = {'train_policy_development': 4, 'official_candidate': 100}
TIMEOUT = {'prepare': 900, 'seed': 120, 'neutral': 900,
           'finalize': 120, 'runtime': 90, 'positive': 900,
           'reset': 90, 'wrong_variant': 600}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def write_new(path: Path, value: dict) -> str:
    raw = (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return sha(raw)


def append_event(path: Path, event: dict) -> None:
    raw = (json.dumps(event, sort_keys=True) + '\n').encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def run_step(root: Path, journal: Path, index: int, step: str,
             command: list[str], *, timeout: int) -> dict:
    append_event(journal, {'event': 'step_intent', 'index': index,
                           'step': step, 'time': time.time(),
                           'command_sha256': sha(json.dumps(command).encode())})
    try:
        outcome = subprocess.run(command, cwd=ROOT, capture_output=True,
                                 timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        append_event(journal, {'event': 'step_timeout_uncertain',
                               'index': index, 'step': step, 'time': time.time()})
        raise RuntimeError(f'{step}: timeout uncertain; no automatic retry') from None
    raw = {'exit_code': outcome.returncode,
           'stdout_sha256': sha(outcome.stdout),
           'stderr_sha256': sha(outcome.stderr),
           'stdout_bytes': len(outcome.stdout),
           'stderr_bytes': len(outcome.stderr)}
    if outcome.returncode != 0:
        # Preserve the actual diagnostic bytes under ignored, private work/.
        # Hashes alone cannot distinguish a provider/process timeout from a
        # changed application state during later controlled reconciliation.
        for label, data in (('stdout', outcome.stdout),
                            ('stderr', outcome.stderr)):
            if data:
                fd = os.open(root / f'{step}-{label}.private.bin',
                             os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
    write_new(root / f'{step}-process.private.json', raw)
    append_event(journal, {'event': 'step_finished', 'index': index,
                           'step': step, 'time': time.time(), **raw})
    require(outcome.returncode == 0,
            f'{step}: command failed; private process hashes retained')
    try:
        message = json.loads(outcome.stdout.splitlines()[-1])
    except (IndexError, ValueError, UnicodeError):
        raise RuntimeError(f'{step}: no structured completion') from None
    require(message.get('official_final_tasks_admitted') == 0,
            f'{step}: candidate control unexpectedly claimed admission')
    return message


def assert_absent() -> None:
    for name in (APP, SEARCH):
        result = subprocess.run(['docker', '--context', 'colima-cua-scale',
                                 'inspect', name], capture_output=True,
                                timeout=20)
        require(result.returncode != 0,
                f'{name} exists; inspect/clean manually before dispatch')


def cleanup_pair(runtime_path: Path) -> None:
    runtime = json.loads(runtime_path.read_bytes())
    app = json.loads(subprocess.check_output(
        ['docker', '--context', 'colima-cua-scale', 'inspect', APP],
        timeout=30))[0]
    sidecar = json.loads(subprocess.check_output(
        ['docker', '--context', 'colima-cua-scale', 'inspect', SEARCH],
        timeout=30))[0]
    require(sha(app['Id'].encode()) == runtime['app']['container_id_sha256'] and
            sha(sidecar['Id'].encode()) == runtime['sidecar_id_sha256'] and
            not app['Mounts'] and not sidecar['Mounts'],
            'cleanup refused another runtime identity or mounted container')
    for name in (APP, SEARCH):
        subprocess.run(['docker', '--context', 'colima-cua-scale',
                        'stop', name], check=True, timeout=60,
                       capture_output=True)
        subprocess.run(['docker', '--context', 'colima-cua-scale',
                        'rm', name], check=True, timeout=30,
                       capture_output=True)
    assert_absent()


def validate_preseed_search_drift_recovery(previous: Path,
                                           events: list[dict],
                                           last: dict) -> None:
    """Accept only the one case-31 unseeded pair retired by its exact audit."""
    case_dir = previous.parent / 'case-031/positive'
    cleanup = case_dir / 'index-drift-cleanup.private.json'
    audit = case_dir / 'index-drift-audit.private.json'
    require(cleanup.is_file() and audit.is_file() and
            sha(cleanup.read_bytes()) == last.get('cleanup_receipt_sha256') and
            sha(audit.read_bytes()) == last.get('audit_sha256'),
            'unseeded search-drift audit/cleanup receipt changed')
    record = json.loads(cleanup.read_bytes())
    witness = json.loads(audit.read_bytes())
    require(record.get('schema') ==
            'envloop-magento-preseed-search-drift-cleanup-private-v1' and
            witness.get('schema') ==
            'envloop-magento-preseed-search-drift-private-audit-v1' and
            record.get('case_index') == witness.get('case_index') == 31 and
            record.get('original_journal_sha256') ==
            witness.get('original_journal_sha256') ==
            '4fea2b8ca9d9edb53db21dd6dd6493613e95bc44e2fe73fab9664f37cdacd196' and
            record.get('audit_sha256') == last.get('audit_sha256') and
            record.get('task_seeded') is False and
            record.get('both_containers_cleaned') is True and
            record.get('model_calls') ==
            record.get('official_final_admitted') == 0 and
            witness.get('observed_search_sha256') ==
            '4bd64ae0b2032f221f8c2e56c1dd243f09677ce386860a6f4eb6d582e36ddc20' and
            witness.get('frozen_search_sha256') == SEARCH_SHA and
            witness.get('quote_pages') == 0 and
            any(row.get('event') == 'step_finished' and
                row.get('index') == 31 and
                row.get('step') == 'positive-prepare' and
                row.get('exit_code') != 0 for row in events) and
            not any(row.get('index') == 31 and
                    row.get('step', '').endswith('-seed')
                    for row in events),
            'only the exact unseeded case-31 drift may be retried once')


def task(index: int, case: dict, plan: Path, plan_sha: str,
         source: Path, root: Path, journal: Path,
         train_cron_never_autostart: bool = False,
         cellwide_freeze: dict | None = None) -> dict:
    case_dir = root / f'case-{index:03d}'
    require(not case_dir.exists(),
            'existing case attempt must not be silently retried')
    case_dir.mkdir(mode=0o700)
    required = [str(sys.executable), '--plan', str(plan),
                '--plan-sha256', plan_sha, '--task-id', case['task_id']]
    receipts = {}
    for pair in ('positive', 'negative'):
        assert_absent()
        out = case_dir / pair
        out.mkdir(mode=0o700)
        prep = out / 'prepare.private.json'
        prepare_command = [str(sys.executable),
                           str(ROOT / 'tools/start_magento_native_sidecar_clone_v1.py'),
                           '--expected-search-sha256', SEARCH_SHA, '--out', str(prep)]
        if train_cron_never_autostart or cellwide_freeze is not None:
            prepare_command.append('--train-probe-disable-cron-autostart')
        run_step(out, journal, index, f'{pair}-prepare',
                 prepare_command,
                 timeout=TIMEOUT['prepare'])
        if cellwide_freeze is not None:
            cron_contract.validate_prepared(
                json.loads(prep.read_bytes()),
                config_sha256=cellwide_freeze['runtime']['cron_config_sha256'])
        seed = out / 'seed.private.json'
        run_step(out, journal, index, f'{pair}-seed',
                 [str(sys.executable), '-m', 'magento_catalog_factory.seed',
                  *required[1:], '--container', APP,
                  '--http-port', '7794', '--control-port', '7795',
                  '--out', str(seed)], timeout=TIMEOUT['seed'])
        seed_receipt = json.loads(seed.read_bytes())
        require(seed_receipt['task_id'] == case['task_id'] and
                type(seed_receipt['page_id']) is int and
                seed_receipt['page_id'] > 0,
                'trusted quote page ID changed')
        page_id = str(seed_receipt['page_id'])
        neutral_dir = out / 'neutral'
        run_step(out, journal, index, f'{pair}-neutral',
                 [str(sys.executable), str(ROOT / 'tools/qualify_magento_original_catalog_v1.py'),
                  *required[1:], '--source', str(source),
                  '--container', APP, '--http-port', '7794',
                  '--control-port', '7795', '--page-id', page_id,
                  '--search-host', SEARCH, '--mode', 'neutral',
                  '--out', str(neutral_dir)], timeout=TIMEOUT['neutral'])
        baseline = out / 'normalized-baseline.private.json'
        finalization = out / 'finalization.private.json'
        run_step(out, journal, index, f'{pair}-finalize',
                 [str(sys.executable), str(ROOT / 'tools/finalize_magento_normalized_baseline_v1.py'),
                  *required[1:], '--neutral-result', str(neutral_dir / 'result.json'),
                  '--neutral-after', str(neutral_dir / 'private-after.json'),
                  '--container', APP, '--http-port', '7794',
                  '--control-port', '7795', '--page-id', page_id,
                  '--search-host', SEARCH, '--baseline-out', str(baseline),
                  '--out', str(finalization)], timeout=TIMEOUT['finalize'])
        runtime = out / 'runtime.private.json'
        run_step(out, journal, index, f'{pair}-runtime',
                 [str(sys.executable), str(ROOT / 'tools/capture_magento_native_runtime_v1.py'),
                  *required[1:], '--baseline', str(baseline),
                  '--out', str(runtime)], timeout=TIMEOUT['runtime'])
        if pair == 'positive':
            control_dir = out / 'gui-positive'
            result = run_step(out, journal, index, f'{pair}-gui',
                 [str(sys.executable), str(ROOT / 'tools/qualify_magento_original_catalog_v1.py'),
                  *required[1:], '--source', str(source), '--container', APP,
                  '--http-port', '7794', '--control-port', '7795',
                  '--page-id', page_id, '--search-host', SEARCH,
                  '--mode', 'positive', '--out', str(control_dir)],
                 timeout=TIMEOUT['positive'])
            require(result['score'] == 1.0, 'known-positive saved state failed')
        else:
            reset = out / 'fresh-reset.private.json'
            first = receipts['positive']
            run_step(out, journal, index, 'fresh-reset',
                 [str(sys.executable), str(ROOT / 'tools/audit_magento_original_fresh_reset_v1.py'),
                  *required[1:], '--first-before', str(first['baseline']),
                  '--second-before', str(baseline),
                  '--first-seed', str(first['seed']), '--second-seed', str(seed),
                  '--first-runtime', str(first['runtime']),
                  '--second-runtime', str(runtime),
                  '--first-finalization', str(first['finalization']),
                  '--second-finalization', str(finalization),
                  '--out', str(reset)], timeout=TIMEOUT['reset'])
            control_dir = out / 'gui-wrong-variant'
            result = run_step(out, journal, index, f'{pair}-gui',
                 [str(sys.executable), str(ROOT / 'tools/qualify_magento_original_catalog_v1.py'),
                  *required[1:], '--source', str(source), '--container', APP,
                  '--http-port', '7794', '--control-port', '7795',
                  '--page-id', page_id, '--search-host', SEARCH,
                  '--mode', 'wrong-variant', '--out', str(control_dir)],
                 timeout=TIMEOUT['wrong_variant'])
            require(result['score'] == 0.0, 'wrong-variant negative did not fail')
        receipts[pair] = {'prepare': prep, 'seed': seed, 'baseline': baseline,
                          'finalization': finalization, 'runtime': runtime,
                          'control': control_dir}
        cleanup_pair(runtime)
        append_event(journal, {'event': 'pair_cleanup_verified',
                               'index': index, 'pair': pair, 'time': time.time()})
    values = [receipts[pair] for pair in ('positive', 'negative')]
    summary = {'schema': 'envloop-magento-original-gui-case-calibration-v1',
               'task_id': case['task_id'], 'package_sha256': case['package_sha256'],
               'split': case['split'], 'policy_kind': case['policy_kind'],
               'positive_score': 1.0, 'wrong_variant_score': 0.0,
               'fresh_reset_passed': True,
               'model_calls': 0, 'official_final_admitted': False,
               'receipt_sha256': {f'{pair}_{key}': sha(Path(path).read_bytes())
                                  for pair, row in zip(('positive', 'negative'), values)
                                  for key, path in row.items() if key != 'control'}}
    if cellwide_freeze is not None:
        summary['cellwide_cron_runtime_fingerprint_sha256'] = (
            cellwide_freeze['runtime_fingerprint_sha256'])
    digest = write_new(case_dir / 'calibration.private.json', summary)
    append_event(journal, {'event': 'task_gui_calibrated',
                           'index': index, 'task_id': case['task_id'],
                           'receipt_sha256': digest, 'time': time.time()})
    return {'index': index, 'calibrated': True, 'receipt_sha256': digest}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--plan-sha256', required=True)
    parser.add_argument('--split', choices=tuple(PLAN_CELLS), required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--out-dir', type=Path, required=True)
    parser.add_argument('--start-index', type=int, default=0)
    parser.add_argument('--limit', type=int, required=True)
    parser.add_argument('--recovery-of', type=Path,
                        help='private stopped sweep journal for one controlled retry')
    parser.add_argument('--train-cron-never-autostart', action='store_true',
                        help='train-policy GUI control under proposed revised startup')
    parser.add_argument('--cellwide-cron-freeze', type=Path,
                        help='private post-train freeze required for 100 fresh official-candidate controls')
    args = parser.parse_args()
    require(not args.train_cron_never_autostart or
            args.split == 'train_policy_development',
            'cron startup probe is train-only until cell-wide runtime freeze')
    require(args.split != 'official_candidate' or args.cellwide_cron_freeze is not None,
            'historical Magento runtime stopped; cell-wide cron freeze required')
    require(args.cellwide_cron_freeze is None or
            (args.split == 'official_candidate' and
             args.start_index == 0 and args.limit == 100 and
             args.recovery_of is None and
             not args.train_cron_never_autostart),
            'revised Magento cell requires one fresh 0..99 sweep with no per-case recovery')
    private = (ROOT / 'work').resolve()
    plan, source, out = args.plan.resolve(), args.source.resolve(), args.out_dir.resolve()
    require(plan.is_relative_to(private) and source.is_relative_to(private)
            and out.is_relative_to(private) and not out.exists(),
            'fresh private work/ sweep and source required')
    commit = subprocess.run(['git', '-C', str(source), 'rev-parse', 'HEAD'],
                            capture_output=True, text=True, check=True,
                            timeout=15).stdout.strip()
    require(commit == IMAGE_SOURCE_COMMIT, 'Magento login source revision changed')
    raw_plan = plan.read_bytes()
    require(sha(raw_plan) == args.plan_sha256, 'private task plan changed')
    cellwide_freeze = None
    freeze_sha = None
    if args.cellwide_cron_freeze is not None:
        freeze_path = args.cellwide_cron_freeze.resolve()
        require(freeze_path.is_relative_to(private) and freeze_path.is_file(),
                'private cell-wide runtime freeze under work/ required')
        probe_dir = ROOT / 'work/magento-original/cron-never-autostart-train-probe-20260927-v2'
        train_dir = ROOT / 'work/magento-original/train-cron-never-autostart-gui-v1'
        cellwide_freeze, freeze_sha = cron_contract.validate_freeze(
            freeze_path, ROOT, probe_dir, train_dir)
        require(cellwide_freeze['final_candidate_plan_sha256'] == args.plan_sha256,
                'cell-wide freeze belongs to a different candidate plan')
    manifest = json.loads(raw_plan)
    cases = manifest['cases'][args.split]
    require(len(cases) == PLAN_CELLS[args.split] and
            0 <= args.start_index < len(cases) and
            1 <= args.limit <= len(cases) - args.start_index,
            'declared split/window invalid')
    require(all(load_case(plan, args.plan_sha256, case['task_id']) == case
                for case in cases), 'task package binding changed')
    recovery_sha = None
    recovery_kind = None
    if args.recovery_of is not None:
        previous = args.recovery_of.resolve()
        require(previous.is_relative_to(private) and previous.is_file() and
                args.limit == 1,
                'single-case private recovery journal required')
        previous_raw = previous.read_bytes()
        events = [json.loads(line) for line in previous_raw.splitlines()]
        last = events[-1]
        require(any(row.get('event') == 'sweep_stopped' for row in events) and
                last.get('index') == args.start_index and
                last.get('both_containers_cleaned') is True,
                'prior stopped task was not explicitly reconciled')
        if (last.get('event') ==
                'operator_reconciled_pre_task_prepare_failure' and
                last.get('task_seeded') is False):
            recovery_kind = 'unseeded_prepare_failure'
        elif (last.get('event') ==
              'operator_reconciled_cron_train_gui_interruption' and
              args.split == 'train_policy_development' and
              args.start_index == 0 and args.limit == 1 and
              args.train_cron_never_autostart and
              last.get('task_seeded') is True and
              last.get('negative_gui_attempted') is False):
            public_path = (ROOT / 'docs/evidence/'
                           'magento-cron-train-gui-interruption-2026-09-28.json')
            public = json.loads(public_path.read_bytes())
            original_lines = previous_raw.splitlines(keepends=True)
            require(len(original_lines) >= 3 and
                    sha(b''.join(original_lines[:-2])) ==
                    public['stopped_journal_sha256'] and
                    events[-3].get('event') == 'sweep_stopped' and
                    events[-2].get('event') ==
                    'operator_cron_train_gui_cleanup_intent' and
                    not any(row.get('index') == 0 and
                            row.get('step') == 'negative-gui'
                            for row in events[:-2]),
                    'original stopped train journal or edit boundary changed')
            cleanup = previous.parent / (
                'case-000/negative/train-interruption-cleanup.private.json')
            require(cleanup.is_file() and
                    sha(cleanup.read_bytes()) ==
                    last.get('cleanup_receipt_sha256'),
                    'train-only interruption cleanup receipt changed')
            record = json.loads(cleanup.read_bytes())
            require(record.get('schema') ==
                    'envloop-magento-cron-train-gui-cleanup-private-v1' and
                    record.get('original_stopped_journal_sha256') ==
                    public['stopped_journal_sha256'] and
                    record.get('plan_sha256') == args.plan_sha256 ==
                    public['train_plan_sha256'] and
                    record.get('audit_sha256') == last.get('audit_sha256') and
                    record.get('material_state_unchanged') is True and
                    record.get('saved_positive_score') == 1.0 and
                    record.get('negative_gui_attempted') is False and
                    record.get('both_containers_cleaned') is True and
                    record.get('model_calls') ==
                    record.get('official_final_admitted') == 0,
                    'only the exact cleaned train GUI interruption may retry')
            recovery_kind = 'cron_train_negative_neutral_once'
        elif (last.get('event') ==
              'operator_reconciled_pre_task_search_index_drift' and
              args.start_index == 31 and
              last.get('task_seeded') is False and
              last.get('both_containers_cleaned') is True):
            validate_preseed_search_drift_recovery(previous, events, last)
            recovery_kind = 'unseeded_search_index_drift_case31'
        elif (last.get('event') ==
              'operator_reconciled_postpositive_volatile' and
              last.get('task_seeded') is True):
            cleanup = (previous.parent / f'case-{args.start_index:03d}' /
                       'positive/recovery-cleanup.private.json')
            require(cleanup.is_file() and
                    sha(cleanup.read_bytes()) ==
                    last.get('cleanup_receipt_sha256') and
                    json.loads(cleanup.read_bytes()).get('task_id') ==
                    cases[args.start_index]['task_id'],
                    'postpositive scorer/cleanup receipt binding changed')
            recovery_kind = 'postpositive_volatile_metadata_only'
        elif (last.get('event') ==
              'operator_reconciled_negative_neutral_ui_unstable' and
              last.get('task_seeded') is True and
              last.get('negative_gui_attempted') is False):
            case_dir = previous.parent / f'case-{args.start_index:03d}'
            cleanup = case_dir / 'negative/recovery-cleanup.private.json'
            require(cleanup.is_file() and
                    sha(cleanup.read_bytes()) ==
                    last.get('cleanup_receipt_sha256'),
                    'stopped negative-neutral cleanup receipt changed')
            record = json.loads(cleanup.read_bytes())
            require(record.get('schema') ==
                    'envloop-magento-negative-neutral-ui-cleanup-private-v1' and
                    record.get('task_id') ==
                    cases[args.start_index]['task_id'] and
                    record.get('plan_sha256') == args.plan_sha256 and
                    record.get('material_state_unchanged') is True and
                    record.get('saved_positive_score') == 1.0 and
                    record.get('negative_gui_attempted') is False and
                    record.get('both_containers_cleaned') is True and
                    record.get('model_calls') ==
                    record.get('official_final_admitted') == 0 and
                    any(row.get('event') == 'step_finished' and
                        row.get('index') == args.start_index and
                        row.get('step') == 'negative-neutral' and
                        row.get('exit_code') != 0 for row in events) and
                    not any(row.get('event') == 'step_intent' and
                            row.get('index') == args.start_index and
                            row.get('step') == 'negative-gui'
                            for row in events),
                    'one incomplete negative-neutral control required')
            recovery_kind = 'postpositive_negative_neutral_ui_unstable'
        else:
            raise ValueError('prior failure type has no approved one-case recovery')
        recovery_sha = sha(previous_raw)
        for candidate in (ROOT / 'work/magento-original').glob('*/events.private.jsonl'):
            if candidate.resolve() == previous:
                continue
            lines = candidate.read_bytes().splitlines()
            if not lines:
                continue
            initial = json.loads(lines[0])
            require(initial.get('recovery_of_private_journal_sha256') !=
                    recovery_sha,
                    'one-case recovery already dispatched for this stopped journal')
    out.mkdir(parents=True, mode=0o700)
    lock_path = ROOT / 'work/magento-original/exclusive-worker.lock'
    lock_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise RuntimeError('another Magento admission worker is active') from None
    assert_absent()
    journal = out / 'events.private.jsonl'
    append_event(journal, {'event': 'sweep_started', 'time': time.time(),
                           'plan_sha256': args.plan_sha256,
                           'split': args.split, 'start_index': args.start_index,
                           'limit': args.limit, 'max_concurrent_pairs': 1,
                           'recovery_of_private_journal_sha256': recovery_sha,
                           'recovery_kind': recovery_kind,
                           'train_cron_never_autostart': args.train_cron_never_autostart,
                           'cellwide_cron_freeze_sha256': freeze_sha,
                           'runtime_fingerprint_sha256': (
                               cellwide_freeze['runtime_fingerprint_sha256']
                               if cellwide_freeze is not None else None),
                           'model_calls': 0, 'official_final_admitted': False})
    passed = 0
    try:
        for index in range(args.start_index, args.start_index + args.limit):
            result = task(index, cases[index], plan, args.plan_sha256,
                          source, out, journal,
                          train_cron_never_autostart=args.train_cron_never_autostart,
                          cellwide_freeze=cellwide_freeze)
            passed += 1
            print(json.dumps({'status': 'candidate_gui_calibrated',
                              'completed_in_run': passed,
                              'requested': args.limit,
                              'official_final_admitted': 0}), flush=True)
        append_event(journal, {'event': 'sweep_completed', 'time': time.time(),
                               'passed': passed, 'requested': args.limit,
                               'official_final_admitted': 0})
    except Exception as error:
        append_event(journal, {'event': 'sweep_stopped', 'time': time.time(),
                               'passed': passed, 'requested': args.limit,
                               'error_type': type(error).__name__,
                               'error_message_sha256': sha(str(error).encode()),
                               'official_final_admitted': 0})
        raise
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


if __name__ == '__main__':
    main()
