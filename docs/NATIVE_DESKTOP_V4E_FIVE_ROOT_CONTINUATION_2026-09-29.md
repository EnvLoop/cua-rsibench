# Native Desktop v4e: five-root, reviewed evaluator continuation

The main-checkout [v4d source freeze](evidence/native-wdi-v066-v4d-main-source-freeze-2026-09-29.json) is non-dispatchable. It retains eight independently accepted GUI control trios, four incomplete logical task identities, 88 never-intended identities, and 56 conservatively charged 600-second E2B intents. The fourth partial is the v4c precreate roster failure. Its saved intent is charged even though the hash-matched traceback and absent sandbox ID show no observed provider create. The original 35 evaluator source files, eight complete trios, and stopped evidence remain unchanged.

v4e places all new attempts in an exclusive fifth root. The first untouched candidate is sorted roster index 12. Indices 12–99 are processed in consecutive batches of at most two identities, with positive, near-miss, and cold-reset attempts on distinct fresh guests. Index 11 is eligible for **one separately reviewed fresh-clone full trio**; its stopped v4c intent is never replayed. The original three partial identities at indices 7, 8, and 10 are outside this controller and remain quarantined. Completing only the 88 untouched trios would reserve 320 full leases across five roots; adding the index-11 clone would reserve 323 leases, or $53.83 at the conservative $1/hour planning rate. Neither value is a provider invoice.

The new child uses the same canonical sorted roster as the parent. Before any provider create, it checks the current one-batch review permit, source hashes, old v4d freeze, old four-root bridge, retained attempt trees, stopped v4c budget/intent hashes, fifth-root ledger, exact attempt order, and fsynced intent. The original evaluator's bridge validator is patched only inside that child to validate the immutable old bridge against its original root and separately validate the fifth root. Its action script, strict A/B/A/B caret rule, saved-state scorer, profile guard, and provider API remain unchanged. The durable child-output helper writes private stdout, stderr, and a terminal hash receipt before the parent classifies a result. Any timeout, missing receipt, invalid control, uncertain cleanup, or failed independent audit stops the batch without replay.

The independent v4e auditor reopens the original eight saved OOXML/profile controls, the stopped intent, every new saved positive and target-only near-negative, cold reset, all raw current-frame and A/B/A/B evidence, distinct sandbox identifiers, child output bytes, and the five-root intent ledger. A completed batch must match the consecutive roster prefix and its private journal. A partial or interrupted batch blocks the next plan until reconciled; it cannot be skipped by choosing a later ID.

The [isolated v4e source freeze](evidence/native-wdi-v066-v4e-isolated-source-freeze-v3-2026-09-29.json) is a code and provenance artifact, not a dispatch token. Its private companion is checkout-specific. To bind this source on the main checkout, cherry-pick the source commit, verify the same six source hashes and the main v4d public SHA-256 `f06958825c1d2b5283a4e3ba33c14ee6fcb20e896055d66f31c4dd5f064b6485`, then issue a **new exclusive** main-checkout private/public v4e freeze pair. Do not copy the isolated private freeze: its public path and SHA are tied to the isolated checkout. The source-freeze command requires an active-zero E2B query but creates no sandbox:

```bash
PYTHONPATH=.:src /path/to/desktop-pinned-venv/bin/python \
  -m native_desktop_factory.v066_day_rollover_controller_v4e prepare \
  --v4d-freeze work/native-desktop/v4d-forensics.private/v4d-main-source-freeze.private.json \
  --freeze work/native-desktop/v4e-main.private/v4e-source-freeze.private.json \
  --public docs/evidence/native-wdi-v066-v4e-main-source-freeze-2026-09-29.json
```

Run `plan` first. An independent reviewer then runs the **separate auditor** with `--review-out` and `--permit-out` under private paths. That command reopens current evidence, queries E2B active-zero, and writes a permit for exactly the next batch number, lane, and selected-ID hash. It does not create a sandbox. The root-owned run accepts only that review-bound permit; the child rechecks it before create. Issue a new review and permit for each subsequent batch. A one-ID first batch is the smallest live qualification; use a two-ID batch only after the first result and independent audit are clean.

```bash
PYTHONPATH=.:src /path/to/desktop-pinned-venv/bin/python \
  -m native_desktop_factory.v066_day_rollover_controller_v4e plan \
  --freeze work/native-desktop/v4e-main.private/v4e-source-freeze.private.json \
  --lane untouched --max-new-ids 1

PYTHONPATH=.:src /path/to/desktop-pinned-venv/bin/python \
  -m native_desktop_factory.v066_day_rollover_independent_audit_v4e \
  --freeze work/native-desktop/v4e-main.private/v4e-source-freeze.private.json \
  --lane untouched --max-new-ids 1 \
  --review-out work/native-desktop/v4e-main.private/review-batch-0001.private.json \
  --permit-out work/native-desktop/v4e-main.private/permit-batch-0001.private.json

PYTHONPATH=.:src /path/to/desktop-pinned-venv/bin/python \
  -m native_desktop_factory.v066_day_rollover_controller_v4e run \
  --freeze work/native-desktop/v4e-main.private/v4e-source-freeze.private.json \
  --permit work/native-desktop/v4e-main.private/permit-batch-0001.private.json \
  --run-dir work/native-desktop/v066-day-rollover-final-20260929/v066-v4e-root-owned-runs/batch-0001 \
  --lane untouched --max-new-ids 1

PYTHONPATH=.:src /path/to/desktop-pinned-venv/bin/python \
  -m native_desktop_factory.v066_day_rollover_independent_audit_v4e \
  --freeze work/native-desktop/v4e-main.private/v4e-source-freeze.private.json
```

The actual run directory is derived from the frozen fifth root: it must be the `v066-v4e-root-owned-runs/batch-NNNN` sibling of that root. Verify the exact private path before launch. The one-use clone needs its own `--lane clone --max-new-ids 1` review, permit, and batch. This protocol admits **zero official final tasks and zero model attempts**. A future six-cell ratification must independently accept each Desktop evaluator identity and bind the shared model/action/budget protocol before any control is counted in the formal study.
