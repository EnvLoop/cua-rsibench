"""The full-study output adapter matches the shared fenced-JSON contract."""

from __future__ import annotations

import io
import json
import unittest

from PIL import Image

from cursibench.scale_action_contract import ContractError, make_observation
from cursibench.scale_action_output_v063 import (
    normalize_model_action as old_normalize,
)
from cursibench.scale_action_output_v064 import (
    OUTPUT_VERSION, normalize_model_action, render_for_model,
)


def frame():
    stream = io.BytesIO()
    Image.new('RGB', (64, 48), 'white').save(stream, format='PNG')
    return make_observation(
        task_id='gitlab.train.001', task_binding_sha256='a' * 64,
        instruction='Open the current issue.', step=0,
        screenshot_bytes=stream.getvalue(),
        controls=[{'ref': 'issue-link', 'role': 'link', 'label': 'Issue',
                   'visible': True, 'enabled': True}],
    )


class FullStudyOutputTests(unittest.TestCase):
    def setUp(self):
        self.observation = frame()
        self.raw = json.dumps({'type': 'click',
                               'target': {'ref': 'issue-link'}})

    def normalize(self, raw, *, current=None):
        return normalize_model_action(
            raw, self.observation,
            current_frame_id=current or self.observation.frame_id)

    def test_plain_and_single_labeled_or_unlabeled_fence(self):
        for raw in (self.raw, f'```json\n{self.raw}\n```',
                    f'```\n{self.raw}\n```'):
            self.assertEqual(self.normalize(raw)['target'],
                             {'ref': 'issue-link'})
        with self.assertRaisesRegex(ContractError, 'invalid_action_json'):
            old_normalize(f'```\n{self.raw}\n```', self.observation,
                          current_frame_id=self.observation.frame_id)

    def test_all_other_action_and_frame_checks_remain_strict(self):
        for raw in (f'Explanation\n```json\n{self.raw}\n```',
                    f'```\n{self.raw}\n```\nDone',
                    f'```\n{self.raw}\n```\n```\n{self.raw}\n```',
                    f'```JSON\n{self.raw}\n```',
                    '{"type":"click","type":"finish",'
                    '"target":{"ref":"issue-link"}}'):
            with self.subTest(raw=raw[:20]):
                with self.assertRaisesRegex(ContractError, 'invalid_action_json'):
                    self.normalize(raw)
        with self.assertRaisesRegex(ContractError, 'stale_frame'):
            self.normalize(f'```\n{self.raw}\n```', current='stale')
        wrong = json.dumps({'type': 'click', 'target': {'ref': 'old-ref'}})
        with self.assertRaisesRegex(ContractError, 'stale_frame'):
            self.normalize(f'```\n{wrong}\n```')

    def test_cell_neutral_prompt_has_budget_without_trusted_ids(self):
        rendered = render_for_model(self.observation)
        instruction = json.loads(rendered['instruction'])
        self.assertEqual(instruction['output_version'], OUTPUT_VERSION)
        self.assertEqual(instruction['max_actions'], 90)
        self.assertIn('unlabeled', instruction['contract'])
        for hidden in (self.observation.task_id,
                       self.observation.task_binding_sha256,
                       self.observation.frame_id):
            self.assertNotIn(hidden, rendered['instruction'])


if __name__ == '__main__':
    unittest.main()
