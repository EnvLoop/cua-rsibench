/* Read-only actual Office DOM geometry/focus projection. No DOM mutations. */
import {createHash} from 'node:crypto';
import {genericDocumentIdentity} from './office_owned_folder_cua_host_v2.mjs';
const sha=v=>createHash('sha256').update(v).digest('hex');
const check=(ok,code)=>{if(!ok)throw new Error(code);};

// This function is serialized into the currently bound native document only.
export function inspectNativeOfficeDocument(root,arg) {
 const doc=root.ownerDocument||root;const win=doc.defaultView;const clip=arg.clip;const offset=arg.frameOffset;
 const path=e=>{const pieces=[];for(let n=e;n&&n.nodeType===1;n=n.parentElement){const peers=Array.from(n.parentElement?.children||[]).filter(x=>x.tagName===n.tagName);pieces.push(n.tagName.toLowerCase()+':'+peers.indexOf(n));}return pieces.reverse().join('/');};
 const deny=/^(share|sharing|manage access|copy link|download|print|export|delete|remove|sign out|account|profile|open in desktop app|open in app)(\b|\s)/i;
 const visible=e=>{const r=e.getBoundingClientRect(),s=win.getComputedStyle(e);return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility==='visible'&&s.opacity!=='0';};
 const safeBox=e=>{const r=e.getBoundingClientRect();return [Math.round(r.x+offset.x-clip.x),Math.round(r.y+offset.y-clip.y),Math.round(r.width),Math.round(r.height)];};
 const nodes=Array.from(doc.querySelectorAll('button,input,textarea,canvas,a,[role="button"],[role="textbox"],[role="tab"],[role="menuitem"],[role="gridcell"],[role="option"],[role="treeitem"],[contenteditable="true"],#WACViewPanel,#pptonline-sorter-view-id'));
 const records=[];const focus=doc.activeElement;
 for(const e of nodes){if(!visible(e))continue;const original=safeBox(e);const left=Math.max(0,original[0]),top=Math.max(0,original[1]),right=Math.min(clip.width,original[0]+original[2]),bottom=Math.min(clip.height,original[1]+original[3]);const b=[left,top,right-left,bottom-top];if(b[2]<1||b[3]<1)continue;
  const role=e.getAttribute('role')||'';const label=e.getAttribute('aria-label')||e.getAttribute('title')||(['BUTTON','A'].includes(e.tagName)||['button','menuitem','tab'].includes(role)?e.textContent.trim().slice(0,160):'');
  const link=e.tagName==='A'||e.hasAttribute('href');const unsafe=link||deny.test(label)||e.type==='file'||e.type==='password';
  const editable=!unsafe&&!e.readOnly&&(e.tagName==='TEXTAREA'||e.tagName==='INPUT'&&!['button','checkbox','radio','submit','reset','file','password','hidden'].includes(e.type)||(e.getAttribute('contenteditable')==='true')&&role==='textbox');
  const hit=doc.elementFromPoint(b[0]+b[2]/2+clip.x-offset.x,b[1]+b[3]/2+clip.y-offset.y);const obscured=!hit||!(e===hit||e.contains(hit));
  records.push({native_path:path(e),bounds:b,visible:true,enabled:!unsafe&&!e.disabled&&e.getAttribute('aria-disabled')!=='true',obscured,keyboard:editable,
   actions:unsafe?[]:(editable?['click','double_click','type','key','scroll','drag']:['click','double_click','scroll','drag']),editor_surface:e.tagName==='CANVAS'||role==='gridcell'||e.getAttribute('id')==='WACViewPanel'||editable,focused:e===focus||e.contains(focus),fill_scope:editable&&(e.tagName==='INPUT'||e.tagName==='TEXTAREA'||(e.getAttribute('contenteditable')==='true')&&role==='textbox')});
 }
 const dialogs=Array.from(doc.querySelectorAll('[role="dialog"]')).filter(visible);const safeDialog=dialogs.every(e=>!deny.test(e.getAttribute('aria-label')||e.getAttribute('title')||''));
 const mode=arg.modeSelector?doc.querySelector(arg.modeSelector):null;const modeLabel=mode?.getAttribute(arg.modeAttribute||'aria-label')||'';const editingObserved=arg.modePattern?new RegExp(arg.modePattern).test(modeLabel):false;
 const chrome=Array.from(doc.querySelectorAll('#O365_MainLink_Me,[role="banner"]')).filter(visible);const chromeOutside=chrome.every(e=>{const b=safeBox(e);return b[0]+b[2]<=0||b[1]+b[3]<=0||b[0]>=clip.width||b[1]>=clip.height;});
 return {editing_mode_observed:editingObserved,private_chrome_observed:chrome.length>0,private_chrome_outside_crop:chromeOutside,document_ready:doc.readyState,document_native_url:doc.URL,viewport:[clip.width,clip.height],focus_path:focus?path(focus):'no-focus',targets:records,
  modal_path:dialogs.map(path).join('|'),modal_safe:safeDialog,editor_surface_observed:records.some(r=>r.editor_surface&&r.enabled&&!r.obscured)};
}

