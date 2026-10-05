# Office environment repair and acceptance

The environment must support original application upload, native editing,
saved-file download, independent scoring, and a fresh reset. Model inference
and training are separate from environment acceptance.

## PowerPoint web validation

A TRAIN-only recovery on 5 October 2026 used the existing account and its
dedicated disposable folder. The original presentation was uploaded through
the macOS file picker. OneDrive acknowledged the upload and the editor opened
the resulting document. A summary correction was saved and downloaded as an
actual PPTX file. The test document was sent to the recycle bin, the empty
folder was reopened, and the original input was uploaded to a distinct cloud
document identity.

For the second document, an untouched Office download was frozen before the
edit. The independent saved-file controls were unchanged baseline 0, correct
summary 1, and deliberately wrong summary 0. The wrong value preserved the
remaining document content. The final folder returned to empty. These are
sequential manual TRAIN controls, not a fresh three-attempt model evaluation
or acceptance of the automated actor runtime.

## Verifier repair

PowerPoint adds a revision sidecar after editing. The existing verifier
rejected the newly added part and its relationship and content-type entry.
The additive `ppt_wdi_factory.office_revision_verifier_v2` validates that
exact metadata triple before excluding it from the existing comparison.
Its revision client counter uses the unsigned-integer range documented in
[Microsoft MS-PPTX section 5.5](https://learn.microsoft.com/en-us/openspecs/office_standards/ms-pptx/e5047fb0-5d6d-421f-bfe9-ce8cd549843f).
Unknown elements, attributes, external relationships, duplicate bindings,
text payloads, invalid counters and invalid timestamps are rejected. Slides,
text, geometry, charts and embedded workbooks retain the original rules.
The raw-source score and all earlier failures remain preserved.

The evaluator must freeze an untouched Office-normalized baseline before
opening the actor. A raw generated file is insufficient because the editor
rewrites OOXML during its first open/export. The oracle remains evaluator-only.

```bash
PYTHONPATH=.:src python -m ppt_wdi_factory.office_revision_verifier_v2 \
  --baseline /private/evaluator/untouched-office-baseline.pptx \
  --candidate /private/evaluator/actor-saved.pptx \
  --oracle /private/evaluator/frozen-oracle.json
```

## Remaining acceptance work

Connect baseline freezing and this verifier to a new bound automated runtime
epoch. Preserve the existing action guards. Validate native upload focus,
the current download workflow, three separate attempts, and a fresh cloud
reset using that exact runtime. Excel web and LibreOffice acceptance remain
separate application tracks; the PowerPoint control cannot qualify them.

The additive `tools.office_web_normalized_runtime_v8` adapter now copies the
verified native before-actor download to evaluator-owned storage and freezes
its oracle before calling `host.actor_open`. It rejects baseline reuse,
changed baseline or receipt bytes, and candidate scoring before the freeze.
Its reserve-task snapshot, provenance and source ZIP are copied only from the
original hash-bound evaluator descriptor and rechecked during scoring.
Ten standard-library tests passed, and an offline replay of the actual saved
TRAIN files produced 0/1/0. Binding and native acceptance of that new adapter
are still pending.

## Automated retry findings

The 5 October native retry confirmed that the desktop was unlocked. An initial
folder inventory failed because the parent page had not rendered its heading
within the browser's built-in selector wait. The additive parent readiness
helper now polls the same heading and folder card within the original ten-second
budget. Native inventory passed after that repair.

A later fresh run completed upload, editor readiness, two actual untouched-file
downloads, baseline binding, actor opening and two native surface captures. It
then stopped before input because the lease adapter treated a validated
`NativeLease` record as a dictionary. Reset creation separately exposed an
exact-URL check that rejected removal of OneDrive's `CT` and `OR` tracking
parameters. Read-only URL logging confirmed unchanged origin, document path,
document identity and every other query parameter.

The next repair must accept only those observed tracking-parameter transitions
and validate the actual structured lease against its current account lease
file. Existing document identity, principal, action guard, scoring and time
budgets remain required. Earlier failed runs are retained, and their owned
files were recycled before another attempt. No model or training calls were
made, and a complete automated lifecycle remains unqualified.

The next native attempt verified two distinct cloud creates and one stable
download pair. The navigation-hint repair worked during fresh reset creation.
The attempt also exposed a missing clocked-actor base class in the typed lease
adapter and another built-in selector timeout on returning to the task folder.
The runtime closed and recycled both owned documents, confirmed a final empty
inventory, and released its account lease. The successor must preserve the
original clocked actor and use bounded visibility checks consistently.

The full PowerPoint editor and its cropped view were visually inspected before
actor opening in that attempt. The title, flagged summary and instructions were
readable. Actual actor observations still require a separate visual check; an
earlier attempt returned mostly blank captures.

The clock-preserving successor completed native observation, pre-dispatch
verification, an accepted guarded neutral finish, two saved-state downloads and
an independent score of zero. The document was closed and recycled, and the
folder inventory returned empty. Fresh reset upload then stopped before native
menu input because macOS had locked. The retained lease was recovered only after
worker termination, an empty native-picker evidence directory and a new empty
folder observation were verified. A complete reset is still pending.

Actual actor captures remained mostly blank through the browser's clip API,
while a full screenshot of the same current editor was readable. Another clip
capture immediately after that full capture was also blank. The next capture
adapter must take one actual full screenshot, retain its original encoded bytes
privately, and derive the unchanged viewport crop from its decoded pixels.
Independent validation must verify the rectangle and every output pixel. The
model receives only the cropped view; the private header remains excluded.

The single-full-capture adapter is now implemented. A joined evaluator artifact
worker crops the one native screenshot while the existing operation request
waits; it never operates the UI. Concurrent request completion, tampering,
timeout and worker shutdown tests passed. The actual saved full screenshot was
JPEG. Its derived PNG was independently checked against manual decoded-pixel
row slices and visually inspected: the slide is readable and the account header
is excluded. A fresh native replay of this adapter still requires desktop
unlock, and the three-attempt acceptance gate remains pending.
