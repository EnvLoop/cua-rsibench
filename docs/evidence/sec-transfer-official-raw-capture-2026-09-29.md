# SEC transfer-source raw capture, 29 September 2026

The [capture receipt](sec-transfer-official-raw-capture-2026-09-29.json) and
[independent offline audit](sec-transfer-official-raw-capture-audit-2026-09-29.json)
bind four candidate original Form 10-K filings to evaluator-private raw source
bytes. The audit re-opened and rehashed **12 files**: four filing indexes, four
primary 10-K HTML documents, and four CompanyFacts JSON snapshots. It matched
each index to the frozen filing identity and primary document, found facts under
each accession with form 10-K, replayed **62** numeric-literal screens, and
rechecked **four** calculated debt totals against their filed components. The
source-availability pilot's salted commitment still matches the earlier public
receipt. No issuer, accession, source URL, or selected fact value is published.

The host's default DNS maps SEC names to a local tunnel address that failed
during TLS negotiation. The capture tool obtained public addresses through
verified HTTPS DNS-over-HTTPS and passed them to `curl --resolve`. Requests
still used the original `www.sec.gov` or `data.sec.gov` hostname for SNI and
certificate verification; every accepted response had HTTP 200 and TLS verify
result zero. The declared contact User-Agent was sent at no more than one SEC
request per second. The official [EDGAR data API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces),
[archive access guidance](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data),
and [fair-access policy](https://www.sec.gov/about/privacy-information) define
the source endpoints and access limits.

This is a source-capture milestone. A numeric literal in a 10-K is not yet an
independent semantic validation of a particular table cell, sign, period, or
unit. Complete fact reviews, authored training workbooks, saved Excel-web
controls, train-analogue admissions, and official final admissions remain
**zero**. The older source-availability receipt is a historical snapshot and
has not been rewritten to imply its then-pending raw capture had already run.
The evaluator-private files and manifest are not distributed with the repo.
