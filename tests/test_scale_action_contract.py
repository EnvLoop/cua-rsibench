"""Offline boundary tests: no Office account, provider, or UI dispatch."""
import io
import json
import unittest

from PIL import Image

from cursibench.scale_action_contract import (
    ContractError, ContractLimits, VERSION, make_observation, public_receipt,
    render_for_proxy, sample_and_validate_action, validate_action,
)


def screenshot(color='white', size=(64, 48)):
    stream = io.BytesIO()
    Image.new('RGB', size, color).save(stream, format='PNG')
    return stream.getvalue()


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.image = screenshot()
        self.source = {
            'task_id': 'excel.001', 'task_binding_sha256': 'a' * 64,
            'instruction': 'Correct the quarterly forecast.', 'step': 0,
            'screenshot_bytes': self.image,
            'a11y_text': 'Forecast sheet, cell B2, Save button',
            'dom_text': '<button>Save</button>',
            'controls': [
                {'ref': 'cell-B2', 'role': 'cell', 'label': 'B2', 'visible': True, 'enabled': True},
                {'ref': 'save', 'role': 'button', 'label': 'Save', 'visible': True, 'enabled': True},
                {'ref': 'locked', 'role': 'button', 'label': 'Restricted', 'visible': True, 'enabled': False},
            ],
            'memory': 'Inspect B2 before changing it.',
        }
        self.frame = make_observation(**self.source)

    def action(self, kind='click', **updates):
        data = {
            'version': VERSION, 'task_id': self.frame.task_id,
            'task_binding_sha256': self.frame.task_binding_sha256,
            'step': self.frame.step, 'frame_id': self.frame.frame_id,
            'type': kind, 'memory': 'B2 updated.',
        }
        if kind == 'click':
            data['target'] = {'ref': 'save'}
        elif kind == 'type':
            data.update(target={'ref': 'cell-B2'}, mode='fill', text='125000')
        elif kind == 'key':
            data['key'] = 'Enter'
        elif kind == 'scroll':
            data.update(dx=0, dy=200)
        elif kind == 'drag':
            data.update({'from': {'x': 2, 'y': 3}, 'to': {'x': 21, 'y': 30}})
        elif kind == 'wait':
            data['duration_ms'] = 500
        data.update(updates)
        return data

    def check(self, action):
        return validate_action(json.dumps(action), self.frame,
                               current_frame_id=self.frame.frame_id)

    def assert_bad(self, action, code):
        with self.assertRaises(ContractError) as caught:
            self.check(action)
        self.assertEqual(caught.exception.code, code)

    def test_observation_carries_verified_image_and_all_visible_modalities(self):
        self.assertEqual(self.frame.screenshot['sha256'], __import__('hashlib').sha256(self.image).hexdigest())
        self.assertEqual((self.frame.screenshot['width'], self.frame.screenshot['height']), (64, 48))
        self.assertEqual(self.frame.screenshot['bytes'], len(self.image))
        self.assertEqual(self.frame.modalities, ('screenshot', 'a11y', 'dom'))
        rendered = render_for_proxy(self.frame)
        self.assertEqual(rendered['image_bytes'], self.image)
        instruction = json.loads(rendered['instruction'])
        visible = json.loads(rendered['visible_text'])
        self.assertEqual(instruction['task_binding_sha256'], 'a' * 64)
        self.assertEqual(instruction['previous_action_result'], None)
        self.assertEqual(instruction['memory'], 'Inspect B2 before changing it.')
        self.assertEqual(visible['controls'][1]['ref'], 'save')
        self.assertEqual(visible['dom_text'], '<button>Save</button>')

    def test_every_allowed_action_and_coordinate_or_current_ref_target(self):
        for kind in ('click', 'type', 'key', 'scroll', 'drag', 'wait', 'finish'):
            with self.subTest(kind=kind):
                self.assertEqual(self.check(self.action(kind))['type'], kind)
        self.assertEqual(self.check(self.action(target={'x': 63, 'y': 47}))['target'], {'x': 63, 'y': 47})
        self.assertEqual(self.check(self.action('key', target={'ref': 'cell-B2'}))['key'], 'Enter')
        self.assertEqual(self.check(self.action('scroll', target={'x': 1, 'y': 2}))['dy'], 200)
        self.assertEqual(self.check(self.action('drag', **{'from': {'ref': 'cell-B2'}, 'to': {'x': 5, 'y': 6}}))['type'], 'drag')

    def test_stale_task_step_frame_expiry_and_refs_rejected(self):
        other = make_observation(**self.source)
        self.assertNotEqual(other.frame_id, self.frame.frame_id)
        with self.assertRaisesRegex(ContractError, 'stale_frame'):
            validate_action(self.action(), self.frame, current_frame_id=other.frame_id)
        self.assert_bad(self.action(task_id='excel.002'), 'stale_frame')
        self.assert_bad(self.action(task_binding_sha256='b' * 64), 'stale_frame')
        self.assert_bad(self.action(step=1), 'stale_frame')
        self.assert_bad(self.action(frame_id=other.frame_id), 'stale_frame')
        self.assert_bad(self.action(target={'ref': 'old-ref'}), 'stale_frame')
        self.assert_bad(self.action(target={'ref': 'locked'}), 'stale_frame')
        with self.assertRaisesRegex(ContractError, 'expired_frame'):
            validate_action(self.action(), self.frame,
                            current_frame_id=self.frame.frame_id,
                            now=self.frame.expires_at + 0.001)

    def test_strict_schema_rejects_api_shell_paths_selectors_and_unsafe_values(self):
        for changes in (
            {'type': 'shell', 'command': 'rm -rf /'},
            {'api': '/v1/files'}, {'path': '/tmp/fake.xlsx'},
            {'url': 'https://example.com'}, {'selector': '#save'},
            {'target': {'selector': '#save'}},
            {'target': {'x': -1, 'y': 1}}, {'target': {'x': 64, 'y': 1}},
            {'target': {'x': True, 'y': 1}}, {'target': {'x': 1.1, 'y': 1}},
        ):
            with self.subTest(changes=changes):
                self.assert_bad(self.action(**changes), 'invalid_action')
        self.assert_bad(self.action('key', key='Control+L'), 'invalid_action')
        self.assert_bad(self.action('key', key='python -c evil'), 'invalid_action')
        self.assert_bad(self.action('key', key={'name': 'Enter'}), 'invalid_action')
        self.assert_bad(self.action(type=[]), 'invalid_action')
        self.assert_bad(self.action('scroll', dx=0, dy=0), 'invalid_action')
        self.assert_bad(self.action('scroll', dy=2001), 'invalid_action')
        self.assert_bad(self.action('wait', duration_ms=2001), 'invalid_action')
        self.assert_bad(self.action('type', text='x' * 8193), 'invalid_action')
        self.assert_bad(self.action(memory='x' * 4097), 'invalid_action')
        self.assert_bad(self.action('finish', target={'ref': 'save'}), 'invalid_action')
        duplicate = json.dumps(self.action())[:-1] + ',"type":"shell"}'
        with self.assertRaisesRegex(ContractError, 'invalid_action_json'):
            validate_action(duplicate, self.frame, current_frame_id=self.frame.frame_id)

    def test_observation_bounds_and_previous_result_schema(self):
        changes = [
            {'task_binding_sha256': 'not-a-digest'},
            {'step': True}, {'step': 1},
            {'screenshot_bytes': b'not an image'},
            {'instruction': ''}, {'memory': 'x' * 4097},
            {'issued_at': 10**1000},
            {'a11y_text': 'x' * 16385},
            {'controls': self.source['controls'] + [self.source['controls'][0]]},
            {'controls': [{'ref': 'x', 'role': 'link', 'label': 'x', 'visible': True, 'enabled': True, 'url': 'https://bad'}]},
            {'controls': [{'ref': 'hidden', 'role': 'button', 'label': 'Hidden', 'visible': False, 'enabled': True}]},
        ]
        for change in changes:
            with self.subTest(change=list(change)):
                with self.assertRaises(ContractError):
                    make_observation(**(self.source | change))
        followup = make_observation(**(self.source | {
            'step': 1, 'previous_action_result': {'status': 'applied', 'code': 'ok'},
        }))
        self.assertEqual(json.loads(render_for_proxy(followup)['instruction'])['previous_action_result'],
                         {'status': 'applied', 'code': 'ok'})
        with self.assertRaises(ContractError):
            make_observation(**(self.source | {'step': 1, 'previous_action_result': {'status': 'applied', 'code': 'ok', 'raw': 'secret'}}))
        with self.assertRaises(ContractError):
            make_observation(**(self.source | {'step': 1, 'previous_action_result': {'status': [], 'code': 'ok'}}))
        with self.assertRaises(ContractError):
            make_observation(**(self.source | {'step': 1, 'previous_action_result': {'status': 'applied', 'code': 'environment_error'}}))
        with self.assertRaises(ContractError):
            ContractLimits(max_scroll_pixels=0)

    def test_receipt_does_not_expose_task_or_sensitive_ui_text(self):
        private = make_observation(**(self.source | {
            'instruction': 'secret-instruction-987',
            'a11y_text': 'private-customer-name-456',
            'memory': 'secret-memory-123',
        }))
        action = self.action('type', text='private-typed-value-789')
        action['frame_id'] = private.frame_id
        receipt = public_receipt(private, action=action)
        encoded = json.dumps(receipt)
        for secret in ('secret-instruction-987', 'private-customer-name-456',
                       'secret-memory-123', 'private-typed-value-789',
                       'excel.001', 'Forecast sheet'):
            self.assertNotIn(secret, encoded)
        self.assertEqual(receipt['action_type'], 'type')
        self.assertEqual(receipt['screenshot']['bytes'], len(self.image))
        self.assertEqual(receipt['task_binding_sha256'], 'a' * 64)
        historic = make_observation(**(self.source | {'issued_at': 100.0}))
        historic_action = self.action('finish', frame_id=historic.frame_id)
        self.assertEqual(public_receipt(historic, action=historic_action)['action_type'], 'finish')

    def test_proxy_bridge_uses_same_frame_and_checks_live_state_after_sampling(self):
        class FakeAdapter:
            def __init__(self, output, after=None):
                self.output, self.after, self.calls = output, after, []

            def sample(self, **kwargs):
                self.calls.append(kwargs)
                if self.after:
                    self.after()
                return {'status': 'completed', 'text': self.output}

        current = [self.frame.frame_id]
        adapter = FakeAdapter(json.dumps(self.action()))
        action, result = sample_and_validate_action(
            adapter, self.frame, request_id='turn-001', current_frame_id=lambda: current[0])
        self.assertEqual(action['type'], 'click')
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(adapter.calls[0]['image_bytes'], self.image)
        self.assertEqual(adapter.calls[0]['request_id'], 'turn-001')
        stale = FakeAdapter(json.dumps(self.action()), after=lambda: current.__setitem__(0, 'new-frame'))
        with self.assertRaisesRegex(ContractError, 'stale_frame'):
            sample_and_validate_action(stale, self.frame,
                                       request_id='turn-002', current_frame_id=lambda: current[0])
        self.assertEqual(len(stale.calls), 1)
        current[0] = 'new-frame'
        untouched = FakeAdapter(json.dumps(self.action()))
        with self.assertRaisesRegex(ContractError, 'stale_frame'):
            sample_and_validate_action(untouched, self.frame,
                                       request_id='turn-003', current_frame_id=lambda: current[0])
        self.assertEqual(untouched.calls, [])
        current[0] = self.frame.frame_id
        failed = FakeAdapter(json.dumps(self.action()))
        failed.sample = lambda **_: {'status': 'failed', 'error_subtype': 'provider_timeout_uncertain'}
        with self.assertRaisesRegex(ContractError, 'sampling_failed'):
            sample_and_validate_action(failed, self.frame,
                                       request_id='turn-004', current_frame_id=lambda: current[0])


if __name__ == '__main__':
    unittest.main()
