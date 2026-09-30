import test from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {deflateSync} from 'node:zlib';
import {execFileSync} from 'node:child_process';
import {createOfficeLocalTrainBridge,runOfficeLocalTrainEpisode,documentIdentity,accountIdentity,bindingDigest,imageBounds} from '../tools/office_local_browser_train_bridge_v1.mjs';

const hash=x=>createHash('sha256').update(x).digest('hex');
const edit='https://onedrive.live.com/personal/1234567890abcdef/_layouts/15/Doc.aspx?sourcedoc=%7B00000000-0000-0000-0000-000000000001%7D&file=EL-PPT-Train-Fixture.pptx&action=edit';
const ax='0 container Office on the web Frame\n1 container Document Contents\n2 pop up button (collapsed) Description: Mode Menu;Editing Selected\n3 text Zoom level. Click to open the Zoom dialog box.\nThe focused UI element is 4 container Description: Editing Area';

function png(width=1920,height=750,color=0) {
  const crc=data=>{
    let v=0xffffffff;
    for (const b of data) {v^=b;for(let k=0;k<8;k++) v=(v>>>1)^((v&1)?0xedb88320:0);}
    return (v^0xffffffff)>>>0;
  };
  const chunk=(name,data)=>{const type=Buffer.from(name),len=Buffer.alloc(4),sum=Buffer.alloc(4);
    len.writeUInt32BE(data.length);sum.writeUInt32BE(crc(Buffer.concat([type,data])));
    return Buffer.concat([len,type,data,sum]);};
  const ihdr=Buffer.alloc(13);ihdr.writeUInt32BE(width);ihdr.writeUInt32BE(height,4);ihdr[8]=8;ihdr[9]=2;
  const pixels=Buffer.alloc((width*3+1)*height);pixels[1]=color;
  return Buffer.concat([Buffer.from([137,80,78,71,13,10,26,10]),chunk('IHDR',ihdr),chunk('IDAT',deflateSync(pixels)),chunk('IEND',Buffer.alloc(0))]);
}
const originalPixels=png(),changedPixels=png(1920,750,1);

async function fixture(t,changes={}) {
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'office-local-bridge-'));
  await fs.chmod(root,0o700);
  const f={root,now:100_000,ids:['fixture-tab'],pixels:originalPixels,ax,url:edit,calls:[]};
  const tab={id:'fixture-tab',offlineFixture:true,
    url:async()=>f.url,getAXState:async()=>f.ax,
    screenshot:async({clip})=>{f.crop=clip;return f.pixels;},
    click:async(p,opts)=>{f.calls.push(['click',p,opts]);if (f.navigateOnClick) f.url='https://onedrive.live.com/';},
    paste:async(index,text,opts)=>f.calls.push(['paste',index,text,opts]),
    pressKey:async(index,key)=>f.calls.push(['key',index,key]),
    scroll:async(p,d,n)=>f.calls.push(['scroll',p,d,n]),
    close:async()=>f.calls.push(['close']),
  };
  const binding={schema:'office-local-browser-train-binding-v1',mode:'offline_fixture',cell:'powerpoint-web',split:'train',
    scope:'existing_account_dedicated_disposable_folder',tab_id:tab.id,edit_url:edit,account_principal_sha256:accountIdentity(edit),
    task_id:'ppt-wdi-transfer-'+'b'.repeat(16),task_binding_sha256:'c'.repeat(64),max_steps:60,
    expires_at_ms:f.now+60_000,frame_ttl_ms:5000,clip:{x:0,y:126,width:1920,height:750},
    safe_regions:[{x:0,y:0,width:190,height:700},{x:255,y:0,width:1600,height:700}],...changes};
  f.tab=tab;f.binding=binding;
  f.options={tab,binding,artifactRoot:root,listDocumentTabIds:async()=>f.ids,clock:()=>f.now};
  t.after(async()=>{if(f.bridge) await f.bridge.stop();await fs.rm(root,{recursive:true,force:true});});
  return f;
}

const action=(f,frame,type,extra={})=>({version:'scale-computer-use-v0.6',task_id:f.binding.task_id,
  task_binding_sha256:f.binding.task_binding_sha256,step:frame.step,frame_id:frame.frame_id,type,memory:'',...extra});

