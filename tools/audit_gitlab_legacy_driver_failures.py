"""Retain pre-receipt GitLab GUI selector failures as partial private evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from gitlab_world import factory, runtime


PRIVATE = runtime.PRIVATE
OUTPUT = PRIVATE / "legacy-driver-failure-audit-private.json"
GUI = PRIVATE / "gui-controls"


def _record(folder: Path, family: str, subtype: str, minimum_pngs: int) -> dict:
    if not folder.is_dir() or (folder / "receipt.json").exists():
        raise RuntimeError("legacy driver failure is not a partial, unscored folder")
    images = sorted(folder.glob("*.png"))
    if len(images) < minimum_pngs:
        raise RuntimeError("legacy driver failure screenshots missing")
    return {"private_directory": str(folder.relative_to(PRIVATE)),
            "family": family, "failure_subtype": subtype,
            "native_gui_screenshot_sha256": {
                item.name: hashlib.sha256(item.read_bytes()).hexdigest()
                for item in images},
            "independent_score_available": False,
            "official_final_admitted": False}


def build() -> dict:
    first = GUI / "GLW-11-01" / "positive-1"
    milestone = [folder for folder in (GUI / "GLW-11-02").glob("trio-*/positive-1")
                 if not (folder / "receipt.json").exists()]
    if len(milestone) != 1:
        raise RuntimeError("ambiguous legacy milestone selector failure")
    rows = [
        _record(first, "cross_record_issue_triage",
                "label_apply_selector_timeout", 2),
        _record(milestone[0], "release_milestone_coordination",
                "auto_save_milestone_apply_selector_timeout", 3),
    ]
    private = {"schema": "envloop-gitlab-legacy-partial-driver-failures-v1",
               "status": "partial_unscored_gui_artifacts_not_final_results",
               "items": rows}
    if OUTPUT.exists():
        if json.loads(OUTPUT.read_text()) != private:
            raise RuntimeError("legacy partial failure audit drift")
    else:
        factory.write_private(OUTPUT, private)
    return {"schema": "envloop-gitlab-legacy-failure-public-count-v1",
            "partial_unscored_driver_failure_count": len(rows),
            "native_gui_screenshots_retained_private": sum(
                len(row["native_gui_screenshot_sha256"]) for row in rows),
            "promoted_to_official_results": False}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, sort_keys=True))
