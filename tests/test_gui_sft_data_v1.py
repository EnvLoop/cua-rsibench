import copy
import io
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from cursibench.gui_sft_data_v1 import (
    DataGateError, SCHEMA, SOURCE_COMMIT, SOURCE_DATA_SHA256,
    train_exclusion_manifest, validate_episode, render_model_turn, sha256,
)


class GuiSftDataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'frames').mkdir()
        image = Image.new('RGB', (160, 120), (90, 100, 110))
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        self.image = buffer.getvalue()
        self.steps = []
        for index, action in enumerate((
                {'type': 'click', 'target': {'ref': 'c001'},
                 'memory': 'Opened editor.'},
                {'type': 'finish', 'memory': 'Task complete.'})):
            name = f'frames/step-{index:03d}.png'
            (self.root / name).write_bytes(self.image)
            self.steps.append({
                'step': index, 'screenshot_file': name,
                'screenshot_sha256': sha256(self.image),
                'observation': {
                    'task_id': 'webarena.shopping_admin.777',
                    'task_binding_sha256': 'a' * 64,
                    'instruction': 'Update five related catalog variants.',
                    'a11y_text': 'Visible headings: Orders', 'dom_text': '',
                    'controls': [{'ref': 'c001', 'role': 'link', 'label': 'Edit',
                                  'visible': True, 'enabled': True}],
                    'previous_action_result': None if index == 0 else
                        {'status': 'applied', 'code': 'ok'},
                    'memory': '' if index == 0 else 'Opened editor.',
                }, 'action': action,
            })
        self.episode = {
            'schema': SCHEMA, 'split': 'train',
            'source_commit': SOURCE_COMMIT,
            'source_dataset_sha256': SOURCE_DATA_SHA256,
            'site': 'shopping_admin', 'task_id': 777,
            'intent_template_id': 742,
            'entity_tags': [f'magento:product:{entity_id}'
                            for entity_id in (111, 114, 117, 120, 123)],
            'admission': {
                'published_evaluator_score': 1.0,
                'independent_saved_state_pass': True,
                'reset_verified': True,
                'search_index_reset_verified': True,
                'native_save_count': 5,
                'raw_and_sanitized_evaluator_equal': True,
            }, 'steps': self.steps,
        }
        self.write()

    def tearDown(self):
        self.tmp.cleanup()

    def write(self):
        content = json.dumps(self.episode).encode()
        (self.root / 'episode.json').write_bytes(content)
        (self.root / 'result.json').write_text(json.dumps({
            'status': 'completed', 'episode_admitted': True,
            'task_id': 777, 'intent_template_id': 742,
            'final_reset_verified': True, 'independent_saved_state_pass': True,
            'reset_verified': True, 'official_score': 1.0,
            'paid_provider_calls': 0, 'episode_sha256': sha256(content),
            'action_count': len(self.episode['steps']),
            'screenshot_count': len(self.episode['steps']),
            'source': {'git_commit': SOURCE_COMMIT},
        }))

    def test_validated_actions_bind_to_each_current_screen(self):
        episode, turns = validate_episode(self.root)
        self.assertEqual(episode['task_id'], 777)
        self.assertEqual([row['normalized']['type'] for row in turns],
                         ['click', 'finish'])
        model = render_model_turn(turns[0]['observation'])
        self.assertEqual(model['image_bytes'], self.image)
        self.assertIn('one GUI action', model['instruction'])
        self.assertIn('c001', model['visible_text'])

    def test_invalid_screenshot_rejected(self):
        (self.root / 'frames/step-000.png').write_bytes(self.image + b'corrupt')
        with self.assertRaisesRegex(DataGateError, 'screenshot_hash_mismatch'):
            validate_episode(self.root)

    def test_task_or_split_contamination_rejected(self):
        for key, value in (('task_id', 486), ('intent_template_id', 275),
                           ('split', 'final')):
            original = self.episode[key]
            self.episode[key] = value
            self.write()
            with self.assertRaisesRegex(DataGateError, 'invalid_train_source'):
                validate_episode(self.root)
            self.episode[key] = original
        self.write()

    def test_official_or_state_failure_rejected(self):
        for key in ('published_evaluator_score', 'independent_saved_state_pass',
                    'reset_verified', 'search_index_reset_verified',
                    'raw_and_sanitized_evaluator_equal'):
            original = self.episode['admission'][key]
            self.episode['admission'][key] = 0.0 if key == 'published_evaluator_score' else False
            self.write()
            with self.assertRaisesRegex(DataGateError, 'state_or_evaluator_not_admitted'):
                validate_episode(self.root)
            self.episode['admission'][key] = original
        self.write()

    def test_stale_or_unoffered_action_rejected(self):
        old = copy.deepcopy(self.episode['steps'][0]['action'])
        self.episode['steps'][0]['action']['target'] = {'ref': 'c999'}
        self.write()
        with self.assertRaises(Exception):
            validate_episode(self.root)
        self.episode['steps'][0]['action'] = old
        self.write()

    def test_recorder_result_must_match_episode_bytes(self):
        result_path = self.root / 'result.json'
        result = json.loads(result_path.read_text())
        result['episode_sha256'] = '0' * 64
        result_path.write_text(json.dumps(result))
        with self.assertRaisesRegex(DataGateError, 'recorder_result_not_admitted'):
            validate_episode(self.root)

    def test_memory_chain_must_match_previous_validated_action(self):
        self.episode['steps'][1]['observation']['memory'] = 'Unrecorded host hint'
        self.write()
        with self.assertRaisesRegex(DataGateError, 'memory_chain_mismatch'):
            validate_episode(self.root)

    def test_train_exclusion_names_whole_template_and_entity(self):
        manifest = train_exclusion_manifest()
        self.assertEqual(manifest['train_only_task_ids'], [777])
        self.assertEqual(manifest['train_only_intent_template_ids'], [742])
        self.assertIn('magento:product:111', manifest['train_only_entity_tags'])
        self.assertEqual(manifest['other_exposed_unadmitted_task_ids'], [486, 538])


if __name__ == '__main__':
    unittest.main()
