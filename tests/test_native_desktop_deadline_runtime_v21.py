"""Actual v21 RPC/adapter/episode paths with synthetic provider and native guest."""
import io
import json
from pathlib import Path
import queue
import subprocess
import sys
import threading
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from cursibench import scale_vision_proxy as vision
from cursibench.scale_action_contract import make_observation
from native_desktop_factory import deadline_model_transport_v21 as transport
from native_desktop_factory import qwen_sampler_process_v21 as rpc
from native_desktop_factory import prospective_model_worker_v21 as worker
from native_desktop_factory import model_transport_integration_v21 as integration
from native_desktop_factory import train_weak_base_pilot_v21 as pilot
from native_desktop_factory.actor_deadline_future_v21 import ActorDeadlineReached
from native_desktop_factory.factory import digest
from tests.test_native_desktop_uniform_model_transport_v11 import FakeModelGuest,FakeSampler
from tests.test_native_desktop_post_enter_train_probe_v1 import png
from tests.test_native_desktop_selection_worker_v066 import source_case


class Clock:
    def __init__(self):self.now=10.0
    def __call__(self):return self.now


class Backend:
    def __init__(self,clock,kind):
        self.clock=clock;self.kind=kind;self.submits=0;self.waits=[]
        self.identity={'model':vision.MODEL,'renderer':vision.RENDERER,'image_processor':vision.PROCESSOR,
            'sampling_kind':'base','checkpoint_sha256':vision.digest(vision.MODEL),'temperature':0,'seed':23}
    def render(self,*_):return object(),{'input_tokens':100,'image_tokens':12,'chunk_types':['ImageChunk','EncodedTextChunk']}
    def decode(self,_):return '{"type":"click","target":{"x":500,"y":400}}'
    def submit(self,*_):
        self.submits+=1;owner=self
        class Future:
            def result(self,timeout):
                owner.waits.append(timeout)
                if owner.kind=='provider':owner.clock.now+=1;raise TimeoutError('synthetic earlier provider timeout')
                owner.clock.now+=timeout
                if owner.kind=='late':
                    return SimpleNamespace(sequences=[SimpleNamespace(tokens=[1],stop_reason='stop')],prompt_cache_hit_tokens=0)
                raise TimeoutError('synthetic actor deadline')
        return Future()


class QueueInput:
    def __init__(self):self.q=queue.Queue();self.closed=False
    def write(self,line):self.q.put(line)
    def flush(self):pass
    def close(self):self.closed=True;self.q.put(None)
    def __iter__(self):
        while True:
            value=self.q.get()
            if value is None:return
            yield value


class QueueOutput:
    def __init__(self):self.q=queue.Queue();self.pending=''
    def write(self,value):
        self.pending+=value
        while '\n' in self.pending:
            line,self.pending=self.pending.split('\n',1);self.q.put(line+'\n')
    def flush(self):pass
    def readline(self,_=None):return self.q.get(timeout=5)


class ThreadChild:
    def __init__(self,target):
        self.stdin=QueueInput();self.stdout=QueueOutput();self.pid=123456;self.returncode=None;self.error=None
        def run():
            try:target(self)
            except BaseException as exc:self.error=exc;self.returncode=1
            else:self.returncode=0
        self.thread=threading.Thread(target=run,daemon=True)
    def poll(self):return self.returncode
    def wait(self,timeout):
        self.thread.join(timeout)
        if self.thread.is_alive():raise subprocess.TimeoutExpired('synthetic child',timeout)
        return self.returncode
    def terminate(self):self.returncode=-15;self.stdin.close()
    def kill(self):self.returncode=-9;self.stdin.close()


