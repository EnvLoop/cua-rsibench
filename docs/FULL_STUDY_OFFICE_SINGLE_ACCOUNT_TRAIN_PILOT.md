# Single-account original Office train pilot

**Status: local auditor and fake tests only.** This path uses the already
signed-in dedicated Microsoft test account as the GUI actor. It requires no
second account, Microsoft Entra app registration, delegated Graph token,
E2B lease, or model call for the **first manual train control**. No Office
browser was accessed while implementing it. Official selection and final
admissions remain zero.

The local evaluator keeps the original task specification, source workbook
or seven-slide deck, and the reference answer under ignored private `work/`
outside any synced OneDrive folder. Only the current train task file is
placed in a new dedicated cloud folder. The operator uses the **original
PowerPoint or Excel for the web GUI** to make the visible correction and
save it. The actor item is then removed, one separate source-equivalent
neutral copy is opened as the reset, and that copy is removed after the
reset check. The four operator-reviewed folder inventories must show:

| Phase | Files visible in dedicated folder |
| --- | --- |
| Before | Exactly the actor train item |
| Saved | Exactly the same actor train item |
| Reset | Exactly one distinct neutral train item |
| Cleanup | Empty |

Each inventory has a private screenshot and timestamp. The evidence package
also needs different before/after GUI screenshots and **two separate browser
downloads** of the exact item at each of before, saved and reset. The two
bytes in every pair must match. The actor and reset OneDrive edit URLs must
have different `sourcedoc` GUIDs. The evaluator's local auditor never calls
Microsoft, a browser, Graph, E2B, Tinker, or a model API.

The private spec uses schema `cua-office-single-account-train-spec-v1` and
exactly these fields: `cell_id` (`powerpoint-web` or `excel-web`),
`split:"train"`, `task_id`, `package_sha256`, `task_ref`, `source_ref`,
`cases_ref`, `case_id`, `reference_ref`,
`account_principal_sha256`, `folder_label_sha256`, `actor_item`,
`reset_item`, and `official_final_credit:0`. Each file reference has
`path` (relative to `work/`) and `sha256`. Each item has only `edit_url`
and `file_name`, using a `EL-PPT-Train-*.pptx` or
`EL-Excel-Train-*.xlsx` OneDrive edit URL. A name suggesting gold,
answers, a reference, selection or final data is refused. For PowerPoint,
`cases_ref`, `case_id`, and `reference_ref` are `null`; its private
`task.private.json` and raw `source.pptx` remain local. For Excel, provide
the original `actor.xlsx`, one `train_candidate` SEC case manifest, case ID,
and positive `reference.xlsx` in the evaluator's private directory. The
reference is **never** uploaded to Office.

The private evidence uses schema
`cua-office-single-account-train-evidence-v1` with `spec_sha256`,
`split:"train"`, `manual_gui`, and `phases` for `before`, `saved`,
`reset`, `cleanup`. `manual_gui` records
`operator_reviewed:true`, `original_office_gui:true`,
`signed_in_dedicated_test_account:true`, `model_calls:0`,
`application_api_edits:false`, the actor edit URL SHA-256, and two PNG
references. Each phase has an `inventory_ref`; the first three also have
two `downloads` references. Inventory files use schema
`cua-office-single-account-folder-inventory-v1`, their phase, the same
account/folder hashes as the spec, the exact current item list above, a
PNG screenshot reference, `operator_reviewed:true`, and an ISO 8601
`observed_at_utc` timestamp. The four timestamps must increase. The
auditor derives each item's filename, edit URL hash and `sourcedoc` hash
from the private spec; those exact three fields form each inventory item.

After the operator has placed all files under private `work/`, run the
read-only local audit:

```sh
PYTHONPATH=.:src python3.14 -m tools.run_office_single_account_train_pilot_v1 \
  --spec "$OFFICE_SINGLE_TRAIN_SPEC" \
  --evidence "$OFFICE_SINGLE_TRAIN_EVIDENCE" \
  --out "$OFFICE_SINGLE_TRAIN_AUDIT"
```

For PowerPoint, the auditor derives the signed target from pinned WDI data,
checks the saved Office-normalized seven-slide baseline against the local
raw source, scores the downloaded positive, and requires the native chart,
embedded workbook and every unrelated slide part to remain intact. For
Excel, it calibrates the pinned SEC formula/numeric evaluator against the
local reference, requires a saved positive with no unrelated cell or
structure change, and a semantically identical fresh reset. Any missing
download, changed pair, extra folder item, failed save or reset, wrong
split, or changed private file is **invalid** and produces no passing
receipt. A passing result remains a **manual train development control**
with `model_calls:0` and `official_final_credit:0`. The private receipt
hashes the exact independent verifier source files. Injectable fake scorers
used by offline tests are marked `fake_test_control_only` and cannot be
mistaken for an independently scored manual control.

This is intentionally a weaker boundary than the optional
[two-account Graph lease](FULL_STUDY_OFFICE_PERSONAL_GRAPH_BOOTSTRAP_RUNBOOK.md).
The signed-in account may still see other files elsewhere in OneDrive.
Folder contents and GUI provenance are operator-attested by screenshots;
without a delegated Graph owner readback, downloaded bytes cannot be
cryptographically tied to the claimed cloud item ID. The receipt explicitly
marks account-wide ACL, one-file permission and download-item identity as
**not independently verified**. This pilot must not be promoted into a
hidden-set, 20-selection, 100-final, or 24-campaign result. Higher-assurance
publication runs still need independently qualified isolation and billing.

**Minimum live inputs:** unlock or manually operate the existing signed-in
PowerPoint/Excel web session; create one empty dedicated train folder and
two distinct source-equivalent task/reset copies; keep the task source and
reference only in evaluator-private local storage; capture the four folder
inventories, two GUI screenshots and six original-browser downloads. No
second account or Entra app registration is required for this first
manual development control.

Offline fake and real-OOXML tests:

```sh
PYTHONPATH=.:src python3.14 -m unittest \
  tests.test_office_single_account_train_pilot_v1 -v
```
