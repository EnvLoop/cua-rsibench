"""Audit train-source WDI-year reconciliation through PowerPoint-web readbacks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess

from ppt_wdi_factory import verify
from tools.audit_ppt_wdi_web_chart_caption_triad_v1 import require, sha, write_new
from tools.audit_ppt_wdi_web_train_triad_v1 import semantic_source_equal


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = args.private_root.resolve()
    require(root.is_relative_to((Path.cwd() / "work").resolve()),
            "GUI evidence must remain under ignored work/")
    manifest_raw = (root / "manifest.private.json").read_bytes()
    manifest = json.loads(manifest_raw)
    require(manifest["schema"] == "envloop-ppt-wdi-train-policy-development-private-v1" and
            manifest["model_calls"] == manifest["official_final_admitted"] == 0 and
            len(manifest["cases"]) == 10,
            "train-source development manifest changed")
    cases = [row for row in manifest["cases"]
             if row["workflow"] == "source_year_reconciliation"]
    require(len(cases) == 1 and cases[0]["split"] == "train_policy_development" and
            cases[0]["development_source_split"] == "train",
            "source-year GUI pilot is not a unique training-source case")
    task = cases[0]
    source = root / "packages/train_policy_development" / task["task_id"] / "source.pptx"
    gui = root / "gui-source-year"
    baseline = gui / "fully-normalized-baseline.pptx"
    positive = gui / "frozen-positive-saved.pptx"
    near = gui / "frozen-near-miss-saved.pptx"
    reset = gui / "frozen-fresh-reset-saved.pptx"
    require(all(path.is_file() for path in (source, baseline, positive, near, reset)),
            "downloaded source-year role artifact missing")
    semantic = semantic_source_equal(source, baseline)
    require(semantic["slide_count"] == 7 and semantic["slide_text_equal"] and
            semantic["embedded_workbook_bytes_equal"] and
            semantic["native_chart_cache_semantically_equal"],
            "neutral Office-saved source-year deck diverges from pinned WDI")
    raw_base = baseline.read_bytes()
    for role in ("Positive", "NearMiss", "FreshReset"):
        role_input = gui / f"EL-PPT-Source-Year-Frozen-{role}.pptx"
        require(role_input.read_bytes() == raw_base,
                "source-year role copies did not start byte-identically")
    oracle = verify.freeze(baseline, task, office_web_normalized=True)
    require(len(oracle["targets"]) == 4 and
            oracle["source_snapshot_sha256"] == task["source_snapshot_sha256"],
            "source-year frozen oracle changed")
    scores = {name: verify.verify(baseline, artifact, oracle)
              for name, artifact in (("baseline", baseline), ("positive", positive),
                                     ("near_miss", near), ("fresh_reset", reset))}
    require(scores["baseline"]["status"] == "scored" and
            scores["baseline"]["score"] == 0 and
            scores["positive"]["status"] == "scored" and
            scores["positive"]["score"] == 1 and
            scores["positive"]["target_correct"] and
            scores["positive"]["preservation_pass"] and
            scores["near_miss"]["status"] == "scored" and
            scores["near_miss"]["score"] == 0 and
            scores["near_miss"]["preservation_pass"] and
            sum(row["correct"] for row in
                scores["near_miss"]["per_target"].values()) == 3 and
            scores["near_miss"]["per_target"]["attribution"]["correct"] is False and
            scores["fresh_reset"]["status"] == "scored" and
            scores["fresh_reset"]["score"] == 0 and
            scores["fresh_reset"]["preservation_pass"] and
            reset.read_bytes() == raw_base,
            "downloaded source-year GUI triad did not discriminate")
    synthetic = {}
    for name in ("chart_damage", "collateral"):
        artifact = gui / f"{name}-synthetic.private.pptx"
        row = verify.verify(baseline, artifact, oracle)
        require(row["status"] == "scored" and row["score"] == 0 and
                row["target_correct"] and not row["preservation_pass"] and
                len(row["unexpected_parts"]) == 1,
                "source-year chart/collateral attack not rejected")
        synthetic[name] = {"artifact_sha256": sha(artifact.read_bytes()),
                           "unexpected_parts": row["unexpected_parts"]}
    cloud_raw = (gui / "cloud-role-hashes.private.json").read_bytes()
    cloud = json.loads(cloud_raw)
    require(set(cloud) == {"raw_source", "normalization", "positive",
                           "near_miss", "fresh_reset"} and
            len(set(cloud.values())) == 5 and
            all(re.fullmatch(r"[0-9a-f]{64}", value) for value in cloud.values()),
            "source-year cloud item identities are not disjoint")
    pdf = gui / "visual-qa/frozen-positive-saved.pdf"
    pages = subprocess.check_output(["pdfinfo", str(pdf)], text=True,
                                    timeout=15)
    require(re.search(r"^Pages:\s+7$", pages, re.MULTILINE) is not None and
            (gui / "visual-qa/positive-contact-sheet.png").is_file(),
            "seven-page source-year visual QA missing")
    private = {
        "schema": "envloop-ppt-web-source-year-triad-private-v1",
        "status": "train_source_gui_calibrated_not_final_admission",
        "task_id": task["task_id"],
        "source_group": task["source_group"],
        "manifest_sha256": sha(manifest_raw),
        "task_sha256": sha(verify.canonical(task)),
        "oracle_sha256": sha(verify.canonical(oracle)),
        "verifier_sha256": sha(Path(verify.__file__).read_bytes()),
        "cloud_role_url_sha256": cloud,
        "source_semantic_readback": semantic,
        "artifact_sha256": {name: sha(path.read_bytes()) for name, path in
                            (("source", source), ("normalized_baseline", baseline),
                             ("positive", positive), ("near_miss", near),
                             ("fresh_reset", reset))},
        "role_scores": {name: {key: row[key] for key in
                               ("status", "score", "target_correct", "preservation_pass")}
                        for name, row in scores.items()},
        "near_miss_missing_target": "attribution",
        "fresh_reset_byte_equal": True,
        "synthetic_negative_controls": synthetic,
        "positive_pdf_sha256": sha(pdf.read_bytes()),
        "visual_qa_pages": 7,
        "model_calls": 0,
        "official_final_admitted": 0,
    }
    private_raw = (json.dumps(private, sort_keys=True, indent=2) + "\n").encode()
    write_new(gui / "web-source-year-triad.private.json", private_raw, 0o600)
    public = {
        "schema": "envloop-ppt-web-source-year-triad-public-v1",
        "status": private["status"],
        "private_evidence_sha256": sha(private_raw),
        "train_source_workflow_count": 1,
        "target_count": 4,
        "distinct_cloud_items": 5,
        "normalized_role_inputs_byte_identical": True,
        "source_semantic_readback_pass": True,
        "downloaded_positive_score": 1,
        "downloaded_near_miss_score": 0,
        "near_miss_correct_targets": 3,
        "wrong_source_footnote_rejected": True,
        "downloaded_fresh_reset_score": 0,
        "fresh_reset_byte_equal": True,
        "chart_data_mutation_rejected": True,
        "collateral_mutation_rejected": True,
        "visual_qa_pages": 7,
        "model_calls": 0,
        "official_final_admitted": 0,
    }
    write_new(args.out, (json.dumps(public, sort_keys=True, indent=2) + "\n").encode(),
              0o644)
    print(json.dumps({"status": public["status"],
                      "positive": 1, "near_miss": 0,
                      "fresh_reset_byte_equal": True,
                      "official_final_admitted": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
