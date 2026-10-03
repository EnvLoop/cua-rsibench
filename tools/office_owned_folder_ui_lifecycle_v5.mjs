/* Additive evaluator-only native picker lifecycle; original V4 stays intact. */
import * as fs from 'node:fs/promises';
import path from 'node:path';
import {createHash,randomBytes} from 'node:crypto';
import {genericDocumentIdentity} from './office_owned_folder_cua_host_v3.mjs';
import {observeSignedInPrincipal} from './office_signed_in_principal_v3.mjs';
import {validateDocumentDownload} from './office_document_download_v4.mjs';
import {approvedBaseline} from './office_native_picker_uploader_v1.mjs';
const sha=raw=>createHash('sha256').update(raw).digest('hex');
const check=(ok,code)=>{if(!ok)throw new Error(code);};
const ordered=v=>Array.isArray(v)?v.map(ordered):v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,ordered(v[k])])):v;
const bytes=v=>Buffer.from(JSON.stringify(ordered(v)));

export const PARENT_SOURCE_SHA256='7dabfbda912f87999e1b4cd8c009c313b2f445b6cb1f33045d564025458cc813';
export const V5_SOURCE_FILES=Object.freeze(['tools/office_owned_folder_ui_lifecycle_v5.mjs','tools/office_native_picker_uploader_v1.mjs']);
export async function officeLifecycleV5SourceHashes(){const result={};for(const name of V5_SOURCE_FILES)result[name]=sha(await fs.readFile(new URL('./'+name.split('/').at(-1),import.meta.url)));return result;}

