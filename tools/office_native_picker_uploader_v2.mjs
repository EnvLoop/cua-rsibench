/* Read-only bounded Open-sheet readiness; original picker input is unchanged. */
import * as fs from 'node:fs/promises';
import path from 'node:path';
import {approvedBaseline,selectApprovedBaseline as original} from './office_native_picker_uploader_v1.mjs';
import {userInfo} from 'node:os';
export {approvedBaseline};

export async function waitOpenSheet(chromeApp,{retain,clock=Date.now,maximumMs=10000,maximumObservations=8}){
 const began=clock();let state;
 for(let i=0;i<maximumObservations;i++){
  if(clock()-began>=maximumMs)throw new Error('native_picker_open_readiness_deadline');
  state=await chromeApp.getAXState({emit:false,disableDiffing:true});
  await retain(`native-picker-readiness-${i}.private.json`,{schema:'office-native-open-sheet-readiness-v2',observation:i,state,native_input:false});
  if(clock()-began>=maximumMs)throw new Error('native_picker_open_readiness_deadline');
  const sheets=state.split('\n').filter(line=>/^\s*\d+\s+sheet\b/.test(line));
  if(sheets.length){
   if(sheets.length!==1||sheets[0].match(/\bID:\s*([^\s,]+)/)?.[1]!=='open-panel')throw new Error('native_picker_foreign_or_ambiguous_sheet');
   return state;
  }
 }
 throw new Error('native_picker_open_readiness_observation_cap');
}

export async function selectApprovedBaseline(args){
 // Original file/owner/hash checks run before any native observation.
 await approvedBaseline(args.filePath,args.expectedSha256);
 const root=await fs.realpath(args.evidenceRoot),info=await fs.lstat(args.evidenceRoot);
 if(root!==args.evidenceRoot||!info.isDirectory()||info.isSymbolicLink()||info.uid!==userInfo().uid||(info.mode&0o077)!==0)throw new Error('native_picker_evidence_root_invalid');
 const retain=async(name,value)=>fs.writeFile(path.join(root,name),JSON.stringify(value)+'\n',{flag:'wx',mode:0o600});
 let first=await waitOpenSheet(args.chromeApp,{retain});
 const app={getAXState:async options=>{if(first!==null){const state=first;first=null;return state;}return args.chromeApp.getAXState(options);},
  pressKey:(...values)=>args.chromeApp.pressKey(...values),setValue:(...values)=>args.chromeApp.setValue(...values),click:(...values)=>args.chromeApp.click(...values)};
 return original({...args,chromeApp:app});
}
