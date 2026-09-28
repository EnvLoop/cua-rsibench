# 2026-09-28: single-account Office candidate controls

**Pre-result implementation; no live Office/browser/model call and no
official admission.** The first Office pilot may use one dedicated,
already-signed-in Microsoft test account. A second account, Microsoft Entra
app registration and Graph delegated tokens are not prerequisites for this
manual development path. The existing two-account Graph lease remains an
optional, stronger isolation track.

The [train pilot](FULL_STUDY_OFFICE_SINGLE_ACCOUNT_TRAIN_PILOT.md) now shares
its exact private folder-inventory, screenshot, six-download and fresh-reset
checks with [`office_single_account_candidate_control_v1.py`](../tools/office_single_account_candidate_control_v1.py).
For each evaluator-private **selection** or **final candidate** identity,
the latter requires the matching source/template family hashes and split
path, one direct PowerPoint/Excel web document URL, and a distinct reset
document. A private, operator-reviewed navigation trace has exactly six
ordered events: open the dedicated folder, open/edit/save the actor document,
open the reset document, return to the folder. Every URL must be exactly the
folder, actor or reset URL bound in that task's private spec. The four folder
inventories still show actor-only, actor-only, reset-only, then empty. Every
before/saved/reset state has two independent local downloads whose bytes
must agree. The event timestamps must be consistent with the inventories.

The evaluator alone reads the hidden task specification, WDI/SEC source and
reference answer from local `work/`. For PowerPoint, the original seven-slide
WDI verifier covers the active v13 selection three-target and final
four-target variants, including the native chart, embedded workbook and
unrelated slide preservation. For Excel, the current implementation accepts
only the **SEC integrated** selection/final workflow: 33 or 48 checked
targets, two counterfactual numeric profiles, structure and non-target
preservation. Other Excel candidate workflow families fail closed until
their own independent scorer is wired. The known-positive saved artifact
must score 1 and the fresh copy must be neutral. A missing source, changed
split/template, navigation outside the allowlist, extra folder file,
changed download pair or reset drift produces no passing receipt.
The CLI preserves an invalid private receipt with the input hashes and
reason code when it can safely create a fresh output directory; it never
turns a verifier or infrastructure failure into score zero.

The private spec schema is `cua-office-single-account-candidate-spec-v1`.
It carries `cell_id`, `split` (`selection` or `final_candidate`),
`task_id`, `package_sha256`, `task_ref`, `source_ref`, optional
`cases_ref` / `case_id` / `reference_ref` for integrated Excel,
`source_group_sha256`, `template_group_sha256`,
`account_principal_sha256`, `folder_label_sha256`,
`browser_run_sha256`, `folder_url`, `actor_item`, `reset_item`,
`pre_result:true`, `hidden_final_model_attempts:0`, and
`official_final_credit:0`. The evidence schema is
`cua-office-single-account-candidate-evidence-v1`: it reuses the train
pilot's `manual_gui` and four `phases`, adds a private
`browser_trace_ref`, and binds the exact spec SHA-256. All file references
are relative to ignored `work/` and hash-checked. The local command is:

```sh
PYTHONPATH=.:src python3.14 -m tools.run_office_single_account_candidate_control_v1 \
  --spec "$OFFICE_CANDIDATE_SPEC" \
  --evidence "$OFFICE_CANDIDATE_EVIDENCE" \
  --out "$OFFICE_CANDIDATE_CONTROL_OUT"
```

Every receipt binds one private task ID, source/template family, browser-run
hash, exact downloads, navigation trace and verifier source. It is a
**manual pre-result candidate control**, not a Qwen attempt or official
selection/final score. Both the receipt and public status set
`model_calls:0`, `official_selection_credit:0`,
`official_final_credit:0`, `official_final_admitted:false`,
`common_six_cell_freeze_verified:false`, and
`full_cell_denominator_completed:false`. Injectable scorers in fake tests
are labeled `fake_candidate_test_only`.

One train source from the **active seventh-reserve PowerPoint v13** pool and
one train source from the SEC integrated 20/20/100 pool have also been
staged locally as byte-identical actor/reset upload candidates. Their
private evaluator subtrees hold task specifications and positive/reference
files; upload subtrees contain only source copies. The offline stage receipt
hash is `a1689030acd958734e41caa692123390eeef61cec16a9ec837b30e44b3a5a33e`.
No file was uploaded and no task ID or answer appears here. The staging
script explicitly refuses the older PowerPoint v12 source.
It is reproducible offline with
`tools.stage_office_single_account_train_sources_v1` using private
`--ppt-v13-root`, `--excel-integrated-root`, and fresh `--out` paths.

This profile is **weaker** than an identity-bound one-file ACL. The same
account may see files outside the dedicated folder. Folder contents and
browser navigation are operator-attested screenshots/trace entries; without
Graph readback, the downloaded bytes are not cryptographically tied to the
claimed cloud item ID. The receipt explicitly marks account-wide ACL and
item identity and fresh browser-sandbox independence as unverified. A full
100-ID final denominator in each cell,
all source-specific Excel scorers, the common six-cell freeze and an
explicit review of this weaker isolation boundary remain outstanding.
This code cannot promote any candidate to official admission.

**Minimum live steps after the user confirms an unlocked Office session:**
for one private ID at a time, upload only the actor copy into an otherwise
empty dedicated folder, open its direct Office web document URL, make the
known-positive GUI edit, download it twice, remove it, upload/open a fresh
neutral copy, download that twice, remove it, and record the four folder
screenshots plus the bounded navigation trace. Keep source/gold/reference
files outside OneDrive. Run the local auditor with a fresh private output
directory. Do not expose hidden final items to a model during these controls.

Offline checks:

```sh
PYTHONPATH=.:src python3.14 -m unittest \
  tests.test_office_single_account_train_pilot_v1 \
  tests.test_office_single_account_candidate_control_v1 \
  tests.test_stage_office_single_account_train_sources_v1 -v
```
