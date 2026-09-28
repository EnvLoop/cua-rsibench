"""Verify a detached, source-only review before promoting private Excel cards.

`verify` is read-only. `promote` creates a separate private card file whose
only differences from the signed frozen draft are the 13 review flags. Neither
command constructs or admits train analogues, opens final workbooks, or calls
Office or a model.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess

from tools.office_excel_transfer_skill_cards_v1 import validate as validate_cards


SCHEMA = "envloop-sec-excel-transfer-signed-review-gate-public-v1"
REVIEW_SCHEMA = "envloop-sec-excel-transfer-skill-independent-source-review-v1"
PUBLIC_REVIEW_SCHEMA = "envloop-sec-excel-transfer-skill-independent-review-public-v1"
SIGNER = "envloop-excel-independent-review"
NAMESPACE = "envloop-sec-excel-transfer"
PRIVATE_FILES = {
    "registry": "private-split-reservations.json",
    "draft": "skill-cards-draft.private.json",
    "salt": "skill-card-salt.private",
    "review": "independent-source-review-v6.private.json",
    "signature": "independent-source-review-v6.private.json.sig",
    "allowed": "independent-review-allowed-signers.private",
    "promoted": "skill-cards-reviewed.private.json",
}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _require(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError(reason)


def _private_modes(root: Path) -> None:
    _require(root.is_dir() and stat.S_IMODE(root.stat().st_mode) == 0o700,
             "private_snapshot_root_mode_not_0700")
    for path in root.rglob("*"):
        _require(not path.is_symlink(), "private_snapshot_symlink_forbidden")
        _require(path.suffix.lower() not in {".xlsx", ".xls", ".xlsm"},
                 "private_snapshot_must_not_contain_workbooks")
        expected = 0o700 if path.is_dir() else 0o600
        _require(stat.S_IMODE(path.stat().st_mode) == expected,
                 "private_snapshot_nested_mode_changed")


def _signature_verified(review_raw: bytes, signature: Path,
                        allowed_signers: Path) -> bool:
    result = subprocess.run(
        ["ssh-keygen", "-Y", "verify", "-f", str(allowed_signers),
         "-I", SIGNER, "-n", NAMESPACE, "-s", str(signature)],
        input=review_raw, capture_output=True, check=False)
    return result.returncode == 0


def verify(*, private_root: Path, public_review_path: Path,
           public_source_receipt_path: Path) -> dict:
    root = private_root.resolve()
    _private_modes(root)
    files = {key: root / name for key, name in PRIVATE_FILES.items()}
    for key in ("registry", "draft", "salt", "review", "signature", "allowed"):
        _require(files[key].is_file(), "signed_review_private_input_missing")
    public_review = json.loads(public_review_path.read_bytes())
    public_source = json.loads(public_source_receipt_path.read_bytes())
    _require(public_review.get("schema") == PUBLIC_REVIEW_SCHEMA and
             public_review.get("status") == "source_bound_review_passed" and
             public_review.get("signature_namespace") == NAMESPACE and
             public_review.get("signer_identity") == SIGNER and
             public_source.get("status") == "independent_review_pending",
             "public_review_or_frozen_source_receipt_changed")

    draft_raw = files["draft"].read_bytes()
    registry_raw = files["registry"].read_bytes()
    review_raw = files["review"].read_bytes()
    signature_raw = files["signature"].read_bytes()
    allowed_raw = files["allowed"].read_bytes()
    salt = files["salt"].read_bytes()
    _require(len(salt) == 32 and
             _sha(salt + draft_raw) ==
             public_source.get("private_skill_cards_salted_commitment_sha256") ==
             public_review.get("private_cards_salted_commitment_sha256") and
             _sha(review_raw) == public_review.get("private_review_sha256") and
             _sha(signature_raw) ==
             public_review.get("detached_signature_sha256") and
             public_review.get("signer_public_key", "").encode() in allowed_raw,
             "signed_review_public_commitment_mismatch")
    _require(_signature_verified(review_raw, files["signature"],
                                 files["allowed"]),
             "detached_independent_review_signature_invalid")

    source_audit = validate_cards(
        registry_path=files["registry"], cards_path=files["draft"],
        source_root=root / "source_snapshot", commitment_salt=salt)
    _require(source_audit["status"] == "independent_review_pending" and
             source_audit["exact_final_graphs_covered"] == 13 and
             source_audit["source_code_modules_bound"] == 37 and
             source_audit["independently_reviewed_skill_cards"] == 0 and
             source_audit["private_registry_sha256"] == _sha(registry_raw),
             "frozen_draft_source_audit_changed")
    draft = json.loads(draft_raw)
    review = json.loads(review_raw)
    _require(review.get("schema") == REVIEW_SCHEMA and
             review.get("reviewed_draft_sha256") == _sha(draft_raw) and
             review.get("reviewed_registry_sha256") == _sha(registry_raw) and
             review.get("reviewer") ==
             "independent evaluator agent /root/excel_card_review" and
             review.get("conclusion", {}).get("source_bound_card_review") == "pass",
             "signed_review_does_not_bind_frozen_draft_and_registry")
    aggregate = review.get("aggregate", {})
    _require(aggregate.get("card_count") == 13 and
             aggregate.get("registry_final_slots") == 100 and
             aggregate.get("unique_generator_modules") == 37 and
             aggregate.get("official_excel_web_final_admissions") == 0 and
             all(aggregate.get(key) is True for key in (
                 "all_dags_acyclic_connected", "all_skill_signature_hashes_match",
                 "all_source_hashes_match", "all_source_template_hashes_match",
                 "all_sources_have_static_nine_fault_guard")),
             "signed_review_aggregate_incomplete")
    reviewed = review.get("cards", [])
    _require(isinstance(reviewed, list) and len(reviewed) == 13 and
             [row.get("ordinal") for row in reviewed] == list(range(1, 14)),
             "signed_review_card_count_or_order_changed")
    for card, verdict in zip(draft["cards"], reviewed):
        evidence = card["source_code_evidence"]
        reviewed_sources = verdict.get("source_modules", [])
        _require(verdict.get("final_graph_reservation") ==
                 card["final_graph_reservation"] and
                 verdict.get("skill_signature_sha256") ==
                 card["skill_signature_sha256"] and
                 verdict.get("generator_module_set_sha256") ==
                 card["final_template_sha256"] and
                 verdict.get("minimum_target_edits") == 9 and
                 verdict.get("causal_atom_count") ==
                 len(card["causal_skill_atoms"]) and
                 verdict.get("dependency_edge_count") ==
                 len(card["dependency_edges"]) and
                 verdict.get("longest_causal_path_edges", 0) >= 3 and
                 verdict.get("semantic_review", {}).get("verdict") ==
                 "pass_source_code_scope" and
                 all(verdict.get("semantic_review", {}).get(key) is True
                     for key in ("dependency_edges_grounded",
                                 "nine_edit_floor_source_grounded",
                                 "not_artifact_or_gui_admission")) and
                 isinstance(reviewed_sources, list) and
                 len(reviewed_sources) == len(evidence),
                 "signed_per_graph_semantic_verdict_changed")
        for original, checked in zip(evidence, reviewed_sources):
            _require(checked.get("path") == original["path"] and
                     checked.get("sha256") == original["sha256"] and
                     checked.get("static_nine_fault_guard") is True and
                     checked.get("assertions_found") ==
                     len(original["assertions"]),
                     "signed_per_graph_source_module_verdict_changed")

    flags_promoted = 0
    promoted_commitment = None
    if files["promoted"].exists():
        promoted_raw = files["promoted"].read_bytes()
        promoted = json.loads(promoted_raw)
        _require(all(card.get("independent_skill_review") is True for card in
                     promoted.get("cards", [])) and
                 len(promoted.get("cards", [])) == 13,
                 "promoted_cards_do_not_mark_exact_13_reviews")
        normalized = copy.deepcopy(promoted)
        for card in normalized["cards"]:
            card["independent_skill_review"] = False
        _require(normalized == draft,
                 "promoted_cards_differ_from_signed_draft_beyond_review_flags")
        promoted_audit = validate_cards(
            registry_path=files["registry"], cards_path=files["promoted"],
            source_root=root / "source_snapshot")
        _require(promoted_audit["status"] == "reviewed_source_bound" and
                 promoted_audit["independently_reviewed_skill_cards"] == 13,
                 "promoted_cards_source_audit_failed")
        flags_promoted = 13
        promoted_commitment = _sha(salt + promoted_raw)

    return {
        "schema": SCHEMA,
        "status": "source_review_attested_cards_promoted" if flags_promoted
                  else "source_review_attested_promotion_pending",
        "frozen_draft_sha256": _sha(draft_raw),
        "signed_review_sha256": _sha(review_raw),
        "detached_signature_sha256": _sha(signature_raw),
        "reviewed_cards_salted_commitment_sha256": promoted_commitment,
        "signed_source_level_verdicts": 13,
        "review_flags_promoted": flags_promoted,
        "source_modules_verified": 37,
        "train_only_analogues_sourced_or_admitted": 0,
        "excel_web_gui_admitted": 0,
        "official_final_admitted": 0,
        "model_calls": 0,
    }


def promote(*, private_root: Path, public_review_path: Path,
            public_source_receipt_path: Path) -> dict:
    before = verify(private_root=private_root,
                    public_review_path=public_review_path,
                    public_source_receipt_path=public_source_receipt_path)
    _require(before["review_flags_promoted"] == 0,
             "reviewed_card_copy_already_exists")
    root = private_root.resolve()
    draft = json.loads((root / PRIVATE_FILES["draft"]).read_bytes())
    for card in draft["cards"]:
        card["independent_skill_review"] = True
    path = root / PRIVATE_FILES["promoted"]
    raw = (json.dumps(draft, indent=2, sort_keys=True) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as out:
        out.write(raw)
    return verify(private_root=root, public_review_path=public_review_path,
                  public_source_receipt_path=public_source_receipt_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("verify", "promote"))
    parser.add_argument("--private-root", type=Path, required=True)
    parser.add_argument("--public-review", type=Path, required=True)
    parser.add_argument("--public-source-receipt", type=Path, required=True)
    args = parser.parse_args()
    action = verify if args.mode == "verify" else promote
    receipt = action(private_root=args.private_root,
                     public_review_path=args.public_review,
                     public_source_receipt_path=args.public_source_receipt)
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
