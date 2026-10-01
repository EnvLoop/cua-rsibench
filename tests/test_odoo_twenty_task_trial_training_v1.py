"""Synthetic protocol fixtures only: zero actual task/provider/training credit."""
import asyncio
import base64
from dataclasses import replace
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import pickle
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image
from tinker import types
from enterprise_fallback.odoo18 import twenty_task_trial_training_v1 as train


def hashed(raw):
    return sha256(raw).hexdigest()


def packet(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False) + '\n').encode()
    path.write_bytes(raw); path.chmod(0o600)
    return {'path': path.name, 'sha256': hashed(raw)}


def image_bytes():
    out = io.BytesIO(); Image.new('RGB', (8, 8), 'white').save(out, format='PNG'); return out.getvalue()


def actual_datum(image=None):
    image = image or image_bytes()
    chunks = [types.ImageChunk(data=image, format='png', expected_tokens=2), types.EncodedTextChunk(tokens=[1, 2, 3])]
    model = types.ModelInput(chunks=chunks)
    return types.Datum(model_input=model, loss_fn_inputs={
        'target_tokens': types.TensorData(data=[0, 0, 2, 3, 4], dtype='int64', shape=[5]),
        'weights': types.TensorData(data=[0, 0, 0, 1, 1], dtype='float32', shape=[5])})


def synthetic_batch(task_id, episode_sha, turns, _vision=None):
    datum = actual_datum(turns[0]['observation'].screenshot_bytes)
    prompt = types.ModelInput(chunks=[datum.model_input.chunks[0], types.EncodedTextChunk(tokens=[1, 2])])
    return SimpleNamespace(datums=[datum], prompts=[prompt], receipt={
        'schema': train.trial.teacher.RENDER_SCHEMA, 'cell_id': 'odoo-community',
        'model': train.MODEL, 'action_profile': 'scale-action-profile-v0.6.6',
        'train_task_ids': [task_id], 'episode_receipt_sha256s': [episode_sha],
        'datum_token_lengths': [5], 'prompt_token_lengths': [4],
        'student_inference_prompt_equality_checked': True})


