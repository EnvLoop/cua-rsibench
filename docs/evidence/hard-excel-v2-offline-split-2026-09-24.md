# Hard Excel candidate split (offline, 2026-09-24)

The pinned [SpreadsheetBench 2](https://arxiv.org/html/2606.29955) Financial_Model and Debugging manifests contain 200 task instances but only 30 base workbook families. This audit creates a **provisional 100-task final candidate set** from 15 families and a **20-task selection candidate set** from three different families. It does not certify a single task for Microsoft Excel for the web or create a hidden final exam. The workbook files and task instructions remain outside this repository's public artifacts.

The exact source archive is Hugging Face revision `5a2215ed4121945ab09d8723df2995602090b042`, SHA-256 `17147ef9578cd57ce76c9a719d19da7821f3e5cb0d8f776c820f699fdcdb761c`. [`prepare_hard_excel_v2_split.py`](../../tools/prepare_hard_excel_v2_split.py) parses all 200 source records, groups tasks by their gold base workbook, and inspects the first input from each family. It requires at least seven sheets and 1,000 existing formula cells, excludes external links, data connections and VBA from this first web track, and sends workbooks with more than 400,000 instantiated cells to a separate UI-budget review. These are **triage thresholds**, not a validated measure of reasoning difficulty or compatibility.

| Offline result | Count |
|---|---:|
| Published Financial_Model + Debugging instances | 200 |
| Base workbook families | 30 |
| Families passing the structural screen | 22 |
| Provisional final | 100 instances / 15 families (50 financial, 50 debugging) |
| Selection | 20 instances / 3 families (10 financial, 10 debugging) |
| GUI-qualified tasks | **0** |

For the 15 final families, the first input has **7–25 sheets** (median 12), **1,014–73,063 formula cells** (median 2,009), and **4,374–394,080 instantiated cells** (median 40,453). The 20 selection tasks have no base-workbook family overlap with the 100 final candidates. The script uses a fixed hash ordering so reruns on the same pinned archive choose the same families, and it outputs task identities and hashes without copying instructions, inputs, or answers. The private generated JSON is `work/scale-v06/excel-hard-offline-split.json`.

This split improves the starting difficulty and makes the unit of diversity explicit. It still repeats tasks within 15 base models, and all published source gold files may be discoverable by a model. Admission to a benchmark requires a per-task untouched Excel-web save/download comparison, a visible-GUI positive solution, an independent saved-artifact verifier, wrong-answer and unrelated-edit negatives, hidden input perturbation, and reset proof. A final set intended to be truly hidden needs new private variants or independently authored families, with source-document and template leakage audited. The already tested 25-sheet Education model opened in Excel web and retained cell semantics on an untouched round trip, but Office removed two Note drawings; it has **not** passed whole-workbook preservation or positive task completion.

The [paper](https://arxiv.org/html/2606.29955) states CC BY-SA 4.0 for the dataset while the [Hugging Face card](https://huggingface.co/datasets/KAKA22/SpreadsheetBench-v2) labels it MIT. This release does not redistribute the workbooks or copied task text while that discrepancy remains unresolved.

Reproduce locally after obtaining the pinned upstream archive:

```bash
python3 tools/prepare_hard_excel_v2_split.py \
  --archive work/scale-v06/sources/spreadsheetbench-v2.zip \
  --out work/scale-v06/excel-hard-offline-split.json
python3 -m unittest tests.test_prepare_hard_excel_v2_split -v
```
