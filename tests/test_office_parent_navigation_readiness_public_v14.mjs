import assert from 'node:assert/strict';
import * as fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {waitOwnedParentReady} from '../tools/office_parent_navigation_readiness_v14.mjs';
const url='https://onedrive.live.com/?id=PARENT';
function fixture({headingAt=0,cardAt=0,headings=1,cards=1,changedAt=Infinity,snapshotMs=0}={}){
 let now=0;const snapshots=[],pauses=[];const forbidden=()=>{throw new Error('builtin wait or native input forbidden');};
 const node=(at,count)=>({count:async()=>now>=at?count:0,isVisible:async()=>now>=at,waitFor:forbidden,click:forbidden});
 const tab={url:async()=>now>=changedAt?'https://other.invalid/':url,playwright:{domSnapshot:async()=>{now+=snapshotMs;return 'synthetic parent DOM';}},goto:forbidden};
 return {options:{tab,parentURL:url,heading:node(headingAt,headings),card:node(cardAt,cards),clock:()=>now,retain:async(s,i)=>snapshots.push({s,i}),pause:async ms=>{pauses.push(ms);now+=ms;}},snapshots,pauses};
}
let tests=0;
for(const delay of [0,4500,9900]){const f=fixture({headingAt:delay,cardAt:delay});const value=await waitOwnedParentReady(f.options);assert.equal(value.elapsed_ms,delay);assert.equal(value.maximum_ms,10000);assert.equal(value.readonly,true);tests++;}
for(const [options,code] of [[{headings:2},/heading_ambiguous/],[{cards:2},/card_ambiguous/],[{cardAt:9900,changedAt:1800},/URL_or_deadline_changed/],[{cardAt:Infinity,snapshotMs:5000},/URL_or_deadline_changed/],[{cardAt:Infinity},/observation_cap/]]){const f=fixture(options);await assert.rejects(waitOwnedParentReady(f.options),code);assert.ok(f.snapshots.length<=12);assert.ok(f.pauses.reduce((a,b)=>a+b,0)<10000);tests++;}
const root=await fs.mkdtemp(path.join(os.tmpdir(),'office-parent-ready-oexcl-'));await fs.chmod(root,0o700);
const actual=fixture({headingAt:4500,cardAt:4500});actual.options.retain=async(snapshot,index)=>fs.writeFile(path.join(root,'lifecycle-0000-parent-navigation-ready-'+index+'.private.txt'),Buffer.from(snapshot),{flag:'wx',mode:0o600});
const value=await waitOwnedParentReady(actual.options);assert.equal((await fs.readdir(root)).length,value.observations);assert.ok(value.observations>1);
tests++;
console.log(JSON.stringify({tests,passed:true,native_inputs:0,builtin_waits:0,maximum_ms:10000,maximum_observations:12}));
