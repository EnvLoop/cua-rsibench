"""Build ten final-shaped PowerPoint GUI controls on training source families.

These evaluator-only tasks exercise every final causal workflow without using
or exposing any selection/final country. They never enter the hidden exam.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

from native_desktop_factory import source as wdi
from ppt_wdi_factory import plan as ppt, verify
from ppt_wdi_factory.build import (
    DEFAULT_MODULES, DEFAULT_NODE, DEFAULT_PYTHON, DEFAULT_SKILL,
    prepare_builder,
)
from ppt_wdi_factory.qa import _chart_workbook, _validator


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def write_new(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-plan", type=Path, required=True)
    parser.add_argument("--original-plan-sha256", required=True)
    parser.add_argument("--seed-file", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    out = args.out_dir.resolve()
    require(out.is_relative_to((Path.cwd() / "work").resolve()) and
            not out.exists(), "fresh ignored work/ output required")
    raw_plan = args.original_plan.read_bytes()
    require(sha(raw_plan) == args.original_plan_sha256,
            "original private source split changed")
    original = json.loads(raw_plan)
    require(original["schema"] == ppt.SCHEMA and
            {key: len(rows) for key, rows in original["sets"].items()} == ppt.COUNTS,
            "original 20/20/100 inventory changed")
    seed = bytes.fromhex(args.seed_file.read_text().strip())
    require(len(seed) == 32 and original["seed_commitment_sha256"] == sha(seed),
            "private planning seed changed")
    train_families = list(dict.fromkeys(row["source_group"]
                                        for row in original["sets"]["train"]))
    held_out = {row["source_group"] for split in ("selection", "final_candidate")
                for row in original["sets"][split]}
    require(len(train_families) == 5 and not set(train_families) & held_out,
            "training source families overlap held-out source")
    source = wdi.load()
    cases = {}
    for country_index, iso in enumerate(train_families):
        for slot in range(4):
            row = ppt.task(seed, "final_candidate", iso, country_index,
                           slot, wdi.country_facts(source, iso))
            workflow = row["workflow"]
            if workflow in cases:
                continue
            row["split"] = "train_policy_development"
            row["task_id"] = "ppt-wdi-dev-" + ppt.keyed(
                seed, f"train-policy-development:{iso}:{workflow}").hex()[:16]
            row["instance_group"] = row["task_id"]
            row["template_group"] = f"train-policy-development-{workflow}-v1"
            row["development_source_split"] = "train"
            cases[workflow] = row
    require(set(cases) == set(ppt.WORKFLOWS) and len(cases) == 10 and
            len({row["task_id"] for row in cases.values()}) == 10,
            "ten distinct train-source final-shaped workflows required")
    out.mkdir(parents=True, mode=0o700)
    manifest = {"schema": "envloop-ppt-wdi-train-policy-development-private-v1",
                "status": "train_source_gui_development_not_final_admission",
                "original_plan_sha256": args.original_plan_sha256,
                "cases": [cases[workflow] for workflow in ppt.WORKFLOWS],
                "model_calls": 0, "official_final_admitted": 0}
    manifest_raw = ppt.canonical(manifest)
    write_new(out / "manifest.private.json", manifest_raw)
    builder = prepare_builder(out, DEFAULT_MODULES)
    finalizer = Path("ppt_wdi_factory/finalize_deck.mjs").resolve()
    env = {**os.environ, "NODE_OPTIONS": "--max-old-space-size=4096",
           "PRESENTATIONS_SKILL_DIR": str(DEFAULT_SKILL),
           "RUNTIME_PYTHON": str(DEFAULT_PYTHON),
           "RUNTIME_NODE": str(DEFAULT_NODE),
           "RUNTIME_NODE_MODULES": str(DEFAULT_MODULES)}
    tool_dir = DEFAULT_SKILL / "container_tools"

    def build_one(row: dict) -> dict:
        package = out / "packages/train_policy_development" / row["task_id"]
        spec = package / "task.private.json"
        write_new(spec, ppt.canonical(row))
        draft, deck = package / "draft.pptx", package / "source.pptx"
        subprocess.run([str(DEFAULT_NODE), str(builder), str(spec), str(draft)],
                       check=True, capture_output=True, env=env, timeout=180)
        draft.chmod(0o600)
        subprocess.run([str(DEFAULT_NODE), str(finalizer), str(draft), str(deck)],
                       check=True, capture_output=True, env=env, timeout=180)
        deck.chmod(0o600)
        _validator(tool_dir / "inspect_presentation_package_integrity.py",
                   ["--fail-on-findings"], deck)
        _validator(tool_dir / "inspect_presentation_layout_geometry.py",
                   ["--expected-aspect", "16:9", "--expected-slide-count", "7",
                    "--require-native-table-slide", "2", "--require-native-table-slide", "4",
                    "--approved-font-family", "Arial", "--validate-heading-fit",
                    "--fail-on-findings"], deck)
        require(_chart_workbook(deck), "native chart workbook missing")
        result = verify.calibrate(package)
        require(result["offline_controls_pass"],
                "train-source final-shaped offline controls failed")
        return {"workflow": row["workflow"],
                "task_id": row["task_id"],
                "source_group": row["source_group"],
                "deck_sha256": sha(deck.read_bytes()),
                "calibration_sha256": sha((package / "calibration.private.json").read_bytes())}

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(build_one, manifest["cases"]))
    receipt = {"schema": "envloop-ppt-wdi-train-policy-development-receipt-private-v1",
               "manifest_sha256": sha(manifest_raw),
               "builder_sha256": sha(builder.read_bytes()),
               "finalizer_sha256": sha(finalizer.read_bytes()),
               "verifier_sha256": sha(Path(verify.__file__).read_bytes()),
               "results": results,
               "source_families": len({row["source_group"] for row in results}),
               "workflows": len(results),
               "offline_positive_negative_reset_controls_passed": len(results),
               "model_calls": 0, "official_final_admitted": 0}
    receipt_raw = ppt.canonical(receipt)
    write_new(out / "receipt.private.json", receipt_raw)
    print(json.dumps({"status": manifest["status"],
                      "workflow_count": 10,
                      "train_source_family_count": receipt["source_families"],
                      "offline_controls_passed": len(results),
                      "private_manifest_sha256": sha(manifest_raw),
                      "private_receipt_sha256": sha(receipt_raw),
                      "official_final_admitted": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
