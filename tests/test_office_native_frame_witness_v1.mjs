import test from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {createHash} from 'node:crypto';
import {retainOfficeNativeFrames} from '../tools/office_native_frame_witness_v1.mjs';

test('native witness retains and returns identical bytes and preserves native receiver', async () => {
  const root = await fs.realpath(await fs.mkdtemp(path.join(os.tmpdir(), 'office-native-witness-')));
  try {
    const clip = {x: 0, y: 126, width: 1920, height: 747};
    const raw = Buffer.from([255, 216, 255, 0, 1, 2]);
    const tab = {id: 'owned-tab', screenshot: async options => {
      assert.deepEqual(options, {clip}); return raw;
    }, url() {assert.equal(this, tab); return 'synthetic-owned-document';}};
    const wrapped = await retainOfficeNativeFrames(tab, {artifactRoot: root, clip});
    assert.equal(wrapped.id, tab.id); assert.equal(wrapped.url(), tab.url());
    assert.equal(await wrapped.screenshot({clip}), raw);
    const folder = path.join(root, 'native-frame-witness.private');
    assert.deepEqual(await fs.readFile(path.join(folder, '000.private.image')), raw);
    const receipt = JSON.parse(await fs.readFile(path.join(folder, '000.private.json')));
    assert.equal(receipt.image_sha256, createHash('sha256').update(raw).digest('hex'));
    assert.equal(receipt.returned_bytes_unchanged, true);
    assert.equal((await fs.stat(path.join(folder, '000.private.image'))).mode & 0o077, 0);
    await assert.rejects(retainOfficeNativeFrames(tab, {artifactRoot: root, clip}), {code: 'EEXIST'});
  } finally {await fs.rm(root, {recursive: true, force: true});}
});

test('scope mismatch is rejected before another native screenshot', async () => {
  const root = await fs.realpath(await fs.mkdtemp(path.join(os.tmpdir(), 'office-native-witness-')));
  try {
    const clip = {x: 0, y: 126, width: 1920, height: 747}; let calls = 0;
    const wrapped = await retainOfficeNativeFrames({screenshot: async () => {calls++; return Buffer.from('unchanged');}},
      {artifactRoot: root, clip});
    await assert.rejects(wrapped.screenshot({clip: {...clip, y: 0}}), /scope_changed/);
    assert.equal(calls, 0);
  } finally {await fs.rm(root, {recursive: true, force: true});}
});
