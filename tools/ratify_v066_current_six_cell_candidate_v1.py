"""Build a dated, source-bound six-cell candidate without dispatch authority.

The historical 2026-09-28 ratifications remain immutable. This candidate
binds their two known adapter amendments, the current Odoo physical-dispatch
exception, and the v0.6.6 validator correction. It is intentionally rejected
by the live campaign ratification validator until separate live evidence and
the 600-task qualification witness exist.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath

from cursibench.full_study_matrix_v1 import CELLS
from cursibench import shared_action_bundle_v066
from native_desktop_factory.v066_final_freeze import source_hashes


ROOT = Path(__file__).resolve().parents[1]
DATE = "2026-09-29"
EVIDENCE = ROOT / "docs/evidence"
UPSTREAM = {
    "static_ledger": (
        "full-study-v066-six-cell-static-2026-09-28-ledger.json",
        "f1a7c220cbe6208294cc07059ea2991aa73d651ae875020a7eeda7909f7211a2"),
    "original_code_ratification": (
        "full-study-v066-code-only-control-ratification-2026-09-28.json",
        "e5171d0a38cfead6836e19f50d6116e2f74c3f8f3bb9cc5b0ec6feae67bd1a38"),
    "caret_amendment": (
        "native-wdi-v066-caret-pre-result-amendment-2026-09-28.json",
        "d48c9aa3f1a55f563c0ab04f68fca4c486fe466770e2c4c424cdda1e70cdf16d"),
    "caret_code_ratification": (
        "full-study-v066-caret-amended-control-ratification-2026-09-28.json",
        "80974630920354dd4d5b0277efd3091cdbbf9849d4c796bd9ee04b0c11c0dbf9"),
    "odoo_drift_audit": (
        "odoo-v066-historical-ratification-source-drift-2026-09-29.json",
        "d7c8def22898374eeb8ad95b76a411a95fc0cdaf8b3f44174f820dbde7edda9d"),
    "odoo_validator_source_freeze": (
        "odoo-v066-scale-validator-v066-source-freeze-2026-09-29.json",
        "14495b6b9851c9b425931b09c664a19efb0959b4889de6b7a5eb1cc3958e2c16"),
    "odoo_selection_plan": (
        "odoo-v066-selection-control-plan-validator-v066-2026-09-29.json",
        "c5892f532b571907b3f50b282cfe0e019fdfab296f1559c2f9c4959b199eb4fa"),
    "odoo_hidden_plan": (
        "odoo-v066-official_hidden-control-plan-validator-v066-2026-09-29.json",
        "2c65d9d0bf13eb48332b963c6df676564e7914ec19adab9d3f2429439c76d517"),
}
PRIVATE_SCHEMA = "cua-six-cell-v066-current-source-candidate-private-v1"
PUBLIC_SCHEMA = "cua-six-cell-v066-current-source-candidate-public-v1"
STATUS = "source_bound_candidate_only_no_dispatch_authority"


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, allow_nan=False) + "\n").encode()


def require(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError(code)


def source_digest(relative: str) -> str:
    require(type(relative) is str, "candidate_source_path_invalid")
    path_part = PurePosixPath(relative)
    require(not path_part.is_absolute() and
            ".." not in path_part.parts and relative == str(path_part),
            "candidate_source_path_invalid")
    path = ROOT / relative
    require(path.is_file() and not path.is_symlink() and
            path.resolve().is_relative_to(ROOT.resolve()),
            "candidate_source_missing_or_symlink")
    return digest(path.read_bytes())


def upstream() -> tuple[dict[str, dict], dict[str, str]]:
    data, hashes = {}, {}
    for label, (name, expected) in UPSTREAM.items():
        path = EVIDENCE / name
        require(path.is_file() and not path.is_symlink() and
                digest(path.read_bytes()) == expected,
                "candidate_upstream_evidence_changed")
        data[label] = json.loads(path.read_bytes())
        hashes[label] = expected
    return data, hashes


def build() -> tuple[dict, dict]:
    records, upstream_hashes = upstream()
    ledger = records["static_ledger"]
    original = records["original_code_ratification"]
    caret = records["caret_code_ratification"]
    amendment = records["caret_amendment"]
    drift = records["odoo_drift_audit"]
    odoo = records["odoo_validator_source_freeze"]
    bundle = shared_action_bundle_v066.build(ROOT)
    common = source_hashes()
    require(ledger.get("schema") == "cua-six-cell-v066-adapter-readiness-proposed-v1" and
            ledger.get("status") == "development_evidence_only_not_ratified" and
            ledger.get("shared_action_bundle_sha256") == bundle["bundle_sha256"] and
            ledger.get("official_final_identities") == 0 and
            ledger.get("researcher_campaigns") == 0 and
            type(ledger.get("cells")) is list and len(ledger["cells"]) == 6 and
            original.get("static_ledger_sha256") == upstream_hashes["static_ledger"] and
            original.get("status") == "source_bytes_frozen_for_evaluator_controls_only" and
            original.get("six_cell_live_smokes_complete") is False and
            original.get("qualified_final_tasks") == 0 and
            caret.get("status") == "new_source_bytes_frozen_for_evaluator_controls_only" and
            caret.get("six_cell_live_smokes_complete") is False and
            caret.get("qualified_final_tasks") == 0 and
            caret.get("researcher_campaigns") == 0 and
            caret.get("official_final_model_results") == 0 and
            original.get("private_ratification_sha256") ==
                caret.get("supersedes_old_private_ratification_sha256") and
            caret.get("amendment_public_sha256") == upstream_hashes["caret_amendment"] and
            caret.get("common_source_sha256s") == common and
            amendment.get("proposed_new_adapter_sha256") ==
                caret.get("cell_adapter_sha256s", {}).get("desktop-native") and
            drift.get("historical_adapter_sha256") ==
                caret.get("cell_adapter_sha256s", {}).get("odoo-community") and
            drift.get("historical_record_preserved") is True and
            drift.get("new_six_cell_ratification_required_before_campaign") is True and
            drift.get("official_final_admissions") == 0 and
            drift.get("researcher_campaigns") == 0 and
            drift.get("official_model_results") == 0,
            "candidate_historical_boundary_invalid")
    require(odoo.get("schema") == "envloop-odoo-v066-scale-gui-source-freeze-v1" and
            odoo.get("status") == "frozen_after_v066_pre_dispatch_validator_correction" and
            odoo.get("ratification_sha256") == caret.get("private_ratification_sha256") and
            odoo.get("physical_dispatch_profile") ==
                "pinned-noninteractive-border-dispatch-2026-09-29" and
            odoo.get("validator_amendment") == "v066-pre-dispatch-validation-2026-09-29" and
            odoo.get("retained_selection_failed_controls_before_freeze") == 3 and
            odoo.get("official_final_gui_controls_before_freeze") == 0 and
            odoo.get("official_final_tasks_admitted") == 0 and
            odoo.get("model_attempts") == 0 and
            odoo.get("planned_split_counts") == {"selection": 20, "official_hidden": 100} and
            type(odoo.get("source_sha256s")) is dict,
            "candidate_odoo_source_freeze_invalid")
    for split, count, label in (("selection", 20, "odoo_selection_plan"),
                                ("official_hidden", 100, "odoo_hidden_plan")):
        plan = records[label]
        require(plan.get("schema") == "envloop-odoo-v066-split-gui-control-plan-public-v1" and
                plan.get("status") == "split_source_bound_plan_only_no_gui_dispatch" and
                plan.get("cell") == "odoo-community" and
                plan.get("split") == split and plan.get("candidate_count") == count and
                plan.get("ratification_sha256") == caret.get("private_ratification_sha256") and
                plan.get("source_freeze_sha256") == upstream_hashes["odoo_validator_source_freeze"] and
                plan.get("physical_dispatch_profile") == odoo["physical_dispatch_profile"] and
                plan.get("validator_amendment") == odoo["validator_amendment"] and
                plan.get("fresh_current_profile_gui_controls") == 0 and
                plan.get("model_attempts") == 0 and
                plan.get("official_final_tasks_admitted") == 0 and
                plan.get("researcher_campaigns") == 0,
                "candidate_odoo_split_plan_not_live_evidence")
    for relative, expected in odoo["source_sha256s"].items():
        require(source_digest(relative) == expected,
                "candidate_odoo_runtime_source_changed")
    required_odoo = {
        "enterprise_fallback/odoo18/odoo_v066_train_adapter.py",
        "enterprise_fallback/odoo18/odoo_v066_scale_exact_return_adapter.py",
        "enterprise_fallback/odoo18/odoo_v066_scale_pinned_border_adapter.py",
        "src/cursibench/scale_action_contract_v066.py",
        "tools/odoo_v066_scale_controller_v1.py",
        "tools/odoo_v066_scale_audit_v1.py",
        "enterprise_fallback/odoo18/reset.py",
        "enterprise_fallback/odoo18/verify.py",
    }
    require(required_odoo.issubset(odoo["source_sha256s"]),
            "candidate_odoo_runtime_binding_incomplete")
    profiles, cell_sources = {}, {}
    for row in ledger["cells"]:
        cell = row.get("cell_id")
        primary = row.get("v066_adapter_source")
        historical_sources = row.get("adapter_source_sha256s")
        require(cell in CELLS and cell not in profiles and
                type(primary) is str and type(historical_sources) is dict and
                primary in historical_sources and
                row.get("v066_parser_and_gui_mapping_synthetic") == "passed" and
                row.get("official_final_admissions") == 0 and
                row.get("official_model_outcomes") == 0,
                "candidate_static_cell_invalid")
        current = {}
        for relative, historical in historical_sources.items():
            expected = historical
            if cell == "desktop-native" and relative == primary:
                require(historical == amendment.get("old_adapter_sha256"),
                        "candidate_desktop_historical_source_changed")
                expected = amendment["proposed_new_adapter_sha256"]
            elif cell == "odoo-community" and relative == primary:
                require(historical == drift.get("historical_adapter_sha256"),
                        "candidate_odoo_historical_source_changed")
                expected = drift.get("current_adapter_sha256")
                require(expected == odoo["source_sha256s"].get(relative),
                        "candidate_odoo_adapter_not_in_current_freeze")
            require(source_digest(relative) == expected,
                    "candidate_six_cell_source_changed")
            current[relative] = expected
        require(current[primary] == caret["cell_adapter_sha256s"].get(cell)
                if cell not in ("odoo-community",) else
                current[primary] == drift["current_adapter_sha256"],
                "candidate_cell_revision_boundary_invalid")
        profiles[cell] = {"common_source_sha256s": common,
                          "adapter_sha256": current[primary]}
        cell_sources[cell] = current
    require(set(profiles) == set(CELLS) and
            all(source_digest(relative) == expected
                for relative, expected in bundle["source_sha256s"].items()),
            "candidate_six_cell_source_incomplete")
    candidate = {
        "schema": PRIVATE_SCHEMA,
        "status": STATUS,
        "as_of_date": DATE,
        "action_profile": "scale-action-profile-v0.6.6",
        "student_model": "Qwen/Qwen3.8-27B",
        "upstream_evidence_sha256s": upstream_hashes,
        "shared_action_bundle_sha256": bundle["bundle_sha256"],
        "common_source_sha256s": common,
        "cell_profiles": profiles,
        "cell_adapter_dependency_sha256s": cell_sources,
        "odoo_current_runtime_source_sha256s": odoo["source_sha256s"],
        "odoo_physical_dispatch_profile": odoo["physical_dispatch_profile"],
        "odoo_validator_amendment": odoo["validator_amendment"],
        "base_and_selected_profile_source_equal": True,
        "all_six_current_live_smokes_ratified": False,
        "all_600_final_tasks_admitted": False,
        "campaign_dispatch_authorized": False,
        "official_final_model_attempts": 0,
    }
    public = {
        "schema": PUBLIC_SCHEMA,
        "status": STATUS,
        "as_of_date": DATE,
        "private_candidate_sha256": digest(canonical(candidate)),
        "upstream_evidence_sha256s": upstream_hashes,
        "shared_action_bundle_sha256": bundle["bundle_sha256"],
        "cell_adapter_sha256s": {cell: profiles[cell]["adapter_sha256"] for cell in CELLS},
        "odoo_runtime_source_bundle_sha256": digest(canonical(odoo["source_sha256s"])),
        "odoo_physical_dispatch_profile": odoo["physical_dispatch_profile"],
        "odoo_validator_amendment": odoo["validator_amendment"],
        "retained_odoo_selection_failures": 3,
        "all_six_current_live_smokes_ratified": False,
        "full_study_pre_campaign_witness_published": False,
        "qualified_final_tasks": 0,
        "researcher_campaigns": 0,
        "official_final_model_results": 0,
        "campaign_dispatch_authorized": False,
    }
    return candidate, public


def _private_path(path: Path) -> Path:
    path = Path(path).absolute()
    work = ROOT / "work"
    require(not work.is_symlink() and
            path.parent.resolve().is_relative_to(work.resolve()) and
            not path.exists() and not path.is_symlink(),
            "candidate_private_path_must_be_new_under_work")
    return path


def write_private(path: Path, *, public_path: Path | None = None) -> dict:
    """Recreate the deterministic private candidate beside a published receipt."""
    private = _private_path(path)
    value, public = build()
    if public_path is not None:
        published = Path(public_path).absolute()
        require(published.parent.resolve() == EVIDENCE.resolve() and
                published.is_file() and not published.is_symlink() and
                json.loads(published.read_bytes()) == public,
                "candidate_public_receipt_changed")
    private.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    private.parent.chmod(0o700)
    descriptor = os.open(private, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(canonical(value))
        stream.flush()
        os.fsync(stream.fileno())
    require(digest(private.read_bytes()) == public["private_candidate_sha256"],
            "candidate_private_write_mismatch")
    return public


def write(private_path: Path, public_path: Path) -> dict:
    published = Path(public_path).absolute()
    require(published.parent.resolve() == EVIDENCE.resolve() and
            not published.exists() and not published.is_symlink(),
            "candidate_public_path_must_be_new_evidence")
    public = write_private(private_path)
    with published.open("x", encoding="utf-8") as stream:
        json.dump(public, stream, sort_keys=True, indent=2)
        stream.write("\n")
    return public


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private", type=Path, required=True)
    parser.add_argument("--public", type=Path, required=True)
    parser.add_argument("--materialize-private-for-published", action="store_true")
    args = parser.parse_args()
    result = (write_private(args.private, public_path=args.public)
              if args.materialize_private_for_published else
              write(args.private, args.public))
    print(json.dumps({"status": result["status"],
                      "private_candidate_sha256": result["private_candidate_sha256"],
                      "campaign_dispatch_authorized": False,
                      "qualified_final_tasks": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
