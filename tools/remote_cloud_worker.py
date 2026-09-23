"""Trusted, durable supervisor for remote-control-plane-v1 (stdlib only).

The frozen legacy launcher remains the sole evaluation entry point. This
supervisor verifies inputs, journals one dispatch, bounds its process group,
and packages evidence. It never retries an evaluation.
"""
import argparse
import fcntl
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import signal
import subprocess
import sys
import tarfile
import time

VERSION = 'remote-control-plane-v1'
MAX_BYTES = 512 * 1024 * 1024


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    temporary = path.with_suffix('.tmp')
    with temporary.open('w') as stream:
        json.dump(value, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def safe_name(name):
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or '..' in path.parts or '\\' in name
            or str(path) != name or name in ('.', '..')):
        raise ValueError('unsafe archive path')
    return path


def read_archive(data):
    if len(data) > MAX_BYTES:
        raise ValueError('archive exceeds byte bound')
    files, total = {}, 0
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        for entry in archive:
            if len(files) >= 10000:
                raise ValueError('archive contains too many files')
            safe_name(entry.name)
            if not entry.isfile() or entry.name in files:
                raise ValueError('archive contains a link, special file, or duplicate')
            total += entry.size
            if total > MAX_BYTES:
                raise ValueError('expanded archive exceeds byte bound')
            files[entry.name] = archive.extractfile(entry).read()
    return files


def unpack_payload(data, root, manifest_sha):
    files = read_archive(data)
    manifest_bytes = files.get('manifest.json', b'')
    if sha(manifest_bytes) != manifest_sha:
        raise ValueError('payload manifest hash mismatch')
    manifest = json.loads(manifest_bytes)
    expected_blobs = {'blobs/' + row['sha256'] for row in manifest['files'].values()}
    if set(files) != expected_blobs | {'manifest.json'}:
        raise ValueError('payload blob set mismatch')
    for name, row in manifest['files'].items():
        safe_name(name)
        blob = files['blobs/' + row['sha256']]
        if len(blob) != row['bytes'] or sha(blob) != row['sha256']:
            raise ValueError('payload file hash mismatch')
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(blob)
        target.chmod(row['mode'])
    return manifest


def verify_runtime(expected):
    if sys.version_info[:2] != (3, 12) or sys.platform != 'linux':
        raise ValueError('remote runtime must use Linux and Python 3.12')
    actual = {name: importlib.metadata.version(name) for name in expected['packages']}
    if actual != expected['packages']:
        raise ValueError('installed package versions differ from the frozen origin')
    source_hashes = {}
    for key, row in expected['package_sources'].items():
        path = importlib.metadata.distribution(row['distribution']).locate_file(row['path'])
        source_hashes[key] = sha(Path(path).read_bytes())
        if source_hashes[key] != row['sha256']:
            raise ValueError('installed package source differs from the frozen origin')
    return {'python': sys.version, 'platform': sys.platform,
            'packages': actual, 'package_source_hashes': source_hashes,
            'all_installed_packages': {d.metadata['Name']: d.version for d in importlib.metadata.distributions()}}


def verify_materialized(root, manifest):
    for name, row in manifest['files'].items():
        path = root / name
        if path.is_symlink() or sha(path.read_bytes()) != row['sha256']:
            raise ValueError('materialized input changed')


def assert_no_credentials(data, secrets):
    if any(secret.encode() in data for secret in secrets if secret):
        raise ValueError('credential detected in evidence; archive withheld')
    if re.search(rb'(?:tml-|e2b_|sk-)[A-Za-z0-9_-]{20,}|Bearer\s+[A-Za-z0-9_-]{20,}', data):
        raise ValueError('possible credential detected; archive withheld')
    if re.search(rb'"object"\s*:\s*"(?:response|chat\.completion)"', data):
        raise ValueError('raw provider envelope detected; archive withheld')
    # Provider envelopes are not necessary for this frozen student adapter.
    try:
        value = json.loads(data)
    except (ValueError, UnicodeDecodeError):
        return
    if isinstance(value, dict) and value.get('object') in ('response', 'chat.completion'):
        raise ValueError('raw provider envelope detected; archive withheld')


def archive_evidence(root, destination, secrets):
    source = root / 'evidence'
    if not source.is_dir():
        raise ValueError('legacy launcher produced no evidence directory')
    contents, hashes, total = {}, {}, 0
    for path in sorted(source.rglob('*')):
        if path.is_symlink():
            raise ValueError('evidence contains a symlink')
        if not path.is_file():
            continue
        relative = str(path.relative_to(source))
        safe_name(relative)
        data = path.read_bytes()
        total += len(data)
        if total > MAX_BYTES:
            raise ValueError('evidence exceeds byte bound')
        assert_no_credentials(data, secrets)
        contents['evidence/' + relative] = data
        hashes[relative] = {'sha256': sha(data), 'bytes': len(data)}
    index = {'version': VERSION, 'files': hashes, 'total_bytes': total}
    contents['evidence-index.json'] = json.dumps(index, sort_keys=True).encode()
    temporary = destination.with_suffix('.tmp')
    with tarfile.open(temporary, 'w:gz') as archive:
        for name, data in sorted(contents.items()):
            entry = tarfile.TarInfo(name)
            entry.size = len(data)
            entry.mode = 0o600
            archive.addfile(entry, io.BytesIO(data))
    temporary.replace(destination)
    return {'archive_sha256': sha(destination.read_bytes()),
            'archive_bytes': destination.stat().st_size,
            'evidence_index_sha256': sha(contents['evidence-index.json']),
            'evidence_files': len(hashes)}


