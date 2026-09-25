# Ten additional SEC issuer anchors, with a narrower evidence tier

The [machine-readable receipt](sec-ten-official-crosschecked-anchors-2026-09-25.json) adds ten issuer identities and ten distinct **original** Form 10-K accessions with report periods ending in calendar 2024. For each issuer, the SEC filing index confirms the accession, filing date, CIK, and period end. An independently opened SEC-hosted 10-K or annual-report view confirms both the period-end assets and the annual revenue amount. [`sec_excel_factory/sources/anchors`](../../sec_excel_factory/sources/anchors) publishes **only those two cross-checked facts per issuer**, with their XBRL concept, period, form, accession, fiscal label, unit, and source hashes. Lowe's February 2, 2024 period is correctly fiscal **2023**; the 2025-filed comparative is excluded.

| Issuer | Original filing | Assets, USD m | Revenue, USD m | Official value view |
| --- | --- | ---: | ---: | --- |
| TSLA | [10-K index](https://www.sec.gov/Archives/edgar/data/1318605/000162828025003063/0001628280-25-003063-index.html) | 122,070 | 97,690 | [10-K](https://www.sec.gov/Archives/edgar/data/1318605/000162828025003063/tsla-20241231.htm) |
| IBM | [10-K index](https://www.sec.gov/Archives/edgar/data/51143/000005114325000015/0000051143-25-000015-index.html) | 137,175 | 62,753 | [SEC-hosted annual report](https://www.sec.gov/Archives/edgar/data/51143/000110465925022191/tm2429998d6_ars.pdf) |
| INTC | [10-K index](https://www.sec.gov/Archives/edgar/data/50863/000005086325000009/0000050863-25-000009-index.html) | 196,485 | 53,101 | [10-K](https://www.sec.gov/Archives/edgar/data/50863/000005086325000009/intc-20241228.htm) |
| CSCO | [10-K index](https://www.sec.gov/Archives/edgar/data/858877/000085887724000017/0000858877-24-000017-index.htm) | 124,413 | 53,803 | [10-K](https://www.sec.gov/Archives/edgar/data/858877/000085887724000017/csco-20240727.htm) |
| ADBE | [10-K index](https://www.sec.gov/Archives/edgar/data/796343/000079634325000004/0000796343-25-000004-index.html) | 30,230 | 21,505 | [10-K](https://www.sec.gov/Archives/edgar/data/796343/000079634325000004/adbe-20241129.htm) |
| LOW | [10-K index](https://www.sec.gov/Archives/edgar/data/60667/000006066724000033/0000060667-24-000033-index.html) | 41,795 | 86,377 | [Fiscal 2023 10-K](https://www.sec.gov/Archives/edgar/data/60667/000006066724000033/low-20240202.htm) |
| MCD | [10-K index](https://www.sec.gov/Archives/edgar/data/63908/000006390825000012/0000063908-25-000012-index.html) | 55,182 | 25,920 | [10-K](https://www.sec.gov/Archives/edgar/data/63908/000006390825000012/mcd-20241231.htm) |
| PEP | [10-K index](https://www.sec.gov/Archives/edgar/data/77476/000007747625000007/0000077476-25-000007-index.html) | 99,467 | 91,854 | [10-K](https://www.sec.gov/Archives/edgar/data/77476/000007747625000007/pep-20241228.htm) |
| ADP | [10-K index](https://www.sec.gov/Archives/edgar/data/8670/000000867024000024/0000008670-24-000024-index.html) | 54,362.7 | 19,202.6 | [10-K](https://www.sec.gov/Archives/edgar/data/8670/000000867024000024/adp-20240630.htm) |
| DE | [10-K index](https://www.sec.gov/Archives/edgar/data/315189/000155837024016169/0001558370-24-016169-index.html) | 107,320 | 51,716 | [SEC-hosted annual report](https://www.sec.gov/Archives/edgar/data/315189/000155837025000116/de-20241027xars.pdf) |

The local shell could not directly complete SEC TLS. The ten full companyfacts responses were acquired through a throttled read-only text proxy with an organization/contact User-Agent. Known Apple and Microsoft control responses recovered exactly the previously pinned direct-SEC bytes after removing the proxy's single trailing newline. **Unlike the preceding 16-issuer expansion, these ten full responses have no prior direct-SEC raw hash.** Their raw bodies remain in ignored `work/`, and their other facts are not committed or treated as verified. The manually checked official views plus `freeze_crosschecked_anchors.py` establish precisely two SEC-view-supported facts per new issuer, not provenance of every field in the full proxy payload.

The development inventory now contains **28 issuer identities with at least two official-view-crosschecked anchors**: the earlier 18 source snapshots plus these ten. Only 18 have full companyfacts bytes matched to an independently recorded direct-SEC SHA-256. No new source family here has an Excel-web GUI admission or hidden final task. These twenty published facts are development material and cannot serve as a sealed final exam. Before constructing a 100-case final set, obtain and independently pin the remaining facts for each intended workflow, enforce issuer/accession/template separation, and perform per-task original Excel-web save/download/readback, negative controls, and reset. The ten-issuer count satisfies a **source-identity inventory milestone**, not the full publication admission rule.

Reproduce the verified two-fact extraction from the ignored captured snapshots:

```bash
python3 sec_excel_factory/freeze_crosschecked_anchors.py \
  --raw-dir work/sec-expansion/new-ten \
  --crosschecks sec_excel_factory/new_issuer_official_crosschecks.json \
  --out-dir sec_excel_factory/sources/anchors \
  --report docs/evidence/sec-ten-official-crosschecked-anchors-2026-09-25.json
python3 -m unittest discover -s sec_excel_factory -p test_crosschecked_anchors.py -v
```

The manual crosscheck manifest provides the exact source pages and values. It is an auditable claim about the checks performed, not a cryptographic attestation by the SEC. Future captures must retain the documented at-most-one-request-per-second rate and `SEC_USER_AGENT` organization/contact declaration.
