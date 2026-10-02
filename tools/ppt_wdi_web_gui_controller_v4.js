/*
 * Evaluator-side PowerPoint web controller under the dated saved-artifact
 * amendment. Load v1, the pre-task open helper, and v2 before this file in an
 * authorized cua_repl session. PowerPoint GUI edits are required, while the
 * independent downloaded PPTX is the authoritative saved-state observation.
 * This controller returns two read-only downloads for outside OOXML scoring.
 */

async function twoCloudDownloadsV4(name) {
  const files = [];
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      files.push(await downloadCloudExactV2(name));
    } catch (error) {
      if (String(error).includes('exact cloud selection failed')) {
        await officeTab.reload();
        files.push(await downloadCloudExactV2(name));
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

async function finishNeutralSavedArtifactV4(c, tab) {
  const name = c.baselinePath.split('/').at(-1);
  const frame = tab.playwright.frameLocator('iframe#WacFrame_PowerPoint_0');
  await waitForSevenSlidesV2(tab, frame);
  for (const target of c.targets)
    await commitTargetV7(tab, frame, target,
                         target.draft, target.correct);
  for (const target of c.targets)
    await commitTargetV7(tab, frame, target,
                         target.correct, target.draft);
  await tab.getAXState({emit: false});
  await tab.reload();
  await tab.close();
  const downloads = await twoCloudDownloadsV4(name);
  evaluatorNeutralRuns.push({index: c.index, download_paths: downloads,
                             targets_attempted: c.targets.length,
                             artifact_readback_required: true,
                             official_final_admitted: 0});
  return {index: c.index, downloads,
          targets_attempted: c.targets.length,
          artifact_readback_required: true,
          official_final_admitted: 0};
}

async function neutralControlSavedArtifactV4(c) {
  const name = await uploadOneV3(c);
  const tab = await openAfterConfirmedUploadV1(name);
  return await finishNeutralSavedArtifactV4(c, tab);
}

async function finishRoleSavedArtifactV4(c, tab, role) {
  if (!['positive', 'near_miss', 'fresh_reset', 'collateral'].includes(role))
    throw Error('unregistered PowerPoint role');
  const name = c.baselinePath.split('/').at(-1);
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
  const downloads = await twoCloudDownloadsV4(name);
  evaluatorRoleRuns.push({index: c.index, role, download_paths: downloads,
                          artifact_readback_required: true,
                          official_final_admitted: 0});
  return {index: c.index, role, downloads,
          artifact_readback_required: true,
          official_final_admitted: 0};
}

async function roleControlSavedArtifactV4(c, role) {
  const name = await uploadOneV3(c);
  const tab = await openAfterConfirmedUploadV1(name);
  return await finishRoleSavedArtifactV4(c, tab, role);
}