async function admittedNativeFixture(f) {
  const control={schema:'cua-office-single-account-train-audit-v1',status:'passed_manual_folder_train_development_control',
    cell_id:'powerpoint-web',task_id:f.binding.task_id,package_sha256:f.binding.task_binding_sha256,
    independent_scorer_executed:true,original_software_gui_operator_reviewed:true,dedicated_folder_empty_after_cleanup:true,
    download_count:6,folder_inventory_count:4,
    before_sha256:'e'.repeat(64),model_calls:0,official_final_credit:0,selection_or_final_admitted:false};
  const controlRaw=JSON.stringify(control);await fs.writeFile(path.join(f.root,'control.json'),controlRaw,{mode:0o600});
  const bridgeFile=fileURLToPath(new URL('../tools/office_local_browser_train_bridge_v1.mjs',import.meta.url));
  const review={schema:'office-local-browser-bridge-source-review-v1',status:'approved_train_development_only',
    control_receipt_sha256:hash(controlRaw),bridge_source_sha256:hash(await fs.readFile(bridgeFile)),
    action_adapter_source_sha256:hash(await fs.readFile(fileURLToPath(new URL('../tools/office_local_browser_train_action_adapter_v1.py',import.meta.url)))),
    sampler_source_sha256:hash(await fs.readFile(fileURLToPath(new URL('../tools/office_local_browser_qwen_base_sampler_v1.py',import.meta.url)))),
    visible_instruction_sha256:hash('Repair fictional benchmark text.'),
    binding_sha256:bindingDigest(f.binding),actor_before_sha256:control.before_sha256,
    account_principal_sha256:f.binding.account_principal_sha256,live_development_authorized:true,
    actor_no_external_links_verified:true,official_final_credit:0,selection_or_final_eligible:false};
  const reviewRaw=JSON.stringify(review);await fs.writeFile(path.join(f.root,'review.json'),reviewRaw,{mode:0o600});
  f.options.admission={control_ref:{path:'control.json',sha256:hash(controlRaw)},source_review_ref:{path:'review.json',sha256:hash(reviewRaw)}};
  return control;
}

test('native lease and frame work without global process or a node:process import',async t=>{
  const f=await fixture(t,{mode:'native_development'});
  await admittedNativeFixture(f);
  assert.equal(os.userInfo().uid,process.getuid());
  const bridgeUrl=new URL('../tools/office_local_browser_train_bridge_v1.mjs',import.meta.url).href;
  const script=`
    import assert from 'node:assert/strict';
    import * as fs from 'node:fs/promises';
    import os from 'node:os';
    import path from 'node:path';
    import vm from 'node:vm';
    const bridgeUrl=${JSON.stringify(bridgeUrl)};
    const context=vm.createContext({Buffer,URL,structuredClone});
    assert.equal(vm.runInContext('typeof process',context),'undefined');
    const allowed=new Set(['node:crypto','node:fs/promises','node:path','node:os','node:url','node:child_process']);
    let restrictedImports=0;
    const module=new vm.SourceTextModule(await fs.readFile(new URL(bridgeUrl),'utf8'),{
      context,identifier:bridgeUrl,initializeImportMeta:meta=>{meta.url=bridgeUrl;},
      importModuleDynamically:async specifier=>{
        restrictedImports++;
        throw new Error('restricted_module_import:'+specifier);
      },
    });
    await module.link(async specifier=>{
      assert.ok(allowed.has(specifier),'static import is outside the native module allowlist');
      const real=await import(specifier);
      return new vm.SyntheticModule(Object.keys(real),function(){
        for(const name of Object.keys(real)) this.setExport(name,real[name]);
      },{context});
    });
    await module.evaluate();
    const binding=${JSON.stringify(f.binding)},admission=${JSON.stringify(f.options.admission)};
    const root=${JSON.stringify(f.root)},calls=[];
    const tab={id:binding.tab_id,url:async()=>binding.edit_url,getAXState:async()=>${JSON.stringify(ax)},
      screenshot:async()=>Buffer.from(${JSON.stringify(f.pixels.toString('base64'))},'base64'),
      click:async()=>calls.push('click'),close:async()=>calls.push('close')};
    let bridge;
    try {
      bridge=await module.namespace.createOfficeLocalTrainBridge({tab,binding,artifactRoot:root,
        listDocumentTabIds:async()=>[tab.id],admission,clock:()=>100000});
      assert.equal(restrictedImports,0);
      const store=path.join(await fs.realpath(os.tmpdir()),'envloop-office-account-leases-v1.private');
      assert.equal((await fs.lstat(store)).uid,os.userInfo().uid);
      const frame=await bridge.observe();
      await bridge.dispatch({version:'scale-computer-use-v0.6',task_id:binding.task_id,
        task_binding_sha256:binding.task_binding_sha256,step:frame.step,frame_id:frame.frame_id,
        type:'click',memory:'',target:{x:1000,y:300}});
    } finally {if(bridge) await bridge.stop();}
    assert.deepEqual(calls,['click','close']);
    assert.equal(restrictedImports,0);
    await assert.rejects(module.namespace.createOfficeLocalQwenBaseFrameSampler({}),
      /restricted_module_import:node:process/);
    assert.equal(restrictedImports,1);
    assert.equal(vm.runInContext('typeof process',context),'undefined');
    console.log('restricted_module_context_fixture_passed');
  `;
  const result=execFileSync(process.execPath,['--experimental-vm-modules','--input-type=module','-e',script],{
    env:{PATH:process.env.PATH,TMPDIR:os.tmpdir()},encoding:'utf8',timeout:30000,
  });
  assert.equal(result.trim(),'restricted_module_context_fixture_passed');
});