class SyntheticNativeTeacherFixture:
    """A fully reopenable fixture, never represented as actual provider evidence."""
    def __init__(self, root):
        self.directory = root / 'synthetic-teacher.private'; self.directory.mkdir()
        self.episode = self.directory / 'episode.private'; self.episode.mkdir()
        self.task = {'task_id': 'ELPO-TRN-SYNTH-0001', 'package_sha256': 'a' * 64,
                     'visible_instruction': 'Synthetic fixture only. Finish the synthetic GUI task.'}
        self.plan = {'models': {'teacher': 'gpt-6-sol'}, 'native_binding_sha256': 'b' * 64,
                     'actor_limits': {'actions': 90}}
        self.proposal = {'teacher_request': 'Synthetic public TRAIN fixture only.'}
        self.manifest = {'trial_plan_sha256': 'c' * 64, 'proposal_ref': {'sha256': 'd' * 64}}
        frame = image_bytes()
        observation = train.contract.make_observation(task_id=self.task['task_id'],
            task_binding_sha256=self.task['package_sha256'], instruction=self.task['visible_instruction'],
            step=0, screenshot_bytes=frame)
        self.observation = observation
        action = train.output.normalize_model_action('{"type":"finish","memory":""}', observation,
                                                    current_frame_id=observation.frame_id)
        rendered = train.output.render_for_model(observation)
        provider = {'text': '{"type":"finish","memory":""}', 'receipt': {
            'reported_model': 'gpt-6-sol', 'status': 'completed', 'response_id': 'synthetic-response-0'}}
        provider_ref = packet(self.directory / 'teacher-call-000-result.private.json', provider)
        request = {'model': 'gpt-6-sol', 'image_data_url': 'data:image/png;base64,' + base64.b64encode(frame).decode(),
                   'user_text': json.dumps({'instruction': rendered['instruction'],
                       'visible_text': rendered['visible_text'], 'researcher_teacher_request': self.proposal['teacher_request']})}
        packet(self.directory / 'teacher-call-000-request.private.json', request)
        row = {'step': 0, 'frame_id': observation.frame_id, 'frame_sha256': hashed(frame),
               'action': action, 'teacher_result_sha256': provider_ref['sha256'],
               'actual_response_id': 'synthetic-response-0', 'provider_latency_ms': 1}
        packet(self.directory / 'teacher-call-000-intent.private.json', {**{k:row[k] for k in ('step','frame_id','frame_sha256')},
            'task_id': self.task['task_id'], 'before_provider_post': True, 'same_request_replay_authorized': False})
        packet(root / (self.directory.name + '-paid-intent.private.json'), {
            'trial_plan_sha256': 'c' * 64, 'proposal_sha256': 'd' * 64, 'teacher_model': 'gpt-6-sol',
            'task': self.task, 'same_request_replay_authorized': False})
        frame_path = self.episode / 'frames/step-000.png'; frame_path.parent.mkdir()
        frame_path.write_bytes(frame); frame_path.chmod(0o600)
        trace_ref = packet(self.episode / 'actions.private.json', [row])
        artifact = self.episode / 'artifacts/saved.json'; artifact_ref = packet(artifact, {'fixture': 'synthetic'})
        artifact_ref['path'] = 'artifacts/saved.json'
        base = self.episode / 'artifacts/baseline.json'; base_ref = packet(base, {'fixture': 'synthetic-reset'})
        base_ref['path'] = 'artifacts/baseline.json'
        restored = self.episode / 'artifacts/restored.json'; restored_ref = packet(restored, {'fixture': 'synthetic-reset'})
        restored_ref['path'] = 'artifacts/restored.json'
        common = {'cell_id': 'odoo-community', **{k:self.task[k] for k in ('task_id','package_sha256')}}
        self.state = {'schema': train.trial.teacher.STATE_SCHEMA, **common, 'independent_of_actor': True,
            'native_save_observed': True, 'target_state_pass': True, 'no_regression_pass': True,
            'saved_artifact_sha256': artifact_ref['sha256'], 'saved_artifact_ref': artifact_ref,
            'verifier_sha256': 'e' * 64, 'evaluator_result': 'pass'}
        state_ref = packet(self.episode / 'state.private.json', self.state)
        self.reset = {'schema': train.trial.teacher.RESET_SCHEMA, **common, 'independent_of_actor': True,
            'fresh_environment': True, 'state_equivalence_pass': True, 'baseline_semantic_sha256': base_ref['sha256'],
            'restored_semantic_sha256': restored_ref['sha256'], 'sandbox_terminated': True,
            'baseline_state_ref': base_ref, 'restored_state_ref': restored_ref}
        reset_ref = packet(self.episode / 'reset.private.json', self.reset)
        native = {'schema': train.trial.teacher.EPISODE_SCHEMA, 'status': 'admitted', 'split': 'train', **common,
            'action_profile': 'scale-action-profile-v0.6.6', 'teacher_model': 'gpt-6-sol',
            'original_software_gui': True, 'original_surface': 'native', 'runtime_sha256': 'b'*64,
            'adapter_sha256': 'f'*64, 'frame_refs': [{'path':'frames/step-000.png','sha256':hashed(frame)}],
            'action_trace_ref':trace_ref, 'saved_state_ref':state_ref, 'reset_ref':reset_ref,
            'teacher_result_sha256s':[provider_ref['sha256']], 'e2b_attempt_ids':[]}
        native_ref = packet(self.episode / 'episode.private.json', native)
        packet(self.directory / 'native-teacher-result.private.json', {
            'episode_receipt_path':str(self.episode / 'episode.private.json'), 'episode_receipt_sha256':native_ref['sha256']})
        packet(self.episode / 'artifacts/native-contracts/step-000.private.json', {
            'step':0,'action':action,'frame_sha256':hashed(frame),'native_dispatch_status':'finished'})
        self.batch = synthetic_batch(self.task['task_id'], native_ref['sha256'], [{'observation':observation}])
        self.descriptor = {'task_id':self.task['task_id'], 'episode_receipt_sha256':native_ref['sha256']}
        self.replace_pickle(self.batch)
        packet(self.directory / 'teacher-provider-close.private.json', {
            'real_close_call_returned':True,'owned_callback_completion_proved':True})

    def replace_pickle(self, batch):
        raw = pickle.dumps({'datums':batch.datums,'prompts':batch.prompts,'receipt':batch.receipt}, protocol=5)
        path = self.directory / 'trusted-rendered-train.private.pkl'; path.write_bytes(raw); path.chmod(0o600)
        self.descriptor['rendered_sha256'] = hashed(raw)
        self.render_receipt = {'schema':'envloop-odoo20-real-teacher-render-v1','task_id':self.task['task_id'],
            'source_split':'train','trial_plan_sha256':'c'*64,'proposal_sha256':'d'*64,'native_saved_state_checked':True,
            'formal_large_study_credit':0,'teacher_turns':1,'positive_training_turns':1,'rejected_turns_excluded':0,
            'rendered_sha256':hashed(raw),'renderer_receipt':batch.receipt}
        self.descriptor['render_receipt_sha256'] = packet(self.directory / 'rendered-train-receipt.private.json', self.render_receipt)['sha256']

    def reopen(self):
        binding = {'source_sha256s': {'enterprise_fallback/odoo18/verify.py':'e'*64}}
        with patch.object(train.trial.workers, 'public_binding', return_value=binding), \
             patch.object(train.trial.workers, '_model_modules', return_value=(SimpleNamespace(adapter_sha256=lambda:'f'*64),)), \
             patch.object(train.trial, 'render_trial_turns', side_effect=synthetic_batch):
            return train.reopen_episode(self.directory,self.descriptor,self.manifest,self.plan,self.task,self.proposal,None)


