# Second selection control: post-intent exact-frame failure

The gated same-ID selection retry passed its separate cold-baseline check and
opened the native supplier-confirmation PDF. Eight positive-phase GUI actions
completed. The next intended action was a double-click in the purchase line's
quantity editor. Its step-8 intent was durably recorded, but there is no
step-8 dispatch result, pre-intent rejection, saved positive readback, or
negative phase.

The exact-return guard was active. Its step-8 parse sample matched the
observed PNG exactly. All six dispatch samples then showed one identical
alternate image: only the two previously audited noninteractive tab-border
pixels at `(41, 419)` and `(132, 419)` changed from RGB
`(235, 237, 239)` to `(235, 237, 240)`. The observed PNG did not return,
so the source-bound adapter raised `stale_frame` before the mouse action.
This is a **post-intent, pre-dispatch** failure. The recorded intent makes
the attempt terminal under the current no-replay rule.

The [independent read-only receipt](odoo-v066-selection-second-post-intent-stale-2026-09-29.json)
reopens the source-bound action intents/results, all 23 physical guard PNGs,
the source-PDF frame, gate, journal, lease, saved SQL, and full physical
filestore manifests. The saved baseline and restored SQL are byte-identical;
the saved restored and current 888-entry filestore manifests equal the frozen
manifest. A separate read-only archive check found all 888 frozen files with
matching hashes. The worker lease acquired and released correctly; selection
web and database services are exited with code 0, and locks are free. A live
post-exit Docker-volume rescan was not performed.

Both failed attempts remain intact. Their two-row journal files have the
same bytes and SHA-256 because the journal rows contain the same case and
ordinal without a run nonce. The distinct batch intents, source freezes,
attempt intents, and directories establish which run produced each record.
Future journals should bind a run-specific nonce or batch-intent hash;
historical rows must not be rewritten.

A possible dated profile may treat exactly those two observed border-pixel
variants as equivalent **only at dispatch** when URL, task binding, target
position, and all other pixels remain unchanged. It must retain both PNGs
and a distinct physical-dispatch receipt, and the independent auditor must
recompute the pixel and target checks. That proposal is not part of this
failed attempt. A future same-ID attempt would require a fresh source freeze,
new run directory, and separate current SQL/full-filestore baseline authority.
No further GUI retry, model attempt, or official final admission is claimed.
