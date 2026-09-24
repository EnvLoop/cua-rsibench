"""No paid calls. Cached renderer integration is an explicit offline opt-in."""
import base64
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import http.client
import importlib.util
import io
import json
import os
from pathlib import Path
import sqlite3
import stat
import tempfile
import threading
from types import SimpleNamespace
import unittest

from PIL import Image

from cursibench.scale_vision_proxy import (
    Limits, MODEL, PROCESSOR, RENDERER, ProxyError, QwenVisionRenderer,
    TinkerVisionBackend, VisionSamplingAdapter, error_subtype, image_from_bytes,
    make_http_server, public_receipt,
)


def picture(format='PNG', color='red', size=(32, 32)):
    stream = io.BytesIO()
    Image.new('RGB', size, color).save(stream, format=format)
    return stream.getvalue()


class FakeFuture:
    def __init__(self, backend): self.backend = backend

    def result(self, timeout):
        self.backend.timeouts.append(timeout)
        if self.backend.error: raise self.backend.error
        return SimpleNamespace(sequences=[SimpleNamespace(tokens=self.backend.tokens, stop_reason='stop')],
                               prompt_cache_hit_tokens=self.backend.cache_tokens)


class FakeBackend:
    def __init__(self):
        self.identity = {'model': MODEL, 'renderer': RENDERER, 'image_processor': PROCESSOR,
                         'sampling_kind': 'base', 'seed': 23}
        self.submissions = []
        self.rendered = []
        self.timeouts = []
        self.tokens = [1, 2, 3]
        self.cache_tokens = 0
        self.error = None
        self.text = '{"action":"click","x":10,"y":20}'
        self.metadata = {'input_tokens': 20, 'image_tokens': 12,
                         'chunk_types': ['EncodedTextChunk', 'ImageChunk', 'EncodedTextChunk']}

    def render(self, image, instruction, visible_text):
        self.rendered.append((image, instruction, visible_text))
        return object(), dict(self.metadata)

    def submit(self, prompt, max_output_tokens):
        self.submissions.append(max_output_tokens)
        return FakeFuture(self)

    def decode(self, tokens): return self.text


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'journal'
        self.backend = FakeBackend()
        self.adapter = VisionSamplingAdapter(self.backend, self.root)
        self.request = {'request_id': 'request_001', 'image_bytes': picture(),
                        'instruction': 'Use the visible page.', 'visible_text': 'Save button'}

    def sample(self, **updates): return self.adapter.sample(**(self.request | updates))

    def test_png_and_jpeg_pass_actual_rgb_image_and_bounded_sampling(self):
        for index, format in enumerate(('PNG', 'JPEG')):
            result = self.sample(request_id=f'request_{index:03}', image_bytes=picture(format))
            self.assertEqual(result['status'], 'completed')
            image, instruction, visible = self.backend.rendered[-1]
            self.assertIsInstance(image, Image.Image)
            self.assertEqual((image.mode, image.size, image.info), ('RGB', (32, 32), {}))
            self.assertEqual((instruction, visible), ('Use the visible page.', 'Save button'))
            self.assertEqual(result['usage']['input_tokens'], 20)
            self.assertEqual(result['usage']['image_tokens'], 12)
            self.assertEqual(result['usage']['output_tokens'], 3)
            self.assertIsNone(result['usage']['provider_billed_tokens'])
            self.assertIsNone(result['cost_usd'])
            self.assertEqual(result['text'], self.backend.text)
            self.assertEqual(result['stop_reason'], 'stop')
        self.assertEqual(self.backend.submissions, [512, 512])
        self.assertEqual(self.backend.timeouts, [240, 240])

    def test_completed_id_is_reused_after_restart_without_inference(self):
        first = self.sample()
        reused = self.sample()
        replacement = FakeBackend()
        restarted = VisionSamplingAdapter(replacement, self.root)
        after_restart = restarted.sample(**self.request)
        self.assertTrue(first['new_dispatch'])
        for result in (reused, after_restart):
            self.assertEqual(result['text'], first['text'])
            self.assertEqual(result['usage'], first['usage'])
            self.assertTrue(result['reused'])
            self.assertFalse(result['new_dispatch'])
        self.assertEqual(len(self.backend.submissions), 1)
        self.assertEqual(replacement.submissions, [])
        self.assertEqual(len((self.root / 'usage.jsonl').read_text().splitlines()), 1)

    def test_request_id_collision_for_image_instruction_or_visible_text(self):
        self.sample()
        for change in ({'image_bytes': picture(color='blue')}, {'instruction': 'Different instruction'},
                       {'visible_text': 'Different page'}):
            with self.subTest(change=list(change)):
                self.assertEqual(self.sample(**change)['error_subtype'], 'request_id_collision')
        self.assertEqual(len(self.backend.submissions), 1)

    def test_duplicate_threads_and_separate_adapters_dispatch_once(self):
        other = FakeBackend()
        other_adapter = VisionSamplingAdapter(other, self.root)
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit((self.adapter if i % 2 else other_adapter).sample, **self.request)
                       for i in range(8)]
            results = [f.result(timeout=5) for f in futures]
        self.assertEqual(sum(x['new_dispatch'] for x in results), 1)
        self.assertEqual(len(self.backend.submissions) + len(other.submissions), 1)

    def test_interrupted_dispatch_remains_uncertain_and_never_replays(self):
        class SimulatedProcessInterruption(BaseException): pass
        self.backend.error = SimulatedProcessInterruption()
        with self.assertRaises(SimulatedProcessInterruption): self.sample()
        self.backend.error = None
        result = VisionSamplingAdapter(self.backend, self.root).sample(**self.request)
        self.assertEqual(result['error_subtype'], 'prior_dispatch_uncertain')
        self.assertTrue(result['dispatch_may_have_occurred'])
        self.assertFalse(result['new_dispatch'])
        self.assertEqual(len(self.backend.submissions), 1)
        with closing(sqlite3.connect(self.root / 'requests.sqlite3')) as db:
            self.assertEqual(db.execute('SELECT state FROM requests').fetchone(), ('intent',))

    def test_provider_timeout_is_cached_charged_and_sanitized(self):
        adapter = VisionSamplingAdapter(self.backend, Path(self.temp.name) / 'bounded', limits=Limits(max_actions=1))
        self.backend.error = TimeoutError('secret-provider-token raw-envelope private-checkpoint')
        result = adapter.sample(**self.request)
        self.assertEqual(result['error_subtype'], 'provider_timeout_uncertain')
        self.assertTrue(result['dispatch_may_have_occurred'])
        self.assertIsNone(result['usage']['output_tokens'])
        self.assertNotIn('secret-provider-token', json.dumps(result))
        self.backend.error = None
        self.assertTrue(adapter.sample(**self.request)['reused'])
        self.assertEqual(adapter.sample(**(self.request | {'request_id': 'request_002'}))['error_subtype'], 'action_limit')
        self.assertEqual(len(self.backend.submissions), 1)

    def test_invalid_inputs_and_render_failure_do_not_consume_action(self):
        for changes, expected in [({'request_id': '../secret'}, 'invalid_request_id'),
                                  ({'request_id': 1}, 'invalid_request_id'),
                                  ({'image_bytes': '/tmp/image.png'}, 'invalid_image_bytes'),
                                  ({'image_bytes': b'https://example.com/a.png'}, 'invalid_image_encoding'),
                                  ({'instruction': ''}, 'invalid_text'),
                                  ({'visible_text': []}, 'invalid_text'),
                                  ({'instruction': '\ud800'}, 'invalid_text'),
                                  ({'instruction': 'a' * 16385}, 'text_limit')]:
            with self.subTest(expected=expected):
                self.assertEqual(self.sample(**changes)['error_subtype'], expected)
        self.backend.metadata['input_tokens'] = 40000
        self.assertEqual(self.sample()['error_subtype'], 'input_token_limit')
        self.backend.metadata['input_tokens'] = 20
        self.backend.metadata['chunk_types'] = ['EncodedTextChunk']
        self.assertEqual(self.sample()['error_subtype'], 'image_chunk_missing_or_unbounded')
        with closing(sqlite3.connect(self.root / 'requests.sqlite3')) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM requests').fetchone()[0], 0)
        self.assertEqual(self.backend.submissions, [])

    def test_invalid_provider_output_is_saved_without_replay(self):
        for index, tokens in enumerate(([1] * 513, [True], [-1], ['text'])):
            self.backend.tokens = tokens
            result = self.sample(request_id=f'invalid_{index}')
            self.assertEqual(result['error_subtype'], 'provider_response_invalid')
            self.assertIsNone(result['text'])
            self.assertTrue(self.sample(request_id=f'invalid_{index}')['reused'])
        self.backend.tokens = [1]
        self.backend.cache_tokens = 21
        self.assertEqual(self.sample(request_id='bad_cache')['error_subtype'], 'provider_response_invalid')
        self.backend.cache_tokens = 0
        self.backend.text = 'a' * 65537
        self.assertEqual(self.sample(request_id='bad_decode')['error_subtype'], 'decoded_output_limit')

    def test_journal_binds_model_sampler_seed_and_limits(self):
        for field, value in [('seed', 24), ('sampling_kind', 'checkpoint'), ('checkpoint_sha256', 'different')]:
            backend = FakeBackend();backend.identity[field] = value
            with self.assertRaisesRegex(ProxyError, 'journal_binding_mismatch'):
                VisionSamplingAdapter(backend, self.root)
        with self.assertRaisesRegex(ProxyError, 'journal_binding_mismatch'):
            VisionSamplingAdapter(self.backend, self.root, limits=Limits(max_actions=1))
        wrong = FakeBackend();wrong.identity['model'] = 'Qwen/Other'
        with self.assertRaisesRegex(ProxyError, 'backend_identity_mismatch'):
            VisionSamplingAdapter(wrong, self.root)

    def test_private_journal_permissions_and_public_log_redaction(self):
        self.backend.text = 'private-decoded-response-canary'
        result = self.sample(request_id='private_request_canary', instruction='private-instruction-canary',
                             visible_text='private-visible-text-canary')
        serialized = (self.root / 'usage.jsonl').read_text()
        for canary in ['private_request_canary', 'private-decoded-response-canary',
                       'private-instruction-canary', 'private-visible-text-canary',
                       base64.b64encode(self.request['image_bytes']).decode()]:
            self.assertNotIn(canary, serialized)
        self.assertEqual(json.loads(serialized), public_receipt(result))
        self.assertEqual(stat.S_IMODE(self.root.stat().st_mode), 0o700)
        for name in ('requests.sqlite3', 'journal.lock', 'usage.jsonl'):
            self.assertEqual(stat.S_IMODE((self.root / name).stat().st_mode), 0o600)

    def test_journal_symlink_rejected(self):
        target = Path(self.temp.name) / 'link';target.symlink_to(self.root)
        with self.assertRaisesRegex(ProxyError, 'invalid_journal_path'):
            VisionSamplingAdapter(self.backend, target)

    def test_json_contract_allows_only_inline_base64_image(self):
        body = {'request_id': 'request_001', 'image_base64': base64.b64encode(self.request['image_bytes']).decode(),
                'instruction': 'Use this page.', 'visible_text': ''}
        for invalid, subtype in [(body | {'image_url': 'https://example.com/a.png'}, 'invalid_request_schema'),
                                 (body | {'image_base64': '/tmp/image.png'}, 'invalid_image_encoding'),
                                 (body | {'image_base64': 'data:image/png;base64,AAAA'}, 'invalid_image_encoding'),
                                 (body | {'image_base64': None}, 'invalid_image_bytes')]:
            self.assertEqual(self.adapter.handle_json(json.dumps(invalid).encode())['error_subtype'], subtype)
        self.assertEqual(self.adapter.handle_json(b'not-json')['error_subtype'], 'invalid_json')
        self.assertEqual(self.backend.submissions, [])
        self.assertEqual(self.adapter.handle_json(json.dumps(body).encode())['status'], 'completed')


