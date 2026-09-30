"""Private file RPC into the verified Qwen runtime; no native SDK overlay.

Starting the child only verifies runtime evidence. Provider calls require a
separate already-reserved setup/sample command. An uncertain command consumes
its intent and poisons the client: no restart or request resubmission exists.
"""
from __future__ import annotations

import argparse
import base64
from contextlib import redirect_stdout
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import select
import subprocess
import sys

ACTIVE_PROCESS = None
MAX_REQUEST_BYTES = 20_000_000
MAX_COMMANDS = 4_000  # One 20-task batch: setup, up to 1,800 samples/gates, close.


def write_new(path, value):
    raw = (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()
    with path.open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    path.chmod(0o600)
    return sha256(raw).hexdigest()


def private_json(path):
    if not path.is_file() or path.is_symlink() or path.stat().st_mode & 0o077 or not 0 < path.stat().st_size <= MAX_REQUEST_BYTES:
        raise ValueError('Unsafe private sampler message')
    raw = path.read_bytes()
    return json.loads(raw), sha256(raw).hexdigest()


def delegated_pre_dispatch(*, repo_root, study_plan_sha256):
    if (ACTIVE_PROCESS is None or ACTIVE_PROCESS.root != Path(repo_root).absolute() or
            ACTIVE_PROCESS.plan != study_plan_sha256):
        raise ValueError('No source-bound clean sampler process is active')
    return ACTIVE_PROCESS.call('gate', {})


class SamplerProcess:
    def __init__(self, *, repo_root, journal_root, plan_sha256):
        global ACTIVE_PROCESS
        if repo_root is None or journal_root is None or not re.fullmatch('[0-9a-f]{64}', plan_sha256 or ''):
            raise ValueError('Explicit sampler root, journal and source plan are required')
        self.root = Path(repo_root).absolute(); self.journal = Path(journal_root).absolute()
        self.plan = plan_sha256; self.ordinal = 0; self.uncertain = False
        self.closed = False; self.process = None
        executable = self.root / 'work/qwen38-training-runtime/.venv/bin/python'
        if (ACTIVE_PROCESS is not None or not executable.is_file() or self.journal.exists() or
                self.journal.is_symlink() or not self.journal.parent.is_dir()):
            raise ValueError('Sampler runtime or exclusive journal boundary changed')
        self.journal.mkdir(mode=0o700)
        env = os.environ.copy()
        env['PYTHONPATH'] = str(self.root) + os.pathsep + str(self.root / 'src')
        env['PYTHONNOUSERSITE'] = '1'; env['HF_HUB_OFFLINE'] = '1'; env['TRANSFORMERS_OFFLINE'] = '1'
        env.pop('KMP_DUPLICATE_LIB_OK', None)
        for key in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'E2B_API_KEY'):
            env.pop(key, None)
        self.stderr = (self.journal / 'child.stderr.private.log').open('xb')
        (self.journal / 'child.stderr.private.log').chmod(0o600)
        command = [str(executable), '-m', 'native_desktop_factory.qwen_sampler_process_v11',
                   '--repo-root', str(self.root), '--journal', str(self.journal), '--plan', self.plan]
        write_new(self.journal / 'child-launch.private.json',
                  {'argv': command, 'source_plan_sha256': self.plan, 'automatic_restarts': 0})
        try:
            self.process = subprocess.Popen(command, cwd=self.root, env=env, stdin=subprocess.PIPE,
                                            stdout=subprocess.PIPE, stderr=self.stderr, text=True,
                                            bufsize=1, start_new_session=True)
            write_new(self.journal / 'child-started.private.json', {'pid': self.process.pid})
            ACTIVE_PROCESS = self
        except BaseException:
            self.stderr.close(); raise

    def call(self, kind, arguments, *, timeout=900):
        if self.closed or self.uncertain or self.ordinal >= MAX_COMMANDS or kind not in ('setup', 'sample', 'gate', 'close'):
            raise ValueError('Sampler command is consumed, uncertain or outside the finite protocol')
        number = self.ordinal; self.ordinal += 1
        request_path = self.journal / f'{number:03d}.request.private.json'
        checksum = write_new(request_path, {'schema': 'cua-clean-sampler-command-v11',
                'ordinal': number, 'kind': kind, 'plan_sha256': self.plan, 'arguments': arguments,
                'same_request_replay_authorized': False})
        try:
            self.process.stdin.write(json.dumps({'request': request_path.name, 'sha256': checksum}) + '\n')
            self.process.stdin.flush()
            if not select.select([self.process.stdout], [], [], timeout)[0]:
                raise TimeoutError('Sampler subprocess acknowledgement uncertain')
            line = self.process.stdout.readline(4097)
            if not line or len(line) > 4096:
                raise ValueError('Sampler subprocess acknowledgement invalid')
            reply = json.loads(line)
            if (set(reply) != {'ordinal', 'result', 'sha256'} or reply['ordinal'] != number or
                    reply['result'] != f'{number:03d}.result.private.json'):
                raise ValueError('Sampler subprocess response binding changed')
            result, result_sha = private_json(self.journal / reply['result'])
            if result_sha != reply['sha256'] or result['request_sha256'] != checksum:
                raise ValueError('Sampler subprocess result bytes changed')
            if result['status'] != 'completed':
                raise ValueError('Sampler subprocess operation failed; inspect retained private result')
            return result['value']
        except BaseException:
            self.uncertain = True
            raise

    def close(self, success):
        global ACTIVE_PROCESS
        if self.closed:
            return
        try:
            if self.process.poll() is None and not self.uncertain:
                self.call('close', {'success': bool(success)}, timeout=45)
                self.process.wait(timeout=10)
        finally:
            if self.process.poll() is None:
                self.process.terminate()
                try:self.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.process.kill(); self.process.wait(timeout=10)
            write_new(self.journal / 'child-terminal.private.json',
                      {'pid': self.process.pid, 'exit_code': self.process.returncode,
                       'request_acknowledgement_uncertain': self.uncertain, 'automatic_restarts': 0})
            self.stderr.close(); self.closed = True
            if ACTIVE_PROCESS is self:
                ACTIVE_PROCESS = None


