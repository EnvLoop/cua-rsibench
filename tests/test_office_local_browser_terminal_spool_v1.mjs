import test from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash,randomBytes} from 'node:crypto';
import {createOfficeTerminalSpool,publishPrivateNew} from '../tools/office_local_browser_terminal_spool_v1.mjs';

const repo=fileURLToPath(new URL('..',import.meta.url));
const work=path.join(repo,'work');
const sha=raw=>createHash('sha256').update(raw).digest('hex');
const sorted=v=>Array.isArray(v)?v.map(sorted):v&&typeof v==='object'?
  Object.fromEntries(Object.keys(v).sort().map(k=>[k,sorted(v[k])])):v;

async function fixture(t,{steps=1,behavior='ok'}={}) {
  await fs.mkdir(work,{recursive:true});
  const root=await fs.mkdtemp(path.join(work,'spool-fixture-'));
  await fs.chmod(root,0o700);await fs.mkdir(path.join(root,'frames.private'),{mode:0o700});
  const f={root,now:Date.now(),observed:0,dispatched:[],stops:0,behavior};
  f.binding={max_steps:steps,expires_at_ms:f.now+900000,frame_ttl_ms:150000,
    task_id:'ppt-wdi-transfer-'+'b'.repeat(16),task_binding_sha256:'c'.repeat(64)};
  const instructionFile=path.join(root,'visible-instruction.private.txt');
  await publishPrivateNew(instructionFile,Buffer.from('Synthetic fixture task.'));
  const admission={schema:'office-local-browser-native-sampler-admission-v1',mode:'native_development',split:'train',
    max_steps:steps,binding_sha256:sha(JSON.stringify(sorted(f.binding))),
    visible_instruction_sha256:sha(await fs.readFile(instructionFile))};
  await publishPrivateNew(path.join(root,'native-admission.private.json'),admission);
  f.bridge={receipt:()=>({mode:'native_development',status:'active'}),stop:async()=>{f.stops++;},
    observe:async()=>{
      const step=f.observed++,nonce=randomBytes(16).toString('hex'),image=Buffer.from('synthetic fixture image '+step);
      const imagePath=path.join(root,'frames.private',String(step).padStart(3,'0')+'-'+nonce+'.png');
      await publishPrivateNew(imagePath,image);
      const frame={schema:'office-local-browser-frame-v1',frame_id:nonce,step,task_id:f.binding.task_id,
        task_binding_sha256:f.binding.task_binding_sha256,expires_at_ms:f.now+150000,
        screenshot_sha256:sha(image),screenshot_ref:{path:path.relative(work,imagePath),sha256:sha(image)},
        width:1920,height:747,local_profile:{synthetic:true}};
      await publishPrivateNew(imagePath.replace(/\.png$/,'.frame.private.json'),frame);
      return {...frame,screenshot_bytes:image};
    },dispatch:async action=>{f.dispatched.push(action);return action.type==='finish'?{status:'stopped'}:{status:'applied',code:'ok'};},
  };
  f.respond=async()=>{
    f.now+=10;
    if(f.behavior==='timeout'){f.now+=1000;return;}
    const step=f.observed-1,prefix=String(step).padStart(3,'0');
    const spool=path.join(root,'terminal-spool.private');
    const request=JSON.parse(await fs.readFile(path.join(spool,'requests.private',prefix+'.request.private.json')));
    const frameRaw=await fs.readFile(path.join(work,request.frame_ref.path)),frame=JSON.parse(frameRaw);
    const out=path.join(spool,'samples.private',prefix+'.private');await fs.mkdir(out,{mode:0o700});
    const action={version:'scale-computer-use-v0.6',task_id:frame.task_id,task_binding_sha256:frame.task_binding_sha256,
      frame_id:frame.frame_id,step:frame.step,type:f.behavior==='finish'?'finish':'click',memory:'memory'+step};
    if(action.type==='click')action.target={x:500,y:200};
    const actionSha=await publishPrivateNew(path.join(out,'action.private.json'),action);
    const session=JSON.parse(await fs.readFile(path.join(spool,'session.private.json')));
    const result={status:'normalized_current_frame_action_only',action_sha256:actionSha,
      native_admission_sha256:session.native_admission_sha256,frame_sha256:sha(frameRaw),
      image_sha256:frame.screenshot_sha256,visible_instruction_sha256:session.visible_instruction_ref.sha256,
      sampling:{new_dispatch:true,reused:false}};
    const resultSha=await publishPrivateNew(path.join(out,'result.private.json'),result);
    const response={schema:'office-terminal-spool-response-v1',session_sha256:request.session_sha256,
      step,frame_id:f.behavior==='wrong_nonce'?'e'.repeat(32):frame.frame_id,
      status:f.behavior==='uncertain'?'failed_or_uncertain_no_replay':'normalized_current_frame_action_only',
      result_ref:{path:path.relative(work,path.join(out,'result.private.json')),sha256:resultSha},
      action_ref:{path:path.relative(work,path.join(out,'action.private.json')),sha256:actionSha}};
    if(f.behavior==='changed_hash')await fs.appendFile(path.join(out,'action.private.json'),' ');
    if(f.behavior==='late')f.now=request.deadline_ms;
    await publishPrivateNew(path.join(spool,'responses.private',prefix+'.response.private.json'),response);
  };
  f.helper=await createOfficeTerminalSpool({bridge:f.bridge,binding:f.binding,artifactRoot:root,repoRoot:repo,
    visibleInstructionPath:instructionFile,maxCallMs:1000,pollMs:10,clock:()=>f.now,pause:()=>f.respond()});
  f.ready=async()=>publishPrivateNew(path.join(root,'terminal-spool.private/waiter-ready.private.json'),{
    schema:'office-terminal-waiter-ready-v1',status:'ready',session_sha256:f.helper.sessionReceipt().session_sha256});
  t.after(async()=>{await fs.rm(root,{recursive:true,force:true});});
  return f;
}

