import test from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {pathToFileURL} from 'node:url';
import {approvedBaseline,selectApprovedBaseline} from '../tools/office_native_picker_uploader_v1.mjs';

async function fixture(t){
 const root=await fs.realpath(await fs.mkdtemp(path.join(os.tmpdir(),'office-picker-test-')));await fs.chmod(root,0o700);
 t.after(()=>fs.rm(root,{recursive:true,force:true}));
 const file=path.join(root,'baseline.pptx'),raw=Buffer.from('Synthetic test bytes, not a benchmark artifact');
 await fs.writeFile(file,raw,{mode:0o600});const sha=createHash('sha256').update(raw).digest('hex');
 return {root,file,sha};
}

test('changed baseline and symlink refuse before native input',async t=>{
 const f=await fixture(t);let calls=0;const app={getAXState:async()=>{calls++;return ''}};
 await assert.rejects(selectApprovedBaseline({chromeApp:app,filePath:f.file,expectedSha256:'0'.repeat(64),evidenceRoot:f.root}),/baseline_changed/);
 const link=path.join(f.root,'link.pptx');await fs.symlink(f.file,link);
 await assert.rejects(approvedBaseline(link,f.sha),/not_private_owned/);assert.equal(calls,0);
});

test('foreign picker sheet refuses without key presses',async t=>{
 const f=await fixture(t);let keys=0;
 await assert.rejects(selectApprovedBaseline({chromeApp:{getAXState:async()=> '1 sheet ID: unrelated',pressKey:async()=>keys++},filePath:f.file,expectedSha256:f.sha,evidenceRoot:f.root}),/expected_open_sheet/);
 assert.equal(keys,0);
});

test('wrong selected file refuses before the Open click',async t=>{
 const f=await fixture(t);let clicks=0;const states=['1 sheet ID: open-panel','2 sheet ID: GoToWindow\n 3 text field ID: PathTextField','1 sheet ID: open-panel\n 4 text field (selected, settable) URL: file:///foreign.pptx\n 5 button Open, ID: OKButton'];
 const app={getAXState:async()=>states.shift(),pressKey:async()=>{},setValue:async()=>{},click:async()=>clicks++};
 await assert.rejects(selectApprovedBaseline({chromeApp:app,filePath:f.file,expectedSha256:f.sha,evidenceRoot:f.root}),/selected_file_not_exact/);assert.equal(clicks,0);
});

test('baseline changed during selection refuses before the Open click',async t=>{
 const f=await fixture(t);let clicks=0;let count=0;
 const states=['1 sheet ID: open-panel','2 sheet ID: GoToWindow\n 3 text field ID: PathTextField',`1 sheet ID: open-panel\n 4 text field (selected, settable) URL: ${pathToFileURL(f.file).href}\n 5 button Open, ID: OKButton`];
 const app={getAXState:async()=>{if(++count===3)await fs.writeFile(f.file,'Changed');return states.shift()},pressKey:async()=>{},setValue:async()=>{},click:async()=>clicks++};
 await assert.rejects(selectApprovedBaseline({chromeApp:app,filePath:f.file,expectedSha256:f.sha,evidenceRoot:f.root}),/baseline_changed/);assert.equal(clicks,0);
});

test('disabled Open waits through fresh full state without counting the focus footer twice',async t=>{
 const f=await fixture(t);const clicks=[];const selected=`1 sheet ID: open-panel\n 4 text field (selected, settable) URL: ${pathToFileURL(f.file).href}`;
 const states=['1 sheet ID: open-panel','2 sheet ID: GoToWindow\n 3 text field ID: PathTextField\nThe focused UI element is 3 text field ID: PathTextField',selected+'\n 5 button (disabled) Open, ID: OKButton',selected+'\n 5 button Open, ID: OKButton\nThe focused UI element is 5 button Open, ID: OKButton'];
 const app={getAXState:async options=>{assert.equal(options.disableDiffing,true);return states.shift()},pressKey:async()=>{},setValue:async()=>{},click:async index=>clicks.push(index)};
 const result=await selectApprovedBaseline({chromeApp:app,filePath:f.file,expectedSha256:f.sha,evidenceRoot:f.root});
 assert.deepEqual(clicks,[5]);assert.equal(result.native_picker_open_clicked,true);assert.equal(result.upload_server_state_verified,false);
});

test('two real Open controls refuse rather than selecting a convenient first match',async t=>{
 const f=await fixture(t);let clicks=0;
 const states=['1 sheet ID: open-panel','2 sheet ID: GoToWindow\n 3 text field ID: PathTextField',`1 sheet ID: open-panel\n 4 text field (selected, settable) URL: ${pathToFileURL(f.file).href}\n 5 button Open, ID: OKButton\n 6 button Open, ID: OKButton`];
 const app={getAXState:async()=>states.shift(),pressKey:async()=>{},setValue:async()=>{},click:async()=>clicks++};
 await assert.rejects(selectApprovedBaseline({chromeApp:app,filePath:f.file,expectedSha256:f.sha,evidenceRoot:f.root}),/control_missing_or_ambiguous/);assert.equal(clicks,0);
});
