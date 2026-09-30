import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

from tools.office_local_browser_terminal_waiter_v1 import serve,publish_new
from tests import test_office_local_browser_train_action_adapter_v1 as action_fixtures


REPO=Path(__file__).resolve().parents[1]
WORK=REPO/'work'
sha=lambda raw:hashlib.sha256(raw).hexdigest()


class Fixture:
    def __init__(self,case,steps=1,behavior='ok'):
        WORK.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(prefix='waiter-fixture-',dir=WORK)
        case.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.root.chmod(0o700)
        self.spool=self.root/'terminal-spool.private';self.spool.mkdir(mode=0o700)
        for name in ['requests.private','responses.private','samples.private','intents.private','dispatches.private']:
            (self.spool/name).mkdir(mode=0o700)
        (self.root/'frames.private').mkdir(mode=0o700)
        base=action_fixtures.LocalActionAdapterTests();base.setUp()
        self.frame=copy.deepcopy(base.frame);self.image=base.image
        self.now=int(time.time()*1000);self.frame['expires_at_ms']=self.now+100000
        self.steps=steps;self.behavior=behavior;self.calls=[];self.published=0
        self.instruction=self.root/'instruction.private.txt'
        publish_new(self.instruction,b'Synthetic protocol fixture task.')
        self.admission={'schema':'office-local-browser-native-sampler-admission-v1',
            'mode':'native_development','cell':'powerpoint-web','split':'train',
            'task_id':self.frame['task_id'],'task_binding_sha256':self.frame['task_binding_sha256'],
            'account_principal_sha256':'a'*64,'control_receipt_sha256':'b'*64,
            'source_review_sha256':'c'*64,'visible_instruction_sha256':sha(self.instruction.read_bytes()),
            'binding_sha256':'d'*64,'actor_before_sha256':'e'*64,'max_steps':steps,
            'selection_or_final_eligible':False,'official_final_credit':0}
        for field,name in {'bridge_source_sha256':'office_local_browser_train_bridge_v1.mjs',
                'action_adapter_source_sha256':'office_local_browser_train_action_adapter_v1.py',
                'sampler_source_sha256':'office_local_browser_qwen_base_sampler_v1.py'}.items():
            self.admission[field]=sha((REPO/'tools'/name).read_bytes())
        self.admission_path=self.root/'native-admission.private.json';publish_new(self.admission_path,self.admission)
        self.session={'schema':'office-local-terminal-spool-session-v1','session_id':'a'*32,
            'binding_sha256':self.admission['binding_sha256'],
            'native_admission_sha256':sha(self.admission_path.read_bytes()),
            'visible_instruction_ref':{'path':str(self.instruction.relative_to(WORK)),
                'sha256':sha(self.instruction.read_bytes())},
            'cua_helper_sha256':sha((REPO/'tools/office_local_browser_terminal_spool_v1.mjs').read_bytes()),
            'waiter_sha256':sha((REPO/'tools/office_local_browser_terminal_waiter_v1.py').read_bytes()),
            'max_steps':steps,'expires_at_ms':self.now+900000,'max_call_ms':1000}
        publish_new(self.spool/'session.private.json',self.session)
        self.session_sha=sha((self.spool/'session.private.json').read_bytes())

    def publish_request(self):
        assert (self.spool/'waiter-ready.private.json').is_file()
        step=self.published;self.published+=1;prefix=f'{step:03d}'
        image=self.root/'frames.private'/f'{prefix}.png';publish_new(image,self.image)
        frame={**self.frame,'step':step,'frame_id':f'{step+1:032x}',
            'screenshot_ref':{'path':str(image.relative_to(WORK)),'sha256':sha(self.image)}}
        frame_path=image.with_suffix('.frame.private.json');publish_new(frame_path,frame)
        context=self.spool/'requests.private'/f'{prefix}.context.private.json'
        publish_new(context,{'memory':'' if step==0 else 'memory0',
            'previous_action_result':None if step==0 else {'status':'applied','code':'ok'}})
        request={'schema':'office-terminal-spool-request-v1','session_sha256':self.session_sha,
            'step':step,'frame_id':frame['frame_id'],'deadline_ms':self.now+1000,
            'frame_ref':{'path':str(frame_path.relative_to(WORK)),'sha256':sha(frame_path.read_bytes())},
            'context_ref':{'path':str(context.relative_to(WORK)),'sha256':sha(context.read_bytes())}}
        publish_new(self.spool/'requests.private'/f'{prefix}.request.private.json',request)
        if self.behavior=='changed_context':
            context.write_bytes(context.read_bytes()+b' ')
        if self.behavior=='consumed_intent':
            publish_new(self.spool/'intents.private'/f'{prefix}.private.json',{'consumed':True})

    def pause(self,_):
        if self.behavior=='stop':
            publish_new(self.spool/'stop.private.json',{'status':'synthetic_stop'})
        elif self.published<self.steps:
            self.publish_request()

    def runner(self,admission_path,frame_path,instruction_path,out,*,repo_root,**context):
        self.calls.append(context);out.mkdir(mode=0o700)
        publish_new(out/'intent.private.json',{'synthetic_sampler':True,'official_final_credit':0})
        if self.behavior=='uncertain':
            raise TimeoutError('synthetic uncertain provider')
        frame_raw=frame_path.read_bytes();frame=json.loads(frame_raw)
        action={'version':'scale-computer-use-v0.6','task_id':frame['task_id'],
            'task_binding_sha256':frame['task_binding_sha256'],'step':frame['step'],
            'frame_id':frame['frame_id'],'type':'click','target':{'x':20,'y':20},'memory':'memory0'}
        action_sha=publish_new(out/'action.private.json',action)
        result={'schema':'office-local-qwen-base-one-frame-result-v1','status':'normalized_current_frame_action_only',
            'action_sha256':action_sha,'native_admission_sha256':sha(admission_path.read_bytes()),
            'frame_sha256':sha(frame_raw),'image_sha256':frame['screenshot_sha256'],
            'visible_instruction_sha256':sha(instruction_path.read_bytes()),
            'sampling':{'new_dispatch':True,'reused':False},'official_final_credit':0}
        publish_new(out/'result.private.json',result)
        if self.behavior=='late':
            request=json.loads((self.spool/'requests.private'/f"{frame['step']:03d}.request.private.json").read_bytes())
            self.now=request['deadline_ms']+1
        return result

    def run(self):
        return serve(self.root,repo_root=REPO,sampler_runner=self.runner,
            clock=lambda:self.now,pause=self.pause)


