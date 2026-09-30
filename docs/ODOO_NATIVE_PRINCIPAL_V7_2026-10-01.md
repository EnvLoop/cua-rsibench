# Native Odoo principal witness after the v6 pre-observation failure

The actual v6 TRAIN attempt stopped at `guard_native_account_binding_missing`
before its first task GUI action or source frame. Its reset and service-state
restoration passed. The v6 source and consumed attempt remain unchanged.

A separate authorized read-only probe retained eight native DOM samples on the
same original TRAIN worker. The first sample had no navbar/avatar while the
application hydrated; the remaining seven each had one visible loaded avatar.
Its source and current source matched a `res.partner` avatar resource. V6 only
recognized `res.users`, so it returned an empty account UID even after loading.
A first probe failed at login HTTP readiness; its service state was explicitly
restored before a second bounded probe. Neither probe edited a task or queried
an account API.

The official [Odoo 18 UserMenu source](https://raw.githubusercontent.com/odoo/odoo/18.0/addons/web/static/src/webclient/user_menu/user_menu.js)
uses the user's partner ID for its avatar resource. V7 binds an explicit typed
resource token, `res.partner:<id>` or `res.users:<id>`, after trusted browser
login. It never presents a partner ID as a user UID. The original native selector
is retained; only one visible fully loaded avatar with matching same-origin
source/current-source model, positive ID and `avatar_128` field can bind.
Foreign origin, unsupported resource, ambiguous/missing/loading avatar or source
mismatch fails closed. Credentials alone cannot produce a principal witness.

Before binding, v7 takes up to eight passive metadata observations, with fixed
delays totaling 1.68 seconds. Each raw getter result is saved privately before
any missing-principal rejection, making future failures inspectable. No GUI
action, task retry or provider request is performed by this readiness getter.

The new getter was then exercised in eight additional read-only native samples:
all supplied a valid typed partner token. Services were restored again, with
zero task edits, case replays or provider calls. These are native getter checks,
not a passing TRAIN case, qualification control or model outcome.

V7 is an isolated namespace over exact pinned v6 source. All ownership, actual
Unix lease, credential-file hash, native window/origin, nonce/TTL, safe target,
viewport, rejection-budget, saved-state/reset and no-regression rules remain.
The complete four-family 20-selection/100-final roster is unchanged. Old v6 or
earlier TRAIN proofs cannot admit v7. Every model slot and trusted control uses
the same new adapter and typed principal rule.

Validation: six principal/getter tests, six real Unix-lease/fake-UI adapter tests
and nine worker/facade tests pass. The actual native getter test reopens all
eight new retained samples. Preservation of v6 source is enforced by hashes;
no native case has been rerun by this repair.

Use `tools.odoo_v066_native_surface_qualification_v7` to prepare fresh TRAIN,
selection and official-hidden plans and run namespaces. Root source review
must precede one fresh native TRAIN case and its independent source-frame
finalization, followed by the unchanged full 20/100 qualification controls.
The six-cell common ratification and formal model campaign remain separate.