class ImageAndLimitTests(unittest.TestCase):
    def test_formats_byte_and_pixel_caps(self):
        for data, limits, subtype in [(picture('GIF'), Limits(), 'unsupported_image_format'),
                                     (picture(), Limits(image_bytes=10), 'invalid_image_bytes'),
                                     (picture(size=(33, 32)), Limits(image_pixels=1024), 'image_pixel_limit'),
                                     (picture(size=(33, 32)), Limits(image_side=32), 'image_pixel_limit'),
                                     (picture()[:-15], Limits(), 'invalid_image_encoding'),
                                     (bytearray(picture()), Limits(), 'invalid_image_bytes')]:
            with self.subTest(subtype=subtype), self.assertRaisesRegex(ProxyError, subtype):
                image_from_bytes(data, limits)

    def test_animated_png_is_rejected(self):
        stream = io.BytesIO()
        Image.new('RGB', (32, 32), 'red').save(stream, format='PNG', save_all=True,
                                             append_images=[Image.new('RGB', (32, 32), 'blue')])
        with self.assertRaisesRegex(ProxyError, 'unsupported_image_format'):
            image_from_bytes(stream.getvalue(), Limits())

    def test_invalid_limits_are_rejected(self):
        for change in [{'image_bytes': 0}, {'max_actions': True}, {'request_timeout_seconds': 901},
                       {'input_tokens': 64000}, {'output_tokens': 4097}, {'image_pixels': 20_000_000}]:
            with self.subTest(change=change), self.assertRaisesRegex(ProxyError, 'invalid_limits'):
                Limits(**change)

    def test_provider_exception_body_never_becomes_error_subtype(self):
        for status, expected in [(401, 'provider_authentication'), (403, 'provider_authentication'),
                                 (429, 'provider_rate_limit'), (502, 'provider_unavailable')]:
            exception = RuntimeError('private provider body');exception.status_code = status
            self.assertEqual(error_subtype(exception), expected)
        self.assertEqual(error_subtype(RuntimeError('raw-secret')), 'provider_error_uncertain')