class TerminalWaiterTests(unittest.TestCase):
    def test_waiter_entry_is_callable(self):
        self.assertTrue(callable(serve))

    def test_ready_precedes_two_unique_requests_and_each_is_sampled_once(self):
        f=Fixture(self,steps=2);result=f.run()
        self.assertEqual(result['completed_samples'],2);self.assertEqual(len(f.calls),2)
        self.assertIsNone(f.calls[0]['previous_action_result'])
        self.assertEqual(f.calls[1]['previous_action_result'],{'status':'applied','code':'ok'})
        self.assertEqual(len(list((f.spool/'intents.private').iterdir())),2)
        self.assertEqual(len(list((f.spool/'responses.private').iterdir())),2)
        self.assertTrue((f.spool/'waiter-terminal.private.json').exists())
        with self.assertRaises(FileExistsError):f.run()
        self.assertEqual(len(f.calls),2)

    def test_uncertain_failure_is_consumed_poisoned_and_never_resubmitted(self):
        f=Fixture(self,behavior='uncertain')
        with self.assertRaises(TimeoutError):f.run()
        self.assertEqual(len(f.calls),1)
        self.assertTrue((f.spool/'poison.private.json').exists())
        self.assertTrue((f.spool/'samples.private/000.private/intent.private.json').exists())
        with self.assertRaises(FileExistsError):f.run()
        self.assertEqual(len(f.calls),1)

    def test_late_completed_result_is_preserved_and_poisoned(self):
        f=Fixture(self,behavior='late');result=f.run()
        self.assertEqual(result['status'],'poisoned');self.assertEqual(len(f.calls),1)
        response=json.loads((f.spool/'responses.private/000.response.private.json').read_bytes())
        self.assertEqual(response['status'],'late_no_replay')
        self.assertTrue((f.spool/'samples.private/000.private/action.private.json').exists())
        self.assertTrue((f.spool/'poison.private.json').exists())

    def test_consumed_intent_or_changed_context_refuses_sampler(self):
        for behavior in ['consumed_intent','changed_context']:
            with self.subTest(behavior=behavior):
                f=Fixture(self,behavior=behavior)
                with self.assertRaises((ValueError,OSError)):f.run()
                self.assertEqual(f.calls,[]);self.assertTrue((f.spool/'poison.private.json').exists())

    def test_changed_reviewed_waiter_source_refuses_startup(self):
        f=Fixture(self);f.session['waiter_sha256']='f'*64
        (f.spool/'session.private.json').write_text(json.dumps(f.session))
        with self.assertRaises(ValueError):f.run()
        self.assertEqual(f.calls,[]);self.assertFalse((f.spool/'waiter-ready.private.json').exists())

    def test_stop_before_frame_has_no_sampler_calls(self):
        f=Fixture(self,behavior='stop');result=f.run()
        self.assertEqual(result['status'],'stopped');self.assertEqual(f.calls,[])

    def test_real_node_spool_and_python_waiter_exchange_two_frames(self):
        f=Fixture(self,steps=2)
        shutil.rmtree(f.spool)  # Synthetic setup: the actual Node helper owns session creation.
        binding={'max_steps':2,'expires_at_ms':int(time.time()*1000)+900000,'frame_ttl_ms':150000,
            'task_id':f.frame['task_id'],'task_binding_sha256':f.frame['task_binding_sha256']}
        f.admission['binding_sha256']=sha(json.dumps(binding,sort_keys=True,separators=(',',':')).encode())
        f.admission_path.write_text(json.dumps(f.admission))
        publish_new(f.root/'fixture-frame.private.json',f.frame)
        publish_new(f.root/'fixture-image.private.png',f.image)
        script=r'''
          import * as fs from 'node:fs/promises';
          import path from 'node:path';
          import {createHash,randomBytes} from 'node:crypto';
          import {createOfficeTerminalSpool,publishPrivateNew} from './tools/office_local_browser_terminal_spool_v1.mjs';
          const root=ROOT,repo=REPO,binding=BINDING;
          const image=await fs.readFile(path.join(root,'fixture-image.private.png'));
          const base=JSON.parse(await fs.readFile(path.join(root,'fixture-frame.private.json')));
          const sha=v=>createHash('sha256').update(v).digest('hex');
          let observed=0,applied=0,stops=0;
          const bridge={receipt:()=>({mode:'native_development',status:'active'}),
            stop:async()=>{stops++;},dispatch:async()=>{applied++;return {status:'applied',code:'ok'};},
            observe:async()=>{
              const step=observed++,id=randomBytes(16).toString('hex');
              const imagePath=path.join(root,'frames.private',String(step).padStart(3,'0')+'-'+id+'.png');
              await publishPrivateNew(imagePath,image);
              const frame={...base,step,frame_id:id,expires_at_ms:Date.now()+100000,
                screenshot_sha256:sha(image),screenshot_ref:{path:path.relative(path.join(repo,'work'),imagePath),sha256:sha(image)}};
              await publishPrivateNew(imagePath.replace(/\.png$/,'.frame.private.json'),frame);
              return {...frame,screenshot_bytes:image};
            }};
          const helper=await createOfficeTerminalSpool({bridge,binding,artifactRoot:root,repoRoot:repo,
            visibleInstructionPath:path.join(root,'instruction.private.txt')});
          const ready=path.join(root,'terminal-spool.private/waiter-ready.private.json');
          while(true){try{await fs.stat(ready);break;}catch(e){if(e.code!=='ENOENT')throw e;
            await new Promise(resolve=>setTimeout(resolve,10));}}
          await helper.runOneFrame();await helper.runOneFrame();
          console.log(JSON.stringify({observed,applied,stops}));
        '''
        script=script.replace('ROOT',json.dumps(str(f.root))).replace('REPO',json.dumps(str(REPO))).replace('BINDING',json.dumps(binding))
        process=subprocess.Popen(['node','--input-type=module','-e',script],cwd=REPO,
            env={'PATH':os.environ['PATH']},stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        self.addCleanup(lambda:process.kill() if process.poll() is None else None)
        deadline=time.monotonic()+5
        while not (f.spool/'session.private.json').exists():
            self.assertLess(time.monotonic(),deadline)
            if process.poll() is not None:
                self.fail(process.communicate()[1])
            time.sleep(0.01)
        result=serve(f.root,repo_root=REPO,sampler_runner=f.runner,poll_seconds=0.01)
        stdout,stderr=process.communicate(timeout=10)
        self.assertEqual(process.returncode,0,stderr)
        self.assertEqual(json.loads(stdout),{'observed':2,'applied':2,'stops':1})
        self.assertEqual(result['completed_samples'],2)
        self.assertEqual(len(f.calls),2)
