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


def task(index: int, case: dict, plan: Path, plan_sha: str,
         source: Path, root: Path, journal: Path) -> dict:
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
        run_step(out, journal, index, f'{pair}-prepare',
                 [str(sys.executable), str(ROOT / 'tools/start_magento_native_sidecar_clone_v1.py'),
                  '--expected-search-sha256', SEARCH_SHA, '--out', str(prep)],
                 timeout=TIMEOUT['prepare'])
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
        receipts[pair] = {'seed': seed, 'baseline': baseline,
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
    args = parser.parse_args()
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
    manifest = json.loads(raw_plan)
    cases = manifest['cases'][args.split]
    require(len(cases) == PLAN_CELLS[args.split] and
            0 <= args.start_index < len(cases) and
            1 <= args.limit <= len(cases) - args.start_index,
            'declared split/window invalid')
    require(all(load_case(plan, args.plan_sha256, case['task_id']) == case
                for case in cases), 'task package binding changed')
    recovery_sha = None
    if args.recovery_of is not None:
        previous = args.recovery_of.resolve()
        require(previous.is_relative_to(private) and previous.is_file() and
                args.limit == 1,
                'single-case private recovery journal required')
        previous_raw = previous.read_bytes()
        events = [json.loads(line) for line in previous_raw.splitlines()]
        require(any(row.get('event') == 'sweep_stopped' for row in events) and
                events[-1].get('event') ==
                'operator_reconciled_pre_task_prepare_failure' and
                events[-1].get('index') == args.start_index and
                events[-1].get('task_seeded') is False and
                events[-1].get('both_containers_cleaned') is True,
                'prior pre-task failure was not explicitly reconciled')
        recovery_sha = sha(previous_raw)
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
                           'model_calls': 0, 'official_final_admitted': False})
    passed = 0
    try:
        for index in range(args.start_index, args.start_index + args.limit):
            result = task(index, cases[index], plan, args.plan_sha256,
                          source, out, journal)
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
