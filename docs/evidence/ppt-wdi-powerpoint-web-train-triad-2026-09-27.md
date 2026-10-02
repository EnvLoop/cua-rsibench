# Original WDI PowerPoint web: one train-source saved-state control

**Status, 2026-09-27:** a development control on one exposed **training** source. It admits **zero** official final tasks, contains **zero** model actions, and is not a result from the planned 24-campaign study. The [aggregate receipt](ppt-wdi-powerpoint-web-train-triad-2026-09-27.json) binds the evaluator-private cloud items and downloaded artifacts by SHA-256 without publishing the account, task identity, instructions, or answer.

The input is an original seven-slide monitoring brief derived from a pinned World Bank WDI snapshot under CC BY 4.0. Its analyst brief, defect, and committee rule are benchmark-authored simulations. The source contains a native chart and its embedded Excel workbook. A preliminary upload used the pre-finalization draft, which lacked those chart parts; that upload was rejected at source preflight and contributes no control score. The accepted run uploaded the chart-finalized source into four distinct private OneDrive items in the dedicated test account.

The evaluator first downloaded an untouched copy and confirmed its bytes matched the local source. In PowerPoint for the web, the evaluator then made a reversible text edit and restored the original text in that copy to obtain an Office-saved baseline. The source and that baseline had identical visible text across all seven slides, identical embedded workbook bytes, and semantically equal native chart labels and numeric cache values; Office rewrote some package metadata and two numeric strings at floating-point representation precision. The evaluator froze the normalized baseline **before** scoring the other saved copies.

| Distinct cloud copy | GUI action | Independent downloaded-PPTX readback |
| --- | --- | --- |
| Positive | Corrected the flagged training summary | Target correct, all other saved package state preserved: **1.0** |
| Near miss | Saved a plausible but incorrect summary | Target incorrect, all other saved package state preserved: **0.0** |
| Fresh reset | Repeated the same neutral save and restored the original text in a new copy | Matches the frozen baseline under the same narrow metadata rules: **0.0**, as expected for an unrepaired seed |

The [auditor](../../tools/audit_ppt_wdi_web_train_triad_v1.py) read the three downloaded files and checked their source, native chart, embedded workbook, target text, and unrelated package parts. The [verifier](../../ppt_wdi_factory/verify.py) masks only observed PowerPoint-generated bookkeeping within the **named target shape** and the chart's opaque per-series UUID; it still rejects altered chart values, non-target text, and formatting damage. Focused tests cover the metadata masks, text-run split, and chart-value negative. The original failed pre-finalization draft and the raw-to-Office normalization are retained separately in private development records.

The downloaded positive, near-miss, and fresh-copy decks were also rendered to seven-page PDF inspection copies. All seven positive pages were visually checked at full-page scale, including the native chart and source attribution; the contrasting first pages of the near miss and fresh reset were checked separately. The inspection copies are private QA artifacts, not the full-study result paper.

This proves one original training deck can undergo real PowerPoint-web GUI edit, autosave, download, independent positive/negative scoring, and a separate fresh-copy reset. It does **not** establish final-task admission, four-edit final workflows, native chart-legend editing, a Qwen screenshot/action run, legal clearance for every source item, or a PowerPoint-web 100-task denominator. Those gates remain open under the [pre-result protocol](../FULL_STUDY_PREREGISTRATION.md).
