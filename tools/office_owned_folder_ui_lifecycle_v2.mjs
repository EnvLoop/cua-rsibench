/* Evaluator-owned original Office GUI lifecycle. No Graph/network file API. */
import * as fs from 'node:fs/promises';
import path from 'node:path';
import {createHash,randomBytes} from 'node:crypto';
import {genericDocumentIdentity} from './office_owned_folder_cua_host_v2.mjs';
const sha=raw=>createHash('sha256').update(raw).digest('hex');
const check=(ok,code)=>{if(!ok)throw new Error(code);};
const ordered=v=>Array.isArray(v)?v.map(ordered):v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,ordered(v[k])])):v;
const bytes=v=>Buffer.from(JSON.stringify(ordered(v)));

export async function createOfficeUiLifecycle({folderTab,browser=null,binding,profile,evidenceRoot,qualification=null}) {
 check(folderTab.id===binding.tab_id&&profile.schema==='office-owned-folder-native-ui-profile-v2'&&profile.source_reviewed===true,'native_folder_tab_profile_review_required');
 const root=await fs.realpath(evidenceRoot);const stat=await fs.lstat(root);check(stat.isDirectory()&&!stat.isSymbolicLink()&&(stat.mode&0o077)===0,'native_private_evidence_root_required');
 const folderURL=new URL(binding.folder_url);check(folderURL.origin==='https://onedrive.live.com'&&folderURL.searchParams.get('id')&&binding.folder_url_sha256===sha(Buffer.from(binding.folder_url)), 'exact_native_folder_url_required');
 let sequence=0;const owned=new Map(),documentTabs=new Map();
 const locator=(step,tab=folderTab)=>{const scope=tab!==folderTab&&profile.editor_frame_selector?tab.playwright.frameLocator(profile.editor_frame_selector):tab.playwright;return step.selector?scope.locator(step.selector):scope.getByRole(step.role,{name:step.name,exact:true});};
 async function write(name,raw){await fs.writeFile(path.join(root,name),raw,{flag:'wx',mode:0o600});return {path:name,sha256:sha(raw)};}
 async function visible(step,tab=folderTab){const node=locator(step,tab);check(await node.count()===1&&await node.isVisible()&&await node.isEnabled(),'native_visible_unique_control_required');return node;}
 async function click(step,tab=folderTab){await (await visible(step,tab)).click({timeoutMs:10000});}
 async function snapshot(label){const refs=[];refs.push(await write(label+'.native.private.txt',Buffer.from(await folderTab.playwright.domSnapshot())));refs.push(await write(label+'.image',Buffer.from(await folderTab.screenshot({clip:binding.folder_clip}))));return refs;}
 async function begin(op,payload){const n=sequence++;const label='lifecycle-'+String(n).padStart(4,'0');await write(label+'.intent.private.json',bytes({schema:'office-owned-folder-ui-intent-v2',operation:op,payload,sequence:n,one_use:true}));return {label,refs:await snapshot(label+'-before')};}
 async function finish(state,op,extra){state.refs.push(...await snapshot(state.label+'-after'));const receipt={schema:'office-owned-folder-native-operation-v2',operation:op,account_principal_sha256:binding.account_principal_sha256,folder_scope_sha256:binding.folder_scope_sha256,native_ui:true,graph_used:false,new_account_used:false,status:'completed',raw_refs:state.refs,...extra};await write(state.label+'.receipt.private.json',bytes(receipt));return receipt;}
 async function folder(){if(await folderTab.url()!==binding.folder_url)await folderTab.goto(binding.folder_url);check(await folderTab.url()===binding.folder_url,'native_folder_navigation_changed');await visible(profile.folder_heading);}
 async function inventoryRaw(){
  const table=folderTab.playwright.locator(profile.item_rows_selector);
  const rows=await table.evaluateAll((elements,arg)=>elements.map((e,index)=>({name:arg.nameSelector?e.querySelector(arg.nameSelector)?.textContent?.trim():e.getAttribute('data-file-name')||e.getAttribute('title')||e.querySelector('[data-automationid="name"]')?.textContent||e.textContent.trim(),href:e.querySelector('a[href]')?.href||null,row_index:index})),{nameSelector:profile.name_cell_selector},{timeoutMs:10000});
  const countNode=await visible(profile.folder_count);const count=await countNode.evaluate(e=>e.textContent.trim());
  const match=count.match(profile.count_regex?new RegExp(profile.count_regex):/^(\d+) items?$/);check(match&&Number(match[1])===rows.length&&rows.length<=1,'native_folder_full_inventory_not_proved');
  return rows;
 }
 function checkItem(item){check(owned.has(item.item_identity_sha256)&&bytes(owned.get(item.item_identity_sha256)).equals(bytes(item)),'native_item_not_owned_by_this_lifecycle');}
 async function doc(item){
  checkItem(item);let tab=documentTabs.get(item.item_identity_sha256);
  if(!browser&&profile.offline_fixture===true){if(await folderTab.url()!==item.edit_url)await folderTab.goto(item.edit_url);await visible(profile.editor_ready);return folderTab;}
  if(tab){const actual=genericDocumentIdentity(await tab.url(),{cell:item.cell_id,fileName:item.file_name});check(actual.documentSha256===item.item_identity_sha256,'native_doc_navigation_changed');return tab;}
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
   if(candidates.length===1){const native=candidates[0];const tab=await browser.tabs.get(native.id);await visible(profile.editor_ready,tab);return tab;}
   await new Promise(resolve=>setTimeout(resolve,250));
  }
  throw new Error('native_open_new_document_tab_uncertain_no_retry');
 }
 async function menu(steps){check(Array.isArray(steps)&&steps.length>0&&steps.length<=5,'native_ui_menu_recipe_missing');for(const step of steps)await click(step);}
 return Object.freeze({qualification,
  async folderInventory(){await folder();const state=await begin('folder_inventory',{});return finish(state,'folder_inventory',{items:await inventoryRaw()});},
  async createFromBaseline(_binding,task,baseline,{purpose}){
   await folder();check((await inventoryRaw()).length===0,'native_task_folder_not_empty');const file=path.basename(baseline);check(file.endsWith(task.cell_id==='powerpoint-web'?'.pptx':'.xlsx'),'native_baseline_extension_changed');
   const raw=await fs.readFile(baseline);check(sha(raw)===task.baseline_sha256,'native_upload_source_changed');const state=await begin('create_document',{purpose,baseline_sha256:sha(raw),task_id:task.task_id});
   const steps=profile.upload_steps;check(steps.length>=1&&steps.length<=4,'native_upload_recipe_missing');for(const step of steps.slice(0,-1))await click(step);
   const chooserPromise=folderTab.playwright.waitForEvent('filechooser',{timeoutMs:30000});await click(steps.at(-1));const chooser=await chooserPromise;state.refs.push(await write(state.label+'-chooser.private.json',bytes({native_filechooser_event:true,allows_multiple:chooser.isMultiple(),files_set:1,source_sha256:sha(raw)})));await chooser.setFiles(baseline,{timeoutMs:30000});
   await locator(profile.item_ready||{role:'gridcell',name:file}).waitFor({state:'visible',timeoutMs:60000});const rows=await inventoryRaw();check(rows.length===1&&rows[0].name===file,'native_uploaded_item_identity_unproved');
   check(browser||profile.offline_fixture===true,'native_browser_required_without_fixture');const opened=browser?await openNativeRow(rows[0],file,task.cell_id):null;const editUrl=opened?await opened.url():rows[0].href;check(editUrl,'native_created_document_url_unobserved');const actual=genericDocumentIdentity(editUrl,{cell:task.cell_id,fileName:file});check(actual.accountSha256===binding.account_principal_sha256,'native_upload_account_changed');
   const item={account_principal_sha256:actual.accountSha256,folder_scope_sha256:binding.folder_scope_sha256,item_identity_sha256:actual.documentSha256,edit_url:editUrl,file_name:file,cell_id:task.cell_id,purpose};owned.set(item.item_identity_sha256,item);if(opened)documentTabs.set(item.item_identity_sha256,opened);
   return finish(state,'create_document',{item});
  },
  async doubleDownload(_binding,item,{purpose}){
   const documentTab=await doc(item);const state=await begin('double_download',{item_identity_sha256:item.item_identity_sha256,purpose});const downloadRefs=[];
   for(let k=0;k<2;k++){
    const steps=profile.download_steps;for(const step of steps.slice(0,-1))await click(step,documentTab);
    const downloadPromise=documentTab.playwright.waitForEvent('download',{timeoutMs:60000});await click(steps.at(-1),documentTab);const download=await downloadPromise;const nativePath=await download.path({timeoutMs:60000});check(nativePath,'native_download_path_missing');
    const raw=await fs.readFile(nativePath);check(raw.length>0&&raw.length<=50000000,'native_download_size_invalid');downloadRefs.push(await write(state.label+'-download-'+k+path.extname(item.file_name),raw));
    state.refs.push(await write(state.label+'-download-'+k+'.native.private.json',bytes({native_download_path_sha256:sha(Buffer.from(nativePath)),download_sha256:sha(raw),native_event:'download',item_identity_sha256:item.item_identity_sha256})));
   }
   return finish(state,'double_download',{item_identity_sha256:item.item_identity_sha256,download_refs:downloadRefs});
  },
  async closeDocument(_binding,item){checkItem(item);const state=await begin('close_document',{item_identity_sha256:item.item_identity_sha256});const tab=documentTabs.get(item.item_identity_sha256);if(tab){await tab.close();documentTabs.delete(item.item_identity_sha256);}await folder();return finish(state,'close_document',{item_identity_sha256:item.item_identity_sha256,owned_document_tab_closed:!!tab,owned_folder_scope_reopened:true});},
  async removeOwnedItem(_binding,item){await folder();checkItem(item);const rows=await inventoryRaw();check(rows.length===1&&rows[0].name===item.file_name,'native_delete_item_scope_changed');
   const state=await begin('remove_document',{item_identity_sha256:item.item_identity_sha256});await menu(profile.delete_steps);await locator(profile.item_ready||{role:'gridcell',name:item.file_name}).waitFor({state:'hidden',timeoutMs:30000});check((await inventoryRaw()).length===0,'native_owned_item_delete_not_proved');owned.delete(item.item_identity_sha256);return finish(state,'remove_document',{item_identity_sha256:item.item_identity_sha256});
  },
  async openOwnedDocument(item){return doc(item);},
 });
}
