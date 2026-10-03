/* Evaluator-owned normal macOS file selection; no permission or network API. */
import * as fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import {userInfo} from 'node:os';

const check=(condition,code)=>{if(!condition)throw new Error(code);};
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');

export async function approvedBaseline(filePath,expectedSha256){
 check(path.isAbsolute(filePath)&&/^[0-9a-f]{64}$/.test(expectedSha256),'native_picker_baseline_arguments_invalid');
 const info=await fs.lstat(filePath);
 check(info.isFile()&&!info.isSymbolicLink()&&info.uid===userInfo().uid&&(info.mode&0o077)===0,'native_picker_baseline_not_private_owned_file');
 check(await fs.realpath(filePath)===filePath,'native_picker_baseline_parent_symlink_forbidden');
 check(['.pptx','.xlsx'].includes(path.extname(filePath).toLowerCase()),'native_picker_baseline_extension_invalid');
 const raw=await fs.readFile(filePath);check(sha(raw)===expectedSha256,'native_picker_baseline_changed');
 return {path:filePath,sha256:expectedSha256,bytes:raw.length};
}

function uniqueIndex(state,pattern){
 const rows=state.split('\n').filter(line=>/^\s*\d+\s/.test(line)&&pattern.test(line));
 check(rows.length===1,'native_picker_control_missing_or_ambiguous');
 const match=rows[0].match(/^\s*(\d+)\s/);check(match,'native_picker_control_index_missing');
 return Number(match[1]);
}

export async function selectApprovedBaseline({chromeApp,filePath,expectedSha256,evidenceRoot}){
 const baseline=await approvedBaseline(filePath,expectedSha256);
 const root=await fs.realpath(evidenceRoot),info=await fs.lstat(evidenceRoot);
 check(root===evidenceRoot&&info.isDirectory()&&!info.isSymbolicLink()&&info.uid===userInfo().uid&&(info.mode&0o077)===0,'native_picker_evidence_root_invalid');
 const retain=async(name,value)=>fs.writeFile(path.join(root,name),JSON.stringify(value)+'\n',{flag:'wx',mode:0o600});
 let state=await chromeApp.getAXState({emit:false,disableDiffing:true});
 check(/sheet.*ID: open-panel/.test(state),'native_picker_expected_open_sheet_required');
 await retain('native-picker-intent.private.json',{schema:'office-evaluator-native-picker-v1',baseline_sha256:baseline.sha256,baseline_bytes:baseline.bytes,permission_changes:false,actor_access:false});
 await chromeApp.pressKey('super+shift+g');state=await chromeApp.getAXState({emit:false,disableDiffing:true});
 check(/sheet.*ID: GoToWindow/.test(state),'native_picker_go_to_sheet_required');
 await chromeApp.setValue(uniqueIndex(state,/text field.*ID: PathTextField/),baseline.path);
 await chromeApp.pressKey('Return');state=await chromeApp.getAXState({emit:false,disableDiffing:true});
 check(/sheet.*ID: open-panel/.test(state),'native_picker_open_sheet_not_restored');
 const uri=pathToFileURL(baseline.path).href;
 let button;
 for(let sample=0;sample<3;sample++){
  check(/sheet.*ID: open-panel/.test(state),'native_picker_open_sheet_not_restored');
  const selected=state.split('\n').filter(line=>{
   if(!/^\s*\d+\s/.test(line)||!/text field \(selected/.test(line))return false;
   const observed=line.match(/\bURL:\s*(file:\/\/[^\s,]+)/);
   return observed?.[1]===uri;
  });
  check(selected.length===1,'native_picker_selected_file_not_exact_baseline');
  const controls=state.split('\n').filter(line=>/^\s*\d+\s/.test(line)&&/button Open, ID: OKButton/.test(line));
  check(controls.length<=1,'native_picker_control_missing_or_ambiguous');
  if(controls.length===1){button=uniqueIndex(state,/button Open, ID: OKButton/);break;}
  if(sample<2)state=await chromeApp.getAXState({emit:false,disableDiffing:true});
 }
 check(Number.isInteger(button),'native_picker_enabled_open_button_unavailable');
 await approvedBaseline(filePath,expectedSha256);
 await retain('native-picker-selected.private.json',{source_sha256:baseline.sha256,selected_file_exact:true,native_control:'OKButton',private_input_only:true});
 await chromeApp.click(button);
 return {schema:'office-evaluator-native-picker-v1',source_sha256:baseline.sha256,native_picker_open_clicked:true,upload_server_state_verified:false,permission_changes:false,actor_api:false};
}
