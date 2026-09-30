# v13 guest-attestation terminal evidence

The actual main v13 first positive guest passed the provider shape check and
stopped at `guest_content_attestation` with a recorded `ValueError`. The
receipt records a successful kill and subsequent `is_running=false`. It has
zero applied actions, screenshots, staged-file confirmation or saved artifact.
The readonly storage ledger contains zero rows and zero reserved bytes.

The expected guest reference, task package, staged-input hash, evaluator script,
immutable runner, pinned SDK and provider shape match the earlier v10b attempt
that passed content attestation. The v13 changes affect accounting validation;
passive focus readiness had not run. The retained files therefore provide no
evidence of a new GUI, formula or model failure.

The immutable runner checks command completion and then compares content tree,
counts, kernel and exclusion fields. It retained neither command stdout/stderr
nor the per-file compressed guest manifest before this stop. The detached
stderr contains only the later generic trio failure. The failed guest's exact
probe result and differing field cannot be recovered from these local files.
The installed E2B SDK normally raises `CommandExitException` for a nonzero
command exit; its result contains exit code, stdout and stderr. An ordinary
manifest mismatch fits the recorded `ValueError`, but attributing a specific
image or kernel change without the missing raw result would be an inference.

The additive neutral v14 capture tool preserves command exit, stdout, stderr
and the raw per-file gzip manifest **before** JSON parsing or field comparison.
It also captures the SDK's nonzero-exit exception fields. It stages no task,
performs no GUI action and cannot sample a model or invoke a task scorer.
Preparation binds the current v13 source and existing reference; root review
requires provider active zero. One fresh 600-second create consumes its intent
and uses a private artifact root outside all frozen accounting roots. The
original failed guest and all 68 v13 source files remain unchanged.

Five offline tests passed under the pinned native SDK runtime. They verify raw
nonzero-exit capture, empty streams, malformed JSON retention, separate missing
manifest reporting, strict comparison of each existing attestation field and
refusal before private reads without the paid flag. No provider or native call
was performed by this author. A new neutral diagnostic would describe its own
observed runtime; it cannot retroactively recover the failed v13 guest.
