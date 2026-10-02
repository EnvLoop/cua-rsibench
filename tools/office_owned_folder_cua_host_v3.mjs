/* Additive generic original Office CUA host. No calls occur at construction.
 * Folder lifecycle operations are evaluator-owned, never model actions.
 * Native target metadata must come from the reviewed real browser extractor.
 */
import {createHash} from 'node:crypto';
import {imageBounds} from './office_local_browser_train_bridge_v1.mjs';
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const assert=(ok,code)=>{if(!ok)throw new Error(code);};

const KEYS=Object.freeze({Enter:'Return',Escape:'Escape',Backspace:'BackSpace',Delete:'Delete',Space:'space',ArrowUp:'Up',ArrowDown:'Down',ArrowLeft:'Left',ArrowRight:'Right',Home:'Home',End:'End','Shift+End':'shift+End','Control+S':'super+s','Control+F':'super+f','Control+H':'super+h','Control+End':'super+End','Control+A':'super+a','Meta+A':'super+a'});

export function genericDocumentIdentity(raw,{cell,fileName}) {
 const url=new URL(raw);
 assert(url.protocol==='https:'&&url.hostname==='onedrive.live.com'&&!url.username&&!url.password,
  'office_native_origin_invalid');
 assert(/^\/personal\/[a-f0-9]{16}\/_layouts\/15\/Doc\.aspx$/i.test(url.pathname)&&
  url.searchParams.getAll('sourcedoc').length===1&&/^\{[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}\}$/i.test(url.searchParams.get('sourcedoc'))&&
  url.searchParams.getAll('file').length===1&&url.searchParams.get('file')===fileName&&
  ['edit','default'].includes(url.searchParams.get('action')),'office_native_document_identity_invalid');
 assert(['powerpoint-web','excel-web'].includes(cell)&&fileName.endsWith(cell==='powerpoint-web'?'.pptx':'.xlsx'),
  'office_native_cell_extension_invalid');
 return {documentSha256:sha(Buffer.from(url.origin+url.pathname+'|'+url.searchParams.get('sourcedoc').toLowerCase()+'|'+fileName)),
  documentOwnerSha256:sha(Buffer.from('onedrive-personal-document-owner:'+url.pathname.split('/')[2].toLowerCase()))};
}