test('current cropped frame dispatches bounded click and focused text; receipts contain hashes only',async t=>{
  const f=await fixture(t);f.bridge=await createOfficeLocalTrainBridge(f.options);
  let frame=await f.bridge.observe();
  assert.deepEqual(f.crop,f.binding.clip);
  assert.equal(frame.edit_url,undefined);assert.equal(frame.a11y_text,undefined);
  await f.bridge.dispatch(action(f,frame,'double_click',{target:{x:1000,y:300}}));
  frame=await f.bridge.observe();
  await f.bridge.dispatch(action(f,frame,'key',{key:'Home'}));
  frame=await f.bridge.observe();
  await f.bridge.dispatch(action(f,frame,'key',{key:'Shift+End'}));
  frame=await f.bridge.observe();
  await f.bridge.dispatch(action(f,frame,'type',{mode:'insert',text:'fictional benchmark repair'}));
  assert.deepEqual(f.calls[0],['click',[1000,426],{clickCount:2}]);
  assert.equal(f.calls.at(-1)[3].format,'text');
  assert.ok(!JSON.stringify(f.bridge.receipt()).includes('fictional benchmark repair'));
  assert.equal(f.bridge.receipt().native_model_qualification,false);
});

test('parallel account lease is refused; stopping releases only own lease',async t=>{
  const f=await fixture(t);f.bridge=await createOfficeLocalTrainBridge(f.options);
  await assert.rejects(createOfficeLocalTrainBridge(f.options),/account_already_leased/);
  await f.bridge.stop();await f.bridge.stop();
  await assert.rejects(createOfficeLocalTrainBridge(f.options),/EEXIST/);
  assert.equal((await fs.readdir(path.join(f.root,'leases.private'))).length,0);
});

test('duplicate same-document sessions and wrong tab fail before capture',async t=>{
  for (const kind of ['duplicate','wrong']) {
    const f=await fixture(t);f.ids=kind==='duplicate'?['fixture-tab','extra']:['different'];
    await assert.rejects(createOfficeLocalTrainBridge(f.options),/parallel_or_wrong_document_session/);
    assert.equal(f.crop,undefined);assert.deepEqual(f.calls,[]);
  }
});

test('wrong document URL, non-TRAIN and header-reaching crop fail closed',async t=>{
  const f=await fixture(t);f.url='https://onedrive.live.com/';
  await assert.rejects(createOfficeLocalTrainBridge(f.options));
  for (const bad of [{split:'final'},{cell:'excel-web'},{clip:{x:0,y:0,width:1920,height:750}}]) {
    const g=await fixture(t,bad);await assert.rejects(createOfficeLocalTrainBridge(g.options));
  }
});

test('expired lease and stale frame reject actions without GUI calls',async t=>{
  for (const kind of ['lease','frame','pixels']) {
    const f=await fixture(t);f.bridge=await createOfficeLocalTrainBridge(f.options);
    const frame=await f.bridge.observe();
    if (kind==='lease') f.now+=61_000;
    if (kind==='frame') f.now+=6000;
    if (kind==='pixels') f.pixels=changedPixels;
    await assert.rejects(f.bridge.dispatch(action(f,frame,'click',{target:{x:1000,y:300}})));
    assert.deepEqual(f.calls,[]);
  }
});

