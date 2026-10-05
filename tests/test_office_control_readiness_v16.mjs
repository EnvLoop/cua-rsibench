import assert from 'node:assert/strict';
import * as fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {waitCurrentControlReady} from '../tools/office_control_readiness_v16.mjs';
const url='https://onedrive.live.com/?id=OWN';
function fixture({readyAt=0,count=1,changedAt=Infinity,snapshotMs=0,disabled=false,hidden=false}={}){
 let now=0;const files=[];const forbidden=()=>{throw new Error('builtin wait or native input forbidden');};
 const tab={url:async()=>now>=changedAt?'https://other.invalid/':url,playwright:{domSnapshot:async()=>{now+=snapshotMs;return 'synthetic current control';}},goto:forbidden};
 const node={count:async()=>hidden?(now>=readyAt?0:count):(now>=readyAt?count:0),isVisible:async()=>hidden?now<readyAt:now>=readyAt,isEnabled:async()=>!disabled,click:forbidden,waitFor:forbidden};
 return {options:{tab,expectedURL:url,node,hidden,clock:()=>now,pause:async ms=>{now+=ms;},retain:async(s,i)=>files.push({s,i})},files};
}
let tests=0;
for(const delay of [0,4500,9900]){const f=fixture({readyAt:delay});const value=await waitCurrentControlReady(f.options);assert.equal(value.elapsed_ms,delay);assert.equal(value.maximum_ms,10000);tests++;}
for(const [options,code] of [[{count:2},/ambiguous/],[{readyAt:4500,changedAt:1800},/URL_changed/],[{readyAt:Infinity,snapshotMs:5000},/deadline/],[{disabled:true},/deadline/]]){await assert.rejects(waitCurrentControlReady(fixture(options).options),code);tests++;}
const hidden=await waitCurrentControlReady(fixture({readyAt:4500,hidden:true}).options);assert.equal(hidden.hidden,true);tests++;
const root=await fs.mkdtemp(path.join(os.tmpdir(),'office-control-ready-oexcl-'));await fs.chmod(root,0o700);const real=fixture({readyAt:4500});real.options.retain=async(s,i)=>fs.writeFile(path.join(root,'control-ready-0000-'+i+'.private.txt'),Buffer.from(s),{flag:'wx',mode:0o600});const value=await waitCurrentControlReady(real.options);assert.equal((await fs.readdir(root)).length,value.observations);tests++;
console.log(JSON.stringify({tests,passed:true,original_budget_ms:10000,native_inputs:0,builtin_waits:0,indexed_O_EXCL:true}));
