/* One-operation CUA scripting-host pump. Explicit polling never replays work. */
import * as fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {createOfficeUiLifecycle} from './office_owned_folder_ui_lifecycle_v3.mjs';
import {createOfficeNativeExtractor} from './office_owned_folder_native_extractor_v3.mjs';
import {createOfficeOwnedFolderCuaHost} from './office_owned_folder_cua_host_v3.mjs';
const canonical=v=>Array.isArray(v)?v.map(canonical):v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,canonical(v[k])])):v;
const raw=v=>Buffer.from(JSON.stringify(canonical(v)));
const sha=v=>createHash('sha256').update(v).digest('hex');
const check=(ok,code)=>{if(!ok)throw new Error(code);};
async function readPrivate(file){const st=await fs.lstat(file);check(st.isFile()&&!st.isSymbolicLink()&&(st.mode&0o077)===0,'private_native_rpc_artifact_required');return fs.readFile(file);}

export const V3_SOURCE_FILES=Object.freeze(['tools/office_owned_folder_cua_pump_v3.mjs','tools/office_owned_folder_cua_host_v3.mjs','tools/office_owned_folder_native_extractor_v3.mjs','tools/office_owned_folder_native_profile_v3.mjs','tools/office_owned_folder_ui_lifecycle_v3.mjs','tools/office_signed_in_principal_v3.mjs']);
export async function officeV3SourceHashes(){const values={};for(const name of V3_SOURCE_FILES)values[name]=sha(await fs.readFile(new URL('./'+name.split('/').at(-1),import.meta.url)));return values;}

