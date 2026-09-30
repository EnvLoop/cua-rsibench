# Native Desktop real model wire

The additive model worker uses the same Qwen vision renderer, minimal GUI
grammar, 90-turn/action bound, 720-second actor clock, native saved-artifact
verifier and separate fresh reset for the shared base and all four selected
checkpoints. Its native transport includes the unchanged v9 neutral Calc Enter
samples and v12 passive full-frame focus readiness. Current source and control
admission checks bind the additive v17 bounded-transfer epoch. No evaluator script
is used as a student action policy.

The pinned native SDK host uses E2B Desktop 2.2.0, E2B 2.51.0 and Pillow 11.3.0.
The verified Qwen environment has a different Pillow pin and a dedicated
provider/renderer stack. Sampling therefore runs in the existing clean Qwen
subprocess, with no native SDK installation or package overlay in that venv.
The child invokes the unchanged runtime evidence and active-process gate.
Only rendered image/text requests reach its sampler. It receives no task
oracle, saved-state score, evaluator script or native provider credential.

Private file RPC records each request before sending its envelope and checks
the returned request hash, result hash and ordinal. A timeout or malformed
acknowledgement poisons that process: the caller cannot resend a request or
restart it automatically. Child-side setup is consumed before its provider
acknowledgement; a failed command terminates the command loop. Its sampling
journal also refuses duplicate or uncertain request IDs. All five model slots
share this behavior. The [Tinker configuration documentation](https://github.com/thinking-machines-lab/tinker/blob/main/_autodocs/configuration.md)
describes configurable sampling retries. The implementation follows the
installed 0.30.0 source fields: sampling retry logic is disabled and the HTTP
client retry count is zero.

The full worker still requires 120 independently completed current control
trios, the authentic six-cell/600-task study freeze, all four common harness
bindings and the matched base/selected sampling policy. It implements shared
base selection, selected-checkpoint selection and the existing final-worker
interface. Native preservation and target correctness are reported as
separate facts. These source paths are runnable code, not evidence of a
completed study, model improvement or provider invoice.

`train_weak_base_pilot_v11` provides one narrower public-TRAIN qualification
episode. Source preparation refuses selection/final packages and freezes one
TRAIN package plus the entire model wire. Root review checks provider active
zero and writes one exact permit. Paid execution uses actual base-model
responses only, saves and independently scores the native artifact, then
opens a distinct fresh guest and verifies original input bytes. Its result
remains TRAIN diagnostic evidence with zero official model results. A failed
or uncertain paid call consumes its intent and cannot be resubmitted.

Place this pilot outside every frozen historical accounting root, for example
under `work/full-study`, and start it only after the active control trio has
terminated. Preparation enforces this separation. The native host launches the
sampler from the root checkout's existing
`work/qwen38-training-runtime/.venv/bin/python`.

```sh
python -m native_desktop_factory.train_weak_base_pilot_v11 prepare \
  --control-freeze <current-v17-private-freeze> --task-id <public-TRAIN-id> \
  --output-root <fresh-work/full-study/pilot-root> --freeze <private-pilot-freeze>
python -m native_desktop_factory.train_weak_base_pilot_v11 review \
  --freeze <private-pilot-freeze> --permit <new-private-permit>
python -m native_desktop_factory.train_weak_base_pilot_v11 run \
  --freeze <private-pilot-freeze> --permit <new-private-permit> --enable-paid-pilot
```

The paid run must use the pinned native Desktop Python executable and quiet
environment credentials. The clean child verifies its own runtime separately.
Source preparation and review do not sample a model or create a guest.

Twenty related offline tests passed in the pinned native host. They cover all
five slots, actual native transport Enter/focus behavior with synthetic
screenshots, saved-state/reset integration, fake-provider uncertainty,
subprocess request consumption, TRAIN-only refusal and protected-content
preservation reporting. The fixture episodes and fake service callbacks are
code checks and contribute no native controls or model outcomes. Actual child
startup, provider sampling and the one TRAIN pilot remain unexecuted by this
author. They require root-side source review and the exact permit.
