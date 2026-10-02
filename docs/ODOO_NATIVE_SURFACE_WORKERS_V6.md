# Odoo native surface workers v6

The v6 facade integrates the shared native safety envelope into original Odoo
workers. It preserves the frozen v2 source files and loads them in an isolated
namespace with checked, exact substitutions. SQL scoring, filestore and database
reset, source attachments, checkpoint binding, paid sampling, worker leases,
rosters and budgets retain their existing implementation.

`enterprise_fallback/odoo18/native_surface_workers_v6.py` supplies the existing
worker APIs. Teacher, base, selected checkpoints and evaluator controls share
`OdooV066NativeSurfaceAdapter`. The worker binding includes the shared policy
hash and all reused/new runtime source hashes. Historical v2-v5 TRAIN receipts
cannot satisfy the new v6 prerequisite.

Lease/evidence binding happens before the first observation:

- Evaluator controls bind to the attempt artifact root and actual worker private
  directory after constructing the action journal.
- Teacher workers bind the active adapter after opening the real backend, to the
  episode artifact root and actual TRAIN worker private directory.
- Selection workers bind the newly constructed adapter to its task artifact root
  and actual selection worker private directory.

The sampling freshness getter delegates to the adapter's nonce/TTL getter and
does not compare screenshots. Dispatch takes a fresh native snapshot and real
lease evidence through the adapter. Recoverable native rejections return their
actual status and consume the existing bounded model turn. The next observation
carries truthful separately versioned rejection feedback and a new nonce. The
same action is not replayed or relocated.

The teacher worker's own post-sample validation uses the adapter's pure bound
syntax check, allowing dispatch to retain current native/TTL rejection evidence.
An external `sample_teacher` callback may still enforce the legacy TTL before
returning an action. Until that shared helper receives an equivalent prospective
amendment, such a callback failure retains its original evidence and stops; it
cannot be relabeled as a recovered native action or replayed automatically.

Teacher dispatch returns its actual result. A rejected finish action cannot end
the teacher episode. A logical finish has status `finished` only for an action
of type `finish`; its durable intent has no native driver-success claim. Native
actions require actual `applied` results. Qualification controls stop on any
rejection, leaving the original intent and native rejection artifacts intact.
Rejected controls never receive a successful result or trace entry.

`tools/odoo_v066_native_surface_qualification_v6.py` retains metadata-only
`prepare`, explicit live `run --execute`, and saved-only
`finalize-train-control` interfaces. It uses new private plan, proof and run
namespaces. Selection contains all 20 tasks, and official-hidden qualification
contains all 100 tasks; each includes all four families. A new independently
reviewed TRAIN control is required before either full split runs. There is no
resume, historical positive credit, automatic replay, provider call during
preparation, or formal result admission by this facade.

Saved auditing reopens each native guard capsule and its complete observation
and current evidence through the adapter's `audit_guard`. The worker verifies
task/package/step/frame bindings and the actual decision/dispatch status pair.
Controls require accepted/applied evidence, or accepted/finished for a purely
logical finish. The old three-sample raster/material assertions do not apply to
the new safety-envelope profile. The old durable action chain and independent
saved-state verifier still apply.

Source-only tests exercise isolated adapter identity, teacher rejected-turn
recovery, pure-finish semantics, control rejection, metadata-only balanced
rosters, fresh TRAIN prerequisites, old proof rejection and artifact integrity.
They do not establish native qualification. Formal comparisons still need a
pre-result freeze of equivalent policy and plugin bindings across every model
slot/cell, new native qualification, and independent final scoring.