class HttpTests(unittest.TestCase):
    def test_local_authentication_request_contract_and_idempotence(self):
        with tempfile.TemporaryDirectory() as temp:
            backend = FakeBackend();adapter = VisionSamplingAdapter(backend, temp)
            token = 'local-only-test-bearer-token'
            server = make_http_server(adapter, token, port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True);thread.start()
            try:
                conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
                conn.request('GET', '/health');response = conn.getresponse()
                health = json.loads(response.read())
                self.assertEqual(response.status, 200)
                self.assertEqual(health['model'], MODEL)
                self.assertNotIn(token, json.dumps(health))
                body = json.dumps({'request_id': 'request_001', 'image_base64': base64.b64encode(picture()).decode(),
                                   'instruction': 'Click Save.', 'visible_text': ''})
                conn.request('POST', '/sample', body=body);response = conn.getresponse()
                self.assertEqual(response.status, 401);response.read()
                for reused in (False, True):
                    conn.request('POST', '/sample', body=body, headers={'Authorization': 'Bearer ' + token})
                    response = conn.getresponse();result = json.loads(response.read())
                    self.assertEqual(response.status, 200)
                    self.assertEqual(result['reused'], reused)
                self.assertEqual(len(backend.submissions), 1)
                conn.close()
            finally:
                server.shutdown();server.server_close();thread.join(timeout=3)