class ProvenanceTests(unittest.TestCase):
    def test_reopens_actual_types_and_original_independent_verifier_with_synthetic_receipts(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = SyntheticNativeTeacherFixture(Path(temp))
            result = fixture.reopen()
            self.assertIs(type(result.datums[0]), types.Datum)
            self.assertEqual(train.data_signature(result.datums[0]), train.data_signature(fixture.batch.datums[0]))

    def test_hash_matching_foreign_teacher_or_changed_provider_response_rejected(self):
        for model in ('gpt-6-astra','gpt-6.1-sol'):
            with self.subTest(model=model), tempfile.TemporaryDirectory() as temp:
                fixture = SyntheticNativeTeacherFixture(Path(temp))
                path = fixture.directory / 'teacher-call-000-request.private.json'
                value = json.loads(path.read_bytes()); value['model'] = model; packet(path,value)
                with self.assertRaisesRegex(train.TrainingError, 'actual_active_teacher_model'):
                    fixture.reopen()

    def test_rehashed_arbitrary_datum_cannot_replace_actual_trajectory(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = SyntheticNativeTeacherFixture(Path(temp))
            altered = actual_datum(); altered.loss_fn_inputs['target_tokens'] = types.TensorData(data=[9]*5,dtype='int64',shape=[5])
            fixture.replace_pickle(SimpleNamespace(datums=[altered],prompts=fixture.batch.prompts,receipt=fixture.batch.receipt))
            with self.assertRaisesRegex(train.TrainingError, 'rendered_datum_differs'):
                fixture.reopen()

    def test_independent_saved_artifact_or_reset_drift_rejected(self):
        for name in ('saved.json','restored.json'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                fixture = SyntheticNativeTeacherFixture(Path(temp))
                packet(fixture.episode / 'artifacts' / name, {'fixture':'modified'})
                with self.assertRaises(Exception):
                    fixture.reopen()

    def test_source_drift_and_missing_explicit_pickle_trust_rejected(self):
        names = {'enterprise_fallback/odoo18/twenty_task_trial_teacher_v1.py',
            'src/cursibench/full_study_teacher_adapter_v1.py','src/cursibench/scale_vision_proxy.py',
            'src/cursibench/scale_action_output_v066.py','src/cursibench/full_study_campaign_dispatch_v1.py'}
        sources = {n:hashed((train.ROOT/n).read_bytes()) for n in names}
        train.check_sources({'source_sha256s':sources})
        sources[next(iter(sources))] = '0'*64
        with self.assertRaisesRegex(train.TrainingError,'training_source_changed'):
            train.check_sources({'source_sha256s':sources})
        with self.assertRaisesRegex(train.TrainingError,'explicit_owned_rendered_trust'):
            train.load_inputs(plan_path='unused',plan_sha='0'*64,manifest_path='unused',manifest_sha='0'*64,trust_owned_rendered=False)

    def test_restricted_pickle_cannot_execute_foreign_globals(self):
        class Dangerous:
            def __reduce__(self):
                return eval, ('1+1',)
        with self.assertRaisesRegex(train.TrainingError,'non_datum_global'):
            train.RestrictedRenderedUnpickler(io.BytesIO(pickle.dumps(Dangerous()))).load()

    def test_text_only_wrong_tensor_and_zero_assistant_loss_rejected(self):
        datum = actual_datum()
        for defect in ('text','shape','weights'):
            with self.subTest(defect=defect):
                bad = actual_datum()
                if defect == 'text':
                    bad = replace(bad, model_input=types.ModelInput.from_ints([1]*5))
                if defect == 'shape':
                    bad.loss_fn_inputs['target_tokens'] = types.TensorData(data=[1],dtype='int64',shape=[1])
                if defect == 'weights':
                    bad.loss_fn_inputs['weights'] = types.TensorData(data=[0]*5,dtype='float32',shape=[5])
                with self.assertRaises(train.TrainingError):
                    train.data_signature(bad)
        self.assertIsNotNone(train.data_signature(datum))

    def test_bound_external_train_directory_is_accepted_but_wrong_split_or_public_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve(); namespace = root/'main/work/trial.private'
            namespace.mkdir(parents=True)
            worker = root/'independent-checkout/partition_workers/train'
            task_sha = packet(worker/'private/task_set_manifest.json', {'train':[
                {'task_id':f'TRN-SYNTH-{index:03d}', 'package_sha256':'a'*64} for index in range(20)]})['sha256']
            packet(worker/'private/partition_cases.json', {'cases':{'synthetic':[]}})
            ref = {'path':str(worker),'sha256':task_sha}
            with patch.object(train,'ROOT',root/'main'):
                self.assertFalse(worker.is_relative_to(train.ROOT))
                self.assertEqual(train.checked_train_worker(namespace,ref),worker)
                reopened = train.private_json(worker/'private/task_set_manifest.json',task_sha,root=worker)
                self.assertEqual(len(reopened['train']),20)
                wrong = worker.with_name('selection'); wrong.mkdir()
                with self.assertRaisesRegex(train.TrainingError,'public_train_worker_only'):
                    train.checked_train_worker(namespace,{'path':str(wrong),'sha256':task_sha})
                (worker/'private/partition_cases.json').chmod(0o644)
                with self.assertRaisesRegex(train.TrainingError,'private_train_partition_inputs'):
                    train.checked_train_worker(namespace,ref)

    def test_actual_certified_external_train_path_metadata_is_accepted_without_body_reads(self):
        configured = os.environ.get('ENVLOOP_CERTIFIED_TRAIN_WORKER')
        if not configured:
            self.skipTest('Set ENVLOOP_CERTIFIED_TRAIN_WORKER to run the optional local metadata check')
        worker = Path(configured).resolve()
        if not worker.is_dir():
            self.skipTest('The user-certified local TRAIN directory is unavailable on this host')
        with patch.object(Path,'read_bytes',side_effect=AssertionError('Metadata check must not read task bodies')):
            self.assertFalse(worker.is_relative_to(train.ROOT))
            self.assertEqual(train.checked_train_worker(train.ROOT/'work',{'path':str(worker),'sha256':'a'*64}),worker)

    def test_hidden_or_foreign_proposal_id_fails_before_renderer_or_pickle(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve(); namespace = root/'work/trial.private'; namespace.mkdir(parents=True)
            worker = root/'certified-external-partition/train'; worker.mkdir(parents=True)
            families = ('purchase','inventory','sales','crm')
            cases = {family:[{'id':f'TRN-{family}-{i}','family':family,'prompt':'Synthetic public TRAIN fixture'}
                             for i in range(5)] for family in families}
            task_rows = [{'task_id':case['id'],'package_sha256':'a'*64} for group in cases.values() for case in group]
            task_sha = packet(worker/'private/task_set_manifest.json',{'train':task_rows})['sha256']
            cases_sha = packet(worker/'private/partition_cases.json',{'cases':cases})['sha256']
            manifest = {'schema':train.SCHEMA,'trial_plan_sha256':'b'*64,'formal_large_study_credit':0,
                'train_worker_ref':{'path':str(worker),'sha256':task_sha},'train_cases_sha256':cases_sha,
                'proposal_ref':{'path':'synthetic-proposal.json','sha256':'c'*64}}
            path = namespace/'training-input.private.json'; ref = packet(path,manifest)
            plan = {'models':{'student':train.MODEL,'teacher':'gpt-6-sol','initial_researcher':'gpt-6-sol'},
                    'formal_large_study_credit':0,'unknown_billing_is_null':True}
            proposal = {'hypothesis':'synthetic','train_task_ids':['ELPO-HID-SYNTH-001'],
                        'teacher_request':'Synthetic fixture. Never execute this as actual evidence.'}
            with patch.object(train,'ROOT',root), patch.object(train.trial,'checked_trial',return_value=plan), \
                 patch.object(train,'check_sources'), patch.object(train,'frozen_training',return_value=({},'d'*64)), \
                 patch.object(train.trial,'checked_proposal',return_value=proposal), \
                 patch.object(train.trial.teacher,'_load_renderer',side_effect=AssertionError('No renderer or provider')):
                with self.assertRaisesRegex(train.TrainingError,'actual_public_train_proposal'):
                    train.load_inputs(plan_path=namespace/'plan.private.json',plan_sha='b'*64,
                        manifest_path=path,manifest_sha=ref['sha256'],trust_owned_rendered=True)


class TrainingScheduleTests(unittest.TestCase):
    def test_bound_fixed_schedule_covers_all_datums_and_refuses_larger_or_costly_data(self):
        settings = {'batch_size':2,'optimizer_steps':2,'max_supervised_tokens':10,'max_scheduled_tokens':20}
        datums = [actual_datum() for _ in range(3)]
        self.assertEqual(train.fixed_schedule(datums,settings), ([[0,1],[2,0]],20))
        with self.assertRaisesRegex(train.TrainingError,'capacity_prerequisite'):
            train.fixed_schedule(datums*2,settings)
        with self.assertRaisesRegex(train.TrainingError,'scheduled_token_cap'):
            train.fixed_schedule(datums,{**settings,'max_scheduled_tokens':19})

    def test_new_pilot_settings_bind_real_anchor_and_do_not_claim_full_study(self):
        namespace = train.ROOT/'work/odoo-twenty-task-trial-20261001.private'
        path = namespace/'trial-training-sol6.private.json'; raw = path.read_bytes()
        settings, digest = train.frozen_training({'training_asset_sha256':hashed(raw)},namespace,
            {'trial_training_ref':{'path':str(path),'sha256':hashed(raw)}})
        self.assertEqual((settings['optimizer_steps'],settings['batch_size'],settings['lora_rank']), (64,2,8))
        self.assertFalse(settings['full_study_ratified_training_profile_claim'])


class NoRetryAndOwnershipTests(unittest.TestCase):
    def test_owned_holder_attempts_once_including_retryable_error_without_global_patch(self):
        from tinker.lib.internal_client_holder import InternalClientHolder
        original = InternalClientHolder.execute_with_retries
        cls = train.no_retry_service_class()
        holder = cls._get_session_holder.__globals__['InternalClientHolder']
        seen = []
        async def fail():
            seen.append('attempt'); raise TimeoutError('synthetic provider timeout')
        with self.assertRaises(TimeoutError):
            asyncio.run(holder.execute_with_retries(object(),fail))
        self.assertEqual(seen,['attempt'])
        self.assertIs(InternalClientHolder.execute_with_retries,original)

    def test_durable_intent_precedes_callback_uncertain_error_is_retained_no_replay(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp); calls = train.OwnedCalls(out,'synthetic-dataset'); seen = []
            def fail():
                self.assertTrue((out/'optim-intent.private.json').exists())
                seen.append('optim'); raise RuntimeError('synthetic uncertain operation')
            with self.assertRaises(RuntimeError):
                calls.call('optim',{},fail)
            with self.assertRaises(FileExistsError):
                calls.call('optim',{},fail)
            self.assertEqual(seen,['optim'])
            self.assertEqual(json.loads((out/'optim-error.private.json').read_bytes())['status'],'uncertain_no_replay')
            self.assertTrue(calls.settle()['all_owned_calls_settled'])

    def test_late_completion_is_retained_without_a_second_provider_call(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp); calls = train.OwnedCalls(out,'synthetic-dataset'); release = threading.Event(); seen=[]
            def late():
                seen.append('submit'); release.wait(2); return {'synthetic':'late-result'}
            with self.assertRaisesRegex(train.TrainingError,'uncertain_no_replay'):
                calls.call('sample',{},late,timeout=0.01)
            release.set(); self.assertTrue(calls.settle()['all_owned_calls_settled'])
            self.assertEqual(seen,['submit'])
            self.assertEqual(json.loads((out/'sample-result.private.json').read_bytes())['result'],{'synthetic':'late-result'})

    def test_actual_sdk_dataclass_tensors_and_sample_results_are_retained(self):
        tensor = types.TensorData(data=[-0.5],dtype='float32',shape=[1])
        response = types.ForwardBackwardOutput(loss_fn_output_type='cross_entropy',
            loss_fn_outputs=[{'logprobs':tensor}],metrics={'loss':0.5})
        result = train.retain_response(response)
        self.assertEqual(result['loss_fn_outputs'][0]['logprobs']['data'],[-0.5])
        self.assertEqual(result['metrics'],{'loss':0.5})
        sample = types.SampleResponse(sequences=[types.SampledSequence(sequence_id='synthetic-sequence',_tokens_list=[1,2],stop_reason='length')])
        self.assertEqual(train.retain_response(sample)['sequences'][0]['_tokens_list'],[1,2])

    def test_consumed_dataset_prevents_resubmission_with_a_different_output_name(self):
        with tempfile.TemporaryDirectory() as temp:
            namespace = Path(temp).resolve(); inputs = SimpleNamespace(namespace=namespace,identity='a'*64,
                training_sha='b'*64,training={'synthetic':True},plan={'models':{'teacher':'gpt-6-sol'}},
                datums=[actual_datum()],scheduled_tokens=5)
            seen=[]
            def uncertain(_inputs,_out):
                seen.append('provider'); raise RuntimeError('synthetic unknown result')
            kwargs={'plan_path':'unused','plan_sha':'c'*64,'manifest_path':'unused','manifest_sha':'d'*64,
                    'execute':True,'trust_owned_rendered':True}
            with patch.object(train,'load_inputs',return_value=inputs), patch.object(train,'train_real',side_effect=uncertain), \
                 patch.dict('os.environ',{'TINKER_API_KEY':'synthetic-not-a-real-key'}):
                with self.assertRaises(RuntimeError):
                    train.run(output_root=namespace/'first.private',**kwargs)
                with self.assertRaisesRegex(train.TrainingError,'already_consumed_no_replay'):
                    train.run(output_root=namespace/'different.private',**kwargs)
            self.assertEqual(seen,['provider'])


if __name__ == '__main__':
    unittest.main()
