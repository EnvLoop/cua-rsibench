/* Evaluator-owned, tab-bound CUA dispatcher. No provider/model/API calls.
 * Native entry requires separate accepted control and source-review receipts.
 * Offline fixtures exercise the same action gates without controlling a UI.
 */
import {createHash, randomBytes} from 'node:crypto';
import * as fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {fileURLToPath} from 'node:url';
import {execFile} from 'node:child_process';

const HEX = /^[a-f0-9]{64}$/;
const COMMON = ['version','task_id','task_binding_sha256','step','frame_id','type','memory'];
const KEY = Object.freeze({
  Enter:'Return', Escape:'Escape', Backspace:'BackSpace', Delete:'Delete', Space:'space',
  ArrowUp:'Up', ArrowDown:'Down', ArrowLeft:'Left', ArrowRight:'Right',
  Home:'Home', End:'End', 'Shift+End':'shift+End', 'Control+A':'super+a', 'Meta+A':'super+a',
});
const digest = data => createHash('sha256').update(data).digest('hex');
const canonical = value => Array.isArray(value) ? value.map(canonical) :
  value && typeof value==='object' ? Object.fromEntries(Object.keys(value).sort().map(k=>[k,canonical(value[k])])) : value;
export const bindingDigest = binding => digest(JSON.stringify(canonical(binding)));

export function imageBounds(data) {
  const bytes=Buffer.from(data);
  require(bytes.length>32 && bytes.length<=10_000_000, 'invalid_cropped_image');
  if (bytes.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10]))) {
    require(bytes.toString('ascii',12,16)==='IHDR', 'invalid_cropped_image');
    return {width:bytes.readUInt32BE(16),height:bytes.readUInt32BE(20)};
  }
  if (bytes[0]===255 && bytes[1]===216) {
    let p=2;
    while (p+4<bytes.length) {
      require(bytes[p]===255, 'invalid_cropped_image');
      while (bytes[p]===255) p++;
      const marker=bytes[p++];
      if (marker===217 || marker===218) break;
      if (marker===1 || (marker>=208 && marker<=215)) continue;
      require(p+2<bytes.length, 'invalid_cropped_image');
      const len=bytes.readUInt16BE(p);
      require(len>=2 && p+len<=bytes.length, 'invalid_cropped_image');
      if ([192,193,194].includes(marker)) {
        require(len>=8, 'invalid_cropped_image');
        return {width:bytes.readUInt16BE(p+5),height:bytes.readUInt16BE(p+3)};
      }
      p+=len;
    }
  }
  throw new BridgeError('invalid_cropped_image');
}
const require = (ok, code) => {if (!ok) throw new BridgeError(code);};
const exact = (obj, keys) => obj && typeof obj === 'object' && !Array.isArray(obj) &&
  Object.keys(obj).sort().join('|') === [...keys].sort().join('|');
const integer = n => Number.isSafeInteger(n);

export class BridgeError extends Error {constructor(code) {super(code);this.code=code;}}

