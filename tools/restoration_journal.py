"""Root-only initialization journal used by the operational restoration tool."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import sys


def initialize_once(worker, journal, expected_hash):
    worker = Path(worker)
    journal = Path(journal)
    if hashlib.sha256(worker.read_bytes()).hexdigest() != expected_hash:
        raise ValueError('initializer worker hash mismatch')
    journal.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(journal, 0o700)
    with (journal / 'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        result_path = journal / 'result.json'
        if result_path.exists():
            result = json.loads(result_path.read_text())
            if result['worker_sha256'] != expected_hash:
                raise ValueError('initialization journal identity mismatch')
            return result
        intent = journal / 'intent.json'
        if intent.exists():
            raise RuntimeError('uncertain initialization; effects must not be replayed')
        with intent.open('x') as stream:
            json.dump({'worker_sha256': expected_hash}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        initialization = runpy.run_path(str(worker))['initialize']()
        if not initialization.get('initialized'):
            raise ValueError('initializer did not confirm success')
        result = {'worker_sha256': expected_hash, 'initialization': initialization}
        temporary = result_path.with_suffix('.tmp')
        with temporary.open('w') as stream:
            json.dump(result, stream)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(result_path)
        return result


if __name__ == '__main__':
    if os.geteuid() != 0 or sys.platform != 'linux':
        raise SystemExit('restoration initialization runs only as root inside E2B')
    operation, worker_hash = sys.argv[1:]
    if not re.fullmatch('[a-f0-9]{32}', operation) or not re.fullmatch('[a-f0-9]{64}', worker_hash):
        raise SystemExit('invalid restoration identity')
    print(json.dumps(initialize_once('/tmp/factory_worker.py', '/tmp/cua-restore-' + operation, worker_hash)))
