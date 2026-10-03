/* Local fixture evidence only; no browser, cloud, or qualification calls. */
import test from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {createOfficeUiLifecycle,PARENT_SOURCE_SHA256,officeLifecycleV5SourceHashes} from '../tools/office_owned_folder_ui_lifecycle_v5.mjs';
import {createOfficeNativeExtractor} from '../tools/office_owned_folder_native_extractor_v3.mjs';
import {ooxmlFixture} from './office_ooxml_fixture_v4.mjs';
const sha=raw=>createHash('sha256').update(raw).digest('hex');

async function fixture(t,{native=true,transport=native?'native_picker':undefined}={}){
 const root=await fs.realpath(await fs.mkdtemp(path.join(os.tmpdir(),'office-native-lifecycle-v5-')));await fs.chmod(root,0o700);
 t.after(()=>fs.rm(root,{recursive:true,force:true}));const evidence=path.join(root,'evidence');await fs.mkdir(evidence,{mode:0o700});
 const baseline=path.join(root,'source.pptx');await fs.writeFile(baseline,ooxmlFixture('powerpoint-web'),{mode:0o600});
 const folder='https://onedrive.live.com/?id=fixture-child',parent='https://onedrive.live.com/?id=fixture-parent';
 const binding={tab_id:1,folder_url:folder,folder_url_sha256:sha(Buffer.from(folder)),account_principal_sha256:'a'.repeat(64),folder_scope_sha256:'b'.repeat(64),folder_clip:{x:0,y:126,width:1000,height:700}};
 const state={url:folder,rows:[],selected:false,editors:new Map(),nextTab:2,nextGuid:1,principal:binding.account_principal_sha256,callbackCalls:[],calls:[],beforeUpload:null,afterUpload:null,receiptChange:null,skipUpload:false,forcedGuid:null,ready:new Set(),asyncMenu:false,waitError:null,deleteToast:false,deleteMessage:'Deleted 1 item',afterDelete:null,afterReload:null,staleDeleteRow:false};
 const install=file=>{
  const guid=state.forcedGuid??state.nextGuid++;const token=String(guid).padStart(12,'0');
  const edit='https://onedrive.live.com/personal/0000000000000001/_layouts/15/Doc.aspx?sourcedoc=%7B00000000-0000-0000-0000-'+token+'%7D&file='+encodeURIComponent(path.basename(file))+'&action=edit';
  state.rows=[{name:path.basename(file),href:edit}];state.selected=false;
 };
 const node=(name,scope='folder')=>({count:async()=>state.asyncMenu&&name==='Open in browser'&&!state.ready.has(name)?0:1,isVisible:async()=>true,isEnabled:async()=>true,waitFor:async options=>{state.calls.push('wait:'+name+':'+options.state);if(state.waitError&&name==='Open in browser')throw state.waitError;if(name==='Deleted 1 item'&&!state.deleteToast)throw new Error('fixture native delete success unavailable');state.ready.add(name);},
  evaluate:async()=>name==='badge'?{text:String(state.rows.length),tag:'SPAN',folderLabel:'Yellow folder'}:name==='card-name'?'Isolated fixture':name==='#SaveStatusButton'?'Saved to OneDrive':name==='Deleted 1 item'?state.deleteMessage:null,
  evaluateAll:async()=>state.rows.map((row,row_index)=>({...row,row_index})),locator:selector=>node(selector,scope),nth:()=>node('row',scope),getByRole:(role,options)=>node(role==='checkbox'?'checkbox':options.name,scope),
  getAttribute:async attribute=>attribute==='aria-checked'?String(state.selected):null,
  click:async()=>{
   state.calls.push(scope+':'+name);
   if(name==='checkbox')state.selected=true;
   if(name==='Delete'){state.deleteToast=true;if(!state.staleDeleteRow)state.rows=[];if(state.afterDelete)await state.afterDelete();}
   if(name==='Open in browser'){
    const id=state.nextTab++,edit=state.rows[0].href;
    state.editors.set(id,{id,url:async()=>edit,close:async()=>state.editors.delete(id),playwright:{frameLocator:()=>({locator:selector=>node(selector,'editor'),getByRole:(role,options)=>node(options.name,'editor')}),locator:selector=>node(selector,'editor'),getByRole:(role,options)=>node(options.name,'editor')}});
   }
  }});
 const tab={id:1,url:async()=>state.url,goto:async url=>{state.url=url;state.calls.push('goto');},reload:async()=>{state.calls.push('reload');state.rows=[];if(state.afterReload)await state.afterReload();},screenshot:async()=>Buffer.from('local fixture image'),playwright:{locator:selector=>node(selector),getByRole:(role,options)=>node(options.name),getByText:text=>node(text),domSnapshot:async()=>JSON.stringify({rows:state.rows}),
  waitForEvent:async event=>{
   state.calls.push('event:'+event);
   if(event==='filechooser')return {isMultiple:()=>false,setFiles:async file=>{state.calls.push('setFiles');install(file);}};
   return {path:async()=>baseline};
  }}};
 const browser={tabs:{list:async()=>[{id:1,url:folder},...await Promise.all([...state.editors.values()].map(async tab=>({id:tab.id,url:await tab.url()})))],get:async id=>state.editors.get(id)}};
 const profile={schema:'office-owned-folder-native-ui-profile-v3',source_reviewed:true,upload_transport:transport,folder_heading:{role:'heading',name:'Isolated fixture'},item_rows_selector:'rows',name_cell_selector:'name',empty_state:{text:'This folder is empty'},
  folder_inventory_proof:{mode:'parent_card_count',parent_url:parent,parent_url_sha256:sha(Buffer.from(parent)),card_selector:'card',name_selector:'card-name',count_selector:'badge'},signed_in_principal:{folder:{},editor:{}},
  upload_steps:[{role:'button',name:'Create or upload'},{role:'menuitem',name:'Files upload'}],open_steps:[{role:'menuitem',name:'Open'},{role:'menuitem',name:'Open in browser'}],editor_frame_selector:'iframe',editor_ready:{selector:'#ModeSwitcher'},saved_status:{selector:'#SaveStatusButton'},saved_status_expected:'Saved to OneDrive',download_surface:'folder_toolbar',download_steps:[{role:'menuitem',name:'Download'}],delete_steps:[{role:'button',name:'Delete'}],delete_success:{text:'Deleted 1 item'}};
 const nativeBaselineUploader=async args=>{
  state.callbackCalls.push(args);state.calls.push('native-callback');
  assert.equal((await fs.stat(args.evidenceRoot)).mode&0o777,0o700);
  if(state.beforeUpload)await state.beforeUpload(args);
  if(!state.skipUpload)install(args.filePath);
  if(state.afterUpload)await state.afterUpload(args);
  const receipt={schema:'office-evaluator-native-picker-v1',source_sha256:args.expectedSha256,native_picker_open_clicked:true,upload_server_state_verified:false,permission_changes:false,actor_api:false};
  return {...receipt,...state.receiptChange};
 };
 const principalObserver=async()=>{state.calls.push('principal');return {nativeUiObserved:true,principalSha256:state.principal};};
 const driver=await createOfficeUiLifecycle({folderTab:tab,browser,binding,profile,evidenceRoot:evidence,principalObserver,nativeBaselineUploader:native?nativeBaselineUploader:null});
 const task={task_id:'fixture-train',cell_id:'powerpoint-web',baseline_sha256:sha(await fs.readFile(baseline))};
 return {root,evidence,baseline,task,binding,profile,driver,state,tab};
}

