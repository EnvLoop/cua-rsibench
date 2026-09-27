"""Cell-neutral v0.6.5 accepts one alias without weakening action safety."""

from __future__ import annotations

import io
import json
import unittest

from PIL import Image

from cursibench.scale_action_contract import ContractError, make_observation
from cursibench.scale_action_output_v064 import normalize_model_action as old_normalize
from cursibench.scale_action_output_v064 import MODEL_ACTION_CONTRACT as OLD_CONTRACT
from cursibench.scale_action_output_v065 import (
    OUTPUT_VERSION, normalize_model_action, render_for_model,
)


def frame(*, controls=()):
    out = io.BytesIO()
    Image.new('RGB', (64, 48), 'white').save(out, format='PNG')
    return make_observation(
        task_id='train.synthetic', task_binding_sha256='a' * 64,
        instruction='Use the visible GUI.', step=0,
        screenshot_bytes=out.getvalue(), controls=list(controls),
    )


class OutputV065Tests(unittest.TestCase):
    def setUp(self):
        self.empty = frame()
        self.with_ref = frame(controls=[{
            'ref': 'open', 'role': 'button', 'label': 'Open',
            'visible': True, 'enabled': True,
        }])

    def parse(self, raw, observation=None, *, current=None):
        observation = observation or self.empty
        return normalize_model_action(raw, observation,
            current_frame_id=current or observation.frame_id)

    def test_unambiguous_alias_is_only_transport_normalization(self):
        alias = '{"action":"click","target":{"x":5,"y":7}}'
        for raw in (alias, f'```json\n{alias}\n```', f'```\n{alias}\n```'):
            self.assertEqual(self.parse(raw)['target'], {'x': 5, 'y': 7})
        with self.assertRaisesRegex(ContractError, 'invalid_action'):
            old_normalize(alias, self.empty,
                          current_frame_id=self.empty.frame_id)
        self.assertEqual(self.parse('{"type":"click","target":{"x":5,"y":7}}')['type'],
                         'click')

    def test_refs_still_require_current_visible_controls(self):
        valid = '{"action":"click","target":{"ref":"open"}}'
        self.assertEqual(self.parse(valid, self.with_ref)['target'], {'ref': 'open'})
        for invalid in (valid, '{"action":"click","target":{"ref":"visible-ref"}}'):
            with self.assertRaisesRegex(ContractError, 'stale_frame'):
                self.parse(invalid, self.empty)
        with self.assertRaisesRegex(ContractError, 'stale_frame'):
            self.parse('{"action":"click","target":{"x":5,"y":7}}',
                       current='old-frame')

    def test_alias_does_not_admit_ambiguous_or_forbidden_actions(self):
        invalid_actions = (
            '{"action":"click","type":"finish","target":{"x":5,"y":7}}',
            '{"action":{"type":"click"},"target":{"x":5,"y":7}}',
            '{"action":"shell","target":{"x":5,"y":7}}',
            '{"action":"click","target":{"x":5,"y":7},"url":"https://x"}',
            '{"action":"click","target":{"x":-1,"y":7}}',
            '{"action":"click","target":{"x":5,"y":7},"command":"ls"}',
        )
        for raw in invalid_actions:
            with self.subTest(raw=raw[:35]):
                with self.assertRaises(ContractError):
                    self.parse(raw)
        invalid_json = (
            'Here is an action: {"action":"click","target":{"x":5,"y":7}}',
            '```json\n{"action":"click","target":{"x":5,"y":7}}\n```\nDone',
            '{"action":"click","action":"finish","target":{"x":5,"y":7}}',
            '{"action":"click","target":{"x":NaN,"y":7}}',
        )
        for raw in invalid_json:
            with self.subTest(raw=raw[:35]):
                with self.assertRaisesRegex(ContractError, 'invalid_action_json'):
                    self.parse(raw)

    def test_prompt_only_removes_dummy_control_ref(self):
        empty = json.loads(render_for_model(self.empty)['instruction'])
        controls = json.loads(render_for_model(self.with_ref)['instruction'])
        self.assertEqual(empty['output_version'], OUTPUT_VERSION)
        self.assertEqual(empty['contract'], controls['contract'])
        self.assertNotIn('visible-ref', empty['contract'])
        self.assertEqual(empty['contract'].replace(
            'a ref copied verbatim from a visible enabled control in the current controls list (when nonempty)',
            '{"ref":"visible-ref"} from current visible controls'), OLD_CONTRACT)
        self.assertNotIn('target_mode', empty)
        for hidden in (self.empty.task_id, self.empty.task_binding_sha256,
                       self.empty.frame_id):
            self.assertNotIn(hidden, json.dumps(empty))


if __name__ == '__main__':
    unittest.main()