def run(root, payload, payload_sha, manifest_sha, worker_sha, lease_deadline):
    root = Path(root)
    control = root.parent / 'control'
    control.mkdir(parents=True, exist_ok=True)
    with (control / 'job.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {'state': 'already_running'}
        if (control / 'completion.json').exists():
            return {'state': 'already_complete'}
        if (control / 'intent.json').exists():
            return {'state': 'prior_dispatch_uncertain_no_replay'}
        receipt = {'operational_version': VERSION, 'started_at': time.time(),
                   'payload_sha256': payload_sha, 'manifest_sha256': manifest_sha,
                   'complete': False, 'evaluation_dispatched': False}
        process = None
        try:
            if sha(Path(__file__).read_bytes()) != worker_sha:
                raise ValueError('supervisor hash mismatch')
            data = Path(payload).read_bytes()
            if sha(data) != payload_sha:
                raise ValueError('payload archive hash mismatch')
            root.mkdir(exist_ok=False)
            manifest = unpack_payload(data, root, manifest_sha)
            if manifest['operational_version'] != VERSION:
                raise ValueError('operational version mismatch')
            receipt['runtime'] = verify_runtime(manifest['runtime'])
            verify_materialized(root, manifest)
            if time.time() + 3000 > lease_deadline:
                raise ValueError('insufficient original lease for full job and evidence reserve')
            # The command vector is fixed; no caller-supplied shell command.
            arguments = ['--out', 'evidence', '--task', 'tasks', '--factory',
                         '--environment', 'journal', '--concurrency', '3', '--job-timeout', '2700']
            model = manifest['model']
            arguments += (['--base', '--model', model['name']] if model['kind'] == 'base'
                          else ['--training', 'inputs/training.json'])
            command = [sys.executable, 'tools/run_cloud_chain.py', *arguments]
            intent = {'started_at': time.time(), 'payload_sha256': payload_sha,
                      'manifest_sha256': manifest_sha, 'command': command,
                      'task_names': manifest['task_names'], 'job_cap_seconds': 2700}
            # This durable intent precedes any model-executing child. A lost ACK,
            # supervisor restart, or second nohup never replays that child.
            with (control / 'intent.json').open('x') as stream:
                json.dump(intent, stream)
                stream.flush()
                os.fsync(stream.fileno())
            env = {key: value for key, value in os.environ.items()
                   if key not in ('OPENAI_API_KEY', 'OPENAI_BASE_URL', 'HTTP_PROXY', 'HTTPS_PROXY',
                                  'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy')}
            env.update(PYTHONPATH=str(root / 'src'), PYTHONDONTWRITEBYTECODE='1')
            process = subprocess.Popen(command, cwd=root, env=env, stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL, start_new_session=True)
            receipt.update(evaluation_dispatched=True, child_pid=process.pid)
            write_json(control / 'running.json', receipt)
            try:
                receipt['child_exit'] = process.wait(timeout=2700)
            except subprocess.TimeoutExpired:
                receipt['child_wall_cap_reached'] = True
                # SIGINT lets the unchanged launcher/Harbor execute their finally
                # cleanup. No new inference is started by this supervisor.
                os.killpg(process.pid, signal.SIGINT)
                try:
                    receipt['child_exit'] = process.wait(timeout=120)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    receipt['child_exit'] = process.wait(timeout=10)
                    receipt['forced_group_kill'] = True
            verify_materialized(root, manifest)
            wrapper = root / 'evidence/result.json'
            if wrapper.exists():
                original = json.loads(wrapper.read_text())
                receipt['legacy_proxy_destroyed'] = original.get('proxy_destroyed')
                receipt['legacy_error_type'] = original.get('error_type')
            receipt.update(archive_evidence(root, control / 'evidence.tar.gz',
                                           [os.environ.get('E2B_API_KEY'), os.environ.get('TINKER_API_KEY')]))
            receipt['complete'] = True  # evidence complete, not a claim of task success
        except Exception as exc:
            receipt['error_type'] = type(exc).__name__
        finally:
            if process is not None and process.poll() is None:
                os.killpg(process.pid, signal.SIGINT)
                try:
                    process.wait(timeout=120)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=10)
                    receipt['forced_group_kill'] = True
            receipt['finished_at'] = time.time()
            receipt['child_cleanup_boundary'] = 'legacy proxy receipt; Harbor cleanup and fixed sandbox leases'
            write_json(control / 'completion.json', receipt)
        return {'state': 'complete' if receipt['complete'] else 'failed',
                'evaluation_dispatched': receipt['evaluation_dispatched']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('root', 'payload', 'payload-sha', 'manifest-sha', 'worker-sha'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--lease-deadline', type=float, required=True)
    args = parser.parse_args()
    # No provider objects, credential values, model output, or raw tracebacks.
    try:
        print(json.dumps(run(args.root, args.payload, args.payload_sha, args.manifest_sha, args.worker_sha, args.lease_deadline)))
    except Exception as exc:
        print(json.dumps({'state': 'supervisor_error', 'error_type': type(exc).__name__}))
