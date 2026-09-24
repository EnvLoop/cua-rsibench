# Financial model 01_01: offline artifact-oracle calibration

This is a reproducible **offline** calibration for one difficult [SpreadsheetBench 2](https://arxiv.org/html/2606.29955) Financial_Model instance, not a Microsoft Excel for the web qualification or a model score. The pinned source archive has SHA-256 `17147ef9578cd57ce76c9a719d19da7821f3e5cb0d8f776c820f699fdcdb761c` at Hugging Face revision `5a2215ed4121945ab09d8723df2995602090b042`. The task input has 25 sheets and 3,943 existing formula cells. Its trusted gold workbook adds **82 formulas in six sheets**. The formulas and cached answer values stay in evaluator memory; no source workbook, instruction, or answer is committed here.

[`hard_excel_v2_ooxml_oracle.py`](../../tools/hard_excel_v2_ooxml_oracle.py) expands OOXML shared formulas before comparing cells. That matters because a raw XML diff reports hundreds of formula changes caused only by the gold workbook's serialization. After normalization, all 82 real additions lie inside the source's declared answer ranges and **no other cell value or formula differs** between input and gold. The oracle freezes those formulas, checks that each candidate has a numeric cached result close to gold, and rejects changes to every other nonblank cell's value or formula. It also checks sheet order, date system, sheet visibility, merged ranges, and defined names. It ignores style indices because the gold file renumbers them; it does not certify equivalent formatting, charts, notes, or other embedded objects.

| Offline probe | Result |
|---|---|
| Unmodified source gold | Pass |
| One target formula replaced while leaving its good cached value | Rejected |
| One unrelated numeric cell changed while leaving targets correct | Rejected |

The synthetic negatives test two distinct failure paths, but their construction is not a substitute for a visible GUI completion. The oracle is independent of the upstream scorer's implementation, **but its exact target formulas are gold-derived**. It does not prove formula-cache freshness or native Excel recalculation. Correct alternative formulas may be rejected; copied gold formulas with forged caches may pass. Hidden input perturbations and independently calculated invariants are still needed before official admission. The already observed untouched Excel-web round trip for this input preserved cell values/formulas but removed two Note drawings and four package parts; this oracle does not waive that preservation issue. There is still **no GUI-positive completion, negative GUI run, reset proof, or qualified final task** for this workbook.

Run the public synthetic tests after installing the optional `excel_v2_oracle` dependency, then run the private source calibration without publishing its archive:

```bash
python3 -m unittest tests.test_hard_excel_v2_ooxml_oracle -v
python3 tools/hard_excel_v2_ooxml_oracle.py \
  --archive work/scale-v06/sources/spreadsheetbench-v2.zip \
  --task-id 01_01 --self-check
```

The private calibration output is summarized without answer content in [`hard-excel-v2-01-01-oracle-2026-09-24.json`](hard-excel-v2-01-01-oracle-2026-09-24.json). The paper and dataset card disagree on license labels, so no source assets are redistributed.
