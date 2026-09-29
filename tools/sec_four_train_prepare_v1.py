"""Prepare four evaluator-private, source-disjoint TRAIN Excel analogue cases.

Uses source-only reviewed SEC data and signed graph cards. Never reads a final
workbook, per-case gold, task text, browser session, or model output.
"""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess

from tools.office_excel_transfer_signed_review_v1 import verify as verify_cards
from tools.office_transfer_source_gate_v1 import EXCEL_SPLIT_SHA


CASH_PROFILE = "cash_train_profile"
INTEREST_PROFILE = "interest_train_profile"
CARD_SIGNATURES = {
    CASH_PROFILE: "2e6e006da0fc88d6025f1c24310543441eba08a31963c59a224ea35359546403",
    INTEREST_PROFILE: "a912e1ee5e25c6288c00d1713a2826af0a74d01065b8dd0844d0508f7ca7926c",
}
CASH_KEYS = ("operating", "investing", "financing", "fx", "net_change",
             "beginning", "ending", "cash", "restricted")
INTEREST_KEYS = ("operating_income", "interest_expense_abs", "cash_from_operations")
CARD_MINIMUM = 9
INDEPENDENT_DEBT_REVIEW_PUBLIC_KEY_SHA256 = (
    "58cd27f21fbd16325c36f0bd2890eeba22dd59256c5a77b92d932075511c1fa8"
)


