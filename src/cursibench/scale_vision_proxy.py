"""v0.6 image/text sampling boundary; independent of the frozen v0.5 proxy.

One adapter/journal belongs to one trusted task execution. Requests contain only
in-memory PNG/JPEG bytes, instruction, visible text, and a durable request ID.
The optional HTTP facade accepts base64 image bytes, never a file or URL. This
module performs no training and cannot dispatch browser actions.

Completed requests survive restarts. An intent without a completed result is
uncertain and is never automatically sampled again. Journal data is private;
public receipts contain only hashes, bounds, token counts, and error subtypes.
"""
from __future__ import annotations

import argparse
import base64
import binascii
from contextlib import contextmanager
from dataclasses import asdict, dataclass
import fcntl
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
import io
import json
import os
from pathlib import Path
import re
import sqlite3
import threading
import time
import warnings

VERSION = 'scale-vision-proxy-v1'
MODEL = 'Qwen/Qwen3.8-27B'
RENDERER = 'qwen3_5_disable_thinking'
PROCESSOR = 'Qwen2VLImageProcessorPil'
REQUEST_ID = re.compile(r'[A-Za-z0-9_-]{8,100}')
CAMPAIGN_ID = re.compile(r'[a-z][a-z0-9-]{0,63}')


def digest(value):
    encoded = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(encoded).hexdigest()


def campaign_metadata(campaign_id):
    """Attribute provider billing events to one declared study campaign."""
    if not isinstance(campaign_id, str) or not CAMPAIGN_ID.fullmatch(campaign_id):
        raise ProxyError('invalid_campaign_id')
    return {'purpose': VERSION, 'campaign_id': campaign_id}


class ProxyError(ValueError):
    """Only a fixed subtype is safe to expose, never an exception body."""
    def __init__(self, subtype):
        self.subtype = subtype
        super().__init__(subtype)


