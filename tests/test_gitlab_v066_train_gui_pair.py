"""No-Docker/no-provider checks for one GitLab v0.6.6 GUI SFT pair."""

from __future__ import annotations

import copy
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from PIL import Image

from cursibench.scale_action_contract import make_observation
from gitlab_world import factory, v066_train_gui_pair as pair
from tools import audit_gitlab_v066_train_gui_pair as audit


def png() -> bytes:
    buffer = io.BytesIO()
    Image.new('RGB', (160, 120), (75, 90, 110)).save(buffer, 'PNG')
    return buffer.getvalue()


class GitLabV066TrainGuiPairTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.root.chmod(0o700)
        self.run = self.root / 'run'
        self.run.mkdir(mode=0o700)
        self.task = {'task_id': 'train-fake-001',
                     'package_sha256': 'a' * 64,
                     'visible_instruction': 'Label only this train issue.'}

    def _observation(self, step: int, previous=None):
        return make_observation(
            task_id=self.task['task_id'],
            task_binding_sha256=self.task['package_sha256'],
            instruction=self.task['visible_instruction'],
            step=step, screenshot_bytes=png(),
            previous_action_result=previous,
            controls=[{'ref': 'c001', 'role': 'button', 'label': 'Labels',
                       'visible': True, 'enabled': True}])

    def test_sampler_records_raw_current_frame_request_and_no_replay_intent(self):
        replies = iter((
            '{"type":"wait","duration_ms":100}',
            '{"type":"finish"}',
        ))
        calls = []
        def provider(request, timeout):
            calls.append((request['model'], timeout, request['user_text']))
            return {'text': next(replies),
                    'receipt': {'reported_model': 'gpt-5.6-sol',
                                'status': 'completed',
                                'response_id': f'fake-{len(calls)}',
                                'usage': {'input_tokens': 10,
                                          'output_tokens': 5}}}
        with patch.object(pair, 'RUN_DIR', self.run):
            sampler = pair.SolSampler(arm='positive', provider=provider)
            sampler.directory.mkdir(mode=0o700)
            first = self._observation(0)
            one = sampler.sample(first, lambda: first.frame_id)
            second = self._observation(
                1, {'status': 'applied', 'code': 'ok'})
            two = sampler.sample(second, lambda: second.frame_id)
            self.assertEqual([one['action']['type'], two['action']['type']],
                             ['wait', 'finish'])
            self.assertEqual(len(calls), 2)
            intent = json.loads((sampler.directory /
                                 'step-000-intent.private.json').read_bytes())
            request = json.loads((sampler.directory /
                                  'step-000-request.private.json').read_bytes())
            self.assertFalse(intent['provider_replay_authorized'])
            self.assertEqual(intent['request_sha256'],
                             pair.sha(pair.canonical(request)))
            self.assertEqual(json.loads(calls[0][2])['task_instruction'],
                             self.task['visible_instruction'])
            self.assertEqual((sampler.directory /
                              'step-000-response.private.json').stat().st_mode &
                             0o777, 0o600)

    def test_offline_trace_reopens_raw_png_and_normalized_actions(self):
        replies = iter((
            '{"type":"wait","duration_ms":100}',
            '{"type":"finish"}',
        ))
        def provider(_request, _timeout):
            return {'text': next(replies),
                    'receipt': {'reported_model': 'gpt-5.6-sol',
                                'status': 'completed',
                                'response_id': 'fake',
                                'usage': {'input_tokens': 10,
                                          'output_tokens': 5}}}
        with patch.object(pair, 'RUN_DIR', self.run):
            (self.run / 'positive').mkdir(mode=0o700)
            frames = self.run / 'positive/frames'
            frames.mkdir(mode=0o700)
            sampler = pair.SolSampler(arm='positive', provider=provider)
            sampler.directory.mkdir(mode=0o700)
            refs = []
            for step in range(2):
                observation = self._observation(
                    step, None if step == 0 else
                    {'status': 'applied', 'code': 'ok'})
                frame = frames / f'step-{step:03d}.png'
                frame.write_bytes(observation.screenshot_bytes)
                frame.chmod(0o600)
                refs.append({'path': 'frames/' + frame.name,
                             'sha256': pair.sha(observation.screenshot_bytes)})
                sampler.sample(observation, lambda o=observation: o.frame_id)
            path = self.run / 'positive/actions.private.json'
            pair.write_new(path, [turn['trace_row'] for turn in sampler.turns])
            turns, usage, digest = audit._trace('positive', self.task, refs, path)
            self.assertEqual(len(turns), 2)
            self.assertEqual(len(usage), 2)
            self.assertEqual(digest, pair.sha(path.read_bytes()))
            (frames / 'step-000.png').write_bytes(b'not the original frame')
            with self.assertRaisesRegex(ValueError, 'raw_frame_changed'):
                audit._trace('positive', self.task, refs, path)

    def test_negative_must_be_exactly_wrong_priority_on_active_train_issue(self):
        original = {'partition': 'train',
                    'template_group': 'issue_label_from_alert',
                    'oracle': {'expected_priority': 'priority::p1'}}
        labels = [
            {'id': 1, 'project_id': 1, 'title': 'priority::p1'},
            {'id': 2, 'project_id': 1, 'title': 'priority::p2'},
        ]
        before = {'business_sha256': '0' * 64,
                  'db': {'labels': labels, 'issues': [],
                         'issue_label_links': []},
                  'git': {'1': {'refs': {}}}}
        after = copy.deepcopy(before)
        after['business_sha256'] = '1' * 64
        after['db']['issue_label_links'] = [
            {'id': 100, 'target_id': 42, 'label_id': 2}]
        progress = {'project_id': 1, 'issue_iids': {'active': 7}}
        with (patch.object(pair.oracle, 'evaluate_train_task',
                           return_value={'reward': 0.0}),
              patch.object(pair.verify, '_context',
                           return_value=({}, progress)),
              patch.object(pair.verify, '_issue', return_value={'id': 42})):
            self.assertTrue(pair._negative_plausible(original, before, after))
            incorrect = copy.deepcopy(after)
            incorrect['db']['issue_label_links'][0]['label_id'] = 1
            self.assertFalse(pair._negative_plausible(original, before, incorrect))
            unrelated = copy.deepcopy(after)
            unrelated['db']['issues'] = [{'id': 99}]
            self.assertFalse(pair._negative_plausible(original, before, unrelated))

    def test_train_task_selection_never_needs_selection_or_final_prompts(self):
        train = []
        for project in range(5):
            for family in ('issue_label_from_alert', 'issue_due_from_register',
                           'milestone_window_from_policy', 'guest_member_from_roster'):
                train.append({'task_id': f'train-{project}-{family}',
                              'partition': 'train',
                              'template_group': family,
                              'prompt': 'One private train instruction.'})
        world = {'schema': factory.SCHEMA,
                 'source': {'excerpt_sha256': factory.EXCERPT_SHA256},
                 'tasks': train}
        path = self.root / 'world-private.json'
        path.write_text(json.dumps(world) + '\n')
        path.chmod(0o600)
        with patch.object(pair.bootstrap, 'WORLD_FILE', path):
            task, binding = pair._train_task()
        self.assertEqual(task['partition'], 'train')
        self.assertEqual(task['template_group'], 'issue_label_from_alert')
        self.assertEqual(binding['package_sha256'],
                         factory.sha256(factory.canonical(task)))

    def test_record_creates_separate_arm_intents_without_provider_or_docker(self):
        original = {'partition': 'train',
                    'template_group': 'issue_label_from_alert'}
        plan = {'ratification_sha256': '1' * 64,
                'worker_runtime_sha256': '2' * 64,
                'worker_verifier_sha256': '3' * 64}
        class FakeWorker:
            def __init__(self, **_kwargs):
                pass

            def run_episode(self, **kwargs):
                self_directory = Path(kwargs['out_dir'])
                self_case = self_directory.parent
                self_test = json.loads((self_case /
                                        'positive-intent.private.json').read_bytes())
                if self_test['arm'] != 'positive':
                    raise AssertionError('positive intent missing before worker')
                if {path.name for path in self_directory.iterdir()} != {'frames'}:
                    raise AssertionError('worker output directory not isolated')
                return {'episode_receipt_path': str(self_directory /
                                                    'episode.private.json'),
                        'episode_receipt_sha256': 'e' * 64}
        with (patch.object(pair, 'RUN_DIR', self.run),
              patch.object(pair, 'validate_plan',
                           return_value=(plan, original, self.task, 'p' * 64)),
              patch.object(pair.worker, 'GitLabTrainEpisodeWorker', FakeWorker),
              patch.object(pair.worker, 'adapter_sha256', return_value='a' * 64),
              patch.object(pair.teacher, '_verify_episode', return_value='e' * 64),
              patch.object(pair, '_negative_arm', return_value={
                  'receipt_sha256': 'n' * 64})):
            # RUN_DIR must be fresh for the real recorder; use a new child.
            fresh = self.root / 'new-pair'
            with patch.object(pair, 'RUN_DIR', fresh):
                result = pair.record(Path('ratification'),
                                     provider=lambda *_args: (_ for _ in ()).throw(
                                         AssertionError('provider should not be called')))
        self.assertEqual(result['positive_action_count'], 0)
        self.assertEqual(result['negative_action_count'], 0)
        self.assertFalse(result['tinker_sft_eligible'])
        self.assertTrue((fresh / 'positive-intent.private.json').is_file())
        self.assertTrue((fresh / 'negative-intent.private.json').is_file())
        self.assertTrue((fresh / 'positive-provider').is_dir())


if __name__ == '__main__':
    unittest.main()
