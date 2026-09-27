/*
 * Evaluator-side PowerPoint for the web controls, frozen before the v8 final
 * source pool is exposed to a model. Run in an authorized cua_repl session.
 * This file contains UI actions only; task data, cloud URLs and downloaded
 * artifacts stay in the evaluator-private work directory. The caller must
 * independently score downloaded OOXML and bind all receipts to the private
 * manifest. A UI success message alone is never an admission or model result.
 */

const normalizeSelected = x => x.replace(/[\u200b-\u200d\ufeff]/g, '').replace(/\s+/g, ' ').trim();

async function findCloudRow(name) {
  await officeTab.reload();
  await officeTab.playwright.getByRole('grid', {name: 'My files'}).waitFor({state: 'visible', timeoutMs: 10000});
  for (let i = 0; i < 10; i++) {
    await officeTab.getAXState({emit: false});
    let r = await officeTab.playwright.evaluate(n => {
      let row = [...document.querySelectorAll('[role=row]')].find(x => x.textContent?.includes(n));
      let box = row?.querySelector('input[data-automationid="selection-checkbox"]');
      let q = box?.getBoundingClientRect();
      return q && {x: q.x, y: q.y, w: q.width, h: q.height};
    }, name);
    if (r && r.h > 0 && r.y >= 190 && r.y <= 820) return {r, scroll_steps: i};
    await officeTab.scroll([765, 600], 'down', 0.5);
  }
  throw Error('cloud row not reachable');
}

async function selectCloudExactV2(name) {
  let {r, scroll_steps} = await findCloudRow(name);
  await officeTab.click([r.x + r.w / 2, r.y + r.h / 2 + 49]);
  let chosen = await officeTab.playwright.evaluate(() =>
    [...document.querySelectorAll('input[data-automationid="selection-checkbox"]')]
      .filter(x => x.checked).map(x => x.closest('[role=row]')?.textContent || ''));
  if (chosen.length !== 1 || !chosen[0].includes(name)) throw Error('exact cloud selection failed');
  return scroll_steps;
}

async function downloadCloudExactV2(name) {
  await selectCloudExactV2(name);
  await officeTab.playwright.getByRole('menuitem', {name: 'More', exact: true}).press('Enter');
  let s = await officeTab.playwright.domSnapshot();
  if (!s.includes('menuitem "Download"')) s = await officeTab.playwright.domSnapshot();
  if (!s.includes('menuitem "Download"')) throw Error('download menu absent');
  await officeTab.pressKey(null, 'ArrowDown');
  s = await officeTab.playwright.domSnapshot();
  if (!s.includes('menuitem "Download" [active]')) throw Error('download not active');
  let dp = officeTab.playwright.waitForEvent('download', {timeoutMs: 15000});
  await officeTab.pressKey(null, 'Enter');
  return await (await dp).path({timeoutMs: 15000});
}

async function openCloud(name) {
  let before = new Set((await (await agent.browsers.get('iab')).tabs.list()).map(x => x.id));
  let sel = await officeTab.playwright.getByRole('menuitem', {name: /1 selected/}).count();
  if (sel) await officeTab.playwright.getByRole('menuitem', {name: /1 selected/}).press('Enter');
  await officeTab.playwright.getByRole('button', {name, exact: true}).press('Enter');
  for (let k = 0; k < 12; k++) {
    let found = (await (await agent.browsers.get('iab')).tabs.list())
      .find(x => x.title === name && !before.has(x.id));
    if (found) return await cua.getTab(found.id, {browser: 'iab'});
    await officeTab.playwright.waitForTimeout(100);
  }
  throw Error('cloud editor tab did not open');
}

async function openCloudExactV2(name) {
  await findCloudRow(name);
  return await openCloud(name);
}

async function uploadOneV3(c) {
  let name = c.baselinePath.split('/').at(-1);
  await officeTab.reload();
  if (await officeTab.playwright.getByRole('button', {name, exact: true}).count() > 0)
    throw Error('file name exists');
  await officeTab.click([85, 150]);
  let s = await officeTab.playwright.domSnapshot();
  if (!s.includes('menuitem "Files upload"')) {
    await officeTab.click([85, 150]);
    s = await officeTab.playwright.domSnapshot();
  }
  if (!s.includes('menuitem "Files upload"')) throw Error('upload menu absent');
  let cp = officeTab.playwright.waitForEvent('filechooser', {timeoutMs: 10000});
  await officeTab.playwright.getByRole('menuitem', {name: 'Files upload'}).press('Enter');
  let chooser = await cp;
  await chooser.setFiles(c.baselinePath);
  let uploaded = false;
  for (let i = 0; i < 20; i++) {
    s = await officeTab.playwright.domSnapshot();
    if (s.includes('Uploaded ' + name + ' to') || s.includes('button "' + name + '"')) {
      uploaded = true;
      break;
    }
    await officeTab.getAXState({emit: false});
  }
  if (!uploaded) throw Error('upload unconfirmed');
  return name;
}

