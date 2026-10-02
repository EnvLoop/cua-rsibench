/* CUA owns only the existing native bridge and a private filesystem spool.
 * The separately started terminal owns the sampler, environment and provider.
 */
import * as fs from 'node:fs/promises';
import path from 'node:path';
import {createHash,randomBytes} from 'node:crypto';
import {fileURLToPath} from 'node:url';

const sha=raw=>createHash('sha256').update(raw).digest('hex');
const canonical=v=>Array.isArray(v)?v.map(canonical):v&&typeof v==='object'?
  Object.fromEntries(Object.keys(v).sort().map(k=>[k,canonical(v[k])])):v;
const digest=v=>sha(JSON.stringify(canonical(v)));
const check=(ok,code)=>{if(!ok)throw new Error(code);};
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));

export async function publishPrivateNew(file,value) {
  const raw=Buffer.isBuffer(value)?value:Buffer.from(JSON.stringify(value)+'\n');
  const temporary=file+'.'+randomBytes(12).toString('hex')+'.pending';
  const h=await fs.open(temporary,'wx',0o600);
  try{await h.writeFile(raw);await h.sync();}finally{await h.close();}
  try {
    await fs.link(temporary,file); // Atomic publication with exclusive destination.
    const directory=await fs.open(path.dirname(file),'r');
    try{await directory.sync();}finally{await directory.close();}
  } finally {await fs.unlink(temporary);}
  return sha(raw);
}

async function privateFile(file,root) {
  const absolute=path.resolve(file),real=await fs.realpath(absolute),st=await fs.lstat(absolute);
  check(real===absolute && absolute.startsWith(root+path.sep) && st.isFile() &&
    !st.isSymbolicLink() && (st.mode&0o077)===0 && st.size>0 && st.size<=2_000_000,
    'unsafe_terminal_spool_file');
  return fs.readFile(absolute);
}
async function privateJson(file,root) {
  const raw=await privateFile(file,root),value=JSON.parse(raw);
  check(value && typeof value==='object' && !Array.isArray(value),'invalid_terminal_spool_json');
  return {value,raw};
}
async function exists(file) {
  try{await fs.lstat(file);return true;}catch(e){if(e.code==='ENOENT')return false;throw e;}
}