test('native route uploads once, preserves verified double download, cleans, and creates distinct reset',async t=>{
 const f=await fixture(t);const first=await f.driver.createFromBaseline(f.binding,f.task,f.baseline,{purpose:'actor'});
 const downloaded=await f.driver.doubleDownload(f.binding,first.item,{purpose:'saved_actor'});
 assert.equal(downloaded.download_refs.length,2);assert.equal(f.state.calls.filter(x=>x==='event:download').length,2);
 await f.driver.closeDocument(f.binding,first.item);await f.driver.removeOwnedItem(f.binding,first.item);
 assert.deepEqual((await f.driver.folderInventory()).items,[]);
 const reset=await f.driver.createFromBaseline(f.binding,f.task,f.baseline,{purpose:'reset'});
 assert.notEqual(reset.item.item_identity_sha256,first.item.item_identity_sha256);
 await f.driver.doubleDownload(f.binding,reset.item,{purpose:'fresh_reset'});
 await f.driver.closeDocument(f.binding,reset.item);await f.driver.removeOwnedItem(f.binding,reset.item);
 assert.deepEqual((await f.driver.folderInventory()).items,[]);
 assert.equal(f.state.callbackCalls.length,2);assert.notEqual(f.state.callbackCalls[0].evidenceRoot,f.state.callbackCalls[1].evidenceRoot);
 assert.ok(!f.state.calls.includes('event:filechooser'));assert.ok(!f.state.calls.includes('setFiles'));
 const names=await fs.readdir(f.evidence);assert.equal(names.filter(x=>x.endsWith('-native-picker-before.private.json')).length,2);assert.equal(names.filter(x=>x.endsWith('-native-picker-after.private.json')).length,2);
});

