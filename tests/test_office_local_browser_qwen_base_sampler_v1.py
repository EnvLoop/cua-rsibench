"""Offline model-to-action checks with synthetic provider adapters."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from cursibench.scale_vision_proxy import MODEL,RENDERER,PROCESSOR,Limits,VisionSamplingAdapter
from tests import test_office_local_browser_train_action_adapter_v1 as action_tests
from tools.office_local_browser_qwen_base_sampler_v1 import LocalQwenBaseSampler,admit,run,sha
from tools import office_single_account_train_pilot_v1 as private


class Adapter:
    def __init__(self,text='{"type":"double_click","target":{"x":20,"y":20}}'):
        self.backend=SimpleNamespace(identity={'model':MODEL,'sampling_kind':'base'})
        self.text=text;self.calls=[]
    def sample(self,**request):
        self.calls.append(request)
        return {'status':'completed','text':self.text}


class LocalBaseSamplerTests(unittest.TestCase):
    def setUp(self):
        f=action_tests.LocalActionAdapterTests();f.setUp();self.frame=f.frame;self.image=f.image
        self.instruction='Repair fictional benchmark text.'
    def sample(self,adapter,frame=None):
        return LocalQwenBaseSampler(adapter).sample_current_frame(frame or self.frame,
            self.image,self.instruction,now_ms=100000)
    def test_image_and_visible_instruction_reach_base_then_v066_action_is_bound(self):
        adapter=Adapter();action,result=self.sample(adapter)
        self.assertEqual(action['frame_id'],self.frame['frame_id'])
        self.assertEqual(action['task_binding_sha256'],self.frame['task_binding_sha256'])
        self.assertEqual(adapter.calls[0]['image_bytes'],self.image)
        prompt=json.loads(adapter.calls[0]['instruction'])
        self.assertEqual(prompt['task_instruction'],self.instruction)
        self.assertFalse(prompt['local_gui_profile']['actor_navigation_and_exports'])
        self.assertNotIn('a11y',json.dumps(prompt));self.assertNotIn('http',json.dumps(prompt))
    def test_bad_frame_and_image_fail_before_sampling(self):
        for change in ({'expires_at_ms':99999},{'screenshot_sha256':'d'*64},{'task_id':'final'}):
            adapter=Adapter()
            with self.subTest(change=change),self.assertRaises(ValueError):
                self.sample(adapter,{**self.frame,**change})
            self.assertEqual(adapter.calls,[])
    def test_checkpoint_or_wrong_model_cannot_be_used_as_base(self):
        for change in ({'sampling_kind':'checkpoint'},{'model':'wrong'}):
            adapter=Adapter();adapter.backend.identity.update(change)
            with self.assertRaises(ValueError):self.sample(adapter)
            self.assertEqual(adapter.calls,[])
    def test_bad_model_action_stops_after_one_sample(self):
        for text in ('{"type":"key","key":"Control+L"}',
                     '{"type":"click","target":{"x":0,"y":0}}',
                     '{"type":"type","mode":"fill","text":"x"}'):
            adapter=Adapter(text)
            with self.assertRaises(ValueError):self.sample(adapter)
            self.assertEqual(len(adapter.calls),1)
    def test_uncertain_provider_result_is_durable_and_not_resubmitted(self):
        class Backend:
            identity={'model':MODEL,'renderer':RENDERER,'image_processor':PROCESSOR,'sampling_kind':'base'}
            count=0
            def render(self,*_):return object(),{'input_tokens':10,'image_tokens':2,'chunk_types':['ImageChunk','EncodedTextChunk']}
            def submit(self,*_):
                self.count+=1
                return SimpleNamespace(result=lambda **_:(_ for _ in ()).throw(TimeoutError()))
        with tempfile.TemporaryDirectory() as tmp:
            backend=Backend();adapter=VisionSamplingAdapter(backend,Path(tmp)/'journal',limits=Limits(max_actions=2))
            for _ in range(2):
                with self.assertRaises(ValueError):self.sample(adapter)
            self.assertEqual(backend.count,1)
    def test_private_admission_and_consumed_output_gate_precedes_provider_factory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);work=root/'work';work.mkdir(mode=0o700)
            folder=work/'episode';folder.mkdir(mode=0o700)
            image=folder/'frame.png';image.write_bytes(self.image);image.chmod(0o600)
            frame=copy.deepcopy(self.frame);frame['expires_at_ms']=int(__import__('time').time()*1000)+100000
            frame['screenshot_ref']={'path':'episode/frame.png','sha256':sha(self.image)}
            frame_path=folder/'frame.json';private._write_new(frame_path,private._canonical(frame))
            instruction_path=folder/'instruction.txt';private._write_new(instruction_path,self.instruction.encode())
            source=Path(__file__).resolve().parents[1]
            admission={'schema':'office-local-browser-native-sampler-admission-v1',
                'mode':'native_development','cell':'powerpoint-web','split':'train',
                'task_id':frame['task_id'],'task_binding_sha256':frame['task_binding_sha256'],
                'account_principal_sha256':'a'*64,'control_receipt_sha256':'b'*64,
                'source_review_sha256':'c'*64,'visible_instruction_sha256':sha(self.instruction.encode()),
                'binding_sha256':'d'*64,'actor_before_sha256':'e'*64,'max_steps':2,
                'selection_or_final_eligible':False,'official_final_credit':0}
            for field,relative in {
                'bridge_source_sha256':'tools/office_local_browser_train_bridge_v1.mjs',
                'action_adapter_source_sha256':'tools/office_local_browser_train_action_adapter_v1.py',
                'sampler_source_sha256':'tools/office_local_browser_qwen_base_sampler_v1.py'}.items():
                admission[field]=sha((source/relative).read_bytes())
            ap=folder/'admission.json';private._write_new(ap,private._canonical(admission))
            self.assertEqual(admit(ap,frame_path,instruction_path,work)[0]['cell'],'powerpoint-web')
            consumed=folder/'consumed';consumed.mkdir(mode=0o700);calls=[]
            with self.assertRaises(ValueError):
                run(ap,frame_path,instruction_path,consumed,repo_root=root,
                    sampler_factory=lambda *_:calls.append(True))
            self.assertEqual(calls,[])
            bad={**admission,'mode':'offline_fixture'}
            bad_path=folder/'bad.json';private._write_new(bad_path,private._canonical(bad))
            with self.assertRaises(ValueError):admit(bad_path,frame_path,instruction_path,work)
            next_frame={**frame,'step':1,'frame_id':'f'*32}
            next_path=folder/'next-frame.json';private._write_new(next_path,private._canonical(next_frame))
            with self.assertRaises(ValueError):admit(ap,next_path,instruction_path,work)
            previous={'status':'applied','code':'ok'}
            admitted=admit(ap,next_path,instruction_path,work,memory='prior action',previous_action_result=previous)
            self.assertEqual(admitted[1]['step'],1)
            seen=[]
            class StopBeforeProvider:
                def sample_current_frame(self,*_,**context):
                    seen.append(context)
                    raise RuntimeError('synthetic_stop_before_provider')
            with self.assertRaisesRegex(RuntimeError,'synthetic_stop_before_provider'):
                run(ap,next_path,instruction_path,folder/'next-sample',repo_root=root,
                    memory='prior action',previous_action_result=previous,
                    sampler_factory=lambda *_:(StopBeforeProvider(),None,{}))
            self.assertEqual(seen,[{'memory':'prior action','previous_action_result':previous}])


if __name__=='__main__':unittest.main()
