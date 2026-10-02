"""Freeze six v0.6.6 adapter source hashes for evaluator-only controls.

This is a pre-result code ratification, not an application readiness claim, a
qualified task manifest, a public campaign witness, or spending permission.
It reopens the already published static ledger and rejects changed bytes.
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
SCHEMA = "cua-six-cell-action-profile-v066-ratification-v1"


def _require(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError(code)


def build() -> tuple[dict, dict]:
    raw = LEDGER.read_bytes()
    ledger = json.loads(raw)
    bundle = shared_action_bundle_v066.build(ROOT)
    _require(ledger.get("schema") ==
             "cua-six-cell-v066-adapter-readiness-proposed-v1" and
             ledger.get("status") == "development_evidence_only_not_ratified" and
             ledger.get("shared_action_bundle_sha256") == bundle["bundle_sha256"] and
             ledger.get("official_final_identities") == 0 and
             ledger.get("researcher_campaigns") == 0 and
             type(ledger.get("cells")) is list and
             len(ledger["cells"]) == len(CELLS),
             "published_static_action_ledger_changed")
    common = source_hashes()
    profiles = {}
    for row in ledger["cells"]:
        cell = row.get("cell_id")
        path = row.get("v066_adapter_source")
        files = row.get("adapter_source_sha256s")
        _require(cell in CELLS and cell not in profiles and
                 type(path) is str and type(files) is dict and
                 path in files and
                 row.get("v066_parser_and_gui_mapping_synthetic") == "passed" and
                 row.get("official_model_outcomes") == 0 and
                 row.get("official_final_admissions") == 0,
                 "six_cell_adapter_ledger_invalid")
        for relative, expected in files.items():
            source = ROOT / relative
            _require(source.is_file() and not source.is_symlink() and
                     source.resolve().is_relative_to(ROOT) and
                     sha256(source.read_bytes()).hexdigest() == expected,
                     "six_cell_adapter_source_changed")
        profiles[cell] = {
            "common_source_sha256s": common,
            "adapter_sha256": files[path],
        }
    _require(set(profiles) == set(CELLS), "six_cell_adapter_ledger_invalid")
    value = {
        "schema": SCHEMA,
        "status": "ratified_pre_result",
        "ratified_utc": datetime.now(timezone.utc).isoformat(),
        "action_profile": "scale-action-profile-v0.6.6",
        "common_source_sha256s": common,
        "cell_profiles": profiles,
        "base_and_selected_identical": True,
        "hidden_final_model_attempts_before_ratification": 0,
    }
    public = {
        "schema": "cua-six-cell-v066-code-only-control-ratification-public-v1",
        "status": "source_bytes_frozen_for_evaluator_controls_only",
        "static_ledger_sha256": sha256(raw).hexdigest(),
        "shared_action_bundle_sha256": bundle["bundle_sha256"],
        "cell_adapter_sha256s": {cell: profiles[cell]["adapter_sha256"]
                                 for cell in CELLS},
        "common_source_sha256s": common,
        "synthetic_action_tests": ledger["test_evidence"]["test_count"],
        "six_cell_live_smokes_complete": False,
        "full_study_pre_campaign_witness_published": False,
        "qualified_final_tasks": 0,
        "researcher_campaigns": 0,
        "official_final_model_results": 0,
    }
    return value, public


def write(private_path: Path, public_path: Path) -> dict:
    private = Path(private_path).absolute()
    public = Path(public_path).absolute()
    work_root = ROOT / "work"
    _require(not work_root.is_symlink() and
             private.parent.resolve().is_relative_to(work_root.resolve()) and
             not private.exists() and not private.is_symlink() and
             public.parent.resolve() == (ROOT / "docs/evidence").resolve() and
             not public.exists() and not public.is_symlink(),
             "new_private_work_and_public_evidence_paths_required")
    value, aggregate = build()
    private.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    private.parent.chmod(0o700)
    raw = (json.dumps(value, sort_keys=True,
                      separators=(",", ":")) + "\n").encode()
    descriptor = os.open(private, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    _, digest = validate_ratification(private)
    aggregate["private_ratification_sha256"] = digest
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
    print(json.dumps({
        "status": result["status"],
        "private_ratification_sha256": result["private_ratification_sha256"],
        "qualified_final_tasks": 0,
        "researcher_campaigns": 0,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