@dataclass(frozen=True)
class Limits:
    image_bytes: int = 8_000_000
    image_pixels: int = 4_194_304
    image_side: int = 4096
    instruction_bytes: int = 16_384
    visible_text_bytes: int = 65_536
    input_tokens: int = 32_768
    output_tokens: int = 512
    decoded_output_bytes: int = 65_536
    max_actions: int = 90
    request_timeout_seconds: int = 240

    def __post_init__(self):
        for name, value in asdict(self).items():
            if type(value) is not int or value <= 0:
                raise ProxyError('invalid_limits')
        if (self.image_bytes > 32_000_000 or self.image_pixels > 16_777_216 or self.image_side > 8192
                or self.instruction_bytes > 262_144 or self.visible_text_bytes > 1_048_576
                or self.input_tokens + self.output_tokens > 64_000 or self.output_tokens > 4096
                or self.decoded_output_bytes > 1_048_576 or self.max_actions > 1000
                or self.request_timeout_seconds > 900):
            raise ProxyError('invalid_limits')

    @property
    def http_body_bytes(self):
        # JSON can escape text to six bytes per character; the independent text
        # and image limits are checked again after parsing.
        return ((self.image_bytes + 2) // 3) * 4 + 6 * (self.instruction_bytes + self.visible_text_bytes) + 4096


def image_from_bytes(data, limits):
    from PIL import Image, UnidentifiedImageError
    if not isinstance(data, bytes) or not data or len(data) > limits.image_bytes:
        raise ProxyError('invalid_image_bytes')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as opened:
                if opened.format not in ('PNG', 'JPEG') or getattr(opened, 'n_frames', 1) != 1:
                    raise ProxyError('unsupported_image_format')
                width, height = opened.size
                if not 0 < width <= limits.image_side or not 0 < height <= limits.image_side or width * height > limits.image_pixels:
                    raise ProxyError('image_pixel_limit')
                format_name = opened.format.lower()
                opened.verify()
            with Image.open(io.BytesIO(data)) as opened:
                opened.load()
                image = opened.convert('RGB')
                image.info.clear()  # Do not forward embedded EXIF/metadata.
    except ProxyError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ProxyError('invalid_image_encoding') from None
    return image, {'format': format_name, 'width': width, 'height': height,
                   'bytes': len(data), 'pixels': width * height, 'sha256': digest(data)}


def validate_text(value, maximum, required=False):
    if not isinstance(value, str) or (required and not value.strip()):
        raise ProxyError('invalid_text')
    try:
        length = len(value.encode('utf-8'))
    except UnicodeError:
        raise ProxyError('invalid_text') from None
    if length > maximum:
        raise ProxyError('text_limit')


class QwenVisionRenderer:
    """Same recipe verified by smoke_tinker_vision.py; no text-only fallback."""
    def __init__(self, tokenizer, processor, renderer):
        if type(processor).__name__ != PROCESSOR or type(renderer).__name__ != 'Qwen3_5DisableThinkingRenderer':
            raise ProxyError('renderer_identity_mismatch')
        self.tokenizer, self.processor, self.renderer = tokenizer, processor, renderer
        self.identity = {'model': MODEL, 'renderer': RENDERER, 'image_processor': PROCESSOR,
                         'processor_config_sha256': digest(processor.to_dict()),
                         'tokenizer_vocabulary_sha256': digest(tokenizer.get_vocab())}

    @classmethod
    def load(cls):
        from tinker_cookbook import renderers, tokenizer_utils
        from tinker_cookbook.image_processing_utils import get_image_processor
        tokenizer = tokenizer_utils.get_tokenizer(MODEL)
        processor = get_image_processor(MODEL)
        renderer = renderers.get_renderer(RENDERER, tokenizer, image_processor=processor)
        return cls(tokenizer, processor, renderer)

    def render(self, image, instruction, visible_text):
        from tinker_cookbook.renderers import ImagePart, Message, TextPart
        content = json.dumps({'instruction': instruction, 'visible_text': visible_text}, ensure_ascii=False, sort_keys=True)
        user = Message(role='user', content=[ImagePart(type='image', image=image), TextPart(type='text', text=content)])
        prompt = self.renderer.build_generation_prompt([user])
        images = [chunk for chunk in prompt.chunks if type(chunk).__name__ == 'ImageChunk']
        if len(images) != 1 or type(images[0].length) is not int or images[0].length <= 0:
            raise ProxyError('image_chunk_missing_or_unbounded')
        return prompt, {'input_tokens': prompt.length, 'image_tokens': images[0].length,
                        'chunk_types': [type(chunk).__name__ for chunk in prompt.chunks]}

    def decode(self, tokens):
        return self.tokenizer.decode(tokens, skip_special_tokens=True)


class TinkerVisionBackend:
    """Provider setup is explicit; constructing the adapter itself is offline."""
    def __init__(self, sampling_client, renderer, *, checkpoint=None, seed=23):
        if checkpoint is not None and (not isinstance(checkpoint, str) or not re.fullmatch(r'tinker://[A-Za-z0-9_./:-]{1,400}', checkpoint)):
            raise ProxyError('invalid_sampler_checkpoint')
        if type(seed) is not int or not 0 <= seed < 2**31:
            raise ProxyError('invalid_sampling_seed')
        self.sampling_client, self.renderer, self.seed = sampling_client, renderer, seed
        self.identity = {**renderer.identity, 'sampling_kind': 'checkpoint' if checkpoint else 'base',
                         'checkpoint_sha256': digest(checkpoint or MODEL), 'temperature': 0, 'seed': seed}

    @classmethod
    def from_service(cls, service, renderer, *, checkpoint=None, seed=23):
        if checkpoint is not None and (not isinstance(checkpoint, str) or not re.fullmatch(r'tinker://[A-Za-z0-9_./:-]{1,400}', checkpoint)):
            raise ProxyError('invalid_sampler_checkpoint')
        if type(seed) is not int or not 0 <= seed < 2**31:
            raise ProxyError('invalid_sampling_seed')
        client = service.create_sampling_client(model_path=checkpoint) if checkpoint else service.create_sampling_client(base_model=MODEL)
        if client.get_base_model() != MODEL:
            raise ProxyError('sampler_base_model_mismatch')
        return cls(client, renderer, checkpoint=checkpoint, seed=seed)

    def render(self, image, instruction, visible_text):
        return self.renderer.render(image, instruction, visible_text)

    def submit(self, prompt, max_output_tokens):
        from tinker import types
        return self.sampling_client.sample(prompt=prompt, num_samples=1,
            sampling_params=types.SamplingParams(max_tokens=max_output_tokens, temperature=0,
                seed=self.seed, stop=self.renderer.renderer.get_stop_sequences()))

    def decode(self, tokens):
        return self.renderer.decode(tokens)


def error_subtype(exc):
    status = getattr(exc, 'status_code', None)
    if status is None:
        status = getattr(getattr(exc, 'response', None), 'status_code', None)
    if status in (401, 403): return 'provider_authentication'
    if status == 429: return 'provider_rate_limit'
    if type(status) is int and status >= 500: return 'provider_unavailable'
    name = type(exc).__name__.lower()
    if isinstance(exc, TimeoutError) or 'timeout' in name: return 'provider_timeout_uncertain'
    if any(word in name for word in ('connect', 'transport', 'protocol')): return 'provider_transport_uncertain'
    return 'provider_error_uncertain'


def public_receipt(result):
    """Allowlist only; model text and arbitrary request IDs are not log fields."""
    return {'version': VERSION, 'model': MODEL, 'renderer': RENDERER,
            'request_id_sha256': digest(result.get('request_id', '')),
            'binding_sha256': result.get('binding_sha256'), 'status': result['status'],
            'error_subtype': result.get('error_subtype'), 'usage': result.get('usage'),
            'image': result.get('image'), 'elapsed_seconds': result.get('elapsed_seconds'),
            'reused': result.get('reused', False), 'new_dispatch': result.get('new_dispatch', False),
            'stop_reason': result.get('stop_reason'),
            'text_sha256': digest(result['text']) if result.get('text') is not None else None,
            'cost_usd': None}


class VisionSamplingAdapter:
    def __init__(self, backend, journal_directory, *, limits=None):
        self.backend, self.limits = backend, limits or Limits()
        if backend.identity.get('model') != MODEL or backend.identity.get('renderer') != RENDERER or backend.identity.get('image_processor') != PROCESSOR:
            raise ProxyError('backend_identity_mismatch')
        self.binding = {'version': VERSION, 'backend': backend.identity, 'limits': asdict(self.limits)}
        self.binding_sha256 = digest(self.binding)
        self.root = Path(journal_directory)
        if self.root.is_symlink(): raise ProxyError('invalid_journal_path')
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.root.chmod(0o700)
        self.db_path = self.root / 'requests.sqlite3'
        for name in ('requests.sqlite3', 'journal.lock', 'usage.jsonl'):
            if (self.root / name).is_symlink(): raise ProxyError('invalid_journal_path')
        self.mutex = threading.RLock()
        with self.locked(), self.connection() as connection:
            connection.execute('CREATE TABLE IF NOT EXISTS metadata (id INTEGER PRIMARY KEY, binding TEXT NOT NULL)')
            connection.execute('CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, state TEXT NOT NULL, result TEXT)')
            row = connection.execute('SELECT binding FROM metadata WHERE id=1').fetchone()
            encoded = json.dumps(self.binding, sort_keys=True)
            if row is not None and row[0] != encoded: raise ProxyError('journal_binding_mismatch')
            connection.execute('INSERT OR IGNORE INTO metadata VALUES (1, ?)', (encoded,))
        self.db_path.chmod(0o600)

    @contextmanager
    def locked(self):
        with self.mutex, (self.root / 'journal.lock').open('a') as lock:
            os.chmod(lock.name, 0o600)
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(self.db_path, timeout=30)
        try:
            connection.execute('PRAGMA synchronous=FULL')
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def failure(self, request_id, subtype, *, dispatched=False, usage=None):
        return {'version': VERSION, 'model': MODEL, 'renderer': RENDERER,
                'request_id': request_id, 'binding_sha256': self.binding_sha256,
                'status': 'error', 'error_subtype': subtype, 'text': None, 'usage': usage,
                'new_dispatch': dispatched, 'dispatch_may_have_occurred': dispatched,
                'reused': False, 'cost_usd': None}

    def sample(self, *, request_id, image_bytes, instruction, visible_text=''):
        # No file/URL input resolver exists anywhere in this request path.
        if not isinstance(request_id, str) or not REQUEST_ID.fullmatch(request_id):
            return self.failure('', 'invalid_request_id')
        try:
            validate_text(instruction, self.limits.instruction_bytes, required=True)
            validate_text(visible_text, self.limits.visible_text_bytes)
            image, image_info = image_from_bytes(image_bytes, self.limits)
        except ProxyError as exc:
            return self.failure(request_id, exc.subtype)
        identity = digest({'binding': self.binding_sha256, 'image_sha256': image_info['sha256'],
                           'instruction': instruction, 'visible_text': visible_text})
        with self.locked():
            with self.connection() as connection:
                prior = connection.execute('SELECT fingerprint,state,result FROM requests WHERE id=?', (request_id,)).fetchone()
                if prior:
                    if prior[0] != identity: return self.failure(request_id, 'request_id_collision')
                    if prior[1] != 'complete':
                        result = self.failure(request_id, 'prior_dispatch_uncertain', dispatched=True)
                        result.update(new_dispatch=False, reused=True)
                        return result
                    result = json.loads(prior[2]);result.update(reused=True, new_dispatch=False)
                    return result
                if connection.execute('SELECT count(*) FROM requests').fetchone()[0] >= self.limits.max_actions:
                    return self.failure(request_id, 'action_limit')
            try:
                prompt, rendered = self.backend.render(image, instruction, visible_text)
                length, image_tokens = rendered['input_tokens'], rendered['image_tokens']
                if type(length) is not int or type(image_tokens) is not int or image_tokens <= 0 or image_tokens >= length:
                    raise ProxyError('invalid_multimodal_token_count')
                if length > self.limits.input_tokens: raise ProxyError('input_token_limit')
                if 'ImageChunk' not in rendered['chunk_types']: raise ProxyError('image_chunk_missing_or_unbounded')
            except Exception as exc:
                return self.failure(request_id, exc.subtype if isinstance(exc, ProxyError) else 'rendering_error')
            # Commit the durable intent BEFORE the single provider dispatch.
            with self.connection() as connection:
                connection.execute('INSERT INTO requests VALUES (?,?,?,NULL)', (request_id, identity, 'intent'))
            started = time.monotonic()
            usage = {'input_tokens': length, 'image_tokens': image_tokens, 'output_tokens': None,
                     'prompt_cache_hit_tokens': None, 'basis': 'rendered multimodal length and returned sample length; not billing',
                     'provider_billed_tokens': None}
            try:
                future = self.backend.submit(prompt, self.limits.output_tokens)
                response = future.result(timeout=self.limits.request_timeout_seconds)
                sequences = response.sequences
                if len(sequences) != 1: raise ProxyError('provider_response_invalid')
                tokens = sequences[0].tokens
                if not isinstance(tokens, (list, tuple)) or any(type(x) is not int or x < 0 for x in tokens) or len(tokens) > self.limits.output_tokens:
                    raise ProxyError('provider_response_invalid')
                usage['output_tokens'] = len(tokens)
                stop_reason = getattr(sequences[0], 'stop_reason', None)
                if stop_reason not in (None, 'stop', 'length'):
                    raise ProxyError('provider_response_invalid')
                cached = getattr(response, 'prompt_cache_hit_tokens', None)
                if cached is not None and (type(cached) is not int or not 0 <= cached <= length):
                    raise ProxyError('provider_response_invalid')
                usage['prompt_cache_hit_tokens'] = cached
                text = self.backend.decode(tokens)
                if not isinstance(text, str) or len(text.encode()) > self.limits.decoded_output_bytes:
                    raise ProxyError('decoded_output_limit')
                result = {'version': VERSION, 'model': MODEL, 'renderer': RENDERER,
                          'request_id': request_id, 'binding_sha256': self.binding_sha256,
                          'status': 'completed', 'error_subtype': None, 'text': text, 'usage': usage,
                          'stop_reason': stop_reason,
                          'new_dispatch': True, 'reused': False, 'cost_usd': None}
            except Exception as exc:
                subtype = exc.subtype if isinstance(exc, ProxyError) else error_subtype(exc)
                result = self.failure(request_id, subtype, dispatched=True, usage=usage)
            result.update(image=image_info, elapsed_seconds=time.monotonic() - started)
            with self.connection() as connection:
                connection.execute('UPDATE requests SET state=?, result=? WHERE id=?', ('complete', json.dumps(result), request_id))
            try:
                fd = os.open(self.root / 'usage.jsonl', os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
                with os.fdopen(fd, 'a') as stream:
                    stream.write(json.dumps(public_receipt(result)) + '\n');stream.flush();os.fsync(stream.fileno())
            except OSError:
                # Durable journal result is authoritative; do not resample to repair a log.
                pass
            return result

    def handle_json(self, body):
        try:
            if not isinstance(body, bytes) or len(body) > self.limits.http_body_bytes:
                raise ProxyError('request_body_limit')
            request = json.loads(body)
            if not isinstance(request, dict) or set(request) != {'request_id', 'image_base64', 'instruction', 'visible_text'}:
                raise ProxyError('invalid_request_schema')
            encoded = request['image_base64']
            if not isinstance(encoded, str) or len(encoded) > ((self.limits.image_bytes + 2) // 3) * 4:
                raise ProxyError('invalid_image_bytes')
            try: image_bytes = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError): raise ProxyError('invalid_image_encoding') from None
            return self.sample(request_id=request['request_id'], image_bytes=image_bytes,
                               instruction=request['instruction'], visible_text=request['visible_text'])
        except ProxyError as exc:
            return self.failure('', exc.subtype)
        except (ValueError, UnicodeError, TypeError):
            return self.failure('', 'invalid_json')


def make_http_server(adapter, bearer_token, host='127.0.0.1', port=8089):
    if not isinstance(bearer_token, str) or len(bearer_token) < 24:
        raise ProxyError('proxy_bearer_required')
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass

        def respond(self, value, status=200):
            body = json.dumps(value).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers();self.wfile.write(body)

        def do_GET(self):
            if self.path != '/health': self.respond({'error_subtype': 'not_found'}, 404);return
            self.respond({'ready': True, 'version': VERSION, 'model': MODEL, 'renderer': RENDERER,
                          'binding_sha256': adapter.binding_sha256, 'limits': asdict(adapter.limits)})

        def do_POST(self):
            if self.path != '/sample': self.respond({'error_subtype': 'not_found'}, 404);return
            if not hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + bearer_token):
                self.respond({'error_subtype': 'unauthorized'}, 401);return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= adapter.limits.http_body_bytes or self.headers.get('Transfer-Encoding'):
                    raise ProxyError('request_body_limit')
                self.connection.settimeout(30)
                body = self.rfile.read(size)
                if len(body) != size: raise ProxyError('incomplete_request_body')
                result = adapter.handle_json(body)
                subtype = result.get('error_subtype')
                status = 200 if result['status'] == 'completed' else 409 if subtype in ('request_id_collision', 'prior_dispatch_uncertain', 'action_limit') else 502 if result.get('dispatch_may_have_occurred') else 400
                self.respond(result, status)
            except Exception:
                self.respond({'status': 'error', 'error_subtype': 'request_transport_error'}, 400)
    return HTTPServer((host, port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--journal', type=Path, required=True)
    parser.add_argument('--campaign-id', required=True)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8089)
    parser.add_argument('--max-actions', type=int, default=90)
    parser.add_argument('--max-input-tokens', type=int, default=32768)
    parser.add_argument('--max-output-tokens', type=int, default=512)
    args = parser.parse_args()
    service = None
    session_status = 'errored'
    try:
        limits = Limits(max_actions=args.max_actions, input_tokens=args.max_input_tokens, output_tokens=args.max_output_tokens)
        token = os.environ.get('CUA_VISION_PROXY_TOKEN', '')
        if len(token) < 24 or not os.environ.get('TINKER_API_KEY'):
            raise ProxyError('required_credentials_missing')
        renderer = QwenVisionRenderer.load()
        import tinker
        service = tinker.ServiceClient(user_metadata=campaign_metadata(args.campaign_id))
        backend = TinkerVisionBackend.from_service(service, renderer, checkpoint=os.environ.get('TINKER_SAMPLER_PATH'))
        adapter = VisionSamplingAdapter(backend, args.journal, limits=limits)
        server = make_http_server(adapter, token, args.host, args.port)
        print(json.dumps({'ready': True, 'version': VERSION, 'binding_sha256': adapter.binding_sha256}), flush=True)
        try: server.serve_forever()
        finally: server.server_close()
        session_status = 'success'
    except Exception as exc:
        print(json.dumps({'ready': False, 'error_subtype': exc.subtype if isinstance(exc, ProxyError) else 'initialization_error'}), flush=True)
        raise SystemExit(1)
    finally:
        if service is not None:
            try: service.close(session_status).result(timeout=30)
            except Exception: pass


if __name__ == '__main__':
    main()
