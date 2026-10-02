import test from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {createHash} from 'node:crypto';
import {createOfficeCuaOperationPump} from '../tools/office_owned_folder_cua_pump_v2.mjs';
const ordered=v=>Array.isArray(v)?v.map(ordered):v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,ordered(v[k])])):v;
const raw=v=>Buffer.from(JSON.stringify(ordered(v)));const sha=v=>createHash('sha256').update(v).digest('hex');
test('durable native claim and exact scope prevent operation replay after a new pump instance',async()=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'office-pump-offline-'));await fs.chmod(root,0o700);
 try{
  const spool=path.join(root,'spool'),evidence=path.join(root,'evidence');await fs.mkdir(spool,{mode:0o700});await fs.mkdir(evidence,{mode:0o700});
  const url='https://onedrive.live.com/?id=fixture-owned-folder';let nativeCalls=0;
  const node={count:async()=>1,isVisible:async()=>true,isEnabled:async()=>true,evaluate:async fn=>fn({textContent:'0 items'}),evaluateAll:async (fn,arg)=>fn([],arg)};
  const tab={id:1,url:async()=>url,screenshot:async()=>{nativeCalls++;return Buffer.from('fixture-image');},playwright:{locator:()=>node,getByRole:()=>node,domSnapshot:async()=>{nativeCalls++;return 'fixture-native-folder-empty';}}};
  const binding={tab_id:1,folder_url:url,folder_url_sha256:sha(Buffer.from(url)),account_principal_sha256:'a'.repeat(64),folder_scope_sha256:'b'.repeat(64),folder_clip:{x:0,y:126,width:1000,height:700}};
  const profile={schema:'office-owned-folder-native-ui-profile-v2',source_reviewed:true,folder_heading:{role:'button',name:'Folder'},folder_count:{role:'button',name:'Count'},item_rows_selector:'rows'};
  const admission={approved:true,account_principal_sha256:binding.account_principal_sha256,folder_scope_sha256:binding.folder_scope_sha256,graph_used:false};
  const config={folderTab:tab,binding,profile,spoolRoot:await fs.realpath(spool),evidenceRoot:await fs.realpath(evidence),sourceAdmission:admission,listDocumentTabIds:async()=>[1]};
  const pump=await createOfficeCuaOperationPump(config);assert.equal((await pump.pumpOnce()).status,'waiting');assert.equal(nativeCalls,0);
  const dir=path.join(spool,'operation-0000');await fs.mkdir(dir,{mode:0o700});const request={schema:'office-owned-folder-operation-request-v2',operation:'folder_inventory',sequence:0,payload:{},account_principal_sha256:binding.account_principal_sha256,folder_scope_sha256:binding.folder_scope_sha256,source_review_sha256:sha(raw(admission)),one_use:true};await fs.writeFile(path.join(dir,'request.private.json'),raw(request),{mode:0o600});
  assert.equal((await pump.pumpOnce()).status,'completed');assert.ok(await fs.stat(path.join(dir,'native-started.private.json')));const before=nativeCalls;
  const reopened=await createOfficeCuaOperationPump(config);await assert.rejects(()=>reopened.pumpOnce(),{code:'EEXIST'});assert.equal(nativeCalls,before);
  const response=JSON.parse(await fs.readFile(path.join(dir,'response.private.json')));assert.equal(response.request_sha256,sha(raw(request)));assert.deepEqual(response.result.items,[]);
 }finally{await fs.rm(root,{recursive:true,force:true});}
});
