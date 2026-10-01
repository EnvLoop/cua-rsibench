import test from 'node:test';
import assert from 'node:assert/strict';
import {genericDocumentIdentity,createOfficeOwnedFolderCuaHost} from '../tools/office_owned_folder_cua_host_v2.mjs';
import {createHash} from 'node:crypto';
const url='https://onedrive.live.com/personal/0000000000000001/_layouts/15/Doc.aspx?sourcedoc=%7B00000000-0000-0000-0000-000000000001%7D&file=review-final-042.pptx&action=edit';
const id=genericDocumentIdentity(url,{cell:'powerpoint-web',fileName:'review-final-042.pptx'});
const binding={tab_id:1,edit_url:url,cell_id:'powerpoint-web',file_name:'review-final-042.pptx',account_principal_sha256:id.accountSha256,item_identity_sha256:id.documentSha256,folder_scope_sha256:'b'.repeat(64),clip:{x:0,y:126,width:1000,height:700}};
const lifecycle=()=>Object.fromEntries(['folderInventory','createFromBaseline','doubleDownload','closeDocument','removeOwnedItem'].map(k=>[k,async()=>{}]));
test('generic current PPT and Excel identifiers do not require legacy TRAIN filenames',()=>{
 assert.match(id.documentSha256,/^[a-f0-9]{64}$/);
 assert.ok(genericDocumentIdentity(url.replace('review-final-042.pptx','annual-model.xlsx'),{cell:'excel-web',fileName:'annual-model.xlsx'}));
 assert.throws(()=>genericDocumentIdentity(url.replace('action=edit','action=view'),{cell:'powerpoint-web',fileName:'review-final-042.pptx'}));
});
test('missing native lifecycle recipe fails before any CUA call',()=>{
 let calls=0;const tab={id:1,url:async()=>{calls++;return url;}};
 assert.throws(()=>createOfficeOwnedFolderCuaHost({tab,binding,lifecycleDriver:{},nativeExtractor:()=>{},listDocumentTabIds:async()=>[1]}));assert.equal(calls,0);
});
test('driver exposes truthful native qualification and documented drag support',()=>{
 const host=createOfficeOwnedFolderCuaHost({tab:{id:1},binding,lifecycleDriver:lifecycle(),nativeExtractor:()=>{},listDocumentTabIds:async()=>[1]});
 assert.equal(host.capabilities().qualified_native_operations,false);assert.equal(host.capabilities().scroll_units,'pixels');assert.deepEqual(host.capabilities().unsupported_actions,[]);
});
test('coordinate mapping adds crop origin and scroll pixels map to fractional pages',async()=>{
 const calls=[];const host=createOfficeOwnedFolderCuaHost({tab:{id:1,click:async(...args)=>calls.push(['click',...args]),scroll:async(...args)=>calls.push(['scroll',...args])},binding,lifecycleDriver:lifecycle(),nativeExtractor:()=>{},listDocumentTabIds:async()=>[1]});
 const item={item_identity_sha256:id.documentSha256};const current={status:'current',native_metadata:{targets:[]}};
 await host.dispatch_native_primitive(item,{type:'click',target:{x:40,y:50}},current);
 await host.dispatch_native_primitive(item,{type:'scroll',target:{x:40,y:50},dx:0,dy:350},current);
 assert.deepEqual(calls[0][1],[40,176]);assert.deepEqual(calls[1],['scroll',[40,176],'down',0.5]);
});