export function createOfficeNativeExtractor({binding}) {
 check(binding.clip?.y>=126&&binding.owned_folder_item_ui_receipt?.status==='completed'&&binding.owned_folder_item_ui_receipt?.graph_used===false,
  'native_folder_membership_evidence_required');
 return async ({tab,clip})=>{
  const actual=genericDocumentIdentity(await tab.url(),{cell:binding.cell_id,fileName:binding.file_name});
  check(actual.documentSha256===binding.item_identity_sha256&&actual.accountSha256===binding.account_principal_sha256&&
   binding.owned_folder_item_ui_receipt.item_identity_sha256===actual.documentSha256&&binding.owned_folder_item_ui_receipt.folder_scope_sha256===binding.folder_scope_sha256,
   'native_observed_document_folder_binding_changed');
  let raw;
  if(binding.editor_frame_selector){
   const frame=tab.playwright.locator(binding.editor_frame_selector);check(await frame.count()===1,'native_editor_frame_ambiguous');
   const offset=await frame.evaluate(e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y};});
   raw=await tab.playwright.frameLocator(binding.editor_frame_selector).locator('body').evaluate(inspectNativeOfficeDocument,{clip,frameOffset:offset,modeSelector:binding.native_mode_selector,modeAttribute:binding.native_mode_attribute,modePattern:binding.native_mode_editing_regex},{timeoutMs:10000});
  }else raw=await tab.playwright.locator('body').evaluate(inspectNativeOfficeDocument,{clip,frameOffset:{x:0,y:0},modeSelector:binding.native_mode_selector,modeAttribute:binding.native_mode_attribute,modePattern:binding.native_mode_editing_regex},{timeoutMs:10000});
  check(raw.document_ready==='complete'&&raw.targets.length<=128,'native_editor_geometry_incomplete_or_unbounded');
  const refs=new Map(raw.targets.map(t=>[t.native_path,'n'+sha(Buffer.from(actual.documentSha256+'|'+t.native_path)).slice(0,24)]));
  const focused=raw.targets.filter(t=>t.focused&&t.keyboard).sort((a,b)=>a.bounds[2]*a.bounds[3]-b.bounds[2]*b.bounds[3])[0];
  return {schema:'office-current-native-surface-v2',native_geometry_observed:true,account_principal_sha256:actual.accountSha256,document_identity_sha256:actual.documentSha256,
   folder_scope_sha256:binding.folder_scope_sha256,window_sha256:binding.window_sha256,owned_document_editing:raw.editor_surface_observed&&raw.editing_mode_observed,private_header_excluded:raw.private_chrome_observed&&raw.private_chrome_outside_crop,
   viewport:raw.viewport,native_context_id:sha(Buffer.from(actual.documentSha256+'|'+raw.modal_path)),modal_id:raw.modal_path?(raw.modal_safe?'owned-editor-dialog':'external-dialog'):'none',
   focus_id:focused?refs.get(focused.native_path):'f'+sha(Buffer.from(raw.focus_path)).slice(0,24),focus_safe_editable:!!focused,focus_fill_scope_verified:!!focused?.fill_scope,
   actual_native_folder_membership_receipt_sha256:binding.owned_folder_item_ui_receipt_sha256,
   targets:raw.targets.map(t=>({ref:refs.get(t.native_path),bounds:t.bounds,visible:t.visible,enabled:t.enabled,obscured:t.obscured,keyboard:t.keyboard,actions:t.actions}))};
 };
}
