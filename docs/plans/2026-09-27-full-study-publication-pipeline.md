# Full-study publication pipeline design

This is an implementation plan, not a completed result. The only publishable
input is the frozen six-cell matrix, its complete 24-campaign execution index,
and the exact audited 600-identity / 3,000-slot summary. The builder rebuilds
the matrix and re-runs the result audit rather than trusting a JSON summary by
filename or declared status. It refuses synthetic validator fixtures.

The existing v1 result index intentionally contains no per-attempt action,
latency, wall-time, or timeout classification. A separate hash-bound final
attempt telemetry ledger preserves compatibility with v1 receipts. It covers
every unique checkpoint execution and every attempt inside each of its 100
task outcomes. Each row binds the original attempt receipt hash, records an
explicit timeout subtype (including `none`), action count, elapsed time, and
cumulative provider latency, and links a controlled second attempt to its
first attempt and a frozen retry rule. The publication builder rejects missing,
extra, or mismatched rows. A six-cell independent review bundle separately
binds per-cell source rights, hidden split, GUI trace/readback, and reset/
negative-control checks. Such attestations document independent review; hashes
alone do not prove that the underlying application traces are truthful.

The v1 selection freeze records only final checkpoint identity and aggregate
counts, so a third hash-bound ledger captures each of the 24 ordered research
trajectories. It binds hypotheses, submitted data, training receipts,
checkpoint lineage, valid or invalid selection attempts, strict-gain and
no-regression promotion, cost, time, and final incumbent. First-to-best gains
and post-peak decline are derived only from these source-bound sequences.

The generated English PDF contains a methods section, source-family coverage,
the complete 4 x 6 paired-effect matrix and family-cluster intervals,
all 24 candidate/selection trajectories,
infrastructure failures versus model timeouts, latency/actions/cost, caveats,
and reproducibility bindings. Vector figures and a pseudonymized family-effect
supplement are generated from the same verified source object. A source-hash
manifest accompanies all outputs. The builder writes into a fresh private
directory only after every gate passes; publication remains a separate
privacy and visual review step. Synthetic fixture PDFs are generated only in
temporary test directories with a conspicuous watermark and are never checked
in or presented as results.

Alternative designs considered: (1) render the existing summary alone, which
cannot validate raw input or operational metrics; (2) expand the historical
v1 receipt schema in place, which would break existing fixtures and audits;
(3) separate bound telemetry, trajectory, and independent review ledgers. The
third preserves earlier evidence while enforcing missing publication fields.