export function documentIdentity(raw) {
  let u;
  try {u=new URL(raw);} catch {throw new BridgeError('invalid_document_url');}
  require(u.protocol==='https:' && u.hostname==='onedrive.live.com' && !u.username && !u.password &&
    /^\/personal\/[a-f0-9]{16}\/_layouts\/15\/Doc\.aspx$/i.test(u.pathname), 'invalid_document_url');
  const file=u.searchParams.getAll('file'), doc=u.searchParams.getAll('sourcedoc');
  require(file.length===1 && doc.length===1 && /^EL-PPT-Train-[^/\\]{1,120}\.pptx$/.test(file[0]) &&
    !/gold|answer|reference|selection|final/i.test(file[0]) &&
    /^\{[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\}$/i.test(doc[0]) &&
    u.searchParams.getAll('action').length===1 && u.searchParams.get('action')==='edit', 'invalid_document_identity');
  return digest(`${u.origin}${u.pathname.toLowerCase()}|${doc[0].toLowerCase()}|${file[0]}`);
}

export function accountIdentity(raw) {
  documentIdentity(raw);
  return digest('onedrive-personal:'+new URL(raw).pathname.split('/')[2].toLowerCase());
}

function bindingCheck(b, now) {
  require(exact(b,['schema','mode','cell','split','scope','tab_id','edit_url','account_principal_sha256',
    'task_id','task_binding_sha256','max_steps','expires_at_ms','frame_ttl_ms','clip','safe_regions']), 'invalid_binding');
  require(b.schema==='office-local-browser-train-binding-v1' && b.cell==='powerpoint-web' && b.split==='train' &&
    b.scope==='existing_account_dedicated_disposable_folder' &&
    ['offline_fixture','native_development'].includes(b.mode) && typeof b.tab_id==='string' &&
    /^ppt-wdi-transfer-[a-f0-9]{16}$/.test(b.task_id) && HEX.test(b.account_principal_sha256) &&
    HEX.test(b.task_binding_sha256) && integer(b.max_steps) && b.max_steps>=1 && b.max_steps<=120 &&
    integer(b.expires_at_ms) && b.expires_at_ms>now && b.expires_at_ms<=now+900_000 &&
    integer(b.frame_ttl_ms) && b.frame_ttl_ms>=1000 && b.frame_ttl_ms<=150_000, 'invalid_train_lease');
  documentIdentity(b.edit_url);
  require(b.account_principal_sha256===accountIdentity(b.edit_url), 'account_document_binding_mismatch');
  require(exact(b.clip,['x','y','width','height']) && Object.values(b.clip).every(integer) &&
    b.clip.x===0 && b.clip.y>=126 && b.clip.width>=640 && b.clip.width<=2560 &&
    b.clip.height>=400 && b.clip.height<=1600, 'unsafe_model_crop');
  require(Array.isArray(b.safe_regions) && b.safe_regions.length>=1 && b.safe_regions.length<=4, 'invalid_safe_regions');
  for (const r of b.safe_regions) require(exact(r,['x','y','width','height']) && Object.values(r).every(integer) &&
    r.x>=0 && r.y>=0 && r.width>0 && r.height>0 && r.x+r.width<=b.clip.width &&
    r.y+r.height<=b.clip.height, 'invalid_safe_region');
}

async function privateJson(ref, root) {
  require(exact(ref,['path','sha256']) && typeof ref.path==='string' && !path.isAbsolute(ref.path) &&
    HEX.test(ref.sha256), 'private_admission_reference_invalid');
  const target=path.resolve(root,ref.path), real=await fs.realpath(target);
  require(real===target && target.startsWith(root+path.sep), 'private_admission_path_invalid');
  const stat=await fs.lstat(target);
  require(stat.isFile() && (stat.mode & 0o077)===0 && stat.size<=2_000_000, 'private_admission_file_invalid');
  const raw=await fs.readFile(target);
  require(digest(raw)===ref.sha256, 'private_admission_hash_changed');
  return JSON.parse(raw);
}

async function nativeAdmission(b, admission, root) {
  require(exact(admission,['control_ref','source_review_ref']), 'native_admission_missing');
  const control=await privateJson(admission.control_ref,root);
  const review=await privateJson(admission.source_review_ref,root);
  require(control.schema==='cua-office-single-account-train-audit-v1' &&
    ['passed_manual_train_development_control','passed_manual_folder_train_development_control'].includes(control.status) &&
    control.cell_id==='powerpoint-web' && control.task_id===b.task_id &&
    control.package_sha256===b.task_binding_sha256 && control.independent_scorer_executed===true &&
    control.original_software_gui_operator_reviewed===true && control.dedicated_folder_empty_after_cleanup===true &&
    control.download_count===6 && control.folder_inventory_count===4 && HEX.test(control.before_sha256) &&
    control.model_calls===0 && control.official_final_credit===0 && control.selection_or_final_admitted===false,
    'native_control_not_accepted');
  require(review.schema==='office-local-browser-bridge-source-review-v1' &&
    review.status==='approved_train_development_only' && review.control_receipt_sha256===admission.control_ref.sha256 &&
    review.bridge_source_sha256===digest(await fs.readFile(fileURLToPath(import.meta.url))) &&
    review.action_adapter_source_sha256===digest(await fs.readFile(fileURLToPath(new URL('./office_local_browser_train_action_adapter_v1.py',import.meta.url)))) &&
    review.sampler_source_sha256===digest(await fs.readFile(fileURLToPath(new URL('./office_local_browser_qwen_base_sampler_v1.py',import.meta.url)))) &&
    HEX.test(review.visible_instruction_sha256) &&
    review.binding_sha256===bindingDigest(b) && review.actor_before_sha256===control.before_sha256 &&
    review.account_principal_sha256===b.account_principal_sha256 &&
    review.live_development_authorized===true && review.actor_no_external_links_verified===true &&
    review.official_final_credit===0 && review.selection_or_final_eligible===false, 'native_source_review_not_accepted');
  return {schema:'office-local-browser-native-sampler-admission-v1',
    mode:b.mode,cell:b.cell,split:b.split,task_id:b.task_id,
    task_binding_sha256:b.task_binding_sha256,account_principal_sha256:b.account_principal_sha256,
    control_receipt_sha256:admission.control_ref.sha256,source_review_sha256:admission.source_review_ref.sha256,
    bridge_source_sha256:review.bridge_source_sha256,
    action_adapter_source_sha256:review.action_adapter_source_sha256,
    sampler_source_sha256:review.sampler_source_sha256,
    visible_instruction_sha256:review.visible_instruction_sha256,max_steps:b.max_steps,
    binding_sha256:bindingDigest(b),actor_before_sha256:control.before_sha256,
    selection_or_final_eligible:false,official_final_credit:0};
}

async function writeNew(target,data) {
  const handle=await fs.open(target,'wx',0o600);
  try {await handle.writeFile(data);await handle.sync();} finally {await handle.close();}
}

export async function createOfficeLocalTrainBridge({tab,binding,artifactRoot,listDocumentTabIds,
                                                   admission=null,clock=Date.now}) {
  const b=structuredClone(binding);
  bindingCheck(b,clock());
  require(tab && tab.id===b.tab_id && typeof listDocumentTabIds==='function', 'bound_tab_missing');
  const root=await fs.realpath(artifactRoot);
  const rootStat=await fs.stat(root);
  require(rootStat.isDirectory() && (rootStat.mode & 0o077)===0, 'private_artifact_root_missing');
  let nativePermit=null;
  if (b.mode==='offline_fixture') require(tab.offlineFixture===true, 'offline_fixture_cannot_control_native_tab');
  else nativePermit=await nativeAdmission(b,admission,root);
  // Native leases use one host/user store, independent of task checkout or
  // artifact directory. Separate output folders cannot bypass serialization.
  const leaseRoot=b.mode==='native_development' ? path.join(await fs.realpath(os.tmpdir()),
    'envloop-office-account-leases-v1.private') : path.join(root,'leases.private');
  await fs.mkdir(leaseRoot,{recursive:true,mode:0o700});
  const leaseStat=await fs.lstat(leaseRoot);
  require(leaseStat.isDirectory() && !leaseStat.isSymbolicLink() && (leaseStat.mode & 0o077)===0 &&
    (typeof process.getuid!=='function' || leaseStat.uid===process.getuid()), 'private_account_lease_store_invalid');
  const leasePath=path.join(leaseRoot,`account-${b.account_principal_sha256}.lease.private.json`);
  const token=randomBytes(16).toString('hex');
  let lease;
  try {lease=await fs.open(leasePath,'wx',0o600);} catch (e) {
    if (e.code==='EEXIST') throw new BridgeError('account_already_leased');
    throw e;
  }
  await lease.writeFile(JSON.stringify({token,expires_at_ms:b.expires_at_ms}));
  await lease.close();
  let stopped=false, identified=false, quarantined=false, released=false, busy=false, step=0, observations=0, frame=null;
  const identity=documentIdentity(b.edit_url);
  const journal=[];
  let terminalWritten=false;
  const framesRoot=path.join(root,'frames.private'),actionsRoot=path.join(root,'actions.private');
  try {
    await fs.mkdir(framesRoot,{mode:0o700});await fs.mkdir(actionsRoot,{mode:0o700});
    if (nativePermit) await writeNew(path.join(root,'native-admission.private.json'),JSON.stringify(nativePermit));
  } catch (e) {await fs.unlink(leasePath);throw e;}

  async function state(afterAction=false) {
    require(!stopped && !quarantined && clock()<b.expires_at_ms &&
      (afterAction ? step<=b.max_steps : step<b.max_steps), 'lease_or_step_expired');
    try {
    const currentLease=JSON.parse(await fs.readFile(leasePath,'utf8'));
    require(currentLease.token===token && currentLease.expires_at_ms===b.expires_at_ms, 'account_lease_owner_changed');
    const ids=await listDocumentTabIds();
    require(Array.isArray(ids) && ids.length===1 && ids[0]===b.tab_id, 'parallel_or_wrong_document_session');
    require(documentIdentity(await tab.url())===identity, 'document_navigation_mismatch');
    identified=true;
    const ax=await tab.getAXState({disableDiffing:true,emit:false});
    require(ax.includes('Document Contents') && ax.includes('Office on the web Frame') &&
      /Mode Menu;Editing Selected/.test(ax) &&
      !/(?:^|\n)\s*\d+ (?:dialog|sheet)\b|(?:pop up button|button) \(expanded\)[^\n]*(?:Description: )?(?:Share|File|App launcher|Account manager)/i.test(ax),
      'unsafe_document_surface');
      return ax;
    } catch (e) {quarantined=true;throw e;}
  }
  const capture=async () => {
    const bytes=Buffer.from(await tab.screenshot({clip:b.clip}));
    const bounds=imageBounds(bytes);
    require(bounds.width===b.clip.width && bounds.height===b.clip.height, 'browser_crop_not_enforced');
    return bytes;
  };
  const safePoint = p => {
    require(exact(p,['x','y']) && integer(p.x) && integer(p.y) &&
      b.safe_regions.some(r=>p.x>=r.x && p.y>=r.y && p.x<r.x+r.width && p.y<r.y+r.height), 'unsafe_click_region');
    return [p.x+b.clip.x,p.y+b.clip.y];
  };
  const editor = ax => /^The focused UI element is [^\n]*Description: Editing Area/.test(ax.trim().split('\n').at(-1));
  const locked = async fn => {
    require(!busy, 'concurrent_bridge_operation');
    busy=true;
    try {return await fn();} finally {busy=false;}
  };
  async function stop() {
    if (released) return {status:'stopped',scope:b.scope,native_model_qualification:false,official_final_credit:0};
    stopped=true;frame=null;
    const raw=JSON.parse(await fs.readFile(leasePath,'utf8'));
    require(raw.token===token, 'account_lease_owner_changed');
    if (b.mode==='native_development' && identified) await tab.close();
    if (!terminalWritten) {
      await writeNew(path.join(root,'execution.private.json'),JSON.stringify({
        schema:'office-local-browser-bridge-execution-v1',status:quarantined?'quarantined':'stopped',
        mode:b.mode,actions:journal,frame_observation_count:observations,
        native_model_qualification:false,independent_saved_state_verified:false,
        fresh_reset_verified:false,selection_or_final_eligible:false,official_final_credit:0}));
      terminalWritten=true;
    }
    await fs.unlink(leasePath);
    released=true;
    return {status:'stopped',scope:b.scope,native_model_qualification:false,official_final_credit:0};
  }
  try {await state();} catch (e) {await stop();throw e;}

  return Object.freeze({
    observe:()=>locked(async()=>{
      await state();
      require(observations<b.max_steps, 'observation_limit_exceeded');
      const bytes=await capture();
      observations++;
      frame={id:randomBytes(16).toString('hex'),sha256:digest(bytes),expires:Math.min(clock()+b.frame_ttl_ms,b.expires_at_ms),step};
      const imagePath=path.join(framesRoot,`${String(observations).padStart(3,'0')}-${frame.id}.png`);
      await writeNew(imagePath,bytes);
      // Only screenshot bytes and binding/frame metadata cross into the model
      // observation builder. Raw AX, URL, account, filenames and receipt data
      // remain evaluator-private. Existing Python v0.6.6 validates image/action.
      const captured={screenshot_sha256:frame.sha256,frame_id:frame.id,
        schema:'office-local-browser-frame-v1',
        screenshot_ref:{path:path.relative(path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../work'),imagePath),sha256:frame.sha256},
        step,task_id:b.task_id,task_binding_sha256:b.task_binding_sha256,
        width:b.clip.width,height:b.clip.height,expires_at_ms:frame.expires,
        local_profile:{action_types:['click','double_click','type','key','scroll','finish'],
          type_mode:'insert',editor_focus_required:true,
          keys:Object.keys(KEY).filter(k=>!['Control+A','Meta+A'].includes(k)),
          actor_navigation_and_exports:false,safe_regions:structuredClone(b.safe_regions)}};
      await writeNew(path.join(framesRoot,`${String(observations).padStart(3,'0')}-${frame.id}.frame.private.json`),JSON.stringify(captured));
      return {...captured,screenshot_bytes:bytes};
    }),
    dispatch:action=>locked(async()=>{
      let ax=await state();
      require(frame && clock()<frame.expires, 'expired_frame');
      const kind=action?.type;
      const extras={click:['target'],double_click:['target'],type:['text','mode'],key:['key'],scroll:['dx','dy','target'],finish:[]};
      require(extras[kind], 'unsupported_local_action');
      const keys=[...COMMON,...extras[kind]];
      if (kind==='type' && action.target) keys.push('target');
      if (kind==='key' && action.target) keys.push('target');
      require(exact(action,keys) && action.version==='scale-computer-use-v0.6' &&
        action.task_id===b.task_id && action.task_binding_sha256===b.task_binding_sha256 &&
        action.step===frame.step && action.frame_id===frame.id && typeof action.memory==='string' &&
        Buffer.byteLength(action.memory)<=2048, 'action_binding_or_schema_invalid');
      require(digest(await capture())===frame.sha256, 'stale_frame');
      const row={step,action_type:kind,action_sha256:digest(JSON.stringify(action)),phase:'intent',gui_attempted:false};
      journal.push(row);
      const prefix=path.join(actionsRoot,String(step).padStart(3,'0'));
      await writeNew(prefix+'-intent.private.json',JSON.stringify(row));
      try {
      if (kind==='click' || kind==='double_click') {
        const p=safePoint(action.target);row.gui_attempted=true;
        await tab.click(p,{clickCount:kind==='double_click'?2:1});
      } else if (kind==='type') {
        require(action.mode==='insert' && typeof action.text==='string' && action.text.length>0 &&
          Buffer.byteLength(action.text)<=2000 && !/https?:\/\/|www\.|mailto:|file:|javascript:/i.test(action.text), 'unsafe_text_action');
        if (action.target) {const p=safePoint(action.target);row.gui_attempted=true;await tab.click(p);ax=await state();}
        require(editor(ax), 'text_editor_focus_unverified');
        row.gui_attempted=true;
        await tab.paste(null,action.text,{format:'text'});
      } else if (kind==='key') {
        require(Object.hasOwn(KEY,action.key), 'unsafe_key_chord');
        if (action.target) {const p=safePoint(action.target);row.gui_attempted=true;await tab.click(p);ax=await state();}
        require(action.key==='Escape' || editor(ax), 'key_editor_focus_unverified');
        // Table fills must use a reviewed cell-range selection, never Cmd+A.
        require(!['Control+A','Meta+A'].includes(action.key), 'whole_editor_selection_not_enabled');
        row.gui_attempted=true;await tab.pressKey(null,KEY[action.key]);
      } else if (kind==='scroll') {
        require(action.dx===0 && integer(action.dy) && action.dy!==0 && Math.abs(action.dy)<=720,
          'unsafe_scroll');
        const p=safePoint(action.target);row.gui_attempted=true;
        await tab.scroll(p,action.dy>0?'down':'up',Math.max(1,Math.ceil(Math.abs(action.dy)/120)));
      } else {
        row.phase='finished';
        await writeNew(prefix+'-terminal.private.json',JSON.stringify(row));
        return await stop();
      }
      frame=null;
      step++;
      await state(true); // No screenshot/model observation after a navigation mismatch.
      const result={status:'applied',code:'ok'};
      row.phase='applied';
      await writeNew(prefix+'-terminal.private.json',JSON.stringify(row));
      return result;
      } catch (e) {
        quarantined=true;
        row.phase='failed';row.error_code=e instanceof BridgeError?e.code:'gui_driver_error';
        row.error_sha256=digest(String(e));
        await writeNew(prefix+'-terminal.private.json',JSON.stringify(row));throw e;
      }
    }),
    stop:()=>locked(stop),
    receipt:()=>({schema:'office-local-browser-bridge-execution-v1',status:stopped?'stopped':quarantined?'quarantined':'active',
      mode:b.mode,actions:structuredClone(journal),native_model_qualification:false,
      frame_observation_count:observations,
      independent_saved_state_verified:false,fresh_reset_verified:false,
      selection_or_final_eligible:false,official_final_credit:0}),
  });
}

export async function runOfficeLocalTrainEpisode(options,{sampleCurrentFrame}) {
  // The evaluator supplies its already authorized, ledger-backed sampler and
  // v0.6.6 normalizer callback. This module has no credentials/provider client.
  require(typeof sampleCurrentFrame==='function', 'current_frame_sampler_missing');
  const bridge=await createOfficeLocalTrainBridge(options);
  let samples=0;
  try {
    for (let n=0;n<options.binding.max_steps;n++) {
      const frame=await bridge.observe();
      samples++;
      const action=await sampleCurrentFrame(frame);
      const result=await bridge.dispatch(action);
      if (result.status==='stopped') return {...bridge.receipt(),sample_callback_count:samples};
    }
    throw new BridgeError('episode_finished_without_finish_action');
  } finally {await bridge.stop();}
}

export async function createOfficeLocalQwenBaseFrameSampler({python,repoRoot,artifactRoot,
                                                            visibleInstructionPath}) {
  // Evaluator-owned subprocess transport. The model sees only the verified
  // crop and visible instruction; browser/account capabilities stay here.
  const repo=await fs.realpath(repoRoot),root=await fs.realpath(artifactRoot);
  require(root.startsWith(path.join(repo,'work')+path.sep) &&
    python===path.join(repo,'work/qwen38-training-runtime/.venv/bin/python'),
    'local_sampler_requires_root_owned_runtime');
  const instruction=await fs.realpath(visibleInstructionPath);
  require(instruction.startsWith(path.join(repo,'work')+path.sep), 'private_instruction_required');
  const samples=path.join(root,'samples.private');
  await fs.mkdir(samples,{mode:0o700});
  let previous=null,memory='';
  return async frame=>{
    const prefix=String(frame.step).padStart(3,'0');
    const launch=path.join(samples,`dispatch-${prefix}.private`),out=path.join(samples,`sample-${prefix}.private`);
    await fs.mkdir(launch,{mode:0o700});
    const context=path.join(launch,'context.private.json');
    await writeNew(context,JSON.stringify({memory,previous_action_result:previous}));
    const image=path.resolve(repo,'work',frame.screenshot_ref.path);
    require(image.startsWith(path.join(root,'frames.private')+path.sep) &&
      digest(await fs.readFile(image))===frame.screenshot_sha256, 'local_sampler_frame_file_changed');
    const framePath=image.replace(/\.png$/,'.frame.private.json');
    const args=['-m','tools.office_local_browser_qwen_base_sampler_v1',
      '--admission',path.join(root,'native-admission.private.json'),
      '--frame',framePath,'--visible-instruction',instruction,'--context',context,
      '--out',out,'--run'];
    await writeNew(path.join(launch,'launch-intent.private.json'),JSON.stringify({
      schema:'office-local-qwen-frame-launch-v1',step:frame.step,frame_id:frame.frame_id,
      frame_sha256:digest(await fs.readFile(framePath)),single_dispatch_only:true,
      model:'Qwen/Qwen3.8-27B',official_final_credit:0}));
    const env={...process.env,PYTHONPATH:`${repo}:${path.join(repo,'src')}`,PYTHONNOUSERSITE:'1',
      HF_HUB_OFFLINE:'1',TRANSFORMERS_OFFLINE:'1'};
    for (const key of ['OPENAI_API_KEY','ANTHROPIC_API_KEY','E2B_API_KEY','HF_TOKEN','HUGGING_FACE_HUB_TOKEN']) delete env[key];
    const completed=await new Promise(resolve=>{
      const child=execFile(python,args,{cwd:repo,env,timeout:150_000,maxBuffer:2_000_000},
        (error,stdout,stderr)=>resolve({error,stdout,stderr,pid:child.pid}));
    });
    await writeNew(path.join(launch,'stdout.private.log'),completed.stdout||'');
    await writeNew(path.join(launch,'stderr.private.log'),completed.stderr||'');
    await writeNew(path.join(launch,'worker-terminal.private.json'),JSON.stringify({
      pid:completed.pid,exit_code:completed.error?completed.error.code:0,
      signal:completed.error?.signal||null,
      status:completed.error?'failed_or_uncertain_no_replay':'completed',
      stdout_sha256:digest(completed.stdout||''),stderr_sha256:digest(completed.stderr||'')}));
    require(!completed.error,'local_sampler_worker_failed_no_replay');
    const receipt=JSON.parse(await fs.readFile(path.join(out,'result.private.json')));
    const raw=await fs.readFile(path.join(out,'action.private.json'));
    require(receipt.status==='normalized_current_frame_action_only' &&
      digest(raw)===receipt.action_sha256, 'local_sampler_action_receipt_changed');
    const action=JSON.parse(raw);memory=action.memory;previous={status:'applied',code:'ok'};
    return action;
  };
}
