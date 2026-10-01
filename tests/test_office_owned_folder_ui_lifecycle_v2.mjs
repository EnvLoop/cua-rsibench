import test from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {createHash} from 'node:crypto';
import {createOfficeUiLifecycle} from '../tools/office_owned_folder_ui_lifecycle_v2.mjs';
import {genericDocumentIdentity} from '../tools/office_owned_folder_cua_host_v2.mjs';
const sha=v=>createHash('sha256').update(v).digest('hex');

test('real lifecycle method path: chooser/download events precede GUI triggers, two downloads, delete only owned item',async()=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'office-ui-offline-'));await fs.chmod(root,0o700);
 try{
  const baseline=path.join(root,'source.pptx');await fs.writeFile(baseline,Buffer.from('fixture OOXML'),{mode:0o600});const evidence=path.join(root,'evidence');await fs.mkdir(evidence,{mode:0o700});
  const folder='https://onedrive.live.com/?id=fixture-owned-folder';const edit='https://onedrive.live.com/personal/0000000000000001/_layouts/15/Doc.aspx?sourcedoc=%7B00000000-0000-0000-0000-000000000001%7D&file=source.pptx&action=edit';const id=genericDocumentIdentity(edit,{cell:'powerpoint-web',fileName:'source.pptx'});
  const calls=[];let url=folder,rows=[],pending=null;
  const node=(name)=>({count:async()=>1,isVisible:async()=>true,isEnabled:async()=>true,waitFor:async()=>{},evaluate:async fn=>fn({textContent:rows.length+' items'}),evaluateAll:async (fn,arg)=>fn(rows.map(row=>({getAttribute:k=>k==='data-file-name'?row.name:null,querySelector:()=>({href:row.href}),textContent:row.name})),arg),click:async()=>{calls.push('click:'+name);if(name==='Files')assert.equal(pending,'filechooser');if(name==='Copy')assert.equal(pending,'download');if(name==='Confirm')rows=[];}});
  const tab={id:1,url:async()=>url,goto:async u=>{url=u;calls.push('goto');},screenshot:async()=>Buffer.from('fixture image only'),playwright:{locator:s=>node(s),getByRole:(r,o)=>node(o.name),domSnapshot:async()=>JSON.stringify({url,rows}),waitForEvent:async event=>{calls.push('event:'+event);pending=event;if(event==='filechooser')return {isMultiple:()=>true,setFiles:async file=>{assert.equal(file,baseline);rows=[{name:'source.pptx',href:edit}];}};return {path:async()=>baseline};}}};
  const p=role=>({role:'button',name:role});const profile={schema:'office-owned-folder-native-ui-profile-v2',source_reviewed:true,offline_fixture:true,folder_heading:p('Owned folder'),folder_count:p('Count'),item_rows_selector:'rows',item_ready:p('source.pptx'),editor_ready:p('Editing'),upload_steps:[p('Upload'),p('Files')],download_steps:[p('File'),p('Copy')],delete_steps:[p('Delete'),p('Confirm')]};
  const binding={tab_id:1,folder_url:folder,folder_url_sha256:sha(Buffer.from(folder)),account_principal_sha256:id.accountSha256,folder_scope_sha256:'b'.repeat(64),folder_clip:{x:0,y:126,width:1000,height:700}};
  const driver=await createOfficeUiLifecycle({folderTab:tab,binding,profile,evidenceRoot:evidence});const task={task_id:'fixture-train',cell_id:'powerpoint-web',baseline_sha256:sha(await fs.readFile(baseline))};
  assert.deepEqual((await driver.folderInventory()).items,[]);const created=await driver.createFromBaseline(binding,task,baseline,{purpose:'actor'});
  const item=JSON.parse(JSON.stringify(created.item,Object.keys(created.item).sort()));const downloads=await driver.doubleDownload(binding,item,{purpose:'saved_actor'});assert.equal(downloads.download_refs.length,2);
  await driver.closeDocument(binding,item);await driver.removeOwnedItem(binding,item);assert.deepEqual((await driver.folderInventory()).items,[]);
  assert.ok(calls.indexOf('event:filechooser')<calls.indexOf('click:Files'));assert.equal(calls.filter(x=>x==='event:download').length,2);
  await assert.rejects(()=>driver.removeOwnedItem(binding,{...item,item_identity_sha256:'f'.repeat(64)}),/not_owned/);
 }finally{await fs.rm(root,{recursive:true,force:true});}
});
