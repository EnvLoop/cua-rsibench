"""Freeze and audit the fair v2 OOXML scorer before any official model outcome.

The 100 private GUI controls are re-read under the new semantic target rubric.
Original receipts are never rewritten. The public freeze emits only aggregate
counts, file hashes, and a private-detailed-audit digest, not final task gold.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

if __package__:
    from . import admit
    from .official_saved_verifier import OFFICIAL_SCHEMA, verify_official
else:
    import admit
    from official_saved_verifier import OFFICIAL_SCHEMA, verify_official


SCORER_FILES = ("official_saved_verifier.py", "formula_semantics.py",
                "target_text_semantics.py", "verify.py")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def scorer_bundle() -> tuple[str, dict[str, str]]:
    root = Path(__file__).resolve().parent
    files = {name: digest((root / name).read_bytes()) for name in SCORER_FILES}
    bundle = digest((json.dumps(files, sort_keys=True) + "\n").encode())
    return bundle, files


def audit(candidate_root: Path, attempts_root: Path, private_map_path: Path) -> tuple[dict, dict]:
    mapping_raw = private_map_path.read_bytes()
    mapping = json.loads(mapping_raw)
    salt = mapping["variant_salt"]
    if not isinstance(salt, str) or len(salt) < 32:
        raise ValueError("Evaluator-private semantic salt missing")
    inventory_raw = (candidate_root / "candidate-inventory.json").read_bytes()
    inventory = json.loads(inventory_raw)
    if inventory.get("private_map_sha256") != digest(mapping_raw) or inventory.get("design_revision") != "v2-distinct-structures":
        raise ValueError("Candidate inventory/private map mismatch")
    gui = admit.audit(candidate_root, attempts_root)
    if (gui["qualified_final_count"], gui["missing_receipt_count"], gui["invalid_receipt_count"]) != (100, 0, 0):
        raise ValueError("All 100 native GUI trios must be admitted before scorer freeze")
    final = [row for row in inventory["tasks"] if row["split"] == "final_candidate"]
    private_rows, failures = [], []
    for row in final:
        task_id = row["task_id"]
        _, baseline, oracle = admit._package(candidate_root, row)
        directory = attempts_root / task_id
        ext = ".xlsx" if row["workflow"].startswith("calc-") else ".pptx" if row["workflow"].startswith("impress-") else ".docx"
        positive = (directory / "positive" / ("saved" + ext)).read_bytes()
        negative = (directory / "near-miss" / ("saved" + ext)).read_bytes()
        good = verify_official(baseline, positive, oracle, private_salt=salt)
        bad = verify_official(baseline, negative, oracle, private_salt=salt)
        valid = (good["passed"] is True and not good["errors"] and
                 bad["passed"] is False and bad["errors"] and
                 all(error.startswith("target_") for error in bad["errors"]) and
                 good["schema"] == OFFICIAL_SCHEMA and bad["schema"] == OFFICIAL_SCHEMA)
        record = {"task_id": task_id, "workflow": row["workflow"],
                  "source_groups": row["source_groups"], "package_sha256": row["package_sha256"],
                  "positive_saved_sha256": digest(positive),
                  "near_miss_saved_sha256": digest(negative),
                  "positive_fair_score": 1 if good["passed"] else 0,
                  "near_miss_fair_score": 1 if bad["passed"] else 0,
                  "near_miss_errors": bad["errors"], "passed": valid}
        private_rows.append(record)
        if not valid:
            failures.append(record)
    bundle, files = scorer_bundle()
    private = {"schema": "cua-native-wdi-fair-scorer-pre-result-private-audit-v1",
               "candidate_inventory_sha256": digest(inventory_raw),
               "private_map_sha256": digest(mapping_raw),
               "scorer_bundle_sha256": bundle,
               "tasks": private_rows, "failures": failures}
    public = {"schema": "cua-native-wdi-fair-scorer-pre-result-freeze-v1",
              "freeze_date": "2026-09-27",
              "candidate_inventory_sha256": digest(inventory_raw),
              "private_map_sha256": digest(mapping_raw),
              "evaluator_private_salt_sha256": digest(salt.encode()),
              "scorer_schema": OFFICIAL_SCHEMA,
              "scorer_file_sha256": files,
              "scorer_bundle_sha256": bundle,
              "final_candidate_count": len(final),
              "final_source_family_count": len({tuple(row["source_groups"]) for row in final}),
              "application_counts": dict(sorted(Counter("Calc" if row["workflow"].startswith("calc-") else
                                                          "Impress" if row["workflow"].startswith("impress-") else "Writer"
                                                          for row in final).items())),
              "gui_trios_independently_accepted": gui["qualified_final_count"],
              "known_positive_passed_fair_scorer": sum(row["positive_fair_score"] == 1 for row in private_rows),
              "known_near_miss_rejected_fair_scorer": sum(row["near_miss_fair_score"] == 0 for row in private_rows),
              "fair_scorer_calibration_failures": len(failures),
              "status": "pre_result_scorer_candidate_frozen" if not failures else "fair_scorer_freeze_rejected",
              "official_full_study_admitted_final_count": 0,
              "official_model_result_count": 0,
              "scope": "100 known GUI positive/negative calibration artifacts only. This scorer does not authorize any Qwen final run until the shared v0.6.4 action/observation, model, image, budget, and hidden-set pre-campaign gates also freeze."}
    return private, public


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--attempts-root", type=Path, required=True)
    parser.add_argument("--private-map", type=Path, required=True)
    parser.add_argument("--private-out", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.private_out, args.public_out):
        if path.exists():
            raise ValueError("Refusing to overwrite scorer freeze evidence")
    private, public = audit(args.candidate_root, args.attempts_root,
                            args.private_map)
    args.private_out.parent.mkdir(parents=True, exist_ok=True)
    args.public_out.parent.mkdir(parents=True, exist_ok=True)
    args.private_out.write_text(json.dumps(private, indent=2, sort_keys=True) + "\n")
    public["private_detailed_audit_sha256"] = digest(args.private_out.read_bytes())
    args.public_out.write_text(json.dumps(public, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": public["status"],
                      "positive_controls_passed": public["known_positive_passed_fair_scorer"],
                      "near_misses_rejected": public["known_near_miss_rejected_fair_scorer"],
                      "receipt_sha256": digest(args.public_out.read_bytes())}, sort_keys=True))
    if private["failures"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
