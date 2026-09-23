"""Bounded operational recovery I/O; never retries researcher or teacher work."""
import hashlib
import json
from pathlib import Path
import time
import uuid


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


class RecoveryIOError(RuntimeError):
    pass


class BoundedIO:
    def __init__(self, sandbox, pause=time.sleep):
        self.sandbox = sandbox
        self.pause = pause
        self.counts = {}
        self.writes = {}

    def charge(self, key):
        count = self.counts.get(key, 0)
        if count >= 3:
            raise RecoveryIOError('identical recovery I/O attempt limit reached')
        self.counts[key] = count + 1

    def read_once(self, path, user='root'):
        self.charge(('read', user, path))
        return self.sandbox.files.read(path, user=user, request_timeout=30)

    def read_text(self, path, user='root'):
        for attempt in range(3):
            try:
                return self.read_once(path, user)
            except Exception:
                if attempt == 2 or self.counts.get(('read', user, path), 0) >= 3:
                    raise RecoveryIOError('bounded recovery read failed') from None
                self.pause(.5 * (attempt + 1))

    def write_text(self, path, text, user='root'):
        digest = sha(text)
        identity = (user, path)
        if identity in self.writes and self.writes[identity] != digest:
            raise ValueError('recovery write identity reused with different content')
        self.writes[identity] = digest
        for attempt in range(3):
            self.charge(('write', user, path, digest))
            try:
                self.sandbox.files.write(path, text, user=user, request_timeout=30)
            except Exception:
                # The upload can have committed even if its response was lost.
                pass
            try:
                if sha(self.read_once(path, user)) == digest:
                    return {'path': path, 'sha256': digest, 'write_attempts': attempt + 1}
            except Exception:
                pass
            if attempt < 2:
                self.pause(.5 * (attempt + 1))
        raise RecoveryIOError('bounded recovery write/readback failed')

    def journal_command(self, command, result_path):
        for attempt in range(3):
            self.charge(('command', command))
            try:
                result = self.sandbox.commands.run(command, timeout=45, user='root')
                return json.loads(result.stdout)
            except Exception:
                try:
                    return json.loads(self.read_once(result_path))
                except Exception:
                    if attempt == 2:
                        raise RecoveryIOError('journaled recovery operation failed') from None
                    self.pause(.5 * (attempt + 1))

    def receipt(self):
        rows = []
        for key, value in self.counts.items():
            row = {'operation': key[0], 'attempts': value}
            if key[0] == 'command':
                row['command_sha256'] = sha(key[1])
            else:
                row.update(user=key[1], path=key[2])
                if key[0] == 'write':
                    row['content_sha256'] = key[3]
            rows.append(row)
        return rows


class RestorationWorkspace:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=False)
        self.sandbox = None
        self.io = None

    def start(self, inputs, worker):
        from e2b import Sandbox
        self.operation = uuid.uuid4().hex
        self.sandbox = Sandbox.create(timeout=3600, allow_internet_access=False, envs={},
            metadata={'project': 'cua-data-factory', 'role': 'research-restoration', 'restoration_id': self.operation})
        (self.root / 'sandbox.json').write_text(json.dumps({'id': self.sandbox.sandbox_id,
            'network': 'no outbound internet', 'provider_credentials_injected': False}))
        self.io = BoundedIO(self.sandbox)
        self.io.write_text('/tmp/factory_worker.py', worker)
        initializer = Path(__file__).with_name('restoration_journal.py').read_text()
        self.io.write_text('/tmp/cua_restore_initializer.py', initializer)
        command = f'python /tmp/cua_restore_initializer.py {self.operation} {sha(worker)}'
        result = self.io.journal_command(command, f'/tmp/cua-restore-{self.operation}/result.json')
        if result.get('worker_sha256') != sha(worker) or not result.get('initialization', {}).get('initialized'):
            raise ValueError('root initialization receipt mismatch')
        (self.root / 'initialization.json').write_text(json.dumps(result['initialization']))
        for name, content in inputs.items():
            if '/' in name or not name or '..' in name:
                raise ValueError('flat controller input names required')
            self.io.write_text('/inputs/' + name, content)

    def restore_file(self, item):
        # The existing supervisor's path policy still defines the trusted boundary.
        from cursibench.factory_worker import resolve_path
        target = resolve_path(item['path'], writing=True)
        if sha(item['content']) != item['sha256']:
            raise ValueError('snapshot content changed')
        # Generated data may exceed the model's 100KB write-action limit. Exact
        # snapshot restoration is controller I/O, performed as the factory user.
        return self.io.write_text(str(target), item['content'], user='factory')

    def snapshot(self):
        request_id = uuid.uuid4().hex
        self.io.write_text('/service/requests/' + request_id + '.json', json.dumps({'op': 'snapshot', 'path': 'factory.py'}))
        result = self.io.journal_command('python /service/factory_worker.py --request ' + request_id,
                                        '/service/results/' + request_id + '.json')
        if 'files' not in result:
            raise ValueError('restoration snapshot verification failed')
        (self.root / 'final-files.json').write_text(json.dumps(result, indent=2))
        return result

    def close(self):
        if self.sandbox is None:
            return
        from e2b import Sandbox
        from e2b.exceptions import SandboxNotFoundException
        destroyed = False
        for attempt in range(3):
            try:
                self.sandbox.kill(request_timeout=30)
            except SandboxNotFoundException:
                destroyed = True
                break
            except Exception:
                pass
            try:
                Sandbox.get_info(self.sandbox.sandbox_id, request_timeout=30)
            except SandboxNotFoundException:
                destroyed = True
                break
            except Exception:
                pass
            if attempt < 2:
                time.sleep(1)
        (self.root / 'cleanup.json').write_text(json.dumps({'sandbox_destroyed': destroyed}))

    def save_io_receipt(self):
        if self.io:
            (self.root / 'io-receipt.json').write_text(json.dumps(self.io.receipt(), indent=2))
