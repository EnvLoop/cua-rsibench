"""Bound only the immutable guest manifest download and provider status reads.

No request is retried. The v16 probe, raw manifest, verifier and GUI policy are
unchanged. All controls and all five model slots use this same wrapper.
"""
from contextlib import contextmanager
import time
from unittest.mock import patch

MANIFEST_PATH = '/tmp/native-guest-content-files.jsonl.gz'
TRANSFER_SECONDS = 180.0
MAX_COMPRESSED_BYTES = 8 * 1024 * 1024
STATUS_SECONDS = 30.0
RECIPE = {
    'schema': 'cua-native-bounded-guest-transport-v17',
    'manifest_path': MANIFEST_PATH,
    'caller_format': 'bytes', 'sdk_format': 'stream',
    'request_timeout_seconds': TRANSFER_SECONDS,
    'monotonic_transfer_seconds': TRANSFER_SECONDS,
    'max_compressed_bytes': MAX_COMPRESSED_BYTES,
    'context_manager_close_on_every_exit': True,
    'status_request_timeout_seconds': STATUS_SECONDS,
    'http_retries': 0, 'action_retries': 0, 'create_retries': 0,
    'same_intent_replays': 0,
}


class BoundedFiles:
    def __init__(self, raw):self.raw = raw
    def __getattr__(self, name):return getattr(self.raw, name)

    def read(self, path, *args, **kwargs):
        # Only the v16 capture's exact request is intercepted. Every other file
        # call, including explicit stream callers, retains its original shape.
        requested_format = args[0] if args else kwargs.get('format', 'text')
        if path != MANIFEST_PATH or requested_format != 'bytes':
            return self.raw.read(path, *args, **kwargs)
        if args:
            args = ('stream', *args[1:])
            if len(args) >= 3:
                args = (*args[:2], TRANSFER_SECONDS, *args[3:])
            else:
                kwargs = {**kwargs, 'request_timeout': TRANSFER_SECONDS}
        else:
            kwargs = {**kwargs, 'format': 'stream', 'request_timeout': TRANSFER_SECONDS}
        started = time.monotonic(); deadline = started + TRANSFER_SECONDS
        chunks = []; total = 0
        with self.raw.read(path, *args, **kwargs) as stream:
            if time.monotonic() >= deadline:raise TimeoutError('v17_manifest_transfer_wall_bound')
            for chunk in stream:
                if time.monotonic() >= deadline:raise TimeoutError('v17_manifest_transfer_wall_bound')
                if not isinstance(chunk, bytes):raise TypeError('v17_manifest_stream_chunk_not_bytes')
                total += len(chunk)
                if total > MAX_COMPRESSED_BYTES:raise ValueError('v17_compressed_manifest_bound')
                chunks.append(chunk)
            if time.monotonic() >= deadline:raise TimeoutError('v17_manifest_transfer_wall_bound')
        return bytearray(b''.join(chunks))


class BoundedSandbox:
    def __init__(self, raw):
        self.raw = raw; self.files = BoundedFiles(raw.files)
    def __getattr__(self, name):return getattr(self.raw, name)
    def get_info(self, *args, **kwargs):
        return self.raw.get_info(*args, **{**kwargs, 'request_timeout': STATUS_SECONDS})
    def is_running(self, *args, **kwargs):
        return self.raw.is_running(*args, **{**kwargs, 'request_timeout': STATUS_SECONDS})


@contextmanager
def create_context():
    """Must precede v16.context so its capture owns the bounded inner guest."""
    from e2b_desktop import Sandbox
    create = Sandbox.create
    with patch.object(Sandbox, 'create', lambda *args, **kwargs: BoundedSandbox(create(*args, **kwargs))):
        yield