def sampler_path(root,clock,kind='deadline',close_error=False):
    journal=root/'sampler-process';journal.mkdir(mode=0o700)
    backend=Backend(clock,kind);clean=transport.CleanRuntimeSampler()
    clean.backend=backend;clean.checkpoint_sha256=vision.digest(vision.MODEL);clean.max_output_tokens=128
    service=Mock();service._session_holder=SimpleNamespace(_session_id='synthetic-owned-session')
    if close_error:service.close.return_value.result.side_effect=TimeoutError('synthetic close uncertainty')
    clean.service=service
    clean.start=lambda **_: {'status':'ready','sampling_kind':backend.identity['sampling_kind']}
    process=object.__new__(rpc.SamplerProcess)
    process.root=root;process.journal=journal;process.plan='a'*64;process.ordinal=0
    process.poisoned=False;process.uncertain=False;process.closed=False;process.acknowledgement_verified=False
    process.stderr=io.StringIO()
    child=ThreadChild(lambda c:rpc.serve(root,journal,'a'*64,sampler_factory=lambda:clean))
    process.process=child
    sampler=object.__new__(transport.ModelSampler);sampler.process=process
    sampler.backend=SimpleNamespace(identity={'sampling_kind':'base'});sampler.checkpoint_sha256=vision.digest(vision.MODEL)
    sampler.deadline_stop=None
    return sampler,child,clean,backend,service