test('declared original filechooser route remains functional without a native callback',async t=>{
 const f=await fixture(t,{native:false});await f.driver.createFromBaseline(f.binding,f.task,f.baseline,{purpose:'actor'});
 assert.equal(f.state.callbackCalls.length,0);assert.equal(f.state.calls.filter(x=>x==='event:filechooser').length,1);assert.ok(f.state.calls.includes('setFiles'));
});

test('wrong account, changed hash, public baseline, or nonempty folder refuse before upload',async t=>{
 for(const kind of ['account','hash','permissions','nonempty']){
  await t.test(kind,async t=>{
   const f=await fixture(t);
   if(kind==='account')f.state.principal='c'.repeat(64);
   if(kind==='hash')await fs.writeFile(f.baseline,'altered fixture');
   if(kind==='permissions')await fs.chmod(f.baseline,0o644);
   if(kind==='nonempty')f.state.rows=[{name:'foreign.pptx',href:null}];
   await assert.rejects(f.driver.createFromBaseline(f.binding,f.task,f.baseline,{purpose:'actor'}));
   assert.equal(f.state.callbackCalls.length,0);assert.ok(!f.state.calls.includes('folder:Files upload'));
  });
 }
});

test('post-picker account, folder, tab, binding, or source change prevents a completed creation',async t=>{
 for(const kind of ['account','folder','tab','binding','source']){
  await t.test(kind,async t=>{
   const f=await fixture(t);f.state.afterUpload=async()=>{
    if(kind==='account')f.state.principal='c'.repeat(64);
    if(kind==='folder')f.state.url='https://onedrive.live.com/?id=foreign';
    if(kind==='tab')f.tab.id=99;
    if(kind==='binding')f.binding.account_principal_sha256='c'.repeat(64);
    if(kind==='source')await fs.writeFile(f.baseline,'altered fixture');
   };
   await assert.rejects(f.driver.createFromBaseline(f.binding,f.task,f.baseline,{purpose:'actor'}));
   assert.equal(f.state.callbackCalls.length,1);assert.ok(!f.state.calls.includes('event:filechooser'));assert.ok(!f.state.calls.includes('folder:Open in browser'));
   assert.ok(!(await fs.readdir(f.evidence)).some(name=>name.endsWith('.receipt.private.json')));
  });
 }
});

test('picker errors and invalid local receipts never trigger a fallback upload',async t=>{
 for(const kind of ['throw','hash','server','actor']){
  await t.test(kind,async t=>{
   const f=await fixture(t);
   if(kind==='throw')f.state.beforeUpload=async()=>{throw new Error('fixture picker result uncertain');};
   if(kind==='hash')f.state.receiptChange={source_sha256:'0'.repeat(64)};
   if(kind==='server')f.state.receiptChange={upload_server_state_verified:true};
   if(kind==='actor')f.state.receiptChange={actor_api:true};
   await assert.rejects(f.driver.createFromBaseline(f.binding,f.task,f.baseline,{purpose:'actor'}));
   assert.equal(f.state.callbackCalls.length,1);assert.ok(!f.state.calls.includes('event:filechooser'));assert.ok(!f.state.calls.includes('setFiles'));
  });
 }
});

