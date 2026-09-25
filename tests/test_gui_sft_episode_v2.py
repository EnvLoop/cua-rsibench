import io
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from cursibench.gui_sft_episode_v2 import (
    ACTION_VERSION, CELLS, GATE_SCHEMA, MODEL, PROCESSOR, RENDERER,
    STUDY_CELL_BY_ADAPTER,
    SCHEMA, SPLIT_SCHEMA, EpisodeGateError, _source_binding,
    render_model_turn, sha256, validate_episode,
)


class EpisodeV2Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'frames').mkdir()
        (self.root / 'receipts').mkdir()
        (self.root / 'receipts/source-synthetic.json').write_text('{}')
        output = io.BytesIO()
        Image.new('RGB', (160, 120), (80, 90, 100)).save(output, format='PNG')
        self.image = output.getvalue()
        self.cell = 'odoo_erp'
        self.source = {
            'name': 'PinnedOdooTasks', 'revision': 'snapshot-1',
            'dataset_sha256': 'a' * 64, 'task_sha256': 'b' * 64,
            'task_id': 'train-1', 'template_id': 'invoice-create',
            'observation_task_id': 'odoo.invoice.train-1',
            'entity_tags': ['odoo:invoice:001'],
        }
        self.steps = []
        for index, action in enumerate((
                {'type': 'click', 'target': {'ref': 'c001'},
                 'memory': 'Opened invoice.'},
                {'type': 'finish', 'memory': 'Done.'})):
            name = f'frames/step-{index:03d}.png'
            (self.root / name).write_bytes(self.image)
            self.steps.append({
                'step': index, 'screenshot_file': name,
                'screenshot_sha256': sha256(self.image),
                'observation': {
                    'task_id': self.source['observation_task_id'],
                    'task_binding_sha256': 'c' * 64,
                    'instruction': 'Create the requested invoice.',
                    'a11y_text': 'Visible headings: Invoices', 'dom_text': '',
                    'controls': [{'ref': 'c001', 'role': 'button', 'label': 'New',
                                  'visible': True, 'enabled': True}],
                    'previous_action_result': None if index == 0 else
                        {'status': 'applied', 'code': 'ok'},
                    'memory': '' if index == 0 else 'Opened invoice.',
                }, 'action': action,
            })
        self.gates = {}
        binding = _source_binding(self.source, self.cell)
        for name, kind, score in (
                ('positive', 'published_evaluator', 1.0),
                ('negative', 'negative_control', 0.0),
                ('saved_state', 'independent_readback', None),
                ('reset', 'state_equivalence', None)):
            row = {'schema': GATE_SCHEMA, 'gate': name, 'cell': self.cell,
                   'source_binding_sha256': binding, 'status': 'pass',
                   'independent_of_actor': True,
                   'verifier_kind': kind,
                   'source_artifact_path': 'receipts/source-synthetic.json',
                   'source_artifact_sha256': sha256(b'{}')}
            if score is not None:
                row['score'] = score
            if name == 'negative':
                row.update(control_kind='wrong_object',
                           independent_state_control_pass=True)
            if name == 'saved_state':
                row.update(target_state_pass=True,
                           unintended_state_preserved=True)
            if name == 'reset':
                row.update(state_equivalence_pass=True,
                           business_state_rows_match_baseline=True,
                           baseline_semantic_sha256='e' * 64,
                           restored_semantic_sha256='e' * 64)
            self.gates[name] = row
        self.selection = self.manifest('selection', 'select-2', 'invoice-review',
                                       ['odoo:invoice:002'])
        self.final = self.manifest('final', 'final-3', 'invoice-approve',
                                   ['odoo:invoice:003'])
        self.write()

    def tearDown(self):
        self.tmp.cleanup()

    def manifest(self, split, task_id, template_id, tags):
        return {'schema': SPLIT_SCHEMA, 'cell': self.cell, 'split': split,
                'source_name': self.source['name'],
                'source_revision': self.source['revision'],
                'source_dataset_sha256': self.source['dataset_sha256'],
                'status': 'provisional', 'entity_coverage': 'declared_hints_only',
                'items': [{'task_id': task_id, 'template_id': template_id,
                           'entity_tags': tags}]}

    def write(self):
        refs = {}
        for name, row in self.gates.items():
            path = self.root / 'receipts' / f'{name}.json'
            payload = json.dumps(row).encode()
            path.write_bytes(payload)
            refs[name] = {'path': f'receipts/{name}.json',
                          'sha256': sha256(payload)}
        episode = {'schema': SCHEMA, 'split': 'train', 'cell': self.cell,
                   'source': self.source,
                   'action_contract_version': ACTION_VERSION,
                   'renderer': {'model': MODEL, 'name': RENDERER,
                                'image_processor': PROCESSOR},
                   'provenance_receipts': refs, 'steps': self.steps}
        raw = json.dumps(episode).encode()
        (self.root / 'episode.json').write_bytes(raw)
        (self.root / 'result.json').write_text(json.dumps({
            'status': 'completed', 'episode_sha256': sha256(raw),
            'action_count': len(self.steps), 'frame_count': len(self.steps),
            'paid_provider_calls': 0,
        }))
        (self.root / 'selection.json').write_text(json.dumps(self.selection))
        (self.root / 'final.json').write_text(json.dumps(self.final))

    def validate(self):
        return validate_episode(self.root,
            selection_manifest=self.root / 'selection.json',
            final_manifest=self.root / 'final.json')

    def test_cell_neutral_action_and_image_turn(self):
        for cell in sorted(CELLS):
            self.cell = cell
            self.selection['cell'] = cell
            self.final['cell'] = cell
            for row in self.gates.values():
                row['cell'] = cell
                row['source_binding_sha256'] = _source_binding(self.source, cell)
            self.write()
            episode, turns, proof = self.validate()
            self.assertEqual(episode['cell'], cell)
            self.assertEqual(proof['study_cell_id'], STUDY_CELL_BY_ADAPTER[cell])
            self.assertEqual(len(turns), 2)
            self.assertEqual(proof['split']['selection_count'], 1)
            self.assertEqual(proof['split']['official_final_admitted'], False)
            request = render_model_turn(turns[0]['observation'])
            self.assertEqual(request['image_bytes'], self.image)
            self.assertIn('visible-ref', request['instruction'])
            self.assertIn('c001', request['visible_text'])

    def test_train_task_template_and_entity_overlap_each_rejected(self):
        for field, value, code in (
                ('task_id', self.source['task_id'], 'train_task_in_evaluation_split'),
                ('template_id', self.source['template_id'],
                 'train_template_in_evaluation_split'),
                ('entity_tags', self.source['entity_tags'],
                 'train_entity_in_evaluation_split')):
            old = self.final['items'][0][field]
            self.final['items'][0][field] = value
            self.write()
            with self.assertRaisesRegex(EpisodeGateError, code):
                self.validate()
            self.final['items'][0][field] = old
        self.write()

    def test_missing_negative_or_bad_reset_rejected(self):
        saved = self.gates.pop('negative')
        # The episode reference still points at the now missing receipt.
        (self.root / 'receipts/negative.json').unlink()
        with self.assertRaisesRegex(EpisodeGateError, 'missing_private_artifact'):
            self.validate()
        self.gates['negative'] = saved
        self.gates['negative']['independent_state_control_pass'] = False
        self.write()
        with self.assertRaisesRegex(EpisodeGateError, 'negative_control_not_independent'):
            self.validate()
        self.gates['negative']['independent_state_control_pass'] = True
        self.gates['reset']['restored_semantic_sha256'] = 'f' * 64
        self.write()
        with self.assertRaisesRegex(EpisodeGateError, 'reset_not_equivalent'):
            self.validate()

    def test_tampered_frame_or_action_rejected(self):
        (self.root / 'frames/step-000.png').write_bytes(self.image + b'tamper')
        with self.assertRaisesRegex(EpisodeGateError, 'frame_hash_mismatch'):
            self.validate()
        (self.root / 'frames/step-000.png').write_bytes(self.image)
        self.steps[0]['action']['target'] = {'ref': 'c999'}
        self.write()
        with self.assertRaises(Exception):
            self.validate()

    def test_selection_and_final_family_overlap_rejected(self):
        self.final['items'][0]['template_id'] = self.selection['items'][0]['template_id']
        self.write()
        with self.assertRaisesRegex(EpisodeGateError,
                                    'selection_final_template_overlap'):
            self.validate()

    def test_selection_and_final_declared_entity_overlap_rejected(self):
        self.final['items'][0]['entity_tags'] = self.selection['items'][0]['entity_tags']
        self.write()
        with self.assertRaisesRegex(EpisodeGateError,
                                    'selection_final_declared_entity_overlap'):
            self.validate()

    def test_tampered_source_artifact_rejected(self):
        (self.root / 'receipts/source-synthetic.json').write_text('{"changed":true}')
        with self.assertRaisesRegex(EpisodeGateError,
                                    'source_artifact_hash_mismatch'):
            self.validate()

    def test_manifest_source_mismatch_rejected(self):
        self.final['source_revision'] = 'other-revision'
        self.write()
        with self.assertRaisesRegex(EpisodeGateError, 'split_manifest_mismatch'):
            self.validate()


if __name__ == '__main__':
    unittest.main()
