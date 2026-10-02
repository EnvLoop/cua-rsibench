/* Evaluator-only actual signed-in UI principal; document CID is not identity. */
import {createHash} from 'node:crypto';
import * as fs from 'node:fs/promises';
import * as os from 'node:os';
const sha=v=>createHash('sha256').update(v).digest('hex');
const check=(v,code)=>{if(!v)throw new Error(code);};
export function signedInPrincipalIdentity(raw,{kind='email'}={}) {
 check(typeof raw==='string'&&raw.length>0&&raw.length<=512,'signed_in_ui_identity_missing');
 const cleaned=raw.normalize('NFKC').trim().replace(/\s+/g,' ');
 let identifier;
 if(kind==='email'){
  const matches=cleaned.match(/[A-Za-z0-9.!#$%&'*+\/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,}/g)||[];
  check(new Set(matches.map(v=>v.toLowerCase())).size===1,'signed_in_ui_email_ambiguous');identifier=matches[0].toLowerCase();
 }else{check(kind==='label','signed_in_ui_identity_kind_invalid');identifier=cleaned.toLowerCase();}
 return {principalSha256:sha(Buffer.from('office-signed-in-ui:'+kind+':'+identifier)),kind};
}
export function signedInPrincipalFromPopup(raw){
 check(typeof raw==='string'&&raw.length>0&&raw.length<=256000,'initial_account_popup_size_invalid');
 const controls=[...raw.matchAll(/button \"Sign out from ([^\"]+)\"/g)].map(m=>m[1]);
 check(controls.length===1,'initial_native_signout_principal_control_ambiguous');
 return signedInPrincipalIdentity(controls[0],{kind:'email'});
}
export async function observeSignedInPrincipal({tab,profile,expectedSha256,retain=null}) {
 check(profile?.schema==='office-signed-in-ui-principal-profile-v3'&&profile.source_reviewed===true&&Array.isArray(profile.open_steps)&&profile.identity_control,'actual_signed_in_ui_profile_required');
 const scope=profile.identity_frame_selector?tab.playwright.frameLocator(profile.identity_frame_selector):tab.playwright;
 const locator=step=>step.selector?scope.locator(step.selector):scope.getByRole(step.role,{name:step.name,exact:true});
 const visible=async step=>{const node=locator(step);check(await node.count()===1&&await node.isVisible()&&await node.isEnabled(),'signed_in_ui_control_not_unique_visible');return node;};
 const refs=[];let opened=false;
 if(profile.mode==='passive_label_continuity'){
  check(profile.open_steps.length===0&&profile.initial_popup_ref&&profile.initial_control_ref,'passive_account_witness_required_without_popup');
  const read=async ref=>{check(ref&&Object.keys(ref).sort().join(',')==='path,sha256','private_account_witness_reference_invalid');const info=await fs.lstat(ref.path);check(info.isFile()&&!info.isSymbolicLink()&&(info.mode&0o077)===0&&info.uid===os.userInfo().uid,'private_account_witness_file_unsafe');const raw=await fs.readFile(ref.path);check(sha(raw)===ref.sha256,'private_account_witness_bytes_changed');return raw;};
  const popup=await read(profile.initial_popup_ref);const identity=signedInPrincipalFromPopup(popup.toString());
  check(identity.principalSha256===expectedSha256,'initial_signed_in_ui_principal_changed');
  const baseline=JSON.parse((await read(profile.initial_control_ref)).toString());const node=await visible(profile.identity_control);
  const current=await node.evaluate(e=>({tag:e.tagName,id:e.id||null,attributes:Array.from(e.attributes).filter(a=>['title','aria-label'].includes(a.name)).map(a=>({name:a.name,value:a.value})),image:e.querySelector('img')?{alt:e.querySelector('img').alt}:null}),undefined,{timeoutMs:10000});
  const projection=v=>({tag:v.tag,id:v.id||null,attributes:(v.attributes||[]).map(a=>Array.isArray(a)?{name:a[0],value:a[1]}:a).sort((a,b)=>a.name.localeCompare(b.name)),image:v.image||null});
  check(JSON.stringify(projection(current))===JSON.stringify(projection(baseline)),'passive_account_display_label_changed');
  return {...identity,nativeUiObserved:true,exactLiveEmailObserved:false,continuityFromInitialSignedInUiWitness:true,initialWitnessSha256:profile.initial_popup_ref.sha256,controlWitnessSha256:profile.initial_control_ref.sha256,rawRefs:refs};
 }
 try{
  for(const step of profile.open_steps){await (await visible(step)).click({timeoutMs:10000});opened=true;}
  const control=await visible(profile.identity_control);
  const raw=await control.evaluate((e,arg)=>arg.attribute?e.getAttribute(arg.attribute):e.textContent.trim(),{attribute:profile.identity_attribute||null},{timeoutMs:10000});
  const identity=signedInPrincipalIdentity(raw,{kind:profile.identity_kind||'email'});
  check(identity.principalSha256===expectedSha256,'actual_signed_in_principal_changed');
  if(retain)refs.push(await retain(Buffer.from(await tab.playwright.domSnapshot())));
  return {...identity,nativeUiObserved:true,exactLiveEmailObserved:profile.identity_kind!=='label',continuityFromInitialSignedInUiWitness:false,rawRefs:refs};
 }finally{
  if(opened){check(profile.close_key==='Escape','signed_in_ui_popup_close_profile_required');await tab.pressKey(null,'Escape');}
 }
}
