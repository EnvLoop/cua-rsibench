# First original Office one-file account pilot

**Status: implementation and fake transport tests only.** No Microsoft
Graph, Office browser, E2B, Tinker, or model call was made for this runbook.
The repo still has zero official Office final admissions and zero Office
selection scores. This pilot never opens selection or final items.

The existing one-file Graph controller needs a valid personal-account
capability receipt before its first invite. The new evaluator-only
[`PersonalGraphBootstrapPilot`](../tools/office_graph_personal_bootstrap_pilot_v1.py)
creates that receipt from one **train** item using a separate, hash-chained
one-shot pilot. It verifies the exact owner, actor, personal drive, target,
parent, unrelated item, private source bytes, and two owner downloads before
the first write. Its invite grants one signed-in actor `write` on that file
with `sendInvitation:false`; its delete removes only the returned permission
ID. A lost response is reconciled by reads, never by replaying a POST or
DELETE. A failed actor-isolation probe can be explicitly cleaned up with
`abort-delete`, which issues no capability. The private
`graph-http.private.jsonl` preserves Graph response bodies and status codes
in a hash chain for evaluator review; bearer tokens are never recorded.

The evaluator must prepare these **private, mode-0600** inputs under `work/`:

1. A six-cell v0.6.6 action ratification and an admitted train task package
   hash. The actor and neutral-reset cloud items must be distinct copies of
   the exact PowerPoint `.pptx` or Excel `.xlsx` seed.
2. Two distinct Microsoft personal accounts. Supply a delegated owner Graph
   token with `Files.ReadWrite` and an actor token with `Files.Read` as
   `MS_GRAPH_OWNER_TOKEN` and `MS_GRAPH_ACTOR_TOKEN` in the host process
   environment. The pilot does not persist or print either token. A separate
   private OAuth-client scope observation must state those scopes, owner and
   actor IDs, token SHA-256 fingerprints, and a current validity window. This
   observation is evaluator-provided; reviewers must inspect its OAuth
   provenance. Authenticated Graph operations separately verify effective
   access.
3. A `cua-office-graph-personal-bootstrap-spec-v1` JSON file binding only
   `split:"train"`: cell, task package/source/action hashes, exact owner and
   actor IDs/emails, drive/item/parent/sentinel IDs, train filename, relative
   references to the ratification, source file and OAuth scope observation,
   and `hidden_final_model_attempts:0`. The source and references remain
   private. The actor must initially be denied the target, parent and
   sentinel; owner/inherited permissions may remain, but broad or unknown
   direct grants are rejected. The OAuth observation is a private local
   assertion tied to the exact token hashes, not a cryptographic Graph
   attestation; the pilot's authenticated operations must also succeed.

Run each command explicitly, with a new private output directory. Paths
below are placeholders for evaluator-owned files; they contain no account
locator or credential:

```sh
PYTHONPATH=.:src python3.14 -m tools.run_office_graph_personal_bootstrap_pilot_v1 \
  --spec "$GRAPH_BOOTSTRAP_SPEC" --out "$GRAPH_PILOT_OUT" check
PYTHONPATH=.:src python3.14 -m tools.run_office_graph_personal_bootstrap_pilot_v1 \
  --spec "$GRAPH_BOOTSTRAP_SPEC" --out "$GRAPH_PILOT_OUT" invite
PYTHONPATH=.:src python3.14 -m tools.run_office_graph_personal_bootstrap_pilot_v1 \
  --spec "$GRAPH_BOOTSTRAP_SPEC" --out "$GRAPH_PILOT_OUT" delete
PYTHONPATH=.:src python3.14 -m tools.run_office_graph_personal_bootstrap_pilot_v1 \
  --spec "$GRAPH_BOOTSTRAP_SPEC" --out "$GRAPH_PILOT_OUT" finalize
```

Run `invite` within five minutes of the successful read-only `check`.
After an uncertain invite or delete, run only `reconcile-invite` or
`reconcile-delete`. If an invited actor can also see the parent or sentinel,
use the explicit `abort-delete` on the uniquely observed grant; do not
finalize it. An unresolved state requires operator review, not another
invite. `finalize` emits private five-stage pilot proofs, a capability
receipt, exact source readback and `ready-train-lease-spec.private.json`.
The latter is accepted by the original `OneFileGraphLease` for the same
train item after the pilot grant has been revoked.

To prepare the **distinct neutral reset copy**, place a private
`cua-office-graph-matching-train-reset-copy-v1` binding under `work/` with
the same cell, train package and source SHA, its own item ID and train file
name, the same parent ID, the former actor item as sentinel, and
`official_final_credit:0`. Then run:

```sh
PYTHONPATH=.:src python3.14 -m tools.run_office_graph_personal_bootstrap_pilot_v1 \
  --spec "$GRAPH_BOOTSTRAP_SPEC" --out "$GRAPH_PILOT_OUT" \
  --reset-copy "$GRAPH_RESET_COPY_BINDING" prepare-reset
```

This is Graph **read-only**. It rechecks both delegated identities, the
personal owner drive, exact reset item and parent, actor denial on reset,
parent and former actor item, effective permissions, and two identical owner
downloads matching the seed. It emits a separate
`matching-reset-copy/ready-reset-lease-spec.private.json`. A reset item that
differs from the source or is already actor-visible cannot be prepared.

For the first GUI save/download/reset control, use the two ready train lease
specs with [`run_office_graph_one_file_lease_v1.py`](../tools/run_office_graph_one_file_lease_v1.py)
in separate private lease directories. Invite only the actor item first.
Start a bounded E2B Desktop through the existing train bridge, have the
distinct actor sign in manually, and create the worker's fresh one-file
`run.private.json`, `actor-scope.private.json`, permission snapshots and
visible target/sentinel evidence. The existing PowerPoint or Excel train
worker then uses GUI actions only, an owner exact-item double download, and
its independent saved-state oracle. On the worker's revocation pause, run
the actor lease's exact `delete`, verify its closed state, and provide the
worker's private revocation signal. Repeat with the distinct reset item and
fresh E2B sandbox. The worker must accept the neutral reset and both
revocations before any train episode is admitted. Keep the source, cloud
locators, screenshots, tokens, permission IDs, and result files private.

This procedure still needs an unlocked human-operated Office sign-in path,
the distinct actor account, real owner/actor delegated tokens and OAuth
scope provenance, two owner-prepared source-equal cloud copies, qualified
per-item GUI evidence, E2B/Tinker availability and campaign billing
reconciliation. Owner-side Graph leasing alone does not provide unattended
login across 24 campaigns. Selection and final remain separately gated by
their own source-frozen account/permission matrix; the train capability
cannot authorize either split.

Offline verification:

```sh
PYTHONPATH=.:src python3.14 -m unittest \
  tests.test_office_graph_personal_bootstrap_pilot_v1 \
  tests.test_office_graph_one_file_lease_v1 -v
```
