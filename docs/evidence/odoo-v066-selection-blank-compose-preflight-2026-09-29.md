# Selection retry preflight: blank Compose service line

The first explicit no-GUI selection retry preflight exited with
`ScaleControlError` before creating its new run directory or retry-gate file.
The old failed selection attempt remains unchanged. No GUI replay, model
attempt, or official final admission occurred.

Read-only replay against the frozen source and private plan passed the source,
plan, worker, and old-failure checks. The next check asked Docker Compose for
running service names. On this host, zero running services produced one blank
line (`"\n"`). The existing helper represented that as a set containing an
empty string, while the new preflight required an empty set. That exact
predicate explains the reported error; this is a source-bound diagnosis, not
a captured original stack trace. A separate read-only `ps --all` confirmed
that both selection services were exited with code 0.

The dated correction removes blank service names only in this new preflight's
cold-state and restored-state checks. It does not alter the earlier failed
attempt, the GUI action contract, or the train batch. A regression test covers
blank-only output and a real running service. The preflight still must perform
an explicit live SQL and full-filestore baseline query before any selection
GUI retry. See the [field-limited receipt](odoo-v066-selection-blank-compose-preflight-2026-09-29.json).
