/*
 * Prospective evaluator-side PowerPoint web baseline preparation. Load v1,
 * the pre-task open helper, v2 and v4 first. Task data and cloud file names
 * stay private. This controller never awards admission: the caller must
 * independently inspect the two downloaded PPTX files from each phase.
 *
 * The positive phase is durably saved before restoration. PowerPoint can
 * rewrite a native chart on the first saved positive edit even when a
 * same-session edit/restoration appears neutral in the editor. Such a rewrite
 * must become visible before a source-bound neutral baseline is accepted.
 */

// A long-lived test account may have more than one screen of files. The v1
// file lookup capped at ten half-screen scrolls; retain exact-name selection
// while extending that navigation bound. No file is selected by position.
async function findCloudRowV5(name) {
  await officeTab.reload();
  await officeTab.playwright.getByRole('grid', {name: 'My files'})
    .waitFor({state: 'visible', timeoutMs: 10000});
  for (let i = 0; i < 80; i++) {
    await officeTab.getAXState({emit: false});
    const r = await officeTab.playwright.evaluate(n => {
      const row = [...document.querySelectorAll('[role=row]')]
        .find(x => x.textContent?.includes(n));
      const box = row?.querySelector('input[data-automationid="selection-checkbox"]');
      const q = box?.getBoundingClientRect();
      return q && {x: q.x, y: q.y, w: q.width, h: q.height};
    }, name);
    if (r && r.h > 0 && r.y >= 190 && r.y <= 820)
      return {r, scroll_steps: i};
    await officeTab.scroll([765, 600], 'down', 0.5);
  }
  throw Error('exact cloud row not reachable within long-list bound');
}

async function openAfterConfirmedUploadV5(name) {
  for (let attempt = 0; attempt < 3; attempt++) {
    const already = (await (await agent.browsers.get('iab')).tabs.list())
      .filter(tab => tab.title === name);
    if (already.length === 1)
      return await cua.getTab(already[0].id, {browser: 'iab'});
    if (already.length > 1) throw Error('ambiguous Office editor tabs');
    await findCloudRowV5(name);
    try {
      return await openCloud(name);
    } catch (error) {
      if (error.message !== 'Cloud editor tab did not open') throw error;
      await officeTab.getAXState({emit: false});
    }
  }
  throw Error('pre-task Office editor did not open after bounded retry');
}

async function downloadCloudExactV5(name) {
  const {r} = await findCloudRowV5(name);
  await officeTab.click([r.x + r.w / 2, r.y + r.h / 2 + 49]);
  const chosen = await officeTab.playwright.evaluate(() =>
    [...document.querySelectorAll('input[data-automationid="selection-checkbox"]')]
      .filter(x => x.checked)
      .map(x => x.closest('[role=row]')?.textContent || ''));
  if (chosen.length !== 1 || !chosen[0].includes(name))
    throw Error('exact cloud selection failed');
  await officeTab.playwright.getByRole('menuitem', {name: 'More', exact: true})
    .press('Enter');
  let state = await officeTab.playwright.domSnapshot();
  if (!state.includes('menuitem "Download"'))
    state = await officeTab.playwright.domSnapshot();
  if (!state.includes('menuitem "Download"'))
    throw Error('download menu absent');
  await officeTab.pressKey(null, 'ArrowDown');
  state = await officeTab.playwright.domSnapshot();
  if (!state.includes('menuitem "Download" [active]'))
    throw Error('download not active');
  const pending = officeTab.playwright.waitForEvent('download', {timeoutMs: 15000});
  await officeTab.pressKey(null, 'Enter');
  return await (await pending).path({timeoutMs: 15000});
}

async function twoCloudDownloadsV5(name) {
  const files = [];
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      files.push(await downloadCloudExactV5(name));
    } catch (error) {
      if (String(error).includes('exact cloud selection failed')) {
        await officeTab.reload();
        files.push(await downloadCloudExactV5(name));
      } else {
        throw error;
      }
    }
  }
  if (files.length !== 2 || !files[0] || !files[1] ||
      files[0] === files[1])
    throw Error('two distinct read-only cloud downloads required');
  return files;
}

async function finishNeutralPersistedPositiveV5(c) {
  const name = c.baselinePath.split('/').at(-1);
  let tab = await openAfterConfirmedUploadV5(name);
  let frame = tab.playwright.frameLocator('iframe#WacFrame_PowerPoint_0');
  await waitForSevenSlidesV2(tab, frame);
  await verifyTargetSetV2(tab, frame, c.targets, 'draft');
  for (const target of c.targets)
    await commitTargetV7(tab, frame, target, target.draft, target.correct);
  await tab.reload();
  await waitForSevenSlidesV2(tab, frame);
  await verifyTargetSetV2(tab, frame, c.targets, 'correct');
  await tab.close();
  const savedPositive = await twoCloudDownloadsV5(name);

  // Reopen the same cloud file only after a durable positive pair exists.
  // Outside OOXML scoring must reject a stale or divergent positive pair.
  tab = await openAfterConfirmedUploadV5(name);
  frame = tab.playwright.frameLocator('iframe#WacFrame_PowerPoint_0');
  await waitForSevenSlidesV2(tab, frame);
  await verifyTargetSetV2(tab, frame, c.targets, 'correct');
  for (const target of c.targets)
    await commitTargetV7(tab, frame, target, target.correct, target.draft);
  await tab.reload();
  await waitForSevenSlidesV2(tab, frame);
  await verifyTargetSetV2(tab, frame, c.targets, 'draft');
  await tab.close();
  const savedNeutral = await twoCloudDownloadsV5(name);

  return {index: c.index, savedPositive, savedNeutral,
          targetsAttempted: c.targets.length,
          artifactReadbackRequired: true,
          officialFinalAdmitted: 0};
}

async function neutralControlPersistedPositiveV5(c) {
  await uploadOneV3(c);
  return await finishNeutralPersistedPositiveV5(c);
}

async function roleControlSavedArtifactV5(c, role) {
  if (!['positive', 'near_miss', 'fresh_reset', 'collateral'].includes(role))
    throw Error('unregistered PowerPoint role');
  const name = await uploadOneV3(c);
  const tab = await openAfterConfirmedUploadV5(name);
  const frame = tab.playwright.frameLocator('iframe#WacFrame_PowerPoint_0');
  await waitForSevenSlidesV2(tab, frame);
  if (role === 'positive' || role === 'near_miss') {
    for (const target of c.targets) {
      if (role === 'near_miss' && target.key === c.near_miss_omits)
        continue;
      await commitTargetV7(tab, frame, target,
                           target.draft, target.correct);
    }
  } else if (role === 'collateral') {
    if (!c.collateral || c.collateral.key !== 'collateral' ||
        c.collateral.slide !== 3 || !c.collateral.draft ||
        !c.collateral.corrupt)
      throw Error('collateral shape not bound');
    await commitTargetV7(tab, frame, c.collateral,
                         c.collateral.draft, c.collateral.corrupt);
  }
  await tab.getAXState({emit: false});
  await tab.reload();
  await tab.close();
  const downloads = await twoCloudDownloadsV5(name);
  return {index: c.index, role, downloads,
          artifactReadbackRequired: true,
          officialFinalAdmitted: 0};
}