export async function createOfficeCuaOperationPump({folderTab,browser,binding,profile,spoolRoot,evidenceRoot,sourceAdmission,listDocumentTabIds}) {
 const supplemental=await officeV3SourceHashes();
 check(raw(binding.supplemental_source_sha256s).equals(raw(supplemental))&&raw(sourceAdmission.supplemental_source_sha256s).equals(raw(supplemental)),'native_v3_supplemental_source_changed');
 const root=await fs.realpath(spoolRoot);check(root===path.resolve(spoolRoot),'native_rpc_root_changed');
 check(sourceAdmission.approved===true&&sourceAdmission.account_principal_sha256===binding.account_principal_sha256&&sourceAdmission.folder_scope_sha256===binding.folder_scope_sha256&&sourceAdmission.graph_used===false,'native_rpc_source_admission_changed');
 const lifecycle=await createOfficeUiLifecycle({folderTab,browser,binding,profile,evidenceRoot,qualification:{actual_native_lifecycle_qualified:sourceAdmission.actual_native_lifecycle_qualified===true}});
 let sequence=0;const items=new Map();let host=null,actorRoot=null,actorTask=null;
 async function put(name,data){await fs.writeFile(path.join(evidenceRoot,name),data,{flag:'wx',mode:0o600});return {path:name,sha256:sha(data)};}
 async function perform(operation,payload,n){
  if(operation==='folder_inventory')return lifecycle.folderInventory();
  if(operation==='create_document'){const result=await lifecycle.createFromBaseline(binding,payload.actor_task,payload.baseline_path,{purpose:payload.purpose});items.set(result.item.item_identity_sha256,{item:result.item,receipt:result});return result;}
  const owned=items.get(payload.item?.item_identity_sha256);
  check(owned&&raw(owned.item).equals(raw(payload.item)),'native_rpc_item_not_owned');
  if(operation==='double_download')return lifecycle.doubleDownload(binding,payload.item,{purpose:payload.purpose});
  if(operation==='close_document'){host=null;return lifecycle.closeDocument(binding,payload.item);}
  if(operation==='remove_document'){const result=await lifecycle.removeOwnedItem(binding,payload.item);items.delete(payload.item.item_identity_sha256);return result;}
  if(operation==='actor_open'){
   const documentTab=await lifecycle.openOwnedDocument(payload.item);actorRoot=payload.artifact_root;actorTask=payload.actor_task;
   const windowSha=sha(raw({browser:binding.browser_id,tab_id:documentTab.id}));
   const bound={...binding,...payload.item,editor_frame_selector:profile.editor_frame_selector,native_mode_selector:profile.native_mode_selector,native_mode_attribute:profile.native_mode_attribute,native_mode_editing_regex:profile.native_mode_editing_regex,tab_id:documentTab.id,window_sha256:windowSha,edit_url:payload.item.edit_url,cell_id:actorTask.cell_id,file_name:payload.item.file_name,owned_folder_item_ui_receipt:owned.receipt,
    owned_folder_item_ui_receipt_sha256:sha(raw(owned.receipt)),signed_in_principal_profile:profile.signed_in_principal.editor};
   host=createOfficeOwnedFolderCuaHost({tab:documentTab,binding:bound,lifecycleDriver:lifecycle,nativeExtractor:createOfficeNativeExtractor({binding:bound}),listDocumentTabIds});
   const surface=await host.current_native_surface(payload.item);check(surface.native_metadata.owned_document_editing===true,'native_actor_document_not_editing');
   return {native_policy_sha256:binding.native_policy_sha256,window_sha256:surface.native_metadata.window_sha256,owned_document_editing:true};
  }
  check(host&&actorTask,'native_rpc_actor_not_open');
  if(operation==='native_surface'){const current=await host.current_native_surface(payload.item);const ref=await put('rpc-'+n+'-cropped.image',current.cropped_image_bytes);await put('rpc-'+n+'-native.private.json',raw(current.native_metadata));return {cropped_image_ref:ref,native_metadata:current.native_metadata};}
  if(operation==='resolve_native_targets')return host.resolve_current_action_targets(payload.item,payload.action,payload.current);
  if(operation==='dispatch_native_primitive'){
   const prefix=path.join(actorRoot,'turn-'+String(payload.action.step).padStart(3,'0'));const intent=JSON.parse(await readPrivate(path.join(prefix,'intent.private.json')));const decision=JSON.parse(await readPrivate(path.join(prefix,'decision.private.json')));
   check(sha(raw(intent.action))===sha(raw(payload.action))&&intent.decision_sha256===sha(raw(decision))&&decision.status==='accepted'&&decision.policy_sha256===binding.native_policy_sha256,'actual_shared_guard_intent_required_before_native_driver');
   const result=await host.dispatch_native_primitive(payload.item,payload.action,payload.resolved);await put('rpc-'+n+'-driver.private.json',raw(result));return result;
  }
  throw new Error('native_rpc_operation_unsupported');
 }
 return Object.freeze({
  async pumpOnce(){
   const n=sequence;const dir=path.join(root,'operation-'+String(n).padStart(4,'0'));const file=path.join(dir,'request.private.json');
   try{await fs.access(file);}catch{return {status:'waiting',sequence:n};}
   const requestRaw=await readPrivate(file);const request=JSON.parse(requestRaw);
   check(request.schema==='office-owned-folder-operation-request-v2'&&request.sequence===n&&request.one_use===true&&request.account_principal_sha256===binding.account_principal_sha256&&request.folder_scope_sha256===binding.folder_scope_sha256&&request.source_review_sha256===sha(raw(sourceAdmission)),'native_rpc_request_scope_changed');
   // Claim precedes any UI call. Existing claim/response is terminal, not retry.
   await fs.writeFile(path.join(dir,'native-started.private.json'),raw({sequence:n,request_sha256:sha(requestRaw),one_use:true}),{flag:'wx',mode:0o600});sequence++;
   let result,status='completed';
   try{result=await perform(request.operation,request.payload,n);}catch(error){status='failed';result={error_class:error.constructor.name,error_code:String(error.message).slice(0,160),native_operation_may_be_uncertain:true};}
   const response={schema:'office-owned-folder-operation-response-v2',sequence:n,operation:request.operation,request_sha256:sha(requestRaw),status,result};
   await fs.writeFile(path.join(dir,'response.private.json'),raw(response),{flag:'wx',mode:0o600});return {status,sequence:n};
  },
 });
}
