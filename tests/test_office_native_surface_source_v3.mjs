import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {createOfficeOwnedFolderCuaHost,genericDocumentIdentity} from '../tools/office_owned_folder_cua_host_v3.mjs';
import {inspectNativeOfficeDocument} from '../tools/office_owned_folder_native_extractor_v3.mjs';
import {signedInPrincipalIdentity,observeSignedInPrincipal} from '../tools/office_signed_in_principal_v3.mjs';
const sha=v=>createHash('sha256').update(v).digest('hex');
const url='https://onedrive.live.com/personal/0000000000000001/_layouts/15/Doc.aspx?sourcedoc=%7B00000000-0000-0000-0000-000000000001%7D&file=fixture.pptx&action=edit';
const identity=genericDocumentIdentity(url,{cell:'powerpoint-web',fileName:'fixture.pptx'});
const principal=signedInPrincipalIdentity('Person <person@example.test>');
const png=()=>{const b=Buffer.alloc(33);Buffer.from([137,80,78,71,13,10,26,10]).copy(b);b.write('IHDR',12);b.writeUInt32BE(1000,16);b.writeUInt32BE(700,20);return b;};
const target=(ref,bounds,keyboard=false,actions=['click'])=>({ref,bounds,visible:true,enabled:true,obscured:false,keyboard,actions});
function hostFixture(){
 const binding={tab_id:1,edit_url:url,cell_id:'powerpoint-web',file_name:'fixture.pptx',account_principal_sha256:principal.principalSha256,
  document_owner_sha256:identity.documentOwnerSha256,item_identity_sha256:identity.documentSha256,folder_scope_sha256:'b'.repeat(64),clip:{x:0,y:126,width:1000,height:700}};
 let meta={schema:'office-current-native-surface-v2',native_geometry_observed:true,account_principal_sha256:principal.principalSha256,document_identity_sha256:identity.documentSha256,
  folder_scope_sha256:binding.folder_scope_sha256,native_context_id:'context',modal_id:'none',focus_id:'a',focus_safe_keyboard:true,focus_safe_editable:false,targets:[target('a',[10,10,100,30],true,['click','key']),target('b',[200,10,50,30])]};
 const calls=[];const tab={id:1,url:async()=>url,getAXState:async()=>({}),screenshot:async()=>png(),click:async(...a)=>calls.push(['click',...a]),pressKey:async(...a)=>calls.push(['key',...a]),paste:async(...a)=>calls.push(['paste',...a])};
 const lifecycle=Object.fromEntries(['folderInventory','createFromBaseline','doubleDownload','closeDocument','removeOwnedItem'].map(k=>[k,async()=>{}]));
 const host=createOfficeOwnedFolderCuaHost({tab,binding,lifecycleDriver:lifecycle,nativeExtractor:async()=>meta,listDocumentTabIds:async()=>[1]});
 return {host,binding,item:{item_identity_sha256:identity.documentSha256},calls,current:()=>({context_id:'context',modal_id:'none',focus_id:'a',targets:structuredClone(meta.targets)}),change:fn=>{meta=fn(meta);}};
}
test('document owner CID is distinct from observed signed-in UI principal',()=>{
 assert.notEqual(identity.documentOwnerSha256,principal.principalSha256);assert.equal(Object.hasOwn(identity,'accountSha256'),false);
 assert.throws(()=>signedInPrincipalIdentity('one@example.test two@example.test'),/ambiguous/);
});
test('actual resolver accepts unrelated target/focus drift but rejects requested geometry or context drift',async()=>{
 const f=hostFixture(),current=f.current(),action={type:'click',target:{ref:'a'}};
 f.change(m=>({...m,focus_id:'b',targets:[m.targets[0],target('b',[300,100,50,30])]}));
 assert.equal((await f.host.resolve_current_action_targets(f.item,action,current)).status,'current');
 f.change(m=>({...m,targets:[target('a',[11,10,100,30],true,['click','key']),m.targets[1]]}));
 assert.equal((await f.host.resolve_current_action_targets(f.item,action,current)).status,'missing');
 f.change(m=>({...m,native_context_id:'other'}));assert.equal((await f.host.resolve_current_action_targets(f.item,action,current)).status,'missing');
});
test('targetless keyboard binds actual focus; Ctrl+S accepts app focus and typing refuses noneditable focus',async()=>{
 const f=hostFixture(),current=f.current(),action={type:'key',key:'Control+S'};
 const resolved=await f.host.resolve_current_action_targets(f.item,action,current);assert.equal(resolved.status,'current');
 await f.host.dispatch_native_primitive(f.item,action,resolved);assert.deepEqual(f.calls,[['key',null,'super+s']]);
 await assert.rejects(()=>f.host.dispatch_native_primitive(f.item,{type:'type',mode:'insert',text:'text'},resolved),/keyboard_focus/);
 f.change(m=>({...m,focus_id:'b'}));assert.equal((await f.host.resolve_current_action_targets(f.item,action,current)).status,'missing');
});
test('coordinate resolver never retargets moved, replaced or newly overlapped physical targets',async()=>{
 const f=hostFixture(),current=f.current(),action={type:'click',target:{x:50,y:20}};
 f.change(m=>({...m,targets:[target('new',[10,10,100,30]),m.targets[1]]}));
 assert.equal((await f.host.resolve_current_action_targets(f.item,action,current)).status,'missing');
});
test('actual DOM extractor separates safe option navigation from editable typing and unsafe account controls',()=>{
 const doc={readyState:'complete',URL:'fixture',defaultView:{getComputedStyle:()=>({display:'block',visibility:'visible',opacity:'1'})}};
 const body={tagName:'BODY',nodeType:1,parentElement:null,children:[]};
 const element=(tag,attrs,x)=>{const e={ownerDocument:doc,tagName:tag,nodeType:1,parentElement:body,children:[],type:attrs.type||'',disabled:false,readOnly:false,textContent:'',getAttribute:k=>attrs[k]??null,hasAttribute:k=>Object.hasOwn(attrs,k),getBoundingClientRect:()=>({x,y:150,width:100,height:30}),contains:v=>v===e};body.children.push(e);return e;};
 const option=element('DIV',{role:'option'},10),input=element('INPUT',{type:'text'},150),account=element('BUTTON',{'aria-label':'Account manager'},300);
 doc.activeElement=option;doc.querySelector=()=>null;doc.querySelectorAll=q=>q==='[role="dialog"]'?[]:[option,input,account];doc.elementFromPoint=x=>x<110?option:x<250?input:account;
 const raw=inspectNativeOfficeDocument(doc,{clip:{x:0,y:126,width:1000,height:700},frameOffset:{x:0,y:0}});
 assert.equal(raw.targets[0].keyboard,true);assert.equal(raw.targets[0].editable,false);assert.ok(raw.targets[0].actions.includes('key'));assert.ok(!raw.targets[0].actions.includes('type'));
 assert.equal(raw.targets[1].editable,true);assert.equal(raw.targets[2].enabled,false);assert.equal(raw.targets[2].keyboard,false);
});
test('actual passive principal method reopens private email witness and compares actual control without popup',async()=>{
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'office-principal-v3-'));await fs.chmod(root,0o700);
 try{
  const popup=path.join(root,'popup.private.txt'),control=path.join(root,'control.private.json');const baseline={tag:'BUTTON',id:null,attributes:[['title','Person']],image:{alt:'Person'}};
  await fs.writeFile(popup,'- generic: person@example.test\n- button "Sign out from person@example.test"',{mode:0o600});await fs.writeFile(control,JSON.stringify(baseline),{mode:0o600});
  let changed=false,clicks=0;const node={count:async()=>1,isVisible:async()=>true,isEnabled:async()=>true,evaluate:async()=>({tag:'BUTTON',id:null,attributes:[{name:'title',value:changed?'Other':'Person'}],image:{alt:'Person'}}),click:async()=>{clicks++;}};
  const tab={playwright:{getByRole:()=>node}};
  const profile={schema:'office-signed-in-ui-principal-profile-v3',source_reviewed:true,mode:'passive_label_continuity',open_steps:[],identity_control:{role:'button',name:'Person'},initial_popup_ref:{path:popup,sha256:sha(await fs.readFile(popup))},initial_control_ref:{path:control,sha256:sha(await fs.readFile(control))}};
  const result=await observeSignedInPrincipal({tab,profile,expectedSha256:principal.principalSha256});assert.equal(result.exactLiveEmailObserved,false);assert.equal(result.continuityFromInitialSignedInUiWitness,true);assert.equal(clicks,0);assert.equal(JSON.stringify(result).includes('person@example'),false);
  changed=true;await assert.rejects(()=>observeSignedInPrincipal({tab,profile,expectedSha256:principal.principalSha256}),/display_label_changed/);
 }finally{await fs.rm(root,{recursive:true,force:true});}
});
