"""One billing-gated read, with no training, sampling or automatic retry.

The private receipt can authorize continuation only after an actual successful
capabilities response and owned close. A failed read never means restored access.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import time

MODEL = 'Qwen/Qwen3.8-27B'
ROOT = Path(__file__).resolve().parents[1]


def private_json(path, expected):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
        raise ValueError('private_original_terminal_required')
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != expected:
        raise ValueError('original_terminal_changed')
    return json.loads(raw)


def write_once(path, value):
    raw = (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return {'path': str(Path(path).resolve()), 'sha256': sha256(raw).hexdigest()}


def result_receipt(*, terminal_ref, terminal, started_at, ended_at,
                   capabilities, status_code, error_type, close_returned,
                   raw_provider_evidence_ref=None):
    after = (type(terminal.get('ended_at')) in (int, float)
             and terminal['ended_at'] <= started_at
             and terminal.get('exit_code') == 1
             and terminal.get('automatic_restarts') == 0)
    models = [] if capabilities is None else capabilities.get('supported_models', [])
    matching = [row for row in models if row.get('model_name') == MODEL]
    supported = (len(matching) == 1 and matching[0].get('trainable') is not False
                 and matching[0].get('sampleable') is not False)
    ready = (after and status_code == 200 and capabilities is not None
             and supported and close_returned is True and error_type is None)
    return {'schema': 'envloop-odoo20-tinker-access-restored-v1',
            'checker_source_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'status': 'ready' if ready else 'not_ready', 'model': MODEL,
            'provider_http_status': status_code, 'error_type': error_type,
            'actual_provider_call': True, 'checked_after_prior_terminal': after,
            'prior_terminal_ref': terminal_ref, 'supported_model_verified': supported,
            'started_at': started_at, 'ended_at': ended_at,
            'checked_at': ended_at, 'raw_provider_evidence_ref': raw_provider_evidence_ref,
            'owned_close_returned': close_returned,
            'owned_close_awaited': close_returned,
            'training_calls': 0, 'model_sampling_calls': 0,
            'automatic_retries': 0, 'actual_cost_usd': None,
            'formal_large_study_credit': 0}


def run(*, terminal_path, terminal_sha, output_root):
    terminal = private_json(terminal_path, terminal_sha)
    out = Path(output_root)
    if (not out.is_absolute() or out.is_symlink() or out.exists()
            or not out.resolve().is_relative_to(ROOT/'work')):
        raise ValueError('fresh_owned_private_access_namespace_required')
    if (terminal.get('exit_code') != 1 or terminal.get('automatic_restarts') != 0
            or type(terminal.get('ended_at')) not in (int, float)
            or terminal['ended_at'] > time.time()):
        raise ValueError('prior_failed_terminal_required')
    out.mkdir(parents=True, mode=0o700)
    out.chmod(0o700)
    terminal_ref = {'path': str(Path(terminal_path).resolve()), 'sha256': terminal_sha}
    started = time.time()
    write_once(out/'access-intent.private.json', {'before_provider_call': True,
        'checker_source_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'operation': 'get_server_capabilities', 'prior_terminal_ref': terminal_ref,
        'automatic_retries': 0, 'training_calls': 0, 'model_sampling_calls': 0})
    # Inspected, hash-pinned SDK facade disables holder retries as well as HTTP
    # retries. Capability reads create no sessionful training or sampling client.
    from enterprise_fallback.odoo18.twenty_task_trial_training_v1 import no_retry_service_class
    service = no_retry_service_class()(max_retries=0, timeout=30)
    capabilities, code, error, closed, raw_ref = None, None, None, False, None
    try:
        response = service.get_server_capabilities()
        capabilities = response.model_dump(mode='json')
        code = 200
        raw_ref = write_once(out/'capabilities-result.private.json', capabilities)
    except Exception as exc:
        code, error = getattr(exc, 'status_code', None), type(exc).__name__
        # Retain the raw message privately; console and public reports get only
        # typed status, never authenticated headers or credentials.
        raw_ref = write_once(out/'capabilities-error.private.json', {
            'error_type': error, 'http_status': code, 'message': str(exc)[:8000]})
    finally:
        try:
            service.close('success' if code == 200 else 'errored').result(timeout=30)
            closed = True
        except Exception as exc:
            write_once(out/'close-error.private.json', {'error_type': type(exc).__name__})
    receipt = result_receipt(terminal_ref=terminal_ref, terminal=terminal,
        started_at=started, ended_at=time.time(), capabilities=capabilities,
        status_code=code, error_type=error, close_returned=closed,
        raw_provider_evidence_ref=raw_ref)
    ref = write_once(out/'access-result.private.json', receipt)
    return receipt, ref


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('terminal-path', 'terminal-sha', 'output-root'):
        parser.add_argument('--'+name, required=True)
    receipt, _ = run(**vars(parser.parse_args()))
    print(json.dumps({key: receipt[key] for key in
        ('status', 'provider_http_status', 'error_type', 'owned_close_returned')}))


if __name__ == '__main__':
    main()
