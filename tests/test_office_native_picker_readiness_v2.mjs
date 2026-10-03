import test from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {pathToFileURL} from 'node:url';
import {waitOpenSheet,selectApprovedBaseline} from '../tools/office_native_picker_uploader_v2.mjs';

test('delayed exact Open sheet is observed without input',async()=>{
 const states=['1 standard window','1 standard window','9 sheet Description: open, ID: open-panel'];let input=0;const rows=[];
 const state=await waitOpenSheet({getAXState:async options=>{assert.equal(options.disableDiffing,true);return states.shift();},pressKey:async()=>input++},{retain:async(n,r)=>rows.push(r)});
 assert.match(state,/open-panel/);assert.equal(input,0);assert.equal(rows.length,3);
});
test('foreign or multiple sheets refuse without waiting for a convenient later sheet',async()=>{
 for(const state of ['1 sheet ID: unrelated','1 sheet ID: open-panel\n2 sheet ID: open-panel']){
  let calls=0;await assert.rejects(waitOpenSheet({getAXState:async()=>{calls++;return state;}},{retain:async()=>{}}),/foreign_or_ambiguous/);assert.equal(calls,1);
 }
});
test('a file named sheet is not an additional native sheet',async()=>{
 const state=await waitOpenSheet({getAXState:async()=> '1 sheet ID: open-panel\n2 text field Value: sheet 1.pptx'},{retain:async()=>{}});
 assert.match(state,/open-panel/);
});
test('observation and elapsed-time limits stop read-only readiness',async()=>{
 let calls=0;await assert.rejects(waitOpenSheet({getAXState:async()=>{calls++;return '1 standard window';}},{retain:async()=>{},maximumObservations:2}),/observation_cap/);assert.equal(calls,2);
 let now=0;await assert.rejects(waitOpenSheet({getAXState:async()=>{now=11;return '1 sheet ID: open-panel';}},{retain:async()=>{},clock:()=>now,maximumMs:10}),/deadline/);
});
test('full wrapper retains original exact file checks and one native Open click',async t=>{
 const root=await fs.realpath(await fs.mkdtemp(path.join(os.tmpdir(),'office-ready-test-')));await fs.chmod(root,0o700);t.after(()=>fs.rm(root,{recursive:true,force:true}));
 const file=path.join(root,'baseline.pptx'),raw=Buffer.from('test fixture only');await fs.writeFile(file,raw,{mode:0o600});const digest=createHash('sha256').update(raw).digest('hex');
 const states=['1 standard window','2 sheet ID: open-panel','3 sheet ID: GoToWindow\n4 text field ID: PathTextField',`2 sheet ID: open-panel\n5 text field (selected, settable) URL: ${pathToFileURL(file).href}\n6 button Open, ID: OKButton`];const keys=[],values=[],clicks=[];
 const app={getAXState:async()=>states.shift(),pressKey:async k=>keys.push(k),setValue:async(i,v)=>values.push([i,v]),click:async i=>clicks.push(i)};
 const result=await selectApprovedBaseline({chromeApp:app,filePath:file,expectedSha256:digest,evidenceRoot:root});assert.equal(result.native_picker_open_clicked,true);assert.deepEqual(keys,['super+shift+g','Return']);assert.deepEqual(values,[[4,file]]);assert.deepEqual(clicks,[6]);assert.equal(result.upload_server_state_verified,false);
});