export async function createOfficeTerminalSpool({bridge,binding,artifactRoot,repoRoot,
    visibleInstructionPath,maxCallMs=55000,pollMs=100,clock=Date.now,pause=sleep}) {
  const repo=await fs.realpath(repoRoot),root=await fs.realpath(artifactRoot),work=path.join(repo,'work');
  const sourceRepo=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
  check(repo===sourceRepo && root===path.resolve(artifactRoot) && root.startsWith(work+path.sep) &&
    (await fs.lstat(root)).isDirectory() &&
    ((await fs.lstat(root)).mode&0o077)===0,'private_root_owned_spool_required');
  check(Number.isSafeInteger(maxCallMs) && maxCallMs>=1000 && maxCallMs<=55000 &&
    Number.isSafeInteger(pollMs) && pollMs>=10 && pollMs<=1000,'invalid_cua_call_budget');
  const {value:admission,raw:admissionRaw}=await privateJson(path.join(root,'native-admission.private.json'),root);
  check(admission.schema==='office-local-browser-native-sampler-admission-v1' &&
    admission.mode==='native_development' && admission.split==='train' &&
    admission.binding_sha256===digest(binding) && admission.max_steps===binding.max_steps &&
    binding.expires_at_ms>clock() && binding.expires_at_ms<=clock()+900000 &&
    Number.isSafeInteger(binding.frame_ttl_ms) && binding.frame_ttl_ms<=150000 &&
    binding.frame_ttl_ms>=1000 && bridge.receipt().mode==='native_development' &&
    bridge.receipt().status==='active','native_spool_binding_required');
  const instruction=path.resolve(visibleInstructionPath);
  const instructionRaw=await privateFile(instruction,root);
  check(sha(instructionRaw)===admission.visible_instruction_sha256,'spool_instruction_changed');
  const spool=path.join(root,'terminal-spool.private');
  await fs.mkdir(spool,{mode:0o700}); // A consumed session cannot be reconstructed.
  for(const name of ['requests.private','responses.private','samples.private','intents.private','dispatches.private'])
    await fs.mkdir(path.join(spool,name),{mode:0o700});
  const session={schema:'office-local-terminal-spool-session-v1',session_id:randomBytes(16).toString('hex'),
    binding_sha256:admission.binding_sha256,native_admission_sha256:sha(admissionRaw),
    visible_instruction_ref:{path:path.relative(work,instruction),sha256:sha(instructionRaw)},
    cua_helper_sha256:sha(await fs.readFile(fileURLToPath(import.meta.url))),
    waiter_sha256:sha(await fs.readFile(path.join(repo,'tools/office_local_browser_terminal_waiter_v1.py'))),
    max_steps:binding.max_steps,expires_at_ms:binding.expires_at_ms,max_call_ms:maxCallMs};
  const sessionSha=await publishPrivateNew(path.join(spool,'session.private.json'),session);
  let next=0,busy=false,stopped=false,memory='',previous=null;
  async function poison(code) {
    try{await publishPrivateNew(path.join(spool,'poison.private.json'),{
      schema:'office-terminal-spool-poison-v1',status:'consumed_session_no_replay',code,
      session_sha256:sessionSha,step:next,official_final_credit:0});}
    catch(e){if(e.code!=='EEXIST')throw e;}
  }
  async function stop(code='operator_stop') {
    if(stopped)return {status:'stopped',official_final_credit:0};
    await bridge.stop();stopped=true;
    await publishPrivateNew(path.join(spool,'stop.private.json'),{
      schema:'office-terminal-spool-stop-v1',session_sha256:sessionSha,code,
      applied_frame_count:next,official_final_credit:0});
    return {status:'stopped',official_final_credit:0};
  }
  async function readRef(ref,expected) {
    check(ref && typeof ref.path==='string' && !path.isAbsolute(ref.path) &&
      typeof ref.sha256==='string','invalid_spool_response_reference');
    const target=path.resolve(work,ref.path);
    check(target===expected,'wrong_spool_response_reference');
    const raw=await privateFile(target,root);
    check(sha(raw)===ref.sha256,'spool_response_hash_changed');
    return {raw,value:JSON.parse(raw)};
  }
  return Object.freeze({
    sessionReceipt:()=>({schema:session.schema,session_sha256:sessionSha,max_steps:session.max_steps,
      max_call_ms:session.max_call_ms,official_final_credit:0}),
    stop,
    runOneFrame:async()=>{
      check(!busy,'concurrent_terminal_spool_call');busy=true;
      const started=clock();let observed=false;
      try {
        check(!stopped && next<session.max_steps && clock()<session.expires_at_ms,'spool_lease_or_step_expired');
        check(!(await exists(path.join(spool,'poison.private.json'))),'poisoned_spool_no_replay');
        const ready=await privateJson(path.join(spool,'waiter-ready.private.json'),root);
        check(ready.value.schema==='office-terminal-waiter-ready-v1' && ready.value.status==='ready' &&
          ready.value.session_sha256===sessionSha,'terminal_waiter_not_ready');
        const frame=await bridge.observe();observed=true;
        check(frame.step===next && frame.task_id===binding.task_id &&
          frame.task_binding_sha256===binding.task_binding_sha256 && frame.expires_at_ms>clock() &&
          frame.expires_at_ms<=clock()+150000,'spool_observed_frame_changed');
        const image=path.resolve(work,frame.screenshot_ref.path),frameFile=image.replace(/\.png$/,'.frame.private.json');
        check(image.startsWith(path.join(root,'frames.private')+path.sep),'spool_frame_outside_actor_root');
        const frameRaw=await privateFile(frameFile,root);
        const {screenshot_bytes,...frameMetadata}=frame;
        check(digest(JSON.parse(frameRaw))===digest(frameMetadata),'spool_frame_file_changed');
        const prefix=String(next).padStart(3,'0'),contextFile=path.join(spool,'requests.private',prefix+'.context.private.json');
        const contextSha=await publishPrivateNew(contextFile,{memory,previous_action_result:previous});
        const deadline=Math.min(started+maxCallMs,frame.expires_at_ms,session.expires_at_ms);
        check(clock()<deadline,'spool_publish_deadline_exceeded');
        const request={schema:'office-terminal-spool-request-v1',session_sha256:sessionSha,
          step:next,frame_id:frame.frame_id,deadline_ms:deadline,
          frame_ref:{path:path.relative(work,frameFile),sha256:sha(frameRaw)},
          context_ref:{path:path.relative(work,contextFile),sha256:contextSha}};
        await publishPrivateNew(path.join(spool,'requests.private',prefix+'.request.private.json'),request);
        const responseFile=path.join(spool,'responses.private',prefix+'.response.private.json');
        while(!(await exists(responseFile))) {
          check(!stopped,'terminal_spool_stopped');
          check(clock()<deadline,'model_wait_deadline_exceeded');
          check(!(await exists(path.join(spool,'poison.private.json'))),'terminal_session_poisoned');
          await pause(Math.min(pollMs,Math.max(1,deadline-clock())));
        }
        check(clock()<deadline,'model_result_arrived_after_call_deadline');
        const response=(await privateJson(responseFile,root)).value;
        check(response.schema==='office-terminal-spool-response-v1' && response.session_sha256===sessionSha &&
          response.step===next && response.frame_id===frame.frame_id,'spool_response_binding_changed');
        check(response.status==='normalized_current_frame_action_only','terminal_sample_failed_or_late_no_replay');
        const sampleRoot=path.join(spool,'samples.private',prefix+'.private');
        const result=await readRef(response.result_ref,path.join(sampleRoot,'result.private.json'));
        const action=await readRef(response.action_ref,path.join(sampleRoot,'action.private.json'));
        check(result.value.status==='normalized_current_frame_action_only' && result.value.action_sha256===sha(action.raw) &&
          result.value.native_admission_sha256===session.native_admission_sha256 &&
          result.value.frame_sha256===sha(frameRaw) && result.value.image_sha256===frame.screenshot_sha256 &&
          result.value.visible_instruction_sha256===session.visible_instruction_ref.sha256 &&
          result.value.sampling?.new_dispatch===true && result.value.sampling?.reused===false &&
          action.value.frame_id===frame.frame_id && action.value.step===next,
          'normalized_spool_action_receipt_changed');
        check(!stopped && clock()<deadline && clock()<frame.expires_at_ms,'spool_dispatch_deadline_exceeded');
        const dispatched=await bridge.dispatch(action.value);
        await publishPrivateNew(path.join(spool,'dispatches.private',prefix+'.private.json'),{
          schema:'office-terminal-spool-dispatch-v1',step:next,frame_id:frame.frame_id,
          action_sha256:sha(action.raw),status:dispatched.status,code:dispatched.code??null,
          native_model_qualification:false,independent_saved_state_verified:false,official_final_credit:0});
        if(dispatched.status==='stopped'){await stop('model_finish');return dispatched;}
        check(dispatched.status==='applied','native_dispatch_result_invalid');
        next++;memory=action.value.memory;previous={status:'applied',code:'ok'};
        check(clock()<started+maxCallMs,'native_dispatch_completed_after_call_deadline');
        if(next===session.max_steps)await stop('max_steps_reached');
        return {...dispatched,step:frame.step,official_final_credit:0};
      } catch(e) {
        await poison(e.code||e.message||'terminal_spool_error');
        await stop(observed?'frame_failed_no_replay':'startup_failed_no_replay');
        throw e;
      } finally {busy=false;}
    },
  });
}
