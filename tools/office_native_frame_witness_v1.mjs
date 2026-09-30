/* Retain unchanged native screenshots for evaluator-only guard diagnosis. */
import * as fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {createHash} from 'node:crypto';

const sha = raw => createHash('sha256').update(raw).digest('hex');

export async function retainOfficeNativeFrames(tab, {artifactRoot, clip}) {
  const root = await fs.realpath(artifactRoot);
  const stat = await fs.lstat(artifactRoot);
  if (root !== path.resolve(artifactRoot) || !stat.isDirectory() ||
      stat.isSymbolicLink() || (stat.mode & 0o077) !== 0 || stat.uid !== os.userInfo().uid)
    throw new Error('private_native_frame_witness_root_required');
  const folder = path.join(root, 'native-frame-witness.private');
  await fs.mkdir(folder, {mode: 0o700});
  const expectedClip = JSON.stringify(clip);
  let sequence = 0;
  async function screenshot(options) {
    if (JSON.stringify(options?.clip) !== expectedClip || sequence >= 8)
      throw new Error('native_frame_witness_scope_changed');
    const raw = await tab.screenshot(options);
    const prefix = String(sequence++).padStart(3, '0');
    await fs.writeFile(path.join(folder, prefix + '.private.image'), raw,
      {flag: 'wx', mode: 0o600});
    await fs.writeFile(path.join(folder, prefix + '.private.json'), JSON.stringify({
      schema: 'office-native-frame-witness-v1', capture_sequence: sequence - 1,
      captured_at_ms: Date.now(), image_sha256: sha(raw), bytes: raw.length,
      clip, returned_bytes_unchanged: true, model_calls: 0, official_final_credit: 0,
    }) + '\n', {flag: 'wx', mode: 0o600});
    return raw;
  }
  return new Proxy(tab, {get(target, key) {
    if (key === 'screenshot') return screenshot;
    const value = Reflect.get(target, key, target);
    return typeof value === 'function' ? value.bind(target) : value;
  }});
}
