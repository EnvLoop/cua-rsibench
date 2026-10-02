# SEC Excel transfer: two-graph source availability screen

**Status: original-filing identity and field availability only.** An
evaluator-private, owner-readable pilot record now holds four candidate
issuer/accession pairs: two distinct issuers for each of two signed Excel
skill-card graphs. The four issuer CIKs and four original Form 10-K accession
numbers are pairwise distinct and do not occur in the frozen 140-slot Excel
train/selection/final registry. Two new authored training-template family
reservations are distinct from the original template reservations. No
workbook, fault, answer, GUI episode, or model output was created.

For each candidate, the evaluator opened the SEC filing-detail page and its
listed original 10-K HTML, then inspected two comparable annual periods of the
fields required by the privately signed graph card. The read-only
[`source-availability screen`](../../tools/sec_excel_transfer_source_availability_v1.py)
recomputes the two profiled accounting identities in both years, validates the SEC URL/CIK/
accession structure, signed-card mapping, two-per-graph allocation, and
issuer/accession/template disjointness. Six synthetic unit tests, including
five fail-closed mutations, pass. Its [field-limited receipt](sec-excel-transfer-two-graph-source-availability-2026-09-29.json)
contains counts and a salted commitment, with no selected issuer, accession,
private graph name, fact value, or task identity.

The host attempted direct SEC access using a declared `User-Agent` and a pace
below one request per second. Both `www.sec.gov` and `data.sec.gov` failed at
the TLS handshake before returning an HTTP response. The official pages were
therefore inspected through browser research; original filing bytes and
Company Facts JSON were **not** captured locally. The two-period arithmetic
screen verifies the privately transcribed values against each other, not an
independent replay of original source bytes. A subsequent source acquisition
must save raw original 10-K and accession-filtered Company Facts with hashes,
verify the selected values and reporting scope independently, and retain the
SEC's [declared User-Agent guidance](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)
and [10-request-per-second fair-access limit](https://www.sec.gov/filergroup/announcements-old/new-rate-control-limits).
The [SEC API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
describes the submissions and Company Facts endpoints. The selected filing
identities remain evaluator-private. Publication is limited to derived filing
facts and EnvLoop-authored scenarios; no complete issuer filing is packaged.

The public receipt therefore records **4 candidate 10-K identities and 4
two-period field profiles screened**, but **0 independently verified complete
fact sets, 0 sourced/admitted training analogues, 0 workbooks, 0 saved-OOXML
controls, 0 original Excel-web controls, and 0 official final admissions**.
The remaining 22 source slots and every case-admission control are pending.