def _sha(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _read(path: Path) -> tuple[bytes, dict]:
    raw = path.read_bytes()
    return raw, json.loads(raw)


def _require(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError(reason)


def _write_private(path: Path, value: dict) -> str:
    raw = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as out:
        out.write(raw)
    return _sha(raw)


def _verify_signed_extension(*, root: Path, extension_raw: bytes,
                             capture_manifest_raw: bytes, source03_review_raw: bytes,
                             source03_companyfacts_raw: bytes,
                             source03_filing_raw: bytes, pilot_raw: bytes,
                             openssl: Path) -> dict:
    review_file = root / "independent-debt-face-review.private.json"
    sig_file = root / "independent-debt-face-review.private.json.sig"
    pub_file = root / "independent-debt-face-review.ed25519.pub"
    for path in (review_file, sig_file, pub_file):
        _require(path.is_file() and (path.stat().st_mode & 0o777) == 0o600,
                 "independent_debt_review_missing_or_exposed")
    _require(_sha(pub_file.read_bytes()) == INDEPENDENT_DEBT_REVIEW_PUBLIC_KEY_SHA256,
             "independent_debt_reviewer_public_key_changed")
    cmd = [str(openssl), "pkeyutl", "-verify", "-pubin", "-inkey", str(pub_file),
           "-sigfile", str(sig_file), "-rawin", "-in", str(review_file)]
    check = subprocess.run(cmd, capture_output=True, check=False)
    _require(check.returncode == 0, "independent_debt_review_signature_invalid")
    _, review = _read(review_file)
    bind = review.get("source_hashes", {})
    _require(review.get("schema") == "envloop.sec_four_train_debt_face_independent_review.private.v1"
             and review.get("status") == "accepted_for_train_source_transfer_only"
             and review.get("not_benchmark_task_admission") is True
             and bind.get("extension") == _sha(extension_raw)
             and bind.get("capture_manifest") == _sha(capture_manifest_raw)
             and bind.get("prior_semantic_review") == _sha(source03_review_raw)
             and bind.get("companyfacts") == _sha(source03_companyfacts_raw)
             and bind.get("original_10k") == _sha(source03_filing_raw)
             and bind.get("pilot") == _sha(pilot_raw)
             and review.get("checks", {}).get("instrument_period_entries") == 8
             and review.get("checks", {}).get("tagged_zero_dash_faces") == 2
             and review.get("checks", {}).get("extension_zero_fact_ids_bound") is True,
             "independent_debt_review_or_source_binding_changed")
    return review


def _field(value: dict, *, status: str | None = None) -> dict:
    _require(isinstance(value.get("signed_value"), (int, float)), "review_field_without_signed_number")
    return {"value": value["signed_value"],
            "evidence_class": status or ("derived_original_identity" if "derivation" in value
                                         else "original_inline_xbrl"),
            "tag": value.get("tag"), "ix_id": value.get("ix_id"),
            "context_ref": value.get("context_ref"),
            "row_sha256": value.get("row_sha256"),
            "derivation": value.get("derivation")}


def _case(index: int, record: dict, source_review: dict, source_review_sha: str,
          capture_source: dict, card: dict, debt_extension: dict | None) -> dict:
    profile = CASH_PROFILE if index < 2 else INTEREST_PROFILE
    period_index = {row["period_end"]: i for i, row in enumerate(record["periods"])}
    _require(len(period_index) == 2 and
             {row["period_end"] for row in source_review["annual_periods"]} == set(period_index),
             "two_exact_reviewed_annual_periods_required")
    assembled = []
    for p in sorted(record["periods"], key=lambda x: x["period_end"]):
        original_index = period_index[p["period_end"]]
        reviewed = source_review["annual_periods"][original_index]
        facts = {}
        if profile == CASH_PROFILE:
            for key in CASH_KEYS:
                _require(reviewed["fields"][key]["signed_value"] == p[key],
                         "cash_fact_review_changed")
                facts[key] = _field(reviewed["fields"][key])
            _require(all(reviewed["equations"].values()), "cash_source_identity_failed")
            component_count = None
        else:
            for key in INTEREST_KEYS:
                _require(reviewed["fields"][key]["signed_value"] == p[key],
                         "interest_fact_review_changed")
                facts[key] = _field(reviewed["fields"][key])
            components = p["debt_principal_components"]
            component_count = len(components)
            _require(component_count in {3, 4} and sum(components) == p["debt_principal_total"],
                     "debt_principal_components_changed")
            if index == 2:
                note = reviewed["debt_note_rows"]
                source_col = 0 if original_index == 0 else 2
                for j, amount in enumerate(components):
                    row = note[j]
                    _require(float(row["values"][source_col]) == amount,
                             "dated_original_debt_row_value_changed")
                    facts[f"debt_component_{j + 1}"] = {
                        "value": amount, "evidence_class": "original_10k_debt_note_row",
                        "tag": None, "note_label": row["label"], "ix_id": None,
                        "context_ref": None, "row_sha256": row["row_sha256"]}
                direct = reviewed["fields"]["debt_principal_total"]
                _require(direct["signed_value"] == p["debt_principal_total"],
                         "direct_principal_fact_changed")
                facts["debt_principal_direct"] = _field(direct)
            else:
                _require(debt_extension is not None, "signed_debt_face_extension_required")
                for j, amount in enumerate(components):
                    row = debt_extension["rows"][j]
                    fact = row["period_values"][original_index]
                    _require(fact["signed_value"] == amount and
                             row["row_sha256"] == reviewed["debt_note_row_sha256"][j] and
                             fact.get("ix_id") and fact.get("context_ref"),
                             "original_debt_face_extension_not_exact")
                    facts[f"debt_component_{j + 1}"] = {
                        "value": amount, "evidence_class": "original_inline_xbrl_debt_face",
                        "tag": "us-gaap:DebtInstrumentFaceAmount", "note_label": row["label"],
                        "ix_id": fact["ix_id"], "context_ref": fact["context_ref"],
                        "row_sha256": row["row_sha256"]}
                bridge = reviewed["carrying_reconciliation"]
                _require(abs(bridge["carrying_value"] + bridge["unamortized_cost"]
                             - p["debt_principal_total"]) < 1e-9,
                         "gross_principal_carrying_identity_changed")
                facts["debt_carrying"] = {
                    "value": bridge["carrying_value"], "evidence_class": "original_10k_debt_note_row",
                    "tag": None, "note_label": "Total senior notes", "ix_id": None,
                    "context_ref": None, "row_sha256": bridge["carrying_row_sha256"]}
                facts["unamortized_cost"] = {
                    "value": bridge["unamortized_cost"], "evidence_class": "original_10k_debt_note_row",
                    "tag": None, "note_label": "Less: unamortized issuance costs",
                    "ix_id": None, "context_ref": None,
                    "row_sha256": bridge["cost_row_sha256"]}
        assembled.append({"period_end": p["period_end"],
                          "period_start": reviewed["period_start"],
                          "facts": facts, "component_count": component_count})
    scenario = ([
        {"operating_change": -0.08, "extra_investing_share": 0.035, "fx_share_change": -0.015},
        {"operating_change": -0.11, "extra_investing_share": 0.055, "fx_share_change": 0.012},
        {"rate_change": 0.0125, "income_change": -0.09, "cash_flow_change": -0.055},
        {"rate_change": 0.0175, "income_change": -0.13, "cash_flow_change": -0.08},
    ])[index]
    _require(card["minimum_target_edits"] == CARD_MINIMUM and
             card["independent_skill_review"] is True,
             "signed_final_graph_skill_card_not_promoted")
    return {"schema": "envloop.sec_four_train_analogue_case.private.v1",
            "scope": "TRAIN-only offline analogue; no final workbook or GUI admission",
            "case_index": index, "profile": profile,
            "source": {"issuer_name": record["issuer_name"],
                       "issuer_cik": record["issuer_cik"],
                       "accession": record["accession"],
                       "original_10k_url": record["sec_original_10k_url"],
                       "filing_index_url": record["sec_filing_index_url"],
                       "raw_sha256": {kind: capture_source["response"][kind]["sha256"]
                                      for kind in ("index", "10k", "companyfacts")},
                       "semantic_review_sha256": source_review_sha,
                       "debt_control_kind": "direct_principal" if index == 2 else
                                            "carrying_plus_unamortized_cost" if index == 3 else None},
            "skill": {"signature_sha256": card["skill_signature_sha256"],
                      "minimum_target_edits": CARD_MINIMUM,
                      "causal_atom_count": len(card["causal_skill_atoms"]),
                      "dependency_edge_count": len(card["dependency_edges"])},
            "scenario": scenario,
            "scenario_provenance": "authored synthetic assumptions, not SEC filing facts",
            "periods": assembled}


def prepare(*, pilot_path: Path, raw_dir: Path, review_dir: Path,
            card_root: Path, public_review: Path, public_card_source: Path,
            extension_root: Path, openssl: Path, out_dir: Path) -> dict:
    card_result = verify_cards(private_root=card_root,
                               public_review_path=public_review,
                               public_source_receipt_path=public_card_source)
    _require(card_result["status"] == "source_review_attested_cards_promoted" and
             card_result["review_flags_promoted"] == 13,
             "thirteen_signed_skill_cards_required")
    pilot_raw, pilot = _read(pilot_path)
    manifest_raw, capture = _read(raw_dir / "capture-manifest.private.json")
    registry_raw, registry = _read(card_root / "private-split-reservations.json")
    _, cards = _read(card_root / "skill-cards-reviewed.private.json")
    _require(_sha(registry_raw) == EXCEL_SPLIT_SHA and
             registry.get("schema") == "private-excel-20-20-100-reservations-v1" and
             Counter(row["split"] for row in registry["slots"]) ==
             {"train": 20, "selection": 20, "final": 100},
             "private_140_registry_not_frozen")
    recs = pilot.get("records", [])
    _require(len(recs) == len(capture.get("sources", [])) == 4,
             "exact_four_captured_sources_required")
    original_issuers = {str(row["issuer_cik"]) for row in registry["slots"]}
    original_accessions = {row["original_filing_accession"] for row in registry["slots"]}
    _require(len({str(r["issuer_cik"]) for r in recs}) == 4 and
             len({r["accession"] for r in recs}) == 4 and
             all(str(r["issuer_cik"]) not in original_issuers and
                 r["accession"] not in original_accessions for r in recs),
             "source_or_issuer_overlaps_original_140")
    card_map = {row["skill_signature_sha256"]: row for row in cards["cards"]}
    _require(all(x in card_map for x in CARD_SIGNATURES.values()),
             "screened_graph_cards_missing")
    extension_raw, extension = _read(extension_root / "debt-face-extension.private.json")
    source03_review_raw = (review_dir / "source-03-review.private.json").read_bytes()
    source03_companyfacts_raw = (raw_dir / "source-03-companyfacts.json").read_bytes()
    source03_filing_raw = (raw_dir / "source-03-10k.html").read_bytes()
    _verify_signed_extension(root=extension_root, extension_raw=extension_raw,
        capture_manifest_raw=manifest_raw, source03_review_raw=source03_review_raw,
        source03_companyfacts_raw=source03_companyfacts_raw,
        source03_filing_raw=source03_filing_raw, pilot_raw=pilot_raw,
        openssl=openssl)
    _require(extension["pilot_sha256"] == _sha(pilot_raw) and
             extension["original_10k_sha256"] == _sha(source03_filing_raw) and
             extension["prior_semantic_review_sha256"] == _sha(source03_review_raw) and
             len(extension["rows"]) == 4,
             "signed_debt_extension_changed")
    cases: list[dict] = []
    for i, record in enumerate(recs):
        source = capture["sources"][i]
        _require(source["source_index"] == i and source["accession"] == record["accession"],
                 "raw_capture_source_identity_changed")
        for kind, suffix in (("10k", "10k.html"), ("index", "index.html"),
                             ("companyfacts", "companyfacts.json")):
            content = (raw_dir / f"source-{i:02d}-{suffix}").read_bytes()
            _require(_sha(content) == source["response"][kind]["sha256"],
                     "original_raw_sec_source_hash_changed")
        review_raw, review = _read(review_dir / f"source-{i:02d}-review.private.json")
        _require(review["source_index"] == i and
                 review["status"] == "accepted_for_train_source_transfer_only" and
                 review["pilot_sha256"] == _sha(pilot_raw) and
                 review["manifest_sha256"] == _sha(manifest_raw) and
                 review["identity"]["accession"] == record["accession"] and
                 review["raw_sha256"] == {kind: source["response"][kind]["sha256"]
                                               for kind in ("10k", "index", "companyfacts")},
                 "independently_reviewed_sec_fact_source_changed")
        profile = CASH_PROFILE if i < 2 else INTEREST_PROFILE
        cases.append(_case(i, record, review, _sha(review_raw), source,
                           card_map[CARD_SIGNATURES[profile]],
                           extension if i == 3 else None))
    _require(all(len(c["periods"]) == 2 for c in cases), "two_period_case_required")
    case_dir = out_dir / "cases"
    _require(not case_dir.exists(), "private_train_case_directory_must_be_fresh")
    case_hashes = []
    for c in cases:
        dest = case_dir / f"case-{c['case_index']:02d}.private.json"
        case_hashes.append(_write_private(dest, c))
    manifest = {"schema": "envloop.sec_four_train_case_manifest.private.v1",
                "status": "offline_train_only_case_packages_prepared",
                "source_count": 4, "source_profile_counts": {CASH_PROFILE: 2, INTEREST_PROFILE: 2},
                "distinct_issuer_count": 4, "distinct_accession_count": 4,
                "original_140_issuer_overlap": 0, "original_140_accession_overlap": 0,
                "published_registry_sha256": EXCEL_SPLIT_SHA,
                "pilot_sha256": _sha(pilot_raw),
                "raw_capture_manifest_sha256": _sha(manifest_raw),
                "signed_debt_extension_sha256": _sha(extension_raw),
                "case_sha256": case_hashes,
                "official_excel_web_admitted": 0}
    _write_private(out_dir / "cases-manifest.private.json", manifest)
    return {"status": manifest["status"], "case_count": 4,
            "profile_count": 2, "original_issuer_overlap": 0,
            "original_accession_overlap": 0, "official_admitted": 0,
            "manifest_sha256": _sha((out_dir / "cases-manifest.private.json").read_bytes())}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", type=Path, required=True)
    ap.add_argument("--raw-dir", type=Path, required=True)
    ap.add_argument("--review-dir", type=Path, required=True)
    ap.add_argument("--card-private-root", type=Path, required=True)
    ap.add_argument("--public-card-review", type=Path, required=True)
    ap.add_argument("--public-card-source", type=Path, required=True)
    ap.add_argument("--extension-root", type=Path, required=True)
    ap.add_argument("--openssl", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()
    result = prepare(pilot_path=args.pilot, raw_dir=args.raw_dir,
        review_dir=args.review_dir, card_root=args.card_private_root,
        public_review=args.public_card_review,
        public_card_source=args.public_card_source,
        extension_root=args.extension_root, openssl=args.openssl,
        out_dir=args.out_dir)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