test('a local picker click never proves a server upload',async t=>{
 const f=await fixture(t);f.state.skipUpload=true;
 await assert.rejects(f.driver.createFromBaseline(f.binding,f.task,f.baseline,{purpose:'actor'}),/uploaded_item_identity_unproved/);
 assert.equal(f.state.callbackCalls.length,1);assert.ok(!f.state.calls.includes('folder:Open in browser'));
});

test('reused cloud GUID is rejected after close/delete even when the baseline is renamed',async t=>{
 const f=await fixture(t);const first=await f.driver.createFromBaseline(f.binding,f.task,f.baseline,{purpose:'actor'});
 await f.driver.closeDocument(f.binding,first.item);await f.driver.removeOwnedItem(f.binding,first.item);
 const renamed=path.join(f.root,'renamed.pptx');await fs.copyFile(f.baseline,renamed);await fs.chmod(renamed,0o600);f.state.forcedGuid=1;
 await assert.rejects(f.driver.createFromBaseline(f.binding,f.task,renamed,{purpose:'reset'}),/created_document_identity_reused/);
 assert.equal(f.state.callbackCalls.length,2);
});

test('mismatched upload transport refuses construction before any upload operation',async t=>{
 await assert.rejects(fixture(t,{transport:'filechooser'}),/upload_transport_binding_changed/);
});

test('source map binds exactly lifecycle and picker; original V4 bytes stay immutable',async()=>{
 const values=await officeLifecycleV5SourceHashes();
 assert.deepEqual(Object.keys(values).sort(),['tools/office_native_picker_uploader_v1.mjs','tools/office_owned_folder_ui_lifecycle_v5.mjs']);
 for(const [name,digest] of Object.entries(values))assert.equal(sha(await fs.readFile(new URL('../'+name,import.meta.url))),digest);
 assert.equal(sha(await fs.readFile(new URL('../tools/office_owned_folder_ui_lifecycle_v4.mjs',import.meta.url))),PARENT_SOURCE_SHA256);
});

test('asynchronous native Open submenu is awaited before uniqueness and click',async t=>{
 const f=await fixture(t);f.state.asyncMenu=true;
 await f.driver.createFromBaseline(f.binding,f.task,f.baseline,{purpose:'actor'});
 assert.ok(f.state.calls.indexOf('wait:Open in browser:visible')<f.state.calls.indexOf('folder:Open in browser'));
 assert.equal(f.state.calls.filter(x=>x==='folder:Open in browser').length,1);
});

test('native readiness timeout propagates without clicking or retrying absent submenu',async t=>{
 const f=await fixture(t);const error=new Error('fixture native submenu wait timeout');f.state.waitError=error;
 await assert.rejects(f.driver.createFromBaseline(f.binding,f.task,f.baseline,{purpose:'actor'}),value=>value===error);
 assert.equal(f.state.calls.filter(x=>x==='folder:Open in browser').length,0);
 assert.equal(f.state.callbackCalls.length,1);
});

test('explicit successful deletion permits exactly one owned-folder reload before empty inventory proof',async t=>{
 const f=await fixture(t);const created=await f.driver.createFromBaseline(f.binding,f.task,f.baseline,{purpose:'actor'});
 await f.driver.closeDocument(f.binding,created.item);f.state.staleDeleteRow=true;
 const result=await f.driver.removeOwnedItem(f.binding,created.item);
 assert.equal(f.state.calls.filter(x=>x==='folder:Delete').length,1);assert.equal(f.state.calls.filter(x=>x==='reload').length,1);
 assert.ok(f.state.calls.indexOf('folder:Delete')<f.state.calls.indexOf('wait:Deleted 1 item:visible'));
 assert.ok(f.state.calls.indexOf('wait:Deleted 1 item:visible')<f.state.calls.indexOf('reload'));
 assert.equal(result.explicit_delete_success_observed,true);assert.equal(result.owned_folder_reloaded_after_success,true);assert.equal(result.delete_retry_performed,false);
 assert.deepEqual((await f.driver.folderInventory()).items,[]);
});

