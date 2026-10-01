import test from 'node:test';import assert from 'node:assert/strict';
import fs from 'node:fs/promises';import os from 'node:os';import path from 'node:path';import {createHash} from 'node:crypto';
import {createOfficeUiLifecycle} from '../tools/office_owned_folder_ui_lifecycle_v3.mjs';
import {genericDocumentIdentity} from '../tools/office_owned_folder_cua_host_v3.mjs';
const sha=x=>createHash('sha256').update(x).digest('hex');
async function fixture(){
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'office-ui-v3-'));await fs.chmod(root,0o700);const evidence=path.join(root,'evidence');await fs.mkdir(evidence,{mode:0o700});
 const baseline=path.join(root,'source.pptx');await fs.writeFile(baseline,'synthetic document bytes',{mode:0o600});
 const folder='https://onedrive.live.com/?id=private-fixture-child',parent='https://onedrive.live.com/?id=private-fixture-parent';
 const edit='https://onedrive.live.com/personal/0000000000000001/_layouts/15/Doc.aspx?sourcedoc=%7B00000000-0000-0000-0000-000000000001%7D&file=source.pptx&action=edit';
 const id=genericDocumentIdentity(edit,{cell:'powerpoint-web',fileName:'source.pptx'});let url=folder,rows=[],selected=false,zip=false,badgeOverride=null,saved=true;const calls=[];
 const node=(name,scope='folder')=>({count:async()=>1,isVisible:async()=>true,isEnabled:async()=>true,
  evaluate:async()=>name==='badge'?{text:String(badgeOverride??rows.length),tag:'SPAN',folderLabel:'Yellow folder'}:name==='card-name'?'Fresh child':name==='#SaveStatusButton'?saved?'Saved to OneDrive\nClick the cloud icon to view file location':'Saving...':null,
  evaluateAll:async()=>rows.map((r,row_index)=>({...r,row_index})),locator:s=>node(s,scope),nth:()=>node('row',scope),getByRole:(r,o)=>node(r==='checkbox'?'checkbox':o.name,scope),
  getAttribute:async name=>name==='aria-checked'?String(selected):null,
  waitFor:async()=>{},click:async()=>{calls.push(scope+':'+name);if(name==='Files upload'){}if(name==='checkbox')selected=true;}});
 const folderTab={id:1,url:async()=>url,goto:async u=>{url=u;calls.push('goto:'+(u===parent?'parent':'child'));},screenshot:async()=>Buffer.from('private fixture image'),
  playwright:{locator:s=>node(s),getByRole:(r,o)=>node(o.name),getByText:t=>node(t),domSnapshot:async()=>JSON.stringify({rows}),waitForEvent:async event=>{calls.push('folder-event:'+event);
   if(event==='filechooser')return {isMultiple:()=>false,setFiles:async()=>{rows=[{name:'source.pptx',href:edit}];}};
   return {suggestedFilename:async()=>zip?'folder.zip':'source.pptx',path:async()=>baseline};}}};
 const editorTab={id:2,url:async()=>edit,close:async()=>calls.push('editor-close'),playwright:{frameLocator:()=>({locator:s=>node(s,'editor'),getByRole:(r,o)=>node(o.name,'editor')}),locator:s=>node(s,'editor'),getByRole:(r,o)=>node(o.name,'editor')}};
 let opened=false;const browser={tabs:{list:async()=>opened?[{id:1,url:folder},{id:2,url:edit}]:[{id:1,url:folder}],get:async()=>editorTab}};
 const original=node;
 const api=folderTab.playwright.getByRole;folderTab.playwright.getByRole=(r,o)=>{const n=api(r,o);const click=n.click;n.click=async()=>{await click();if(o.name==='Open in browser')opened=true;};return n;};
 const p=name=>({role:'button',name});const profile={schema:'office-owned-folder-native-ui-profile-v3',source_reviewed:true,
  folder_heading:{role:'heading',name:'Fresh child'},item_rows_selector:'rows',name_cell_selector:'name',empty_state:{text:'This folder is empty'},
  folder_inventory_proof:{mode:'parent_card_count',parent_url:parent,parent_url_sha256:sha(Buffer.from(parent)),card_selector:'exact-card',name_selector:'card-name',count_selector:'badge'},
  signed_in_principal:{folder:{},editor:{}},upload_steps:[p('Create or upload'),{role:'menuitem',name:'Files upload'}],
  open_steps:[{role:'menuitem',name:'Open'},{role:'menuitem',name:'Open in browser'}],editor_frame_selector:'iframe#WacFrame_PowerPoint_0',editor_ready:{selector:'#ModeSwitcher'},
  saved_status:{selector:'#SaveStatusButton'},saved_status_attribute:'aria-label',saved_status_expected:'Saved to OneDrive\nClick the cloud icon to view file location',
  download_surface:'folder_toolbar',download_steps:[{role:'menuitem',name:'Download'}],delete_steps:[p('Delete')]};
 const binding={tab_id:1,folder_url:folder,folder_url_sha256:sha(Buffer.from(folder)),account_principal_sha256:'a'.repeat(64),folder_scope_sha256:'b'.repeat(64),folder_clip:{x:0,y:126,width:1000,height:700}};
 const principalObserver=async()=>({nativeUiObserved:true,principalSha256:binding.account_principal_sha256});
 const driver=await createOfficeUiLifecycle({folderTab,browser,binding,profile,evidenceRoot:evidence,principalObserver});
 const task={task_id:'fixture',cell_id:'powerpoint-web',baseline_sha256:sha(await fs.readFile(baseline))};
 return {root,driver,task,baseline,binding,calls,profile,setZip:v=>zip=v,setBadge:v=>badgeOverride=v};
}
test('actual lifecycle reads parent badge and downloads exact document twice through folder toolbar after genuine save',async()=>{
 const f=await fixture();try{
  const empty=await f.driver.folderInventory();assert.deepEqual(empty.items,[]);assert.ok(f.calls.includes('goto:parent'));
  const created=await f.driver.createFromBaseline(f.binding,f.task,f.baseline,{purpose:'actor'});
  const downloads=await f.driver.doubleDownload(f.binding,created.item,{purpose:'saved_actor'});
  assert.equal(downloads.download_refs.length,2);assert.equal(downloads.download_surface,'folder_toolbar');
  assert.equal(f.calls.filter(x=>x==='folder-event:download').length,2);assert.equal(f.calls.filter(x=>x==='folder:Download').length,2);assert.ok(!f.calls.some(x=>x==='editor:Download'));
  const files=await fs.readdir(path.join(f.root,'evidence'));assert.ok(files.some(x=>x.includes('saved-status')));assert.ok(files.some(x=>x.includes('parent-count')));
 }finally{await fs.rm(f.root,{recursive:true,force:true});}
});
test('native parent count cannot be replaced by rendered rows or selection count',async()=>{
 const f=await fixture();try{f.setBadge(1);await assert.rejects(()=>f.driver.folderInventory(),/full_inventory/);}finally{await fs.rm(f.root,{recursive:true,force:true});}
});
test('folder zip download is refused before a completed double-download receipt',async()=>{
 const f=await fixture();try{const created=await f.driver.createFromBaseline(f.binding,f.task,f.baseline,{purpose:'actor'});f.setZip(true);await assert.rejects(()=>f.driver.doubleDownload(f.binding,created.item,{purpose:'saved_actor'}),/folder_zip/);assert.equal(f.calls.filter(x=>x==='folder-event:download').length,1);}finally{await fs.rm(f.root,{recursive:true,force:true});}
});
