# Terminal first Office TRAIN spool

This source change connects the existing admitted native bridge to an external terminal waiter. The terminal publishes readiness before the CUA helper captures a frame. One CUA call then observes, publishes an exclusive private request, waits for a normalized result, verifies its receipt and hashes, and dispatches through the same bridge. The helper has no environment, subprocess, provider, credential or page-content access. Its only browser operations are the existing bridge's `observe`, `dispatch` and `stop`.

Create the admitted bridge and the filesystem helper in a fresh private artifact root. The approved native binding, accepted control, instruction, actor seed, crop and safe regions remain evaluator-owned. Source review must bind the updated sampler source; the session additionally binds the exact CUA helper and terminal waiter source hashes. Session files bind the original native admission, maximum steps and actor lease expiry. The helper retains the existing maximum 150-second frame lifetime and maximum 15-minute native account lease.

```javascript
const spoolModule = await import('file://' + OFFICE_REPO + '/tools/office_local_browser_terminal_spool_v1.mjs');
const officeSpool = await spoolModule.createOfficeTerminalSpool({
  bridge: officeBridge, binding: officeBinding,
  artifactRoot: OFFICE_ARTIFACT_ROOT, repoRoot: OFFICE_REPO,
  visibleInstructionPath: OFFICE_ARTIFACT_ROOT + '/visible-instruction.private.txt',
  maxCallMs: 55000
});
```

This creates the session without observing the document. Start the following terminal process before calling `runOneFrame`. The terminal may quietly load the already authorized shell configuration with tracing disabled. Use the durable root's clean-runtime Python, an absolute root-and-src-only `PYTHONPATH`, `PYTHONNOUSERSITE=1`, `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`. Provider credentials stay in the terminal environment. Redirect stdout and stderr to private files under the artifact root with `umask 077`.

```bash
"$OFFICE_REPO/work/qwen38-training-runtime/.venv/bin/python" \
  -m tools.office_local_browser_terminal_waiter_v1 \
  --artifact-root "$OFFICE_ARTIFACT_ROOT" --run
```

Omitting `--run` checks the private session and source hashes without publishing readiness or dispatching a model request. Actual startup creates an exclusive worker intent and then a private readiness receipt. Startup itself creates no provider service. Every published frame uses the unchanged native-admitted one-frame sampler and its clean-runtime pre-dispatch verifier. Each sampled frame has a fresh nonce, exclusive consumption intent, context, output directory and hash-bound response. The sampler admission now accepts the same previous applied action context used by normalization; otherwise step one and later were rejected before inference.

After the private waiter readiness receipt exists, invoke one transaction per CUA tool call, with the tool timeout set to 60 seconds:

```javascript
const frameOutcome = await officeSpool.runOneFrame();
```

The helper sets a deadline of at most 55 seconds from call entry, capped by the existing frame and account expiry. This bounds the filesystem response wait and leaves time within the 60-second tool budget for native dispatch and cleanup. Native GUI method completion remains governed by the documented CUA driver's operation timeout; this source does not invent cancellation or permit a second dispatch after uncertainty. Invoke the next transaction only after an `applied` result and while the bridge remains active. The helper carries only the model's bounded memory and a fixed previous applied status/code into the next frame. It stops on finish or the original maximum step count.

A timeout, uncertain terminal result, changed receipt, wrong frame, changed pixels or expired frame poisons the session and stops the bridge. A completed result arriving after the per-call deadline remains preserved with `late_no_replay`; it is not applied. Neither a consumed session nor its worker can be reconstructed or restarted. Private JSON publication is atomic and exclusive, and file and directory writes are synced before the consumer can observe readiness. The terminal has no browser session or native control capability.

The new checks use synthetic tab and sampler fixtures with real private filesystem operations. They cover readiness before capture, two distinct repeated frames, cross-language Node-to-Python exchange, applied context, changed hashes and frame nonce, timeout and late completion, uncertain provider result, exclusive consumption, source mismatch, concurrent calls and stop. Existing bridge and sampler checks remain required. No new native GUI or provider request was executed during this implementation. Timely native application, saved artifact readback, reset, cleanup and student scoring remain for root execution and independent verification.

Validation passed 31 Node checks, including the existing 23 bridge checks, and 19 Python checks, including the existing 11 bridge/sampler checks. The existing sampler regression also verifies that a later frame is refused without previous applied context and reaches an injected stop-before-provider callback when that context is supplied. All provider callbacks used for validation are synthetic.