test('missing or wrong delete-success witness refuses without reload or duplicate delete',async t=>{
 for(const kind of ['missing','wrong text'])await t.test(kind,async t=>{
  const f=await fixture(t);const created=await f.driver.createFromBaseline(f.binding,f.task,f.baseline,{purpose:'actor'});
  await f.driver.closeDocument(f.binding,created.item);
  if(kind==='missing')f.state.afterDelete=async()=>{f.state.deleteToast=false;};else f.state.deleteMessage='Could not delete item';
  await assert.rejects(f.driver.removeOwnedItem(f.binding,created.item));
  assert.equal(f.state.calls.filter(x=>x==='folder:Delete').length,1);assert.equal(f.state.calls.filter(x=>x==='reload').length,0);
 });
});

test('delete requires declared exact success profile and documented reload capability before input',async t=>{
 for(const kind of ['profile','reload'])await t.test(kind,async t=>{
  const f=await fixture(t);const created=await f.driver.createFromBaseline(f.binding,f.task,f.baseline,{purpose:'actor'});
  await f.driver.closeDocument(f.binding,created.item);
  if(kind==='profile')f.profile.delete_success={text:'Deleted items'};else delete f.tab.reload;
  await assert.rejects(f.driver.removeOwnedItem(f.binding,created.item),/delete_success_and_reload_profile_required/);
  assert.equal(f.state.calls.filter(x=>x==='folder:Delete').length,0);
 });
});

test('foreign navigation before or after delete reload cannot complete owned cleanup',async t=>{
 for(const when of ['before','after'])await t.test(when,async t=>{
  const f=await fixture(t);const created=await f.driver.createFromBaseline(f.binding,f.task,f.baseline,{purpose:'actor'});
  await f.driver.closeDocument(f.binding,created.item);
  const change=async()=>{f.state.url='https://onedrive.live.com/?id=foreign';};
  if(when==='before')f.state.afterDelete=change;else f.state.afterReload=change;
  await assert.rejects(f.driver.removeOwnedItem(f.binding,created.item),/delete_folder_changed/);
  assert.equal(f.state.calls.filter(x=>x==='folder:Delete').length,1);assert.equal(f.state.calls.filter(x=>x==='reload').length,when==='before'?0:1);
 });
});

test('actual lifecycle receipt supplies unchanged Extractor3 membership identity in Host6 binding',async t=>{
 const f=await fixture(t);const created=await f.driver.createFromBaseline(f.binding,f.task,f.baseline,{purpose:'actor'});
 assert.equal(created.item_identity_sha256,created.item.item_identity_sha256);
 const clip={x:0,y:126,width:1440,height:874};let geometryCalls=0;
 const bound={...f.binding,...created.item,clip,window_sha256:'c'.repeat(64),signed_in_principal_profile:{open_steps:[]},owned_folder_item_ui_receipt:created,owned_folder_item_ui_receipt_sha256:sha(Buffer.from(JSON.stringify(created)))};
 const tab={url:async()=>created.item.edit_url,playwright:{locator:()=>({evaluate:async()=>{geometryCalls++;return {document_ready:'complete',targets:[],viewport:[clip.width,clip.height],focus_path:'fixture',modal_path:'',modal_safe:true,editor_surface_observed:true,editing_mode_observed:true,private_chrome_observed:true,private_chrome_outside_crop:true};}})}};
 const principalObserver=async()=>({nativeUiObserved:true,principalSha256:f.binding.account_principal_sha256});
 const extract=createOfficeNativeExtractor({binding:bound,principalObserver});const metadata=await extract({tab,clip});
 assert.equal(metadata.document_identity_sha256,created.item_identity_sha256);assert.equal(geometryCalls,1);
 const foreign=createOfficeNativeExtractor({binding:{...bound,owned_folder_item_ui_receipt:{...created,item_identity_sha256:'0'.repeat(64)}},principalObserver});
 await assert.rejects(foreign({tab,clip}),/observed_document_folder_binding_changed/);assert.equal(geometryCalls,1);
});
