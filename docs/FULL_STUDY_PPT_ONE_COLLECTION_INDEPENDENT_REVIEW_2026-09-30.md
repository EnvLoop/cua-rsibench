# Independent review of the one-collection TRAIN PPT proposal

The corrected proposal is approved for offline development against the single frozen TRAIN collection. The original source at `2c4351c7bc1c7d5978dc4557e5e6afce2e7ad8be` had a concrete namespace bypass and must not be integrated without this correction. This review does not register a task or qualify an automated model, selection, or final run.

Independent replay first reproduced the original 44-rejection, two-equivalence audit byte for byte. A further mutation rebound the existing `dcterms` prefix, preserved expanded element names through a separate alias, and retained `xsi:type="dcterms:W3CDTF"`. ElementTree discarded the namespace declarations used only in attribute values, so the original canonical comparison incorrectly accepted this semantic change with score 1. An allowed namespace-URI set alone did not prevent the bypass.

The correction resolves QName and markup-compatibility prefix-list attribute values against their in-scope namespace bindings before comparison. It covers `xsi:type`, the markup-compatibility QName lists, `Ignorable`, `MustUnderstand`, and `Choice` `Requires`. Unbound prefixes fail. Equivalent controls now retain QName-only bindings during serialization; renaming a prefix without changing its URI and meaning remains equivalent. No native artifact is rewritten, and the core scorer remains byte-identical.

Two corrected real-artifact replays produced identical private audit bytes with SHA-256 `1a567ca6e88edf602205197e9eeab5741daa8f5632b7bd34309ee1dff70238bd`. All 46 adversarial controls failed and both equivalent controls passed. The observed saved positive received proposal score 1; its historical raw strict score remains 0. The source, unsolved native baseline, and exact native reset remain unsolved. The portable and existing manual/source/candidate suites passed 48 tests.

The reviewed allowances remain confined to this observed collection: one bijective embedded workbook rename with identical full ZIP and nested member bytes; the exact relationship and content-type changes; pinned native metadata; known dirty/modification-id serialization; and explicit Calibri children on one ledger target cell. The cell has no authored font/list/table-style override, and its frozen master minor-font and theme/default inheritance resolve to Calibri. Unknown font, style, body, layout, table, chart-cache, binary, relationship, XML-node, or namespace changes remain rejected. No general native PPT normalization policy is established by this evidence.

The existing-account folder amendment remains manual TRAIN development scope. The actual evidence retains four inventories and three independent exact download pairs, with `signed_in_dedicated_test_account=false`. Dedicated-account defaults remain strict. Independent replay of the unchanged folder auditor still refuses the raw saved artifact with `single_account_ppt_saved_positive_or_preservation_failed`; no registration receipt is created. Automated-model qualification, selection/final eligibility, admissions, and official credit remain zero.

The historical proposal evidence is retained unchanged. Corrected source hashes, artifact hashes, counts, and scope are in [the independent review record](evidence/office-ppt-one-collection-independent-review-20260930.json). A later development-only registration adapter requires explicit source-control integration and a fresh registered TRAIN collection; neither step has happened in this review.

Run the corrected artifact audit from this checkout with a frozen private collection and a fresh private output directory below `work/`:

```bash
PYTHONPATH=.:src python3.14 -m tools.run_ppt_native_train_collection_proposal_v1 \
  --collection "$PPT_TRAIN_COLLECTION" --out "$PPT_TRAIN_REVIEW_OUTPUT"
```

Run the scoped offline tests with:

```bash
PYTHONPATH=.:src python3.14 -m unittest \
  tests.test_ppt_native_train_collection_proposal_v1 \
  tests.test_office_existing_account_folder_train_control_v1 \
  tests.test_office_single_account_train_pilot_v1 \
  tests.test_office_single_account_candidate_control_v1 \
  tests.test_stage_office_single_account_train_sources_v1 \
  tests.test_pptx_title_size_guard -q
```