@unittest.skipUnless(importlib.util.find_spec('tinker'), 'optional Tinker SDK required')
class TinkerBindingTests(unittest.TestCase):
    def test_base_and_checkpoint_clients_and_exact_sampling_parameters(self):
        calls = []
        class Client:
            def get_base_model(self): return MODEL
            def sample(self, **kwargs): calls.append(kwargs);return 'future'
        class Service:
            def create_sampling_client(self, **kwargs): calls.append(kwargs);return Client()
        renderer = SimpleNamespace(identity=FakeBackend().identity,
                                   renderer=SimpleNamespace(get_stop_sequences=lambda: ['<|im_end|>']))
        for checkpoint in (None, 'tinker://private-session/sampler_weights/step-0001'):
            backend = TinkerVisionBackend.from_service(Service(), renderer, checkpoint=checkpoint)
            self.assertEqual(calls[-1], {'model_path': checkpoint} if checkpoint else {'base_model': MODEL})
            self.assertEqual(backend.submit('prompt', 48), 'future')
            parameters = calls[-1]['sampling_params']
            self.assertEqual((parameters.max_tokens, parameters.temperature, parameters.seed), (48, 0, 23))
            self.assertEqual(parameters.stop, ['<|im_end|>'])
            self.assertEqual(calls[-1]['num_samples'], 1)
            self.assertNotIn('private-session', json.dumps(backend.identity))

    def test_wrong_checkpoint_model_and_arbitrary_paths_rejected(self):
        calls = []
        class Service:
            def create_sampling_client(self, **kwargs):
                calls.append(kwargs)
                return SimpleNamespace(get_base_model=lambda: 'Qwen/Other')
        renderer = SimpleNamespace(identity=FakeBackend().identity)
        with self.assertRaisesRegex(ProxyError, 'sampler_base_model_mismatch'):
            TinkerVisionBackend.from_service(Service(), renderer)
        for checkpoint in ('/tmp/model', 'https://example.com/model', 'tinker://bad?query'):
            with self.assertRaisesRegex(ProxyError, 'invalid_sampler_checkpoint'):
                TinkerVisionBackend.from_service(Service(), renderer, checkpoint=checkpoint)
        with self.assertRaisesRegex(ProxyError, 'invalid_sampling_seed'):
            TinkerVisionBackend.from_service(Service(), renderer, seed=True)
        self.assertEqual(len(calls), 1)


