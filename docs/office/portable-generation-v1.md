# Portable original Office generation

The additive generators use public `python-pptx` and `openpyxl`. They require neither Codex's bundled artifact runtime nor Office desktop software. They retain the original independent WDI/SEC saved-OOXML verifiers. Their output is a new artifact epoch with new byte hashes. Historical frozen packages, native receipts and qualification do not transfer to regenerated files.

Install the public libraries in the runner's Python environment:

```bash
python -m pip install python-pptx openpyxl
```

Generate the original WDI20/20/100 plan's editable seven-slide decks, then run genuine offline positive, partial, collateral and chart controls:

```bash
python -m ppt_wdi_factory.build_portable_v1 \
  --plan-root "$FROZEN_WDI_SOURCE_ROOT" --output-root "$FRESH_PORTABLE_PPT_ROOT"
```

The input source root contains its original `candidate-plan.private.json`, task specifications and hash-bound WDI source context. A single task can be built with `--task TASK_JSON --output NEW_SOURCE_PPTX`. Native tables, one editable chart and its embedded workbook remain bound to the original source verifier. Literal chart labels and inline embedded-workbook headers are selected using standard OOXML in the new output only.

Generate the legacy public-source SEC engineering pool (development only):

```bash
python -m sec_excel_factory.build_portable_integrated_v1 --output "$FRESH_PORTABLE_SEC_ROOT"
python sec_excel_factory/prepare_integrated_cases.py \
  --private-out "$SEC_CASES" --public-out "$SOURCE_INVENTORY"
python sec_excel_factory/audit_integrated_cases.py \
  --cases "$SEC_CASES" --workbooks "$FRESH_PORTABLE_SEC_ROOT" --public-out "$OFFLINE_AUDIT"
PYTHONPATH=.:src:sec_excel_factory python -m unittest tests.test_office_portable_generators_v1 -v
```

The SEC generator uses the repository's hash-pinned public companyfacts snapshots. Annual/Q3 source records, filing identifiers, calculation dependencies and authored scenario inputs remain explicit. The unchanged independent verifier re-evaluates formulas under two source/scenario perturbations. The 100 proposed final variants still cover only seven filing pairs, two issuer families and one calculation template; they are development candidates, not an independently sealed final exam.

An actual local run generated and independently checked all140 WDI decks and all140 legacy SEC workbook pairs. The legacy SEC pool is excluded from the active Excel protocol. Its engineering controls do not satisfy the current33-issuer,13-final-graph corpus requirement.

`tools.office_package_inventory_v5` prepares WDI descriptors and development-only legacy SEC descriptors. Its Excel entries must not enter the active study.

The current rich Excel corpus is transported using byte-preserving private replay. It has140 distinct original filings from33 issuer families,16 separate semantic graphs including13 final types,1,997 selected original numeric facts,9,985 formula targets and1,260 isolated faults. The original private source excerpt, actor workbook, reference workbook and independent graph code remain unchanged. Only evaluator-local source addressing and new package descriptors are added:

```bash
PYTHONPATH=.:src:sec_excel_factory python -m sec_excel_factory.rich_private_replay_v1 \
  --private-root "$CURRENT_RICH_SEC_ROOT" --output-root "$FRESH_RICH_REPLAY_ROOT"
python -m tools.office_rich_package_inventory_v6 \
  --ppt-metadata-index "$WDI_EXECUTION_INDEX" \
  --rich-metadata-index "$RICH_EXECUTION_INDEX" --output-index "$CURRENT_OFFICE_INDEX"
PYTHONPATH=.:src:sec_excel_factory python -m unittest tests.test_office_rich_sec_portable_v1 -v
```

The full local rich replay passed all140 original positive references and rejected all140 unrepaired seeds and all1,260 separately isolated saved-OOXML faults. Two source/scenario counterfactuals remain mandatory for valid formula outcomes. The combined private index contains140 WDI and140 rich Excel packages, each with20/20/100 allocation; it includes zero legacy Excel entries. Actor projection exposes only the visible instruction, owned document and generic identity. Gold, private source bindings and graph code stay inside the trusted evaluator.

`tools.office_current_package_v5` reopens and scores rich packages in an isolated Python subprocess. It includes a distinct byte-equal local reset-copy check. Use its `--descriptor`, `--package-root` and `--candidate` arguments for a source-only saved score, or `--reset-output` for a fresh local reset copy. After transporting private packages, `rich_private_replay_v1 --relocate-index INDEX --package-root NEW_ROOT --output-index FRESH_INDEX` verifies each frozen descriptor and writes a fresh host-local index without editing package bytes.

`tools.office_current_worker_cli_v5` provides the existing `policy`, `sources`, `check`, `run-teacher`, `run-selection`, `run-shared` and `run-final` modes. The scoped V5 facade binds the same rich package adapter into authority, execution, teacher, selection, shared-base, final and saved-evidence readers. The original native90-action/720-second actor/1,200-second lifecycle, owned cleanup and600-task/24-campaign admission gates remain intact. Historical V4 source bytes stay unchanged. A fresh source witness and actual V5 native controls are required before provider work. `tools.office_current_neutral_v5 prepare/check/run` supports the same zero-model owned-folder lifecycle with rich packages.

No generation, private replay, local reset or offline control proves Microsoft Office web execution, recalculation, cloud readback or native reset. Native qualification and GUI-admitted final counts remain zero.

The current single-account OneDrive session was observed in the designated empty disposable qualification folder. The documented browser file-chooser upload remains blocked until the user grants the ChatGPT Chrome extension's `Allow access to file URLs` permission. The agent has not broadened that permission, created another account or substituted an imitation application. Native upload/save/download/owned-delete/distinct-reset verification must complete before admitting any cloud task.
