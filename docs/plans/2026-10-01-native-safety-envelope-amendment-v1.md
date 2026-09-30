# Native safety envelope amendment v1

This prospective amendment separates native dispatch safety from screenshot
identity. The previous full-raster adapters remain immutable historical evidence.
Their rejected attempts, partial actions, and resets remain in their original
namespaces. Importing this policy provides no admission, result, model sample,
or training credit. Application integration and fresh native qualification are
still required.

## Motivation and decision

Native applications can change rendered pixels without changing the owned
workspace, current focus, or safe action target. Full-raster equality makes those
changes infrastructure rejections before an otherwise safe action is attempted.
Increasing a pixel tolerance could also hide important scope changes. The new
gate instead checks trusted native ownership and the original action's safety.
It preserves both complete images and native envelope artifacts for review.

The shared policy is `src/cursibench/native_surface_guard_policy_v1.py`. Its
immutable `POLICY` and canonical `POLICY_SHA` apply uniformly to the base,
all four selected checkpoints, teachers, and qualification controls. A release
must bind this hash, the application plugin hash, action syntax profile, roster,
budgets, and evaluator sources before any model result is collected. It cannot
silently mix previous raster profiles and the new policy within a comparison.

The alternatives considered were retaining full-raster equality or widening
application-specific pixel masks. The native envelope is chosen because it
expresses the actual safety boundary while retaining unmodified raster evidence.
It adds no answer-pixel mask, approximate image comparison, answer matching,
task narrowing, or retry credit.

## Trusted input and exact schemas

`canonical(value)` returns canonical UTF-8 JSON bytes. `digest(value)` returns its
SHA-256. `validate_artifact_ref`, `validate_lease`, and `validate_envelope` return
frozen dataclasses with tuple fields. Unknown fields, duplicate target refs,
invalid hashes, non-finite timestamps, boolean integers, and invalid geometry
are rejected. The schema excludes labels, task values, expected answers, gold
data, and correctness signals from the decision input.

An artifact ref has exactly `schema`, `path`, `sha256`, `size`, and `kind`.
`schema` is `native-guard-artifact-ref-v1`. Paths are relative to the private
evidence root; absolute paths, traversal, and symlinks are rejected.
`verify_artifact(root, ref)` independently reopens bytes and verifies size/hash.
Schema validation alone does not prove a file exists or its contents match.

A lease has exactly:

- `schema`: `native-surface-lease-v1`.
- `lease_id`, `cell_id`.
- `account_sha256`, `workspace_sha256`, `window_sha256`, `owner_sha256`.
- `issued_at`, `expires_at`, in the evaluator's monotonic clock domain.
- `evidence`: a saved `lease_evidence` artifact ref.

There is no self-declared `active` boolean. `decision` requires a trusted
`lease_check` callback. The callback must inspect the evaluator-owned live lease
and save its evidence, for example the actual lock, PID, and lease binding.
Its result has exactly `schema`, `lease_sha256`, `status`, `checked_at`,
`expires_at`, and `evidence`. The schema is `native-surface-lease-check-v1`;
the digest must match the validated lease; status is `active` or `inactive`.
The evidence kind is `lease_check`. The check must occur after current capture,
remain current at decision time, and expire within the parent lease. Returning
a boolean, echoing a model field, or constructing an active lease from UI
assumptions fails closed. The caller owns the callback's trust boundary.

A native envelope has exactly:

- `schema`: `native-surface-envelope-v1`; `policy_sha256`: `POLICY_SHA`.
- `phase`: `observation` or `predispatch`; `lease`: the validated lease.
- `task_id`, `task_binding_sha256`, `frame_id`, `step`.
- `captured_at`, `expires_at`, `viewport`: `[width, height]`.
- `view_id`, `modal_id`, `focus_id`.
- `allowed_views`, `allowed_modals`, `allowed_focus`.
- `owned_surface`, `targets`, `raw_image`, `raw_envelope`.

The application plugin obtains ownership, application/origin, view, modal,
window, and focus identities from the native runtime. Focus identity may include
element ref, tag, input type, and name; it must exclude current text and values.
Unavailable or ambiguous ownership is not inferred from an attractive screenshot.
The immutable lease hashes bind application origin and owned document/workspace
where appropriate. The allowlists are a declared safety profile, not the set of
correct answers or controls needed for a particular task.

Each target has exactly `ref`, `bounds`, `visible`, `enabled`, `obscured`,
`keyboard`, and `actions`. Bounds are `[x, y, width, height]` in the screenshot
coordinate system. Targets can describe native controls or owned safe regions.
The plugin must account for actual occlusion and hit testing when describing a
safe region. A broad region cannot override an unsafe overlay or account menu.
It must not read hidden task answers to choose allowed targets.

