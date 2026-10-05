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
