"""Reviewed, one-use detached host supervision for reference continuation.

This adds a host lifetime only. It never changes Native10 actor/lifecycle
limits, retries a worker, or turns a host exit into native qualification.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
AUTHORITY_ROOT = ROOT / 'work/magento-reference-host-authority-v1.private'
MODULE = 'magento_catalog_factory.native_reference_host_supervisor_v1'
WORKER_MODULE = 'magento_catalog_factory.native_selection_reference_continuation_v1'
SUPERVISOR_SOURCE = 'magento_catalog_factory/native_reference_host_supervisor_v1.py'
WORKER_SOURCE = 'magento_catalog_factory/native_selection_reference_continuation_v1.py'
SECONDS_LIMIT = 36000
SPEC_SCHEMA = 'magento-reference-host-supervisor-review-v1'
ENVIRONMENT_OVERLAY = {'PYTHONPATH': '.:src:tests', 'PYTHONUNBUFFERED': '1'}


class SupervisionError(ValueError):
    pass


def require(value, code):
    if not value:
        raise SupervisionError(code)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def _sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def _no_alias(path):
    path = Path(path)
    require(path.is_absolute() and str(path) == str(path.resolve()), 'canonical_absolute_path_required')
    require(not any(part.is_symlink() for part in (path, *path.parents)), 'symlink_path_forbidden')
    return path


def _private(path, expected=None):
    path = _no_alias(path)
    require(path.is_file() and path.stat().st_mode & 0o077 == 0 and path.stat().st_size <= 1_000_000,
            'private_review_or_receipt_required')
    raw = path.read_bytes()
    require(expected is None or sha256(raw).hexdigest() == expected, 'private_review_or_receipt_changed')
    value = json.loads(raw)
    require(type(value) is dict, 'private_object_required')
    return value


def _write(path, value):
    path = _no_alias(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(canonical(value))
        stream.flush()
        os.fsync(stream.fileno())
    return {'path': str(path), 'sha256': _sha(path)}


def _log(stack, path):
    fd = os.open(_no_alias(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    return stack.enter_context(os.fdopen(fd, 'wb'))


def _now():
    return datetime.now(timezone.utc).isoformat()


def _interpreter_ref():
    # A virtualenv entry commonly symlinks to the system Python binary. Its
    # lexical launch path selects pyvenv.cfg and must never be dereferenced
    # in argv. This is the only path for which a symlink entry is permitted.
    executable = Path(sys.executable)
    require(executable.is_absolute() and str(executable) == os.path.normpath(str(executable)) and
            executable.is_file() and os.access(executable, os.X_OK), 'expected_interpreter_entry_required')
    resolved = _no_alias(executable.resolve())
    return {'path': str(executable), 'resolved_path': str(resolved), 'sha256': _sha(resolved)}


def _launch_environment(spec):
    # Preserve the runtime's inherited environment without writing or returning
    # it. Only this small, exact overlay is part of the reviewed document.
    return {**os.environ, **spec['environment_overlay']}


def _source_bindings(names):
    require(type(names) is list and names == sorted(set(names)) and
            SUPERVISOR_SOURCE in names and WORKER_SOURCE in names, 'exact_worker_sources_required')
    result = {}
    for name in names:
        require(type(name) is str and name == Path(name).as_posix() and not Path(name).is_absolute() and
                all(part not in ('.', '..') for part in Path(name).parts), 'source_path_unsafe')
        path = _no_alias(ROOT / name)
        require(path.is_file() and path.resolve().is_relative_to(ROOT.resolve()), 'source_file_required')
        result[name] = _sha(path)
    return result


def _output(path, *, fresh):
    path = _no_alias(path)
    require(path.is_relative_to((ROOT / 'work').resolve()) and path != ROOT / 'work',
            'supervisor_output_outside_work')
    if fresh:
        require(not path.exists(), 'fresh_supervisor_output_required')
    else:
        require(path.is_dir() and path.stat().st_mode & 0o077 == 0, 'private_supervisor_output_required')
    return path


def _argument_paths(argv):
    paths = {}
    for index, argument in enumerate(argv[4:], 4):
        name, separator, value = argument.partition('=')
        if not (name.startswith('--') and (name.endswith('-path') or name == '--output')):
            continue
        require(name not in paths, 'worker_path_argument_duplicated')
        if not separator:
            require(index + 1 < len(argv) and not argv[index + 1].startswith('--'),
                    'worker_path_argument_missing')
            value = argv[index + 1]
        require(value, 'worker_path_argument_missing')
        paths[name] = _no_alias(value)
    return paths


def _namespace_scope(argv, host_output):
    """Inspect path metadata only; no original or new task body is loaded."""
    paths = _argument_paths(argv)
    protected = []
    if '--output' in paths:
        protected.append(paths['--output'])
    if '--original-arguments-path' in paths:
        protected.append(paths['--original-arguments-path'].parent)
    for namespace in protected:
        require(host_output != namespace and not host_output.is_relative_to(namespace) and
                not namespace.is_relative_to(host_output), 'host_output_overlaps_worker_or_original_namespace')


def review_spec(*, worker_argv, cwd, output, worker_source_paths=None):
    """Build metadata for Root review; does not create files or processes."""
    require(type(worker_argv) is list and len(worker_argv) >= 4 and
            all(type(item) is str and item and '\0' not in item for item in worker_argv),
            'exact_worker_argv_required')
    interpreter = _interpreter_ref()
    require(worker_argv[:4] == [interpreter['path'], '-m', WORKER_MODULE, 'run'],
            'reference_continuation_command_required')
    cwd = _no_alias(cwd)
    require(cwd == ROOT.resolve(), 'main_repository_cwd_required')
    output = _output(output, fresh=True)
    _namespace_scope(worker_argv, output)
    names = sorted(set([SUPERVISOR_SOURCE, WORKER_SOURCE, *(worker_source_paths or [])]))
    return {'schema': SPEC_SCHEMA, 'worker_argv': worker_argv, 'cwd': str(cwd),
            'output_root': str(output), 'source_sha256s': _source_bindings(names),
            'interpreter_ref': interpreter, 'environment_overlay': dict(ENVIRONMENT_OVERLAY),
            'seconds_limit': SECONDS_LIMIT, 'worker_launch_count': 1,
            'automatic_restart_authorized': False, 'model_calls_by_supervisor': 0,
            'native_actor_seconds': 720, 'native_max_actions': 90,
            'native_owned_lifecycle_seconds': 1200, 'native_qualification_credit': 0}


def _validate(spec, *, fresh):
    require(type(spec) is dict and type(spec.get('source_sha256s')) is dict, 'review_spec_required')
    # Rebuild all fields so added keys, changed limits and source drift fail.
    output = _output(spec.get('output_root'), fresh=fresh)
    if fresh:
        expected = review_spec(worker_argv=spec.get('worker_argv'), cwd=spec.get('cwd'),
                               output=output, worker_source_paths=list(spec['source_sha256s']))
    else:
        # review_spec's fresh-output check is deliberately retained for launch.
        expected = dict(spec)
        expected.update(schema=SPEC_SCHEMA, cwd=str(ROOT.resolve()), output_root=str(output),
                        source_sha256s=_source_bindings(sorted(spec['source_sha256s'])),
                        interpreter_ref=_interpreter_ref(),
                        environment_overlay=dict(ENVIRONMENT_OVERLAY),
                        seconds_limit=SECONDS_LIMIT, worker_launch_count=1,
                        automatic_restart_authorized=False, model_calls_by_supervisor=0,
                        native_actor_seconds=720, native_max_actions=90,
                        native_owned_lifecycle_seconds=1200, native_qualification_credit=0)
        require(set(spec) == {'schema', 'worker_argv', 'cwd', 'output_root', 'source_sha256s',
                             'interpreter_ref', 'environment_overlay', 'seconds_limit', 'worker_launch_count',
                             'automatic_restart_authorized', 'model_calls_by_supervisor',
                             'native_actor_seconds', 'native_max_actions',
                             'native_owned_lifecycle_seconds', 'native_qualification_credit'},
                'review_spec_fields_changed')
        require(type(spec['worker_argv']) is list and len(spec['worker_argv']) >= 4 and
                all(type(item) is str and item and '\0' not in item for item in spec['worker_argv']) and
                spec['worker_argv'][:4] == [_interpreter_ref()['path'], '-m', WORKER_MODULE, 'run'],
                'reference_continuation_command_required')
    require(canonical(spec) == canonical(expected), 'exact_current_supervisor_review_required')
    _namespace_scope(spec['worker_argv'], output)
    return output


def _claim_path(spec_sha256):
    require(type(spec_sha256) is str and len(spec_sha256) == 64 and
            all(char in '0123456789abcdef' for char in spec_sha256), 'review_digest_required')
    return _no_alias(AUTHORITY_ROOT) / (spec_sha256 + '-consumed.private.json')


def launch(*, spec_path, spec_sha256, execute=False):
    """Request one detached supervisor after exact explicit reviewed authority."""
    require(execute is True, 'explicit_reviewed_host_launch_required')
    spec_path = _no_alias(spec_path)
    spec = _private(spec_path, spec_sha256)
    output = _validate(spec, fresh=True)
    authority = _no_alias(AUTHORITY_ROOT)
    authority.mkdir(mode=0o700, parents=True, exist_ok=True)
    require(authority.stat().st_mode & 0o077 == 0, 'private_global_authority_directory_required')
    claim_path = _claim_path(spec_sha256)
    # The global exclusive claim survives output loss and uncertain Popen.
    claim = _write(claim_path, {'schema': 'magento-reference-host-authority-consumed-v1',
                   'review_ref': {'path': str(spec_path), 'sha256': spec_sha256},
                   'output_root': str(output), 'consumed_at_utc': _now(),
                   'automatic_replay_authorized': False, 'worker_launch_count': 1})
    try:
        output.mkdir(mode=0o700, parents=True)
        with ExitStack() as stack:
            stdout = _log(stack, output / 'supervisor.stdout.private.bin')
            stderr = _log(stack, output / 'supervisor.stderr.private.bin')
            process = subprocess.Popen([spec['interpreter_ref']['path'], '-m', MODULE, 'supervise',
                                       '--spec-path', str(spec_path), '--spec-sha256', spec_sha256,
                                       '--claim-sha256', claim['sha256'], '--execute'],
                                      cwd=spec['cwd'], stdin=subprocess.DEVNULL, stdout=stdout,
                                      stderr=stderr, env=_launch_environment(spec),
                                      close_fds=True, start_new_session=True)
            require(type(process.pid) is int and process.pid > 0, 'supervisor_pid_unproved')
            receipt = {'schema': 'magento-reference-host-launch-v1', 'status': 'launch_requested',
                       'supervisor_pid': process.pid, 'popen_returned': True,
                       'review_ref': {'path': str(spec_path), 'sha256': spec_sha256},
                       'authority_ref': claim, 'output_root': str(output),
                       'automatic_restart_authorized': False, 'native_qualification_credit': 0}
            _write(output / 'launch.private.json', receipt)
        return receipt
    except BaseException as error:
        # Never reinterpret an exception as proof that no process started.
        safe_failure_output = False
        try:
            _output(output, fresh=False)
            safe_failure_output = True
        except (SupervisionError, OSError):
            pass
        if safe_failure_output and not (output / 'launch-failure.private.json').exists():
            _write(output / 'launch-failure.private.json', {
                'schema': 'magento-reference-host-launch-failure-v1', 'status': 'launch_uncertain',
                'error_type': type(error).__name__, 'authority_consumed': True,
                'process_start_unknown': True, 'automatic_replay_authorized': False})
        raise


def _stop_owned_worker(process):
    """Signal only the unreaped child process group created by this supervisor."""
    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        return process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        return process.wait(timeout=10)


def supervise(*, spec_path, spec_sha256, claim_sha256, execute=False):
    """Detached entrypoint: one worker, bounded wait, immutable exit evidence."""
    require(execute is True, 'explicit_supervisor_bootstrap_required')
    spec = _private(spec_path, spec_sha256)
    # Current-source validation happens inside the durable failure boundary,
    # after the reviewed claim and exclusive bootstrap receipt are reopened.
    output = _output(spec.get('output_root'), fresh=False)
    claim = _private(_claim_path(spec_sha256), claim_sha256)
    require(claim.get('review_ref') == {'path': str(_no_alias(spec_path)), 'sha256': spec_sha256} and
            claim.get('output_root') == str(output) and claim.get('automatic_replay_authorized') is False and
            claim.get('worker_launch_count') == 1, 'consumed_review_authority_changed')
    started = time.monotonic()
    start = {'schema': 'magento-reference-host-supervisor-start-v1', 'supervisor_pid': os.getpid(),
             'started_monotonic': started, 'deadline_monotonic': started + SECONDS_LIMIT,
             'seconds_limit': SECONDS_LIMIT, 'started_at_utc': _now(),
             'review_sha256': spec_sha256, 'authority_sha256': claim_sha256,
             'automatic_restart_authorized': False}
    # Exclusive bootstrap receipt prevents direct/manual duplicate supervise.
    _write(output / 'supervisor-start.private.json', start)
    process = None
    exit_code = None
    status = 'worker_launch_uncertain'
    error_type = None
    launch_attempts = 0
    with ExitStack() as stack:
        stdout = _log(stack, output / 'worker.stdout.private.bin')
        stderr = _log(stack, output / 'worker.stderr.private.bin')
        try:
            _validate(spec, fresh=False)
            launch_attempts = 1
            process = subprocess.Popen(spec['worker_argv'], cwd=spec['cwd'], stdin=subprocess.DEVNULL,
                                       stdout=stdout, stderr=stderr, env=_launch_environment(spec),
                                       close_fds=True, start_new_session=True)
            require(type(process.pid) is int and process.pid > 0, 'worker_pid_unproved')
            _write(output / 'worker-start.private.json', {
                'schema': 'magento-reference-host-worker-start-v1', 'worker_pid': process.pid,
                'supervisor_pid': os.getpid(), 'popen_returned': True, 'worker_launch_count': 1,
                'argv': spec['worker_argv'], 'cwd': spec['cwd'], 'review_sha256': spec_sha256,
                'observed_monotonic': time.monotonic(), 'automatic_restart_authorized': False})
            remaining = start['deadline_monotonic'] - time.monotonic()
            require(remaining > 0, 'host_deadline_before_worker_wait')
            try:
                exit_code = process.wait(timeout=remaining)
                status = 'worker_exit_zero' if exit_code == 0 else 'worker_exit_nonzero'
            except subprocess.TimeoutExpired:
                status = 'host_deadline_exceeded'
                exit_code = _stop_owned_worker(process)
            _validate(spec, fresh=False)
        except BaseException as error:
            error_type = type(error).__name__
            status = 'supervisor_failed' if process is not None else 'worker_launch_uncertain'
            if process is not None:
                try:
                    exit_code = _stop_owned_worker(process)
                except BaseException:
                    status = 'worker_exit_unproved'
                    exit_code = None
        finally:
            for stream in (stdout, stderr):
                stream.flush()
                os.fsync(stream.fileno())
    value = {'schema': 'magento-reference-host-exit-v1', 'status': status,
             'review_sha256': spec_sha256, 'authority_sha256': claim_sha256,
             'supervisor_pid': os.getpid(), 'worker_pid': process.pid if process is not None else None,
             'worker_exit_code': exit_code, 'worker_exit_acknowledged': exit_code is not None,
             'error_type': error_type, 'started_monotonic': started, 'ended_monotonic': time.monotonic(),
             'finished_at_utc': _now(), 'seconds_limit': SECONDS_LIMIT,
             'worker_launch_attempts': launch_attempts,
             'worker_launch_acknowledgments': int(process is not None),
             'max_worker_launches': 1, 'automatic_restart_authorized': False,
             'native_qualification_credit': 0, 'model_calls_by_supervisor': 0,
             'stdout_ref': {'path': 'worker.stdout.private.bin', 'sha256': _sha(output / 'worker.stdout.private.bin')},
             'stderr_ref': {'path': 'worker.stderr.private.bin', 'sha256': _sha(output / 'worker.stderr.private.bin')}}
    _write(output / 'exit.private.json', value)
    return value


def saved_status(*, spec_path, spec_sha256):
    """Read durable state only; never launches, signals, or infers native reset."""
    spec = _private(spec_path, spec_sha256)
    output = _validate(spec, fresh=False)
    value = {'schema': 'magento-reference-host-saved-status-v1', 'status': 'launch_unproved',
             'review_sha256': spec_sha256, 'native_qualification_credit': 0}
    for name, status in [('launch.private.json', 'launch_requested'),
                         ('supervisor-start.private.json', 'supervisor_started'),
                         ('worker-start.private.json', 'worker_started'),
                         ('launch-failure.private.json', 'launch_uncertain'),
                         ('exit.private.json', None)]:
        path = output / name
        if path.exists():
            receipt = _private(path)
            value[name] = {'path': str(path), 'sha256': _sha(path)}
            value['status'] = status or receipt['status']
            if name == 'exit.private.json':
                require(receipt.get('schema') == 'magento-reference-host-exit-v1' and
                        receipt.get('review_sha256') == spec_sha256 and
                        receipt.get('status') in {'worker_exit_zero', 'worker_exit_nonzero',
                            'host_deadline_exceeded', 'supervisor_failed', 'worker_launch_uncertain',
                            'worker_exit_unproved'} and
                        receipt.get('seconds_limit') == SECONDS_LIMIT and
                        receipt.get('automatic_restart_authorized') is False and
                        type(receipt.get('native_qualification_credit')) is int and
                        receipt['native_qualification_credit'] == 0 and
                        receipt.get('model_calls_by_supervisor') == 0,
                        'host_exit_review_changed')
                code = receipt.get('worker_exit_code')
                require((code is None or type(code) is int) and
                        receipt.get('worker_exit_acknowledged') is (code is not None) and
                        (receipt['status'] != 'worker_exit_zero' or code == 0) and
                        (receipt['status'] != 'worker_exit_nonzero' or code not in (None, 0)),
                        'host_exit_acknowledgment_changed')
                for key in ('stdout_ref', 'stderr_ref'):
                    reference = receipt[key]
                    expected_name = 'worker.' + ('stdout' if key == 'stdout_ref' else 'stderr') + '.private.bin'
                    require(reference['path'] == expected_name,
                            'host_output_reference_unsafe')
                    path = _no_alias(output / reference['path'])
                    require(path.is_file() and path.stat().st_mode & 0o077 == 0 and
                            _sha(path) == reference['sha256'], 'host_output_bytes_changed')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('launch', 'supervise', 'status'))
    parser.add_argument('--spec-path', required=True)
    parser.add_argument('--spec-sha256', required=True)
    parser.add_argument('--claim-sha256')
    parser.add_argument('--execute', action='store_true')
    args = vars(parser.parse_args())
    command = args.pop('command')
    if command == 'status':
        args.pop('execute'); args.pop('claim_sha256')
        value = saved_status(**args)
    elif command == 'launch':
        args.pop('claim_sha256')
        value = launch(**args)
    else:
        value = supervise(**args)
    print(json.dumps({'status': value['status'], 'native_qualification_credit': 0}))
    return 0 if command != 'supervise' or value['status'] == 'worker_exit_zero' else 1


if __name__ == '__main__':
    sys.exit(main())
