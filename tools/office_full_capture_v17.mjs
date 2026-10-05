/* One full UI capture. The evaluator processes only its private image artifact. */
import * as fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
const sha=b=>createHash('sha256').update(b).digest('hex');
const check=(ok,code)=>{if(!ok)throw new Error(code);};
const schema='office-native-full-capture-crop-v17';
export function createFullCapture({spoolRoot,evidenceRoot,binding}){
 let sequence=0;
 return async({tab,clip})=>{
  check(JSON.stringify(clip)===JSON.stringify(binding.clip),'native_full_crop_rectangle_changed');
  const label='capture-'+String(sequence++).padStart(4,'0'),root=path.join(spoolRoot,'capture-crops.private');await fs.mkdir(root,{recursive:true,mode:0o700});const job=path.join(root,label);await fs.mkdir(job,{mode:0o700});
  const full=Buffer.from(await tab.screenshot());await fs.writeFile(path.join(job,'full.image'),full,{flag:'wx',mode:0o600});
  const request=Buffer.from(JSON.stringify({schema,full_sha256:sha(full),full_size:full.length,clip,one_use:true}));await fs.writeFile(path.join(job,'request.private.json'),request,{flag:'wx',mode:0o600});
  const deadline=Date.now()+10000;let result;
  while(Date.now()<deadline){try{result=JSON.parse(await fs.readFile(path.join(job,'response.private.json')));break;}catch(error){if(error.code!=='ENOENT')throw error;}await new Promise(r=>setTimeout(r,25));}
  check(result?.status==='completed'&&result.schema===schema&&result.request_sha256===sha(request),'native_full_capture_crop_failed_or_timeout');
  const cropped=await fs.readFile(path.join(job,'cropped.png')),proof=await fs.readFile(path.join(job,'proof.private.json'));check(sha(cropped)===result.crop_sha256&&cropped.length===result.crop_size&&sha(proof)===result.proof_sha256,'native_full_capture_crop_artifact_changed');
  const refs={};for(const [name,raw] of [['full.image',full],['cropped.png',cropped],['proof.private.json',proof]]){const saved='full-'+label+'-'+name;await fs.writeFile(path.join(evidenceRoot,saved),raw,{flag:'wx',mode:0o600});refs[name]={path:saved,sha256:sha(raw)};}
  return {cropped_image_bytes:cropped,capture_proof:JSON.parse(proof),capture_refs:refs};
 };
}
