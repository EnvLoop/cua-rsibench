"""Prospective six-cell source re-ratification for the Desktop caret amendment.

This does not replace the historical ratification, authorize model campaigns,
or dispatch E2B. It can write a new private/public pair only after the exact
amended adapter and five unchanged cell sources are reviewed.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path

from cursibench.full_study_matrix_v1 import CELLS
from cursibench import shared_action_bundle_v066
from native_desktop_factory.v066_final_freeze import (
    source_hashes, validate_ratification,
)


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs/evidence/full-study-v066-six-cell-static-2026-09-28-ledger.json"
OLD_PUBLIC = ROOT / "docs/evidence/full-study-v066-code-only-control-ratification-2026-09-28.json"
AMENDMENT = ROOT / "docs/evidence/native-wdi-v066-caret-pre-result-amendment-2026-09-28.json"


def build() -> tuple[dict, dict]:
    ledger_raw = LEDGER.read_bytes()
    ledger = json.loads(ledger_raw)
    old_public = json.loads(OLD_PUBLIC.read_bytes())
    amendment_raw = AMENDMENT.read_bytes()
    amendment = json.loads(amendment_raw)
    bundle = shared_action_bundle_v066.build(ROOT)
    if (ledger.get("schema") !=
            "cua-six-cell-v066-adapter-readiness-proposed-v1" or
            ledger.get("shared_action_bundle_sha256") !=
            bundle["bundle_sha256"] or
            old_public.get("static_ledger_sha256") !=
            sha256(ledger_raw).hexdigest() or
            amendment.get("schema") !=
            "cua-native-wdi-v066-caret-pre-result-amendment-v1" or
            amendment.get("status") !=
            "proposed_before_new_paid_controls_and_all_official_model_outcomes" or
            amendment.get("old_six_cell_ratification_sha256") !=
            old_public.get("private_ratification_sha256") or
            amendment.get("old_adapter_sha256") !=
            old_public.get("cell_adapter_sha256s", {}).get("desktop-native") or
            amendment.get("new_e2b_sandboxes_created") != 0 or
            amendment.get("new_model_attempts") != 0 or
            amendment.get("official_model_results") != 0):
        raise ValueError("caret_amendment_historical_source_binding_invalid")
    common = source_hashes()
    if common != old_public.get("common_source_sha256s"):
        raise ValueError("caret_amendment_common_action_source_changed")
    profiles = {}
    for row in ledger["cells"]:
        cell, path, files = (row.get("cell_id"),
                             row.get("v066_adapter_source"),
                             row.get("adapter_source_sha256s"))
        if (cell not in CELLS or cell in profiles or
                type(path) is not str or type(files) is not dict or
                path not in files or
                row.get("official_model_outcomes") != 0 or
                row.get("official_final_admissions") != 0):
            raise ValueError("caret_amendment_six_cell_ledger_invalid")
        for relative, historical_sha in files.items():
            source = ROOT / relative
            expected = historical_sha
            if cell == "desktop-native" and relative == path:
                if historical_sha != amendment["old_adapter_sha256"]:
                    raise ValueError("caret_amendment_old_desktop_sha_changed")
                expected = amendment["proposed_new_adapter_sha256"]
            if (not source.is_file() or source.is_symlink() or
                    not source.resolve().is_relative_to(ROOT) or
                    sha256(source.read_bytes()).hexdigest() != expected):
                raise ValueError("caret_amendment_six_cell_adapter_source_changed")
        adapter_sha = (amendment["proposed_new_adapter_sha256"]
                       if cell == "desktop-native" else files[path])
        if (cell != "desktop-native" and
                adapter_sha != old_public["cell_adapter_sha256s"].get(cell)):
            raise ValueError("caret_amendment_other_cell_adapter_changed")
        profiles[cell] = {"common_source_sha256s": common,
                          "adapter_sha256": adapter_sha}
    if set(profiles) != set(CELLS):
        raise ValueError("caret_amendment_six_cell_incomplete")
    value = {
        "schema": "cua-six-cell-action-profile-v066-ratification-v1",
        "status": "ratified_pre_result",
        "ratified_utc": datetime.now(timezone.utc).isoformat(),
        "action_profile": "scale-action-profile-v0.6.6",
        "common_source_sha256s": common,
        "cell_profiles": profiles,
        "base_and_selected_identical": True,
        "hidden_final_model_attempts_before_ratification": 0,
    }
    public = {
        "schema": "cua-six-cell-v066-caret-code-only-ratification-public-v1",
        "status": "new_source_bytes_frozen_for_evaluator_controls_only",
        "supersedes_old_private_ratification_sha256":
            old_public["private_ratification_sha256"],
        "amendment_public_sha256": sha256(amendment_raw).hexdigest(),
        "static_ledger_sha256": sha256(ledger_raw).hexdigest(),
        "shared_action_bundle_sha256": bundle["bundle_sha256"],
        "cell_adapter_sha256s": {cell: profiles[cell]["adapter_sha256"]
                                 for cell in CELLS},
        "common_source_sha256s": common,
        "six_cell_live_smokes_complete": False,
        "full_study_pre_campaign_witness_published": False,
        "qualified_final_tasks": 0,
        "researcher_campaigns": 0,
        "official_final_model_results": 0,
    }
    return value, public


def write(private_path: Path, public_path: Path) -> dict:
    private, public = Path(private_path).absolute(), Path(public_path).absolute()
    work = ROOT / "work"
    if (work.is_symlink() or
            not private.parent.resolve().is_relative_to(work.resolve()) or
            private.exists() or private.is_symlink() or
            public.parent.resolve() != (ROOT / "docs/evidence").resolve() or
            public.exists() or public.is_symlink()):
        raise ValueError("new_private_and_public_ratification_paths_required")
    value, aggregate = build()
    private.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    private.parent.chmod(0o700)
    raw = (json.dumps(value, sort_keys=True,
                      separators=(",", ":")) + "\n").encode()
    descriptor = os.open(private, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    _, ratification_sha = validate_ratification(private)
    aggregate["private_ratification_sha256"] = ratification_sha
    with public.open("x", encoding="utf-8") as stream:
        json.dump(aggregate, stream, sort_keys=True, indent=2)
        stream.write("\n")
    return aggregate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private", type=Path, required=True)
    parser.add_argument("--public", type=Path, required=True)
    args = parser.parse_args()
    result = write(args.private, args.public)
    print(json.dumps({"status": result["status"],
                      "private_ratification_sha256":
                          result["private_ratification_sha256"],
                      "qualified_final_tasks": 0,
                      "official_final_model_results": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