def serve(root, journal, plan):
    from cursibench.full_study_qwen_runtime_gate_v1 import pre_dispatch
    from .uniform_model_transport_v11 import CleanRuntimeSampler
    sampler = CleanRuntimeSampler(); setup = False; ordinal = 0
    try:
        for line in sys.stdin:
            if ordinal >= MAX_COMMANDS:
                raise ValueError('Sampler batch command bound reached')
            if len(line) > 4096:
                raise ValueError('Sampler envelope exceeds bound')
            envelope = json.loads(line)
            if set(envelope) != {'request', 'sha256'} or envelope['request'] != f'{ordinal:03d}.request.private.json':
                raise ValueError('Sampler command order or replay changed')
            request, checksum = private_json(journal / envelope['request'])
            if (checksum != envelope['sha256'] or request['schema'] != 'cua-clean-sampler-command-v11' or
                    request['ordinal'] != ordinal or request['plan_sha256'] != plan or
                    request['same_request_replay_authorized'] is not False):
                raise ValueError('Sampler command source binding changed')
            kind = request['kind']; args = request['arguments']; stop = False
            try:
                with redirect_stdout(sys.stderr):
                    if kind == 'gate':
                        value = pre_dispatch(repo_root=root, study_plan_sha256=plan)
                    elif kind == 'setup' and not setup:
                        pre_dispatch(repo_root=root, study_plan_sha256=plan)
                        setup = True  # Consume setup before any provider acknowledgement.
                        value = sampler.start(**args)
                    elif kind == 'sample' and setup:
                        task_dir = Path(args['task_dir']).resolve()
                        if not task_dir.is_relative_to(journal.parent.resolve()):
                            raise ValueError('Sampler task journal escaped its private episode')
                        raw = base64.b64decode(args['image_base64'], validate=True)
                        value = sampler.sample_rendered(request_id=args['request_id'], task_dir=task_dir,
                                 remaining_seconds=args['remaining_seconds'], image_bytes=raw,
                                 instruction=args['instruction'], visible_text=args['visible_text'])
                    elif kind == 'close':
                        sampler.close(args['success']); value = {'status': 'closed'}; stop = True
                    else:
                        raise ValueError('Sampler setup/sample state changed')
                result = {'status': 'completed', 'request_sha256': checksum, 'value': value}
            except Exception as exc:
                result = {'status': 'failed', 'request_sha256': checksum,
                          'exception_type': type(exc).__name__,
                          'retained_sampling_failure': getattr(sampler, 'last_failure', None),
                          'same_request_replay_authorized': False}
                stop = True
            path = journal / f'{ordinal:03d}.result.private.json'
            result_sha = write_new(path, result)
            print(json.dumps({'ordinal': ordinal, 'result': path.name, 'sha256': result_sha}), flush=True)
            ordinal += 1
            if stop:
                break
    finally:
        with redirect_stdout(sys.stderr):
            sampler.close(False)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo-root', type=Path, required=True)
    p.add_argument('--journal', type=Path, required=True)
    p.add_argument('--plan', required=True)
    a = p.parse_args()
    if Path(__file__).resolve().parents[1] != a.repo_root.resolve():
        raise ValueError('Sampler code must be inside its source-bound checkout')
    serve(a.repo_root.absolute(), a.journal.absolute(), a.plan)


if __name__ == '__main__':
    main()