test('unsafe click region, extra schema fields, wrong task/frame are rejected',async t=>{
  const f=await fixture(t);f.bridge=await createOfficeLocalTrainBridge(f.options);
  const frame=await f.bridge.observe();
  const original=action(f,frame,'click',{target:{x:1000,y:300}});
  for (const bad of [{...original,target:{x:210,y:20}}, {...original,url:edit},
    {...original,task_binding_sha256:'d'.repeat(64)}, {...original,frame_id:'stale'},
    {...original,target:{ref:'selector'}}]) await assert.rejects(f.bridge.dispatch(bad));
  assert.deepEqual(f.calls,[]);
});

test('text insertion requires real last-line editor focus and plain bounded text',async t=>{
  for (const extra of [{mode:'fill',text:'x'},{mode:'insert',text:'https://unapproved.example/'},
    {mode:'insert',text:'x'.repeat(2001)}]) {
    const f=await fixture(t);f.bridge=await createOfficeLocalTrainBridge(f.options);
    const frame=await f.bridge.observe();
    await assert.rejects(f.bridge.dispatch(action(f,frame,'type',extra)));
    assert.deepEqual(f.calls,[]);
  }
  const f=await fixture(t);f.bridge=await createOfficeLocalTrainBridge(f.options);
  const frame=await f.bridge.observe();
  f.ax=ax+'\nThe focused UI element is 5 button Account manager';
  await assert.rejects(f.bridge.dispatch(action(f,frame,'type',{mode:'insert',text:'x'})),/text_editor_focus_unverified/);
  assert.deepEqual(f.calls,[]);
});

test('browser/OS chords, file search and whole-editor fill are unavailable',async t=>{
  const f=await fixture(t);f.bridge=await createOfficeLocalTrainBridge(f.options);
  const frame=await f.bridge.observe();
  for (const key of ['Meta+L','Control+O','Control+K','Control+F','Control+H','Control+A','Meta+A'])
    await assert.rejects(f.bridge.dispatch(action(f,frame,'key',{key})));
  assert.deepEqual(f.calls,[]);
});

test('navigation after action quarantines episode before another model screenshot',async t=>{
  const f=await fixture(t);f.bridge=await createOfficeLocalTrainBridge(f.options);
  const frame=await f.bridge.observe();f.navigateOnClick=true;
  await assert.rejects(f.bridge.dispatch(action(f,frame,'click',{target:{x:1000,y:300}})));
  assert.equal(f.bridge.receipt().status,'quarantined');
  assert.equal(f.bridge.receipt().actions[0].phase,'failed');
  assert.equal(f.bridge.receipt().actions[0].gui_attempted,true);
  f.url=edit;f.crop=null;
  await assert.rejects(f.bridge.observe());assert.equal(f.crop,null);
});

test('actual dialogs/account menus are rejected; help text saying dialog is harmless',async t=>{
  const f=await fixture(t);f.bridge=await createOfficeLocalTrainBridge(f.options);
  await f.bridge.observe();
  f.ax=ax.replace('0 container','0 dialog');
  await assert.rejects(f.bridge.observe(),/unsafe_document_surface/);
});

test('native entry refuses missing or failed primary control and cannot use fixture flag alone',async t=>{
  const f=await fixture(t,{mode:'native_development'});
  await assert.rejects(createOfficeLocalTrainBridge(f.options),/native_admission_missing/);
  f.binding.mode='offline_fixture';f.tab.offlineFixture=false;
  await assert.rejects(createOfficeLocalTrainBridge(f.options),/offline_fixture_cannot_control_native_tab/);
});

test('native receipt/source/binding gate runs and native stop closes bound tab before lease release',async t=>{
  const f=await fixture(t,{mode:'native_development'});
  await admittedNativeFixture(f);
  f.bridge=await createOfficeLocalTrainBridge(f.options);
  const frame=await f.bridge.observe();await f.bridge.dispatch(action(f,frame,'finish'));
  assert.deepEqual(f.calls,[['close']]);
  assert.equal(f.bridge.receipt().independent_saved_state_verified,false);
  assert.equal(f.bridge.receipt().selection_or_final_eligible,false);
  assert.equal(documentIdentity(edit+'&CT=123'),documentIdentity(edit));
});

