# Magento ordinal-32 pre-seed orchestration interruption — 2026-09-27

The first long continuation after the [one-case search-drift recovery](evidence/magento-original-preseed-index-drift-retry-2026-09-27.md)
was launched from a worker session that ended while `positive-prepare` was
still running. Its durable journal has a sweep start and the first prepare
intent, but no completed step, task seed, actor GUI action, verifier score, or
model call. The exact two disposable no-mount containers remained running.
The [field-limited read-only audit](evidence/magento-original-interrupted-preseed-2026-09-27.json)
binds their image and hashed identities to the stopped journal. The same
stopped journal and pair are retained as infrastructure evidence;
this is not a score and adds no candidate to the 32 GUI controls.

The [exact-pair reconciliation controller](../tools/reconcile_magento_interrupted_preseed_v1.py)
is restricted to that journal, ordinal and prepare intent. Audit mode verifies
the pinned app and search images, loopback ports, dedicated network, zero
mounts, zero benchmark quote pages and hash-bound container identities without
mutating them. Cleanup mode requires the saved audit, repeats the checks,
records intent, and stops/removes only those identities. It neither repairs
the search index nor seeds a task. The private audit, original journal and
cleanup receipt stay under ignored `work/`.

Once exact cleanup is verified, the unchanged evaluator may start **one** new
serial continuation at ordinal 32 with the same frozen plan, source,
application image, GUI controller and verifier, in a fresh private output
directory. The original interrupted intent remains visible. A second
orchestration interruption before seeding stops this mode of recovery and
requires a durable process host; it is not silently retried. Any task-seeded
or model-visible failure must instead follow its own frozen failure rule.
No official final task or researcher outcome is credited by this amendment.
