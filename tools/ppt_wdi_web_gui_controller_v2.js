/*
 * Train-calibrated PowerPoint web baseline controller. Load after the v1
 * controller and pre-task open helper in the same authorized cua_repl session.
 * Its artifact still requires independent OOXML scoring and source binding.
 */

async function commitTargetV7(tab, frame, target, from, to) {
  for (let attempt = 0; attempt < 3; attempt++) {
    let editError = null;
    try {
      await editTargetV6(tab, frame, target, from, to);
    } catch (error) {
      editError = error;
    }
    // PowerPoint can keep a pasted span in its editing shadow root. Exit text
    // mode and observe the slide before accepting the write or retrying a
    // pre-paste selection mismatch. No new file/task attempt is dispatched.
    await tab.pressKey(null, 'Escape');
    await tab.pressKey(null, 'Escape');
    await frame.getByRole('option', {name: /Slide/})
      .nth(target.slide - 1).click();
    await tab.getAXState({emit: false});
    if (await frame.getByText(to, {exact: true}).count() >= 1) return;
    if (await frame.getByText(from, {exact: true}).count() < 1 ||
        attempt === 2)
      throw editError || Error('target edit not committed ' + target.key);
  }
}

async function verifyTargetSetV2(tab, frame, targets, field) {
  for (const target of targets) {
    await frame.getByRole('option', {name: /Slide/})
      .nth(target.slide - 1).click();
    let found = false;
    for (let i = 0; i < 10; i++) {
      if (await frame.getByText(target[field], {exact: true}).count() >= 1) {
        found = true;
        break;
      }
      await tab.getAXState({emit: false});
    }
    if (!found) throw Error('target readback failed ' + target.key);
  }
}

async function waitForSevenSlidesV2(tab, frame) {
  for (let i = 0; i < 20; i++) {
    if (await frame.getByRole('option', {name: /Slide/}).count() === 7)
      return;
    await tab.getAXState({emit: false});
  }
  throw Error('PowerPoint editor seven-slide readiness missing');
}

async function finishNeutralTwoPhaseV2(c, tab) {
  const name = c.baselinePath.split('/').at(-1);
  const frame = tab.playwright.frameLocator('iframe#WacFrame_PowerPoint_0');
  await waitForSevenSlidesV2(tab, frame);
  await verifyTargetSetV2(tab, frame, c.targets, 'draft');
  for (const target of c.targets)
    await commitTargetV7(tab, frame, target, target.draft, target.correct);
  await tab.reload();
  await waitForSevenSlidesV2(tab, frame);
  await verifyTargetSetV2(tab, frame, c.targets, 'correct');
  for (const target of c.targets)
    await commitTargetV7(tab, frame, target, target.correct, target.draft);
  await tab.reload();
  await waitForSevenSlidesV2(tab, frame);
  await verifyTargetSetV2(tab, frame, c.targets, 'draft');
  await tab.close();
  const fresh = await openAfterConfirmedUploadV1(name);
  const freshFrame = fresh.playwright.frameLocator('iframe#WacFrame_PowerPoint_0');
  await waitForSevenSlidesV2(fresh, freshFrame);
  await verifyTargetSetV2(fresh, freshFrame, c.targets, 'draft');
  await fresh.close();
  const path = await downloadCloudExactV2(name);
  evaluatorNeutralRuns.push({index: c.index, download_path: path,
                             targets_verified: c.targets.length,
                             two_phase_gui_readback: true,
                             official_final_admitted: 0});
  return {index: c.index, downloaded: true,
          targets_verified: c.targets.length,
          two_phase_gui_readback: true, official_final_admitted: 0};
}

async function neutralControlTwoPhaseV2(c) {
  const name = await uploadOneV3(c);
  const tab = await openAfterConfirmedUploadV1(name);
  return await finishNeutralTwoPhaseV2(c, tab);
}