Each phase has a distinct raw image path and a distinct native envelope path,
even if bytes happen to match. Kinds are `raw_observation_image`,
`raw_predispatch_image`, `native_observation_envelope`, and
`native_predispatch_envelope`. The native envelope artifacts contain the raw
plugin evidence; they are saved before the normalized envelope adds their refs,
avoiding a self-referential hash. These are private full artifacts. Cropping or
sanitization for model/public exposure is a separate operation.

## Dispatch and evidence order

`decision(observed, current, action, *, lease_check, now=None)` consumes an
already syntax-validated normalized action. Model action fields remain unchanged.
It does not call a driver, browser, application API, provider, or scorer.
The required executor order is:

1. Save the full observation image and raw native envelope; bind the existing
   task/package/step and new one-use frame nonce before sampling.
2. Sample once under the existing paid-call and actor budgets.
3. Save the full current image and raw native envelope, then perform the real
   lease callback. Persist the shared decision before accept or reject.
4. Atomically consume the nonce and turn in the evaluator-owned ledger. A replay
   cannot reach the driver, including after an uncertain previous outcome.
5. If accepted, exclusively create and flush an intent with action and decision
   hashes before the unchanged original action reaches the driver.
6. Save the actual driver result and final dispatch receipt. Only an actual
   successful driver return may be recorded as `applied`.

The policy checks the same lease, account, workspace, window, owner, declared
scope, and viewport. Ownership loss, an invalid/stale lease, an outside view/modal,
or policy drift causes `hard_stop`. A changed nonce/task/step, expiry, transition
between otherwise allowed native contexts, unsafe focus, or unsafe current target
causes `rejected`. Coordinate actions retain their original coordinates. Ref
actions must remain current, visible, enabled, unobscured, and owned. Nothing
relocates coordinates to a newly convenient control.

Untargeted typing and keys require the exact current safe focus. Targeted typing
and keys instead require the original target to remain an owned, visible,
enabled, unobscured keyboard target in both envelopes. After the native target
click and before any keyboard IO, the executor must capture and recheck actual
editable focus and ownership. It must retain that evidence with the driver
result. A failed or uncertain second check after IO starts quarantines the
episode; it never produces an applied shortcut. This permits a model to select
a currently safe input without requiring that input to have been focused before
the selection.

The decision includes both image/envelope refs, original action digest, normalized
envelope digests, lease-check evidence, and `driver_called: false`. It is a safety
decision, not an execution receipt. `consume_turn` and `invalidate_nonce` are
required instructions; the durable executor ledger proves that they occurred.

## Recovery and scoring

A recoverable rejection consumes the existing turn and invalidates the old nonce.
Recovery requires a new observation and a new paid model sample within existing
action, token, time, and lease budgets. The rejected action is never replayed,
silently retargeted, counted as applied, or fed back as `applied/ok`. Hard stops
terminate the episode without a recovery sample.

`rejection_feedback(decision)` returns truthful separately versioned feedback:
`{version: "native-surface-rejection-feedback-v1", status: "rejected", code: reason}`.
The old shared action contract remains unchanged. An application adapter using
its legacy observation constructor may first satisfy that constructor's enum
with `rejected/invalid_action`, then replace only the constructed observation's
previous result with this truthful versioned record before model rendering.
It may not use a success projection or change the actual saved decision.

`validate_receipt` accepts the exact `native-surface-dispatch-receipt-v1` schema.
It requires turn consumption and nonce invalidation. Accepted/applied/failed
records require a saved `action_intent` ref. Applied requires `succeeded` and
saved `driver_result` evidence. Uncertain driver outcomes are `failed/unknown`,
never applied. Rejected and hard-stop receipts cannot claim an attempted driver
or an action intent. Actual file bytes and parent/child hash bindings still need
independent reopening by the evaluator.

A safe wrong click, incorrect value, or ineffective allowed action is model
behavior, scored by the unchanged independent saved-state verifier, protected
state checks, and reset protocol. The safety policy never compares an action
with task answers. Infrastructure/lease failures and model outcomes remain
separate in reports. Existing task rosters, splits, budgets, scorer semantics,
source data, and reset rules are unchanged.

## Validation and release boundary

Focused offline tests cover changed raw images, safe wrong targets, unchanged
coordinates, current refs, ownership and lease loss, context and focus changes,
scope drift, TTL/nonce/task/step binding, immutable schemas, replay-related receipt
semantics, truthful feedback, artifact tampering, traversal, and symlinks.
These tests establish source behavior only. Each integrated application still
needs new native qualification under a frozen common policy and plugin before
any formal model cohort or paper claim uses the amendment.
