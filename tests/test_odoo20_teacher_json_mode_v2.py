"""Offline teacher-format tests; no provider or benchmark credit."""
import json
import os
import unittest
from unittest.mock import patch
from enterprise_fallback.odoo18 import twenty_task_trial_teacher_v2 as teacher
from cursibench import http_transport, scale_action_output_v066 as output


class TeacherJSONModeTests(unittest.TestCase):
    def request(self):
        return {'model': 'gpt-6-sol', 'response_format': 'json_object',
                'max_output_tokens': 4096, 'reasoning_effort': 'high',
                'system_prompt': 'Return JSON only.', 'user_text': 'Synthetic fixture',
                'image_data_url': 'data:image/png;base64,SYNTHETIC', 'image_detail': 'high'}

    def test_actual_wire_payload_retains_image_and_requests_json_syntax(self):
        result = {'model': 'gpt-6-sol', 'status': 'completed', 'id': 'synthetic-response',
                  'usage': {}, 'output': [{'type': 'message', 'content': [
                      {'type': 'output_text', 'text': '{"type":"finish"}'}]}]}
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'synthetic-test-key'}), \
                patch.object(http_transport, 'post_json', return_value=result) as post:
            returned = teacher._json_teacher_provider(self.request(), 120)
        payload = post.call_args.args[1]
        self.assertEqual(payload['text'], {'format': {'type': 'json_object'}})
        self.assertEqual(payload['model'], 'gpt-6-sol')
        self.assertEqual(payload['input'][1]['content'][1]['type'], 'input_image')
        self.assertEqual(json.loads(returned['text']), {'type': 'finish'})
        self.assertFalse(returned['receipt']['action_validation_relaxed'])

    def test_missing_format_refuses_before_provider_dispatch(self):
        request = self.request(); request.pop('response_format')
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'synthetic-test-key'}), \
                patch.object(http_transport, 'post_json') as post:
            with self.assertRaises(ValueError): teacher._json_teacher_provider(request, 120)
        post.assert_not_called()

    def test_shared_action_parser_still_rejects_prose(self):
        from cursibench.scale_action_contract import make_observation, ContractError
        from PIL import Image
        import io
        image = io.BytesIO(); Image.new('RGB', (100, 100)).save(image, 'PNG')
        observation = make_observation(task_id='synthetic', task_binding_sha256='a'*64,
            instruction='Synthetic', step=0, screenshot_bytes=image.getvalue(), controls=[])
        with self.assertRaises(ContractError):
            output.normalize_model_action('Explanation.\n{"type":"finish"}', observation,
                                           current_frame_id=observation.frame_id)


if __name__ == '__main__': unittest.main()