class RuntimeTests(unittest.TestCase):
    def test_actual_rpc_clean_adapter_retains_swallowed_deadline_and_poisoned_close_ack(self):
        for kind in ['deadline','late']:
            with self.subTest(kind=kind),TemporaryDirectory() as tmp:
                root=Path(tmp);root.chmod(0o700);clock=Clock()
                sampler,child,clean,backend,service=sampler_path(root,clock,kind)
                streams=SimpleNamespace(stdin=child.stdin,stdout=child.stdout,stderr=io.StringIO())
                with patch.object(rpc,'sys',streams),\
                     patch('cursibench.full_study_qwen_runtime_gate_v1.pre_dispatch',return_value={}),\
                     patch.object(rpc.select,'select',return_value=([child.stdout],[],[])),\
                     patch.object(transport.time,'monotonic',clock):
                    child.thread.start();sampler.process.call('setup',{})
                    task=root/'task';task.mkdir(mode=0o700)
                    observation=make_observation(task_id='fixture',task_binding_sha256='b'*64,
                        instruction='synthetic public task',step=0,screenshot_bytes=png('white'))
                    with self.assertRaises(ActorDeadlineReached):
                        sampler.sample(observation=observation,request_id='synthetic-000',task_dir=task,
                            remaining_seconds=3.57152125,actor_deadline=13.57152125)
                    sampler.assert_deadline_stop(13.57152125)
                    with self.assertRaisesRegex(ValueError,'poisoned'):sampler.process.call('sample',{})
                    sampler.close(False)
                self.assertIsNone(child.error)
                self.assertAlmostEqual(backend.waits[0],3.57152125)
                self.assertEqual(backend.submits,1)
                rpc_result=json.loads((root/'sampler-process/001.result.private.json').read_bytes())
                self.assertEqual(rpc_result['status'],'actor_deadline')
                self.assertEqual(rpc_result['retained_sampling_failure']['error_subtype'],'provider_timeout_uncertain')
                terminal=json.loads((root/'sampler-process/child-terminal.private.json').read_bytes())
                self.assertTrue(terminal['provider_shutdown_acknowledged']);self.assertFalse(terminal['forced_termination'])
                self.assertTrue(terminal['request_acknowledgement_verified'])
                service.close.assert_called_once()
                if kind=='late':self.assertTrue(list((task/'sampling-journal').glob('*.late-response.private.json')))

    def test_earlier_provider_timeout_is_not_budget_and_close_uncertainty_is_retained(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);root.chmod(0o700);clock=Clock()
            sampler,child,clean,backend,service=sampler_path(root,clock,'provider',True)
            streams=SimpleNamespace(stdin=child.stdin,stdout=child.stdout,stderr=io.StringIO())
            with patch.object(rpc,'sys',streams),patch('cursibench.full_study_qwen_runtime_gate_v1.pre_dispatch',return_value={}),\
                 patch.object(rpc.select,'select',return_value=([child.stdout],[],[])),patch.object(transport.time,'monotonic',clock):
                child.thread.start();sampler.process.call('setup',{})
                task=root/'task';task.mkdir(mode=0o700)
                obs=make_observation(task_id='fixture',task_binding_sha256='b'*64,instruction='synthetic',step=0,screenshot_bytes=png('white'))
                with self.assertRaisesRegex(ValueError,'retained_result'):
                    sampler.sample(observation=obs,request_id='synthetic-provider',task_dir=task,remaining_seconds=720,actor_deadline=730)
                self.assertIsNone(sampler.deadline_stop);sampler.close(False)
            terminal=json.loads((root/'sampler-process/child-terminal.private.json').read_bytes())
            self.assertFalse(terminal['provider_shutdown_acknowledged'])
            ack=json.loads((root/'sampler-process/provider-shutdown.private.json').read_bytes())
            self.assertEqual(ack['status'],'uncertain');self.assertEqual(ack['exception_type'],'TimeoutError')
            self.assertIsNotNone(ack['owned_session_id_sha256']);self.assertEqual(backend.submits,1)

    def test_common_episode_scores_only_after_saved_readback_and_distinct_reset_for_all_five_slots(self):
        source,_neutral,positive,oracle,extension=source_case('calc-growth')
        for owner in ['shared-base',*integration.matrix.RESEARCHERS]:
            with self.subTest(owner=owner),TemporaryDirectory() as tmp:
                root=Path(tmp);root.chmod(0o700);clock=Clock()
                from tests.test_structural_guest_attestation_v16 import fixture
                guest_ref=root/'guest.json';guest_ref.write_text(json.dumps(fixture()[2]))
                private_map=root/'map.json';private_map.write_text(json.dumps({'variant_salt':'offline-only-'*4}));private_map.chmod(0o600)
                admitted={'guest_public':str(guest_ref),'scoped_reference':str(root/'profile'),'private_map':str(private_map)}
                package={'identity':{'task_id':'fixture','package_sha256':'b'*64},'source':source,'oracle':oracle,
                         'filename':'train'+extension,'instruction':'synthetic public TRAIN task'}
                sampler,child,clean,backend,service=sampler_path(root,clock)
                checkpoint=None if owner=='shared-base' else 'tinker://synthetic/sampler_weights/'+owner
                backend.identity.update(sampling_kind='base' if checkpoint is None else 'checkpoint',
                    checkpoint_sha256=vision.digest(checkpoint or vision.MODEL))
                clean.checkpoint_sha256=vision.digest(vision.MODEL) if checkpoint is None else digest(checkpoint.encode())
                streams=SimpleNamespace(stdin=child.stdin,stdout=child.stdout,stderr=io.StringIO())
                freeze={'source_sha256s':integration.proposal()['source_sha256s']}
                paid=pilot.PilotPaidCalls(freeze,root/'paid',sampler)
                made=[]
                def create(**kw):
                    guest=FakeModelGuest(kw['root'],kw['out'],kw['filename'],source,positive,kw['out'].name,package['identity'])
                    if kw['out'].name=='actor':
                        original_observe=guest.observe
                        def near_deadline(**arguments):
                            clock.now=730-3.57152125
                            return original_observe(**arguments)
                        guest.observe=near_deadline
                    made.append(guest);return guest
                model=worker.DesktopProspectiveModelWorker(study=None,admissions_path=Path('/unused'),proposal_path=Path('/unused'))
                with patch.object(rpc,'sys',streams),patch('cursibench.full_study_qwen_runtime_gate_v1.pre_dispatch',return_value={}),\
                     patch.object(rpc.select,'select',return_value=([child.stdout],[],[])),patch.object(transport.time,'monotonic',clock),\
                     patch.object(transport,'create_guest',side_effect=create),\
                     patch('native_desktop_factory.reconcile_interrupted_sweep.active_hashes',return_value=([],0)):
                    child.thread.start();sampler.start(checkpoint_path=checkpoint,
                        checkpoint_sha256=clean.checkpoint_sha256,seed=23,max_output_tokens=128,attempt_id=owner)
                    result,out,trace,elapsed,outcome=model._episode(admitted=admitted,package=package,ordinal=0,
                        batch=root,paid=paid,sampler=sampler)
                    sampler.close(False)
                self.assertEqual(outcome,'actor_wall_budget');self.assertEqual(elapsed,720)
                self.assertEqual(result['score'],0);self.assertEqual(len(made),2)
                self.assertTrue(all(g.killed for g in made));self.assertFalse(made[0].clicked)
                self.assertNotEqual(made[0].sandbox.sandbox_id,made[1].sandbox.sandbox_id)
                self.assertTrue((out/'saved-state.private.json').exists());self.assertTrue((out/'verifier.private.json').exists())
                self.assertTrue((out/'reset.private.json').exists())
                self.assertEqual(trace[0]['status'],'not_applied_actor_deadline')
                self.assertEqual(backend.submits,1)
                self.assertTrue(any('sample-' in v for v in paid.ids))
                self.assertEqual(sampler.backend.identity['sampling_kind'],'base' if checkpoint is None else 'checkpoint')

    def test_readback_reset_failure_or_earlier_provider_fault_has_no_scored_task(self):
        source,_neutral,positive,oracle,extension=source_case('calc-growth')
        for mode in ['readback','reset','provider']:
            with self.subTest(mode=mode),TemporaryDirectory() as tmp:
                root=Path(tmp);root.chmod(0o700);clock=Clock()
                from tests.test_structural_guest_attestation_v16 import fixture
                guest_ref=root/'guest.json';guest_ref.write_text(json.dumps(fixture()[2]))
                private_map=root/'map.json';private_map.write_text(json.dumps({'variant_salt':'offline-only-'*4}));private_map.chmod(0o600)
                admitted={'guest_public':str(guest_ref),'scoped_reference':str(root/'profile'),'private_map':str(private_map)}
                package={'identity':{'task_id':'fixture','package_sha256':'b'*64},'source':source,'oracle':oracle,
                         'filename':'train'+extension,'instruction':'synthetic public TRAIN task'}
                sampler,child,clean,backend,service=sampler_path(root,clock,'provider' if mode=='provider' else 'deadline')
                streams=SimpleNamespace(stdin=child.stdin,stdout=child.stdout,stderr=io.StringIO())
                paid=pilot.PilotPaidCalls({'source_sha256s':integration.proposal()['source_sha256s']},root/'paid',sampler)
                made=[]
                def create(**kw):
                    guest=FakeModelGuest(kw['root'],kw['out'],kw['filename'],source,positive,kw['out'].name,package['identity'])
                    if kw['out'].name=='actor' and mode!='provider':
                        original=guest.observe
                        def observe(**args):clock.now=730-3.57152125;return original(**args)
                        guest.observe=observe
                    if kw['out'].name=='actor' and mode=='readback':guest.read_saved=Mock(side_effect=OSError('synthetic readback failure'))
                    if kw['out'].name=='reset' and mode=='reset':guest.read_saved=lambda:b'wrong restoration'
                    made.append(guest);return guest
                model=worker.DesktopProspectiveModelWorker(study=None,admissions_path=Path('/unused'),proposal_path=Path('/unused'))
                with patch.object(rpc,'sys',streams),patch('cursibench.full_study_qwen_runtime_gate_v1.pre_dispatch',return_value={}),\
                     patch.object(rpc.select,'select',return_value=([child.stdout],[],[])),patch.object(transport.time,'monotonic',clock),\
                     patch.object(transport,'create_guest',side_effect=create),\
                     patch('native_desktop_factory.reconcile_interrupted_sweep.active_hashes',return_value=([],0)):
                    child.thread.start();sampler.process.call('setup',{})
                    try:
                        with self.assertRaises((ValueError,OSError)):
                            model._episode(admitted=admitted,package=package,ordinal=0,batch=root,paid=paid,sampler=sampler)
                    finally:sampler.close(False)
                self.assertTrue(all(g.killed for g in made));self.assertEqual(backend.submits,1)
                self.assertFalse((root/'gui/fixture/evaluator/task.private.json').exists())
                self.assertFalse((root/'gui/fixture/evaluator/verifier.private.json').exists())
                if mode=='provider':self.assertIsNone(sampler.deadline_stop)

    def test_fresh_proposal_preserves_common_limits_guard_scorer_and_legacy_source_pins(self):
        p=integration.proposal()
        self.assertEqual((p['max_actor_actions'],p['max_actor_wall_seconds'],p['lease_seconds_each']),(90,720,1200))
        self.assertEqual(p['configuration_owners'],['shared-base','astra','sol56','sol6','luna6'])
        self.assertFalse(p['uncertain_sample_coverage_relaxed'])
        self.assertIs(transport.ModelGuest,transport.legacy.ModelGuest)
        self.assertFalse(p['dispatch_enabled']);self.assertEqual(p['official_model_results'],0)

    def test_disabled_train_pilot_rejects_before_private_reads(self):
        with patch.object(pilot._bound,'validate',side_effect=AssertionError('private read')):
            with self.assertRaisesRegex(ValueError,'disabled'):
                pilot.run(freeze_path=Path('/absent'),permit_path=Path('/absent'))
