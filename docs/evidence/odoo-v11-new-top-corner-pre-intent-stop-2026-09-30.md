# Odoo v11: new top-corner raster rejected before price intent

The reviewed v11 TRAIN run is terminal. It completed eight GUI actions and
three ready price-editor identity probes, then failed at the first final
stability sample in each observation. It did **not** exhaust six passive
rounds. No positive price double-click intent, dispatch, saved positive, or
negative control exists. SQL and the complete restored filestore exactly
match the baseline; service restoration is the runner's receipt, without a
live Docker query by this auditor.

The [read-only forensic tool](../../tools/audit_odoo_v11_pre_intent_border_stop_20260930.py)
reopens 132 files and all 35 guard PNGs. The first rejected pair changes three
pixels at the top-left form border: `(16,155)`, `(16,157)`, `(17,157)`. The
second and third pairs also change the four previously observed bottom-left
corner pixels. All seven changes are exact RGB pairs retained in the source
audit. The input editor and source identity probes are ready. Visual inspection
places the new pixels on the rounded form border, outside the editable data.
V11 correctly refuses this newly uncalibrated pattern under its frozen rule.

A prospective minimal recovery would define exactly two whole RGB states for
the three top-corner pixels and the two whole states for the existing four
bottom-corner pixels, admitting only their four combinations. It must require
exact equality everywhere else in each full image and retain RFQ, route,
product, value, focus, modal, task/frame and editor-bounds identity checks at
both parse and dispatch. An arbitrary seven-pixel allowance or longer timing
loop would not establish that same legitimate UI state. That new equivalence
is not implemented or live-qualified by this forensic receipt.

The historical v11 source freeze and run remain unchanged and non-replayable.
This failure does not overwrite the retained v10 saved positive. All official
final admissions and model attempts remain **zero**.