test('terminal-first helper exports the native frame transaction',()=>{
  assert.equal(typeof createOfficeTerminalSpool,'function');
});

test('waiter must be ready before observation; startup failure stops without a frame',async t=>{
  const f=await fixture(t);
  await assert.rejects(f.helper.runOneFrame());
  assert.equal(f.observed,0);assert.equal(f.stops,1);assert.equal(f.dispatched.length,0);
});

test('two distinct fresh frames dispatch and carry only applied context',async t=>{
  const f=await fixture(t,{steps:2});await f.ready();
  assert.equal((await f.helper.runOneFrame()).status,'applied');
  assert.equal((await f.helper.runOneFrame()).status,'applied');
  assert.equal(f.observed,2);assert.equal(f.dispatched.length,2);assert.equal(f.stops,1);
  assert.notEqual(f.dispatched[0].frame_id,f.dispatched[1].frame_id);
  const context=JSON.parse(await fs.readFile(path.join(f.root,'terminal-spool.private/requests.private/001.context.private.json')));
  assert.deepEqual(context,{memory:'memory0',previous_action_result:{status:'applied',code:'ok'}});
  await assert.rejects(f.helper.runOneFrame());assert.equal(f.observed,2);
});

test('late, uncertain, nonce-mismatched or changed-hash responses stop before dispatch and cannot replay',async t=>{
  for(const behavior of ['late','uncertain','wrong_nonce','changed_hash','timeout']) {
    const f=await fixture(t,{behavior});await f.ready();
    await assert.rejects(f.helper.runOneFrame());
    assert.equal(f.dispatched.length,0);assert.equal(f.stops,1);
    const poison=JSON.parse(await fs.readFile(path.join(f.root,'terminal-spool.private/poison.private.json')));
    assert.equal(poison.status,'consumed_session_no_replay');
    await assert.rejects(f.helper.runOneFrame());assert.equal(f.observed,1);
  }
});

test('finish closes the bridge and preserves private terminal records',async t=>{
  const f=await fixture(t,{behavior:'finish'});await f.ready();
  assert.equal((await f.helper.runOneFrame()).status,'stopped');assert.equal(f.stops,1);
  assert.equal(f.dispatched[0].type,'finish');
  assert.equal(JSON.parse(await fs.readFile(path.join(f.root,'terminal-spool.private/stop.private.json'))).code,'model_finish');
});

test('concurrent calls cannot publish another frame while one model request is pending',async t=>{
  const f=await fixture(t);await f.ready();
  let entered,release;
  const waiting=new Promise(resolve=>{entered=resolve;}),resume=new Promise(resolve=>{release=resolve;});
  const original=f.respond;
  f.respond=async()=>{entered();await resume;await original();};
  const first=f.helper.runOneFrame();await waiting;
  await assert.rejects(f.helper.runOneFrame(),/concurrent_terminal_spool_call/);
  assert.equal(f.observed,1);assert.equal(f.dispatched.length,0);
  release();assert.equal((await first).status,'applied');assert.equal(f.stops,1);
});

test('consumed artifact root and an oversized per-call budget cannot reopen the spool',async t=>{
  const f=await fixture(t);
  const options={bridge:f.bridge,binding:f.binding,artifactRoot:f.root,repoRoot:repo,
    visibleInstructionPath:path.join(f.root,'visible-instruction.private.txt'),clock:()=>f.now};
  await assert.rejects(createOfficeTerminalSpool({...options,maxCallMs:60000}),/invalid_cua_call_budget/);
  await assert.rejects(createOfficeTerminalSpool(options),/EEXIST/);
});

test('CUA helper contains no environment, subprocess, provider or page-content access',async()=>{
  const source=await fs.readFile(new URL('../tools/office_local_browser_terminal_spool_v1.mjs',import.meta.url),'utf8');
  assert.ok(!/node:process|child_process|process\.env|fetch\(|getDOM|evaluate\(/.test(source));
});
