"""Check every offline candidate's package, layout, and chart workbook link."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile

from .build import DEFAULT_SKILL
from .plan import canonical


def _validator(script: Path, args: list[str], deck: Path) -> dict:
    run = subprocess.run([sys.executable, str(script), *args, str(deck)],
                         check=True, capture_output=True, text=True)
    report = json.loads(run.stdout)
    if report["finding_count"]:
        raise ValueError(script.name + " reported package/layout defects")
    return report


def _chart_workbook(deck: Path) -> bool:
    with ZipFile(deck) as archive:
        names = archive.namelist()
        workbooks = [name for name in names if name.startswith("ppt/embeddings/") and name.endswith(".xlsx")]
        charts = [name for name in names if "/charts/chart" in name and name.endswith(".xml")]
        if len(workbooks) != 1 or len(charts) != 1:
            return False
        return b"externalData" in archive.read(charts[0])


def audit(private: Path, *, skill_dir: Path = DEFAULT_SKILL, limit: int | None = None) -> dict:
    plan = json.loads((private / "candidate-plan.private.json").read_bytes())
    rows = [r for split in ("train", "selection", "final_candidate") for r in plan["sets"][split]]
    if limit:
        rows = rows[:limit]
    directory = skill_dir / "container_tools"
    result = {"candidate_decks": len(rows), "package_integrity_pass": 0,
              "layout_geometry_pass": 0, "chart_workbook_contract_pass": 0}
    for index, row in enumerate(rows, 1):
        deck = private / "packages" / row["split"] / row["task_id"] / "source.pptx"
        _validator(directory / "inspect_presentation_package_integrity.py",
                   ["--fail-on-findings"], deck)
        result["package_integrity_pass"] += 1
        _validator(directory / "inspect_presentation_layout_geometry.py",
                   ["--expected-aspect", "16:9", "--expected-slide-count", "7",
                    "--require-native-table-slide", "2", "--require-native-table-slide", "4",
                    "--approved-font-family", "Arial", "--validate-heading-fit", "--fail-on-findings"], deck)
        result["layout_geometry_pass"] += 1
        if not _chart_workbook(deck):
            raise ValueError("Embedded native chart workbook missing")
        result["chart_workbook_contract_pass"] += 1
        if index % 35 == 0:
            print(json.dumps({"checked": index, "requested": len(rows)}), flush=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-root", type=Path, required=True)
    parser.add_argument("--presentations-skill-dir", type=Path, default=DEFAULT_SKILL)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    result = audit(args.private_root, skill_dir=args.presentations_skill_dir, limit=args.limit)
    if args.limit is None:
        if result["candidate_decks"] != 140:
            raise ValueError("Full QA must cover 140 candidate decks")
        destination = args.private_root / "qa-aggregate.private.json"
        data = canonical(result)
        if destination.exists() and destination.read_bytes() != data:
            raise ValueError("Private QA receipt differs from prior frozen receipt")
        if not destination.exists():
            destination.write_bytes(data)
            destination.chmod(0o600)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