async function editTargetV6(tab, frame, t, from, to) {
  await frame.getByRole('option', {name: /Slide/}).nth(t.slide - 1).click();
  let all = frame.getByText(from, {exact: true});
  let n = await all.count();
  if (n < 1 || n > 3) throw Error('target count unexpected ' + t.key);
  let copied = '';
  for (let attempt = 0; attempt < 3; attempt++) {
    let loc = all.nth(Math.min(attempt, n - 1));
    await loc.waitFor({state: 'visible', timeoutMs: 10000});
    await loc.dblclick();
    await tab.getAXState({emit: false});
    if (t.key === 'ledger') {
      await tab.pressKey(null, 'super+Left');
      await tab.pressKey(null, 'super+shift+Right');
    } else await tab.pressKey(null, 'super+a');
    for (let k = 0; k < 3; k++) {
      await tab.pressKey(null, 'super+c');
      await tab.getAXState({emit: false});
      copied = await tab.clipboard.readText();
      if (normalizeSelected(copied) === normalizeSelected(from)) break;
    }
    if (normalizeSelected(copied) === normalizeSelected(from)) break;
    await tab.pressKey(null, 'Escape');
  }
  if (normalizeSelected(copied) !== normalizeSelected(from))
    throw Error('selection mismatch ' + t.key);
  await tab.clipboard.writeText(to);
  await tab.pressKey(null, 'super+v');
  await frame.getByText(to, {exact: true}).first().waitFor({state: 'visible', timeoutMs: 10000});
}

async function finishNeutralDataV5(c, tab) {
  let frame = tab.playwright.frameLocator('iframe#WacFrame_PowerPoint_0'), ready = false;
  for (let i = 0; i < 20; i++) {
    if (await frame.getByRole('option', {name: /Slide/}).count() === 7) {
      await frame.getByRole('option', {name: /Slide/}).nth(c.targets[0].slide - 1).click();
      if (await frame.getByText(c.targets[0].draft, {exact: true}).count() >= 1) {
        ready = true;
        break;
      }
    }
    await tab.getAXState({emit: false});
  }
  if (!ready) throw Error('editor not ready');
  for (let t of c.targets) await editTargetV6(tab, frame, t, t.draft, t.correct);
  for (let t of c.targets) await editTargetV6(tab, frame, t, t.correct, t.draft);
  for (let t of c.targets) {
    await frame.getByRole('option', {name: /Slide/}).nth(t.slide - 1).click();
    await frame.getByText(t.draft, {exact: true}).first().waitFor({state: 'visible', timeoutMs: 10000});
  }
  let saved = false;
  for (let i = 0; i < 20; i++) {
    let s = await tab.playwright.domSnapshot();
    if (s.includes('Last saved:') || s.includes('Saved to OneDrive')) {
      saved = true;
      break;
    }
    await tab.getAXState({emit: false});
  }
  if (!saved) throw Error('save not confirmed');
  await tab.reload();
  ready = false;
  for (let i = 0; i < 20; i++) {
    if (await frame.getByRole('option', {name: /Slide/}).count() === 7) {
      await frame.getByRole('option', {name: /Slide/}).nth(c.targets[0].slide - 1).click();
      if (await frame.getByText(c.targets[0].draft, {exact: true}).count() >= 1) {
        ready = true;
        break;
      }
    }
    await tab.getAXState({emit: false});
  }
  if (!ready) throw Error('reload not ready');
  for (let t of c.targets) {
    await frame.getByRole('option', {name: /Slide/}).nth(t.slide - 1).click();
    await frame.getByText(t.draft, {exact: true}).first().waitFor({state: 'visible', timeoutMs: 10000});
  }
  let d = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(await tab.url()));
  let cloudSha = [...new Uint8Array(d)].map(x => x.toString(16).padStart(2, '0')).join('');
  let path = await downloadCloudExactV2(c.baselinePath.split('/').at(-1));
  evaluatorNeutralRuns.push({index: c.index, download_path: path, cloud_url_sha256: cloudSha,
                             targets_verified: 4, official_final_admitted: 0});
  await tab.close();
  return {index: c.index, downloaded: true, targets_verified: 4, official_final_admitted: 0};
}

async function neutralControlCaseV5(c) {
  let name = await uploadOneV3(c);
  let tab = await openCloudExactV2(name);
  return await finishNeutralDataV5(c, tab);
}