export async function createOfficeUiLifecycle({folderTab,browser=null,binding,profile,evidenceRoot,qualification=null,principalObserver=observeSignedInPrincipal,nativeBaselineUploader=null}) {
 check(nativeBaselineUploader===null||typeof nativeBaselineUploader==='function','native_baseline_uploader_invalid');
 const uploadTransport=nativeBaselineUploader?'native_picker':'filechooser';
 check(profile.upload_transport===uploadTransport||(!nativeBaselineUploader&&profile.upload_transport===undefined),'native_upload_transport_binding_changed');
 const pickerScope=Object.freeze({tab_id:binding.tab_id,account_principal_sha256:binding.account_principal_sha256,folder_scope_sha256:binding.folder_scope_sha256,folder_url:binding.folder_url,folder_url_sha256:binding.folder_url_sha256});
 check(folderTab.id===binding.tab_id&&profile.schema==='office-owned-folder-native-ui-profile-v3'&&profile.source_reviewed===true,'native_folder_tab_profile_review_required');
 const root=await fs.realpath(evidenceRoot);const stat=await fs.lstat(root);check(stat.isDirectory()&&!stat.isSymbolicLink()&&(stat.mode&0o077)===0,'native_private_evidence_root_required');
 const folderURL=new URL(binding.folder_url);check(folderURL.origin==='https://onedrive.live.com'&&folderURL.searchParams.get('id')&&binding.folder_url_sha256===sha(Buffer.from(binding.folder_url)), 'exact_native_folder_url_required');
 let sequence=0;const owned=new Map(),documentTabs=new Map(),createdIdentities=new Set();
 const locator=(step,tab=folderTab)=>{const scope=tab!==folderTab&&profile.editor_frame_selector?tab.playwright.frameLocator(profile.editor_frame_selector):tab.playwright;return step.selector?scope.locator(step.selector):step.text?scope.getByText(step.text,{exact:true}):scope.getByRole(step.role,{name:step.name,exact:true});};
 async function write(name,raw){await fs.writeFile(path.join(root,name),raw,{flag:'wx',mode:0o600});return {path:name,sha256:sha(raw)};}
 async function visible(step,tab=folderTab){const node=locator(step,tab);await node.waitFor({state:'visible',timeoutMs:10000});check(await node.count()===1&&await node.isVisible()&&await node.isEnabled(),'native_visible_unique_control_required');return node;}
 async function click(step,tab=folderTab){await (await visible(step,tab)).click({timeoutMs:10000});}
 async function snapshot(label){const refs=[];refs.push(await write(label+'.native.private.txt',Buffer.from(await folderTab.playwright.domSnapshot())));refs.push(await write(label+'.image',Buffer.from(await folderTab.screenshot({clip:binding.folder_clip}))));return refs;}
 async function begin(op,payload){const n=sequence++;const label='lifecycle-'+String(n).padStart(4,'0');await write(label+'.intent.private.json',bytes({schema:'office-owned-folder-ui-intent-v2',operation:op,payload,sequence:n,one_use:true}));return {label,refs:await snapshot(label+'-before')};}
 async function finish(state,op,extra){state.refs.push(...await snapshot(state.label+'-after'));const receipt={schema:'office-owned-folder-native-operation-v2',operation:op,account_principal_sha256:binding.account_principal_sha256,folder_scope_sha256:binding.folder_scope_sha256,native_ui:true,graph_used:false,new_account_used:false,status:'completed',raw_refs:state.refs,...extra};await write(state.label+'.receipt.private.json',bytes(receipt));return receipt;}
 async function principal(tab,surface){const observed=await principalObserver({tab,profile:profile.signed_in_principal?.[surface],expectedSha256:binding.account_principal_sha256});check(observed.nativeUiObserved===true&&observed.principalSha256===binding.account_principal_sha256,'native_signed_in_account_not_observed');return observed;}
 async function pickerContext(state,phase){
  check(folderTab.id===pickerScope.tab_id&&Object.entries(pickerScope).every(([key,value])=>binding[key]===value),'native_picker_bound_tab_or_scope_changed');
  check(await folderTab.url()===pickerScope.folder_url,'native_picker_bound_folder_changed');
  await visible(profile.folder_heading);const observed=await principal(folderTab,'folder');
  state.refs.push(await write(state.label+'-native-picker-'+phase+'.private.json',bytes({schema:'office-native-picker-owned-context-v5',phase,tab_id:pickerScope.tab_id,account_principal_sha256:pickerScope.account_principal_sha256,folder_scope_sha256:pickerScope.folder_scope_sha256,folder_url_sha256:pickerScope.folder_url_sha256,native_signed_in_principal_observed:observed.nativeUiObserved===true,principal_witness_kind:observed.continuityFromInitialSignedInUiWitness?'initial_witness_continuity':'current_native_principal'})));
 }
 async function folder(){if(await folderTab.url()!==binding.folder_url)await folderTab.goto(binding.folder_url);check(await folderTab.url()===binding.folder_url,'native_folder_navigation_changed');await visible(profile.folder_heading);await principal(folderTab,'folder');}
 async function childInventoryReady(){
  await visible({selector:'[role="grid"]'});const rows=folderTab.playwright.locator(profile.item_rows_selector),empty=locator(profile.empty_state),deadline=Date.now()+10000;
  while(Date.now()<deadline){
   const count=await rows.count();check(count===0||count===1,'native_child_row_count_unbounded');
   if(count===1&&await rows.nth(0).isVisible())return;
   if(count===0&&await empty.count()===1&&await empty.isVisible())return;
   await new Promise(resolve=>setTimeout(resolve,100));
  }
  throw new Error('native_child_grid_rows_or_empty_not_ready');
 }
 async function inventoryRaw(state=null){
  await childInventoryReady();
  const rows=await folderTab.playwright.locator(profile.item_rows_selector).evaluateAll((elements,arg)=>elements.map((e,index)=>({name:e.querySelector(arg.nameSelector)?.textContent?.trim(),href:e.querySelector('a[href]')?.href||null,row_index:index})),{nameSelector:profile.name_cell_selector},{timeoutMs:10000});
  check(rows.length<=1&&rows.every(r=>typeof r.name==='string'&&r.name.length>0),'native_folder_row_projection_unbounded_or_unnamed');
  const proof=profile.folder_inventory_proof;
  check(proof?.mode==='parent_card_count'&&typeof proof.parent_url==='string'&&proof.parent_url_sha256===sha(Buffer.from(proof.parent_url))&&proof.card_selector&&proof.name_selector&&proof.count_selector,'native_parent_card_inventory_profile_required');
  const parent=new URL(proof.parent_url);check(parent.origin==='https://onedrive.live.com'&&parent.searchParams.get('id'),'native_parent_folder_origin_unproved');
  let observedCount;
  try{
   await folderTab.goto(proof.parent_url);check(await folderTab.url()===proof.parent_url,'native_parent_folder_navigation_changed');await principal(folderTab,'folder');
   const card=folderTab.playwright.locator(proof.card_selector);await card.waitFor({state:'visible',timeoutMs:10000});check(await card.count()===1&&await card.isVisible(),'native_exact_parent_card_missing_or_ambiguous');
   const name=card.locator(proof.name_selector);await name.waitFor({state:'visible',timeoutMs:10000});check(await name.count()===1&&await name.isVisible(),'native_parent_card_name_missing');
   check(await name.evaluate(e=>e.textContent.trim())===profile.folder_heading.name,'native_parent_card_child_name_changed');
   const badge=card.locator(proof.count_selector);await badge.waitFor({state:'visible',timeoutMs:10000});check(await badge.count()===1&&await badge.isVisible(),'native_parent_folder_badge_missing');
   const count=await badge.evaluate(e=>({text:e.textContent.trim(),tag:e.tagName,folderLabel:e.closest('[aria-label="Yellow folder"]')?.getAttribute('aria-label')}));
   check(count.tag==='SPAN'&&count.folderLabel==='Yellow folder'&&/^(0|[1-9][0-9]*)$/.test(count.text),'native_folder_card_count_not_observed');observedCount=Number(count.text);
   if(state)state.refs.push(...await snapshot(state.label+'-parent-count'));
  }finally{await folderTab.goto(binding.folder_url);check(await folderTab.url()===binding.folder_url,'native_child_return_navigation_changed');await visible(profile.folder_heading);await principal(folderTab,'folder');}
  if(observedCount===0)await visible(profile.empty_state);
  else if(observedCount===1&&rows.length===1)await visible(profile.item_ready||{role:'gridcell',name:rows[0].name});
  const reread=await folderTab.playwright.locator(profile.item_rows_selector).evaluateAll((elements,arg)=>elements.map((e,index)=>({name:e.querySelector(arg.nameSelector)?.textContent?.trim(),href:e.querySelector('a[href]')?.href||null,row_index:index})),{nameSelector:profile.name_cell_selector},{timeoutMs:10000});
  check(observedCount===rows.length&&bytes(reread).equals(bytes(rows)),'native_full_inventory_or_child_rows_changed');
  if(observedCount===0)await visible(profile.empty_state);
  return rows;
 }
 async function selectOwnedRow(item){
  const rows=await inventoryRaw();check(rows.length===1&&rows[0].name===item.file_name,'native_exact_owned_download_row_missing');
  const row=folderTab.playwright.locator(profile.item_rows_selector).nth(rows[0].row_index);
  const checkbox=row.getByRole('checkbox');check(await checkbox.count()===1&&await checkbox.isVisible(),'native_exact_owned_row_checkbox_ambiguous');
  if(await checkbox.getAttribute('aria-checked')!=='true')await checkbox.click({timeoutMs:10000});
  check(await checkbox.getAttribute('aria-checked')==='true','native_owned_row_selection_unproved');return rows[0];
 }
 async function saved(tab,state){
  await principal(tab,'editor');check(profile.saved_status?.selector==='#SaveStatusButton'&&typeof profile.saved_status_expected==='string','native_saved_status_profile_missing');
  const status=locator(profile.saved_status,tab);await status.waitFor({state:'visible',timeoutMs:30000});
  const deadline=Date.now()+45000;
  while(Date.now()<deadline){
   check(await status.count()===1&&await status.isVisible(),'native_saved_status_missing_or_ambiguous');
   const label=await status.evaluate((e,arg)=>e.getAttribute(arg.attribute),{attribute:profile.saved_status_attribute||'aria-label'});
   if(label===profile.saved_status_expected){state.refs.push(await write(state.label+'-saved-status.private.json',bytes({selector:profile.saved_status.selector,label,native_ui_observed:true,item_saved_to_onedrive:true})));return;}
   await new Promise(resolve=>setTimeout(resolve,200));
  }
  throw new Error('native_saved_to_onedrive_not_observed');
 }
 function checkItem(item){check(owned.has(item.item_identity_sha256)&&bytes(owned.get(item.item_identity_sha256)).equals(bytes(item)),'native_item_not_owned_by_this_lifecycle');}
 async function doc(item){
  checkItem(item);let tab=documentTabs.get(item.item_identity_sha256);
  if(!browser&&profile.offline_fixture===true){if(await folderTab.url()!==item.edit_url)await folderTab.goto(item.edit_url);await visible(profile.editor_ready);await principal(folderTab,'editor');return folderTab;}
  if(tab){const actual=genericDocumentIdentity(await tab.url(),{cell:item.cell_id,fileName:item.file_name});check(actual.documentSha256===item.item_identity_sha256,'native_doc_navigation_changed');await principal(tab,'editor');return tab;}
  // A prior owner download may have closed the tab; reopen only this exact
  // current folder row through the native Open in browser control.
  await folder();const rows=await inventoryRaw();const row=rows.find(r=>r.name===item.file_name);check(row,'native_owned_row_missing');
  tab=await openNativeRow(row,item.file_name,item.cell_id);const actual=genericDocumentIdentity(await tab.url(),{cell:item.cell_id,fileName:item.file_name});check(actual.documentSha256===item.item_identity_sha256,'native_reopened_document_changed');documentTabs.set(item.item_identity_sha256,tab);return tab;
 }
 async function openNativeRow(row,file,cell){
  check(browser?.tabs&&typeof browser.tabs.list==='function'&&typeof browser.tabs.get==='function','native_browser_tab_catalog_required');
  const before=await browser.tabs.list();const beforeIds=new Set(before.map(t=>t.id));
  // The profile identifies a row from actual folder metadata. Selection uses
  // that row's actual checkbox, never an age prefix or a different item.
  const rows=folderTab.playwright.locator(profile.item_rows_selector);const selected=rows.nth(row.row_index);
  const checkbox=selected.getByRole('checkbox');check(await checkbox.count()===1,'native_owned_row_checkbox_ambiguous');if(await checkbox.getAttribute('aria-checked')!=='true')await checkbox.click({timeoutMs:10000});
  for(const step of profile.open_steps)await click(step);
  const deadline=Date.now()+60000;
  while(Date.now()<deadline){
   const catalog=await browser.tabs.list();const candidates=catalog.filter(t=>!beforeIds.has(t.id)&&typeof t.url==='string').filter(t=>{try{genericDocumentIdentity(t.url,{cell,fileName:file});return true;}catch{return false;}});
   check(candidates.length<=1,'native_document_new_tab_ambiguous');
   if(candidates.length===1){const native=candidates[0];const tab=await browser.tabs.get(native.id);await visible(profile.editor_ready,tab);await principal(tab,'editor');return tab;}
   await new Promise(resolve=>setTimeout(resolve,250));
  }
  throw new Error('native_open_new_document_tab_uncertain_no_retry');
 }
 async function menu(steps){check(Array.isArray(steps)&&steps.length>0&&steps.length<=5,'native_ui_menu_recipe_missing');for(const step of steps)await click(step);}
 return Object.freeze({qualification,
  async folderInventory(){await folder();const state=await begin('folder_inventory',{});return finish(state,'folder_inventory',{items:await inventoryRaw(state)});},
  async createFromBaseline(_binding,task,baseline,{purpose}){
   await folder();check((await inventoryRaw()).length===0,'native_task_folder_not_empty');const file=path.basename(baseline);check(file.endsWith(task.cell_id==='powerpoint-web'?'.pptx':'.xlsx'),'native_baseline_extension_changed');
   const raw=await fs.readFile(baseline);check(sha(raw)===task.baseline_sha256,'native_upload_source_changed');const state=await begin('create_document',{purpose,baseline_sha256:sha(raw),task_id:task.task_id,upload_transport:uploadTransport});
   if(nativeBaselineUploader){await approvedBaseline(baseline,task.baseline_sha256);await pickerContext(state,'before');}
   const steps=profile.upload_steps;check(steps.length>=1&&steps.length<=4,'native_upload_recipe_missing');for(const step of steps.slice(0,-1))await click(step);
   if(nativeBaselineUploader){
    const pickerRoot=path.join(root,state.label+'-native-picker.private');await fs.mkdir(pickerRoot,{mode:0o700});
    await click(steps.at(-1));
    // One declared transport and one callback; uncertainty cannot select a
    // second upload route or manufacture a filechooser/server receipt.
    const receipt=await nativeBaselineUploader({filePath:baseline,expectedSha256:task.baseline_sha256,evidenceRoot:pickerRoot});
    check(receipt?.schema==='office-evaluator-native-picker-v1'&&receipt.source_sha256===task.baseline_sha256&&receipt.native_picker_open_clicked===true&&receipt.upload_server_state_verified===false&&receipt.permission_changes===false&&receipt.actor_api===false,'native_picker_local_receipt_invalid');
    state.refs.push(await write(state.label+'-native-picker-local.private.json',bytes(receipt)));
    await pickerContext(state,'after');await approvedBaseline(baseline,task.baseline_sha256);
   }else{
    const chooserPromise=folderTab.playwright.waitForEvent('filechooser',{timeoutMs:30000});await click(steps.at(-1));const chooser=await chooserPromise;state.refs.push(await write(state.label+'-chooser.private.json',bytes({native_filechooser_event:true,allows_multiple:chooser.isMultiple(),files_set:1,source_sha256:sha(raw)})));await chooser.setFiles(baseline,{timeoutMs:30000});
   }
   await locator(profile.item_ready||{role:'gridcell',name:file}).waitFor({state:'visible',timeoutMs:60000});const rows=await inventoryRaw();check(rows.length===1&&rows[0].name===file,'native_uploaded_item_identity_unproved');
   check(browser||profile.offline_fixture===true,'native_browser_required_without_fixture');const opened=browser?await openNativeRow(rows[0],file,task.cell_id):null;const editUrl=opened?await opened.url():rows[0].href;check(editUrl,'native_created_document_url_unobserved');const actual=genericDocumentIdentity(editUrl,{cell:task.cell_id,fileName:file});await principal(opened||folderTab,'editor');
   // Seen creation IDs survive close/delete. File renaming cannot turn the
   // same original cloud GUID into a fresh reset document.
   const cloudURL=new URL(editUrl),creationIdentity=sha(Buffer.from(cloudURL.origin+cloudURL.pathname.toLowerCase()+'|'+cloudURL.searchParams.get('sourcedoc').toLowerCase()));
   check(!createdIdentities.has(creationIdentity),'native_created_document_identity_reused');createdIdentities.add(creationIdentity);
   const item={account_principal_sha256:binding.account_principal_sha256,folder_scope_sha256:binding.folder_scope_sha256,item_identity_sha256:actual.documentSha256,document_owner_sha256:actual.documentOwnerSha256,edit_url:editUrl,file_name:file,cell_id:task.cell_id,purpose};owned.set(item.item_identity_sha256,item);if(opened)documentTabs.set(item.item_identity_sha256,opened);
   return finish(state,'create_document',{item,item_identity_sha256:actual.documentSha256});
  },
  async doubleDownload(_binding,item,{purpose}){
   check(profile.download_surface==='folder_toolbar','native_folder_toolbar_download_surface_required');
   const documentTab=await doc(item);const state=await begin('double_download',{item_identity_sha256:item.item_identity_sha256,purpose,download_surface:'folder_toolbar'});const downloadRefs=[];
   await saved(documentTab,state);await folder();
   for(let k=0;k<2;k++){
    await selectOwnedRow(item);const steps=profile.download_steps;check(Array.isArray(steps)&&steps.length>0&&steps.length<=5,'native_folder_toolbar_recipe_missing');
    for(const step of steps.slice(0,-1))await click(step,folderTab);
    const downloadPromise=folderTab.playwright.waitForEvent('download',{timeoutMs:60000});await click(steps.at(-1),folderTab);const download=await downloadPromise;
    const nativePath=await download.path({timeoutMs:60000});check(nativePath,'native_download_path_missing');
    const raw=await fs.readFile(nativePath);const verified=validateDocumentDownload(nativePath,raw,{fileName:item.file_name,cell:item.cell_id});downloadRefs.push(await write(state.label+'-download-'+k+path.extname(item.file_name),raw));
    state.refs.push(await write(state.label+'-download-'+k+'.native.private.json',bytes({native_download_path_sha256:sha(Buffer.from(nativePath)),download_sha256:sha(raw),native_event:'download',download_surface:'folder_toolbar',native_path_basename:verified.nativeBasename,browser_collision_suffix:verified.collisionSuffix,native_path_filename_verified:true,http_suggested_filename_claimed:false,ooxml_container_verified:true,item_identity_sha256:item.item_identity_sha256})));
   }
   return finish(state,'double_download',{item_identity_sha256:item.item_identity_sha256,download_surface:'folder_toolbar',download_refs:downloadRefs});
  },
  async closeDocument(_binding,item){checkItem(item);const state=await begin('close_document',{item_identity_sha256:item.item_identity_sha256});const tab=documentTabs.get(item.item_identity_sha256);if(tab){await tab.close();documentTabs.delete(item.item_identity_sha256);}await folder();return finish(state,'close_document',{item_identity_sha256:item.item_identity_sha256,owned_document_tab_closed:!!tab,owned_folder_scope_reopened:true});},
  async removeOwnedItem(_binding,item){await folder();checkItem(item);const rows=await inventoryRaw();check(rows.length===1&&rows[0].name===item.file_name,'native_delete_item_scope_changed');
   check(profile.delete_success?.text==='Deleted 1 item'&&Object.keys(profile.delete_success).length===1&&typeof folderTab.reload==='function','native_delete_success_and_reload_profile_required');
   const state=await begin('remove_document',{item_identity_sha256:item.item_identity_sha256});await selectOwnedRow(item);await menu(profile.delete_steps);
   const success=await visible(profile.delete_success);const message=await success.evaluate(e=>e.textContent.trim(),undefined,{timeoutMs:10000});check(message==='Deleted 1 item','native_explicit_delete_success_not_observed');
   state.refs.push(await write(state.label+'-delete-success.private.json',bytes({schema:'office-owned-item-delete-success-v5',item_identity_sha256:item.item_identity_sha256,observed_message:message,native_ui_observed:true,recoverable_delete:true,delete_retry_performed:false})));
   check(await folderTab.url()===pickerScope.folder_url,'native_delete_folder_changed_before_reload');await folderTab.reload();check(await folderTab.url()===pickerScope.folder_url,'native_delete_folder_changed_after_reload');await visible(profile.folder_heading);await principal(folderTab,'folder');
   await locator(profile.item_ready||{role:'gridcell',name:item.file_name}).waitFor({state:'hidden',timeoutMs:30000});check((await inventoryRaw()).length===0,'native_owned_item_delete_not_proved');owned.delete(item.item_identity_sha256);return finish(state,'remove_document',{item_identity_sha256:item.item_identity_sha256,explicit_delete_success_observed:true,owned_folder_reloaded_after_success:true,delete_retry_performed:false});
  },
  async openOwnedDocument(item){return doc(item);},
 });
}