test('native account serialization spans different artifact directories',async t=>{
  const f=await fixture(t,{mode:'native_development'}),g=await fixture(t,{mode:'native_development'});
  await admittedNativeFixture(f);await admittedNativeFixture(g);
  f.bridge=await createOfficeLocalTrainBridge(f.options);
  await assert.rejects(createOfficeLocalTrainBridge(g.options),/account_already_leased/);
});

test('crop bounds must actually match; full viewport cannot reach model observation',async t=>{
  const f=await fixture(t);f.bridge=await createOfficeLocalTrainBridge(f.options);
  f.pixels=png(1920,880);
  await assert.rejects(f.bridge.observe(),/browser_crop_not_enforced/);
  assert.deepEqual(imageBounds(originalPixels),{width:1920,height:750});
});

test('lease account is bound to the document account and review binds the safe-region map',async t=>{
  const f=await fixture(t,{account_principal_sha256:'a'.repeat(64)});
  await assert.rejects(createOfficeLocalTrainBridge(f.options),/account_document_binding_mismatch/);
  const g=await fixture(t,{mode:'native_development'});await admittedNativeFixture(g);
  g.binding.safe_regions=[{x:0,y:0,width:1920,height:750}];
  await assert.rejects(createOfficeLocalTrainBridge(g.options),/native_source_review_not_accepted/);
});

test('lease ownership is rechecked before every new frame',async t=>{
  const f=await fixture(t);f.bridge=await createOfficeLocalTrainBridge(f.options);
  const lease=path.join(f.root,'leases.private',`account-${f.binding.account_principal_sha256}.lease.private.json`);
  const raw=await fs.readFile(lease,'utf8');
  await fs.writeFile(lease,JSON.stringify({token:'changed',expires_at_ms:f.binding.expires_at_ms}));
  await assert.rejects(f.bridge.observe(),/account_lease_owner_changed/);
  await fs.writeFile(lease,raw);
});

test('one serialized episode samples once per frame and stops after finish',async t=>{
  const f=await fixture(t);
  let n=0;
  const receipt=await runOfficeLocalTrainEpisode(f.options,{sampleCurrentFrame:async frame=>{
    n++;return action(f,frame,n===1?'double_click':'finish',n===1?{target:{x:1000,y:300}}:{});
  }});
  assert.equal(receipt.sample_callback_count,2);
  assert.equal(receipt.actions.length,2);
  assert.equal(receipt.selection_or_final_eligible,false);
  assert.equal(receipt.native_model_qualification,false);
  assert.equal(receipt.status,'stopped');
  const terminal=JSON.parse(await fs.readFile(path.join(f.root,'execution.private.json')));
  assert.equal(terminal.actions.length,2);
  assert.equal((await fs.readdir(path.join(f.root,'actions.private'))).length,4);
  assert.equal((await fs.readdir(path.join(f.root,'frames.private'))).length,4);
});

test('GUI intent is durable before the side effect and terminal failure cannot be replayed',async t=>{
  const f=await fixture(t);f.bridge=await createOfficeLocalTrainBridge(f.options);
  const frame=await f.bridge.observe();
  f.tab.click=async()=>{
    const intent=JSON.parse(await fs.readFile(path.join(f.root,'actions.private/000-intent.private.json')));
    assert.equal(intent.phase,'intent');assert.equal(intent.gui_attempted,false);
    throw Error('synthetic driver failure');
  };
  await assert.rejects(f.bridge.dispatch(action(f,frame,'click',{target:{x:1000,y:300}})));
  const terminal=JSON.parse(await fs.readFile(path.join(f.root,'actions.private/000-terminal.private.json')));
  assert.equal(terminal.phase,'failed');assert.equal(terminal.gui_attempted,true);
  await assert.rejects(f.bridge.dispatch(action(f,frame,'click',{target:{x:1000,y:300}})),/lease_or_step_expired/);
});

test('pixel scroll actions become fractional native pages without rounding to six pages',async t=>{
  const f=await fixture(t);f.bridge=await createOfficeLocalTrainBridge(f.options);
  let frame=await f.bridge.observe();
  assert.equal(frame.local_profile.scroll_units,'cropped_screenshot_pixels');
  await f.bridge.dispatch(action(f,frame,'scroll',{dx:0,dy:120,target:{x:1000,y:300}}));
  assert.deepEqual(f.calls[0],['scroll',[1000,426],'down',120/750]);
  frame=await f.bridge.observe();
  await f.bridge.dispatch(action(f,frame,'scroll',{dx:0,dy:-720,target:{x:1000,y:300}}));
  assert.deepEqual(f.calls[1],['scroll',[1000,426],'up',720/750]);
});

