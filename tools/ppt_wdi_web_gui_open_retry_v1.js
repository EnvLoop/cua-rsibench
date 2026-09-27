/*
 * Evaluator-only pre-task OneDrive open retry. Upload confirmation may precede
 * Office editor availability. This helper retries only before any edit or
 * verifier readback; a partial GUI control is never restarted silently.
 * Load after ppt_wdi_web_gui_controller_v1.js in the same cua_repl session.
 */

async function openAfterConfirmedUploadV1(name) {
  for (let attempt = 0; attempt < 3; attempt++) {
    const already = (await (await agent.browsers.get('iab')).tabs.list())
      .filter(tab => tab.title === name);
    if (already.length === 1) return await cua.getTab(already[0].id, {browser: 'iab'});
    if (already.length > 1) throw Error('ambiguous Office editor tabs');
    try {
      return await openCloudExactV2(name);
    } catch (error) {
      if (error.message !== 'Cloud editor tab did not open') throw error;
      await officeTab.getAXState({emit: false});
    }
  }
  throw Error('pre-task Office editor did not open after bounded retry');
}

async function neutralControlAfterUploadV1(c) {
  const name = await uploadOneV3(c);
  const tab = await openAfterConfirmedUploadV1(name);
  return await finishNeutralDataV5(c, tab);
}

async function durableRoleAfterUploadV1(c, role) {
  const name = await uploadOneV3(c);
  const first = await openAfterConfirmedUploadV1(name);
  await finishRoleDataV1(c, first, role);
  const fresh = await openAfterConfirmedUploadV1(name);
  const frame = fresh.playwright.frameLocator('iframe#WacFrame_PowerPoint_0');
  await frame.getByRole('option', {name: /Slide/}).nth(0)
    .waitFor({state: 'visible', timeoutMs: 15000});
  for (const target of c.targets) {
    const expected = (role === 'positive' ||
                      (role === 'near_miss' &&
                       target.key !== c.near_miss_omits))
      ? target.correct : target.draft;
    await frame.getByRole('option', {name: /Slide/})
      .nth(target.slide - 1).click();
    await frame.getByText(expected, {exact: true}).first()
      .waitFor({state: 'visible', timeoutMs: 10000});
  }
  if (role === 'collateral') {
    await frame.getByRole('option', {name: /Slide/})
      .nth(c.collateral.slide - 1).click();
    await frame.getByText(c.collateral.corrupt, {exact: true}).first()
      .waitFor({state: 'visible', timeoutMs: 10000});
  }
  await fresh.close();
  const path = await downloadCloudExactV2(name);
  evaluatorRoleRuns.push({index: c.index, role, download_path: path,
                          fresh_editor_readback: true,
                          official_final_admitted: 0});
  return {index: c.index, role, downloaded: true,
          fresh_editor_readback: true, official_final_admitted: 0};
}
