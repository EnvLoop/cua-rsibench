# PowerPoint web TRAIN native control — 2026-09-30

One manually executed TRAIN control now passes Microsoft PowerPoint for the web save/download, strict saved-artifact scoring, source preservation and reset checks. The existing verifier stayed unchanged.

| Native control | Score | Correct targets | Preservation | Unexpected parts |
|---|---:|---:|---|---:|
| Fresh positive | 1.0 | 4/4 | Pass | 0 |
| Three-target near miss | 0.0 | 3/4 | Pass | 0 |
| Fresh reset | 0.0 | 0/4 | Pass | 0 |
| Collateral control | 0.0 | 4/4 | Fail | 1 |
| Same-file restoration | 0.0 | 0/4 | Pass | 0 |

The clean application-generated preparation completed a four-target edit/restore cycle and a fresh-session restored-baseline readback. All four isolated control inputs started byte-identically. Five source-equivalence checks preserved seven-slide text/table content, every embedded workbook member and all 26 chart-cache values. Two initial failed attempts and three restoration intermediates remain retained privately.

Seven pages of the fresh positive passed individual visual review after independent read-only PDF rendering. Microsoft PowerPoint for the web executed the task; the separate visual renderer performed inspection only.

The control remains unregistered. Registered native TRAIN, selection, official final and model counts remain **0**. Account/file identities, filenames, exact task/source lineage, downloaded artifacts, screenshots and evaluator answers remain private. The [aggregate receipt](office-ppt-transfer-native-train-control-2026-09-30.json) publishes counts and hash commitments.

Private saved-audit SHA-256: `dc7f46e508ea54ddc437fa19cc3d4c705acf32eefc5e74984b672f7a6a6b5129`.