test('native-save development control binds distinct policy and reviewed source hashes',async t=>{
  for (const valid of [true,false]) {
    const f=await fixture(t,{mode:'native_development'});
    const control=await admittedNativeFixture(f);
    Object.assign(control,{status:'passed_manual_folder_train_native_save_development_control',
      scoring_policy_id:'ppt-native-save-one-frozen-train-collection-v1',raw_strict_saved_score:0,
      one_collection_canonical_saved_score:1,exact_historical_collection_only:true,
      generic_student_verifier_qualified:false,registered:false,
      account_scope:'existing_account_dedicated_disposable_folder',dedicated_test_account_operator_asserted:false,
      native_save_policy_sha256:'a'.repeat(64),scoring_source_hashes:{}});
    for (const name of ['tools/office_ppt_native_save_collection_control_v1.py',
      'tools/office_single_account_train_pilot_v1.py','tools/ppt_native_train_collection_proposal_v1.py',
      'ppt_wdi_factory/verify.py','ppt_wdi_factory/plan.py','tools/audit_ppt_wdi_web_train_triad_v1.py'])
      control.scoring_source_hashes[name]=hash(await fs.readFile(fileURLToPath(new URL('../'+name,import.meta.url))));
    if (!valid) control.generic_student_verifier_qualified=true;
    const raw=JSON.stringify(control);await fs.writeFile(path.join(f.root,'control.json'),raw,{mode:0o600});
    f.options.admission.control_ref.sha256=hash(raw);
    const review=JSON.parse(await fs.readFile(path.join(f.root,'review.json')));
    review.control_receipt_sha256=hash(raw);review.native_save_policy_sha256=control.native_save_policy_sha256;
    const rr=JSON.stringify(review);await fs.writeFile(path.join(f.root,'review.json'),rr,{mode:0o600});
    f.options.admission.source_review_ref.sha256=hash(rr);
    if (valid) f.bridge=await createOfficeLocalTrainBridge(f.options);
    else await assert.rejects(createOfficeLocalTrainBridge(f.options),/native_save_development_policy_not_bound/);
  }
});

test('failed/proposal/fake controls cannot authorize native entry',async t=>{
  for (const status of ['collected_failed_control','passed_fake_test_control_only','proposal_only']) {
    const f=await fixture(t,{mode:'native_development'});const control=await admittedNativeFixture(f);
    control.status=status;const raw=JSON.stringify(control);
    await fs.writeFile(path.join(f.root,'control.json'),raw,{mode:0o600});
    f.options.admission.control_ref.sha256=hash(raw);
    await assert.rejects(createOfficeLocalTrainBridge(f.options),/native_control_not_accepted/);
    assert.deepEqual(f.calls,[]);
  }
});

test('existing Python v066 normalizer feeds the current cropped CUA dispatcher',
  {skip:!process.env.OFFICE_TEST_PYTHON},async t=>{
    const f=await fixture(t);f.bridge=await createOfficeLocalTrainBridge(f.options);
    const captured=await f.bridge.observe();
    const imagePath=path.join(f.root,'frame.png'),framePath=path.join(f.root,'frame.json');
    await fs.writeFile(imagePath,captured.screenshot_bytes,{mode:0o600});
    const frame={...captured,screenshot_ref:{path:'frame.png',sha256:captured.screenshot_sha256}};
    delete frame.screenshot_bytes;
    await fs.writeFile(framePath,JSON.stringify(frame),{mode:0o600});
    const python="import json,sys;from pathlib import Path;from tools.office_local_browser_train_action_adapter_v1 import normalize_local_action;f=json.loads(Path(sys.argv[1]).read_bytes());a=normalize_local_action(sys.argv[3],f,Path(sys.argv[2]).read_bytes(),'Repair fictional benchmark text.',current_frame_id=f['frame_id'],now_ms=f['expires_at_ms']-5000);print(json.dumps(a))";
    const normalized=JSON.parse(execFileSync(process.env.OFFICE_TEST_PYTHON,
      ['-c',python,framePath,imagePath,JSON.stringify({type:'double_click',target:{x:1000,y:300}})],
      {env:{...process.env,PYTHONPATH:'.:src'},encoding:'utf8'}));
    await f.bridge.dispatch(normalized);
    assert.equal(f.calls[0][0],'click');assert.equal(f.calls[0][2].clickCount,2);
  });