export function createOfficeOwnedFolderCuaHost({tab,binding,lifecycleDriver,nativeExtractor,listDocumentTabIds}) {
 assert(tab&&tab.id===binding.tab_id&&typeof nativeExtractor==='function'&&typeof listDocumentTabIds==='function',
  'office_bound_native_tab_and_extractor_required');
 for(const name of ['folderInventory','createFromBaseline','doubleDownload','closeDocument','removeOwnedItem'])
  assert(typeof lifecycleDriver?.[name]==='function','office_native_lifecycle_driver_missing');
 const identity=genericDocumentIdentity(binding.edit_url,{cell:binding.cell_id,fileName:binding.file_name});
 assert(/^[a-f0-9]{64}$/.test(binding.account_principal_sha256)&&identity.documentSha256===binding.item_identity_sha256&&identity.documentOwnerSha256===binding.document_owner_sha256,
  'office_account_document_binding_mismatch');
 const clip=structuredClone(binding.clip);
 async function nativeSurface(item) {
  assert(item.item_identity_sha256===identity.documentSha256,'office_native_item_changed');
  assert(genericDocumentIdentity(await tab.url(),{cell:binding.cell_id,fileName:binding.file_name}).documentSha256===identity.documentSha256,
   'office_native_document_navigation_changed');
  const tabs=await listDocumentTabIds();assert(tabs.length===1&&tabs[0]===tab.id,'office_parallel_document_tab');
  const ax=await tab.getAXState({disableDiffing:true,emit:false});
  const metadata=await nativeExtractor({tab,ax,clip,binding});
  // A reviewed extractor must produce actual native boxes/focus/account/folder
  // proofs. A static safe-region declaration is not a target metadata proof.
  assert(metadata?.schema==='office-current-native-surface-v2'&&metadata.native_geometry_observed===true&&
   metadata.account_principal_sha256===binding.account_principal_sha256&&metadata.document_identity_sha256===identity.documentSha256&&
   metadata.folder_scope_sha256===binding.folder_scope_sha256&&Array.isArray(metadata.targets),
   'office_native_metadata_unproved');
  const bytes=Buffer.from(await tab.screenshot({clip}));const size=imageBounds(bytes);
  assert(size.width===clip.width&&size.height===clip.height,'office_crop_not_enforced');
  return {cropped_image_bytes:bytes,native_metadata:metadata};
 }
 async function resolveTargets(item,action,current) {
  const next=(await nativeSurface(item)).native_metadata;
  if(next.native_context_id!==current.context_id||next.modal_id!==current.modal_id)return {status:'missing'};
  const keyboard=['type','key'].includes(action.type);
  if(keyboard&&!action.target&&next.focus_id!==current.focus_id)return {status:'missing'};
  const safe=(target,kind)=>target.visible&&target.enabled&&!target.obscured&&target.actions.includes(kind)&&(!keyboard||target.keyboard);
  const selected=target=>target.ref?current.targets.filter(t=>t.ref===target.ref):current.targets.filter(t=>target.x>=t.bounds[0]&&target.y>=t.bounds[1]&&target.x<t.bounds[0]+t.bounds[2]&&target.y<t.bounds[1]+t.bounds[3]);
  for(const key of ['target','from','to'])if(action[key]){
   const original=selected(action[key]);if(!original.length||original.some(t=>!safe(t,action.type)))return {status:'missing'};
   for(const old of original){const matches=next.targets.filter(t=>t.ref===old.ref);if(matches.length!==1||!safe(matches[0],action.type)||JSON.stringify(matches[0].bounds)!==JSON.stringify(old.bounds))return {status:'missing'};}
   if(!action[key].ref){const hit=next.targets.filter(t=>action[key].x>=t.bounds[0]&&action[key].y>=t.bounds[1]&&action[key].x<t.bounds[0]+t.bounds[2]&&action[key].y<t.bounds[1]+t.bounds[3]);if(hit.length!==original.length||hit.some(t=>!original.some(o=>o.ref===t.ref)))return {status:'missing'};}
  }
  if(keyboard&&!action.target){const focused=next.targets.filter(t=>t.ref===next.focus_id);if(focused.length!==1||!safe(focused[0],action.type))return {status:'missing'};}
  return {status:'current',native_metadata:next};
 }
 async function dispatch(item,action,resolved) {
  assert(resolved.status==='current','office_missing_native_target');
  const meta=resolved.native_metadata;
  const point=t=>{
   if(t.ref){const r=meta.targets.find(x=>x.ref===t.ref);assert(r,'office_target_missing');return [Math.round(r.bounds[0]+r.bounds[2]/2)+clip.x,Math.round(r.bounds[1]+r.bounds[3]/2)+clip.y];}
   return [t.x+clip.x,t.y+clip.y];
  };
  let focusVerified=false;
  if(['click','double_click'].includes(action.type))await tab.click(point(action.target),{clickCount:action.type==='double_click'?2:1});
  else if(action.type==='drag'){await tab.drag(point(action.from),point(action.to));}
  else if(['type','key'].includes(action.type)) {
   if(action.target)await tab.click(point(action.target));
   const focus=(await nativeSurface(item)).native_metadata;
   const required=action.type==='type'?focus.focus_safe_editable:focus.focus_safe_keyboard;
   assert(required===true&&(!action.target?.ref||focus.focus_id===action.target.ref),
    'office_native_keyboard_focus_changed');focusVerified=true;
   if(action.type==='type') {
    assert(action.mode==='insert'||action.mode==='fill'&&focus.focus_fill_scope_verified===true,'office_fill_requires_proved_selection_profile');
    if(action.mode==='fill')await tab.pressKey(null,'super+a');
    await tab.paste(null,action.text,{format:'text'});
   }else{if(['Control+A','Meta+A'].includes(action.key))assert(focus.focus_fill_scope_verified===true,'office_select_all_requires_proved_selection_profile');assert(Object.hasOwn(KEYS,action.key),'office_native_key_unknown');await tab.pressKey(null,KEYS[action.key]);}
  }else if(action.type==='scroll') {
   assert(action.dx===0&&Math.abs(action.dy)<=720&&action.target,'office_native_scroll_invalid');
   await tab.scroll(point(action.target),action.dy>0?'down':'up',Math.abs(action.dy)/clip.height);
  }else if(action.type==='wait')await new Promise(resolve=>setTimeout(resolve,action.duration_ms));
  else assert(action.type==='finish','office_native_action_unsupported');
  return {status:'applied',focus_verified_before_keyboard:focusVerified||!['type','key'].includes(action.type)};
 }
 return Object.freeze({
  capabilities:()=>({surface:'original-office-web',same_account:true,graph:false,native_operations_source_reviewed:true,
   qualified_native_operations:lifecycleDriver.qualification?.actual_native_lifecycle_qualified===true,
   supported_actions:['click','double_click','type','key','scroll','drag','wait','finish'],scroll_units:'pixels',
   unsupported_actions:[]}),
  current_native_surface:nativeSurface,resolve_current_action_targets:resolveTargets,dispatch_native_primitive:dispatch,
  owned_folder_inventory:()=>lifecycleDriver.folderInventory(binding),
  create_from_baseline:(task,baseline,options)=>lifecycleDriver.createFromBaseline(binding,task,baseline,options),
  double_download:(item,options)=>lifecycleDriver.doubleDownload(binding,item,options),
  close_document:item=>lifecycleDriver.closeDocument(binding,item),remove_owned_item:item=>lifecycleDriver.removeOwnedItem(binding,item),
 });
}