@unittest.skipUnless(os.environ.get('CUA_TEST_CACHED_QWEN_RENDERER') == '1', 'explicit cached-renderer offline integration')
class CachedQwenRendererTests(unittest.TestCase):
    def test_validated_renderer_contains_real_image_chunk_and_no_paid_client(self):
        # Fail rather than download assets if the validation cache is missing.
        os.environ['HF_HUB_OFFLINE'] = '1';os.environ['TRANSFORMERS_OFFLINE'] = '1'
        renderer = QwenVisionRenderer.load()
        image, _ = image_from_bytes(picture(size=(112, 112)), Limits())
        prompt, metadata = renderer.render(image, 'Return exactly RED.', 'A red square is visible.')
        self.assertEqual(type(renderer.processor).__name__, PROCESSOR)
        self.assertEqual(type(renderer.renderer).__name__, 'Qwen3_5DisableThinkingRenderer')
        self.assertIn('ImageChunk', metadata['chunk_types'])
        self.assertEqual(metadata['input_tokens'], prompt.length)
        self.assertGreater(metadata['image_tokens'], 0)
        self.assertGreater(metadata['input_tokens'], metadata['image_tokens'])
        self.assertLess(metadata['input_tokens'], Limits().input_tokens)
        self.assertEqual(renderer.decode(renderer.tokenizer.encode('RED', add_special_tokens=False)), 'RED')


if __name__ == '__main__':
    unittest.main()
