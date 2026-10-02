"""Audit a train-source PowerPoint-web chart-caption GUI triad by saved PPTX."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from ppt_wdi_factory import verify
from tools.audit_ppt_wdi_web_train_triad_v1 import semantic_source_equal


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def write_new(path: Path, data: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = args.private_root.resolve()
    require(root.is_relative_to((Path.cwd() / "work").resolve()),
            "GUI evidence must be under ignored work/")
    raw_manifest = (root / "manifest.private.json").read_bytes()
    manifest = json.loads(raw_manifest)
    require(manifest["schema"] == "envloop-ppt-wdi-train-policy-development-private-v1" and
            manifest["model_calls"] == manifest["official_final_admitted"] == 0 and
            len(manifest["cases"]) == 10,
            "train-source development manifest changed")
    cases = [row for row in manifest["cases"]
             if row["workflow"] == "chart_caption_reconciliation"]
    require(len(cases) == 1 and cases[0]["split"] == "train_policy_development" and
            cases[0]["development_source_split"] == "train",
            "GUI pilot is not a unique train-source chart-caption case")
    task = cases[0]
    source = root / "packages/train_policy_development" / task["task_id"] / "source.pptx"
    gui = root / "gui-pilot"
    baseline = gui / "normalized-restored-baseline.pptx"
    positive = gui / "normalized-positive-refreshed.pptx"
    near = gui / "normalized-near-miss-saved.pptx"
    reset = gui / "normalized-fresh-reset-saved.pptx"
    require(all(path.is_file() for path in (source, baseline, positive, near, reset)),
            "downloaded role artifact missing")
    semantic = semantic_source_equal(source, baseline)
    require(semantic["slide_count"] == 7 and semantic["slide_text_equal"] and
            semantic["embedded_workbook_bytes_equal"] and
            semantic["native_chart_cache_semantically_equal"],
            "neutral Office-saved source diverges from pinned WDI")
    raw_base = baseline.read_bytes()
    for role in ("Positive", "NearMiss", "FreshReset"):
        role_input = gui / f"EL-PPT-Chart-Caption-Normalized-{role}.pptx"
        require(role_input.read_bytes() == raw_base,
                "three isolated cloud roles did not start byte-identically")
    oracle = verify.freeze(baseline, task, office_web_normalized=True)
    require(len(oracle["targets"]) == 4 and
            oracle["source_snapshot_sha256"] == task["source_snapshot_sha256"],
            "four-target frozen WDI oracle changed")
    scored = {name: verify.verify(baseline, path, oracle)
              for name, path in (("baseline", baseline), ("positive", positive),
                                 ("near_miss", near), ("fresh_reset", reset))}
    require(scored["baseline"]["status"] == "scored" and
            scored["baseline"]["score"] == 0 and
            scored["positive"]["status"] == "scored" and
            scored["positive"]["score"] == 1 and
            scored["positive"]["target_correct"] and
            scored["positive"]["preservation_pass"] and
            scored["near_miss"]["status"] == "scored" and
            scored["near_miss"]["score"] == 0 and
            scored["near_miss"]["preservation_pass"] and
            sum(row["correct"] for row in scored["near_miss"]["per_target"].values()) == 3 and
            scored["fresh_reset"]["status"] == "scored" and
            scored["fresh_reset"]["score"] == 0 and
            scored["fresh_reset"]["preservation_pass"] and
            reset.read_bytes() == raw_base,
            "downloaded positive/near-miss/reset triad did not discriminate")
    synthetic = {}
    for name in ("chart_damage", "collateral"):
        path = gui / f"{name}-synthetic.private.pptx"
        row = verify.verify(baseline, path, oracle)
        require(row["status"] == "scored" and row["score"] == 0 and
                row["target_correct"] and not row["preservation_pass"] and
                len(row["unexpected_parts"]) == 1,
                "chart/collateral synthetic control is not rejected")
        synthetic[name] = {"artifact_sha256": sha(path.read_bytes()),
                           "unexpected_parts": row["unexpected_parts"]}
    cloud_raw = (gui / "cloud-role-hashes.private.json").read_bytes()
    cloud = json.loads(cloud_raw)
    require(set(cloud) == {"neutral", "positive", "near_miss", "fresh_reset"} and
            len(set(cloud.values())) == 4 and
            all(re.fullmatch(r"[0-9a-f]{64}", value) for value in cloud.values()),
            "dedicated cloud item identities are not disjoint")
    pdf = gui / "visual-qa/normalized-positive-refreshed.pdf"
    pages = subprocess.check_output(["pdfinfo", str(pdf)], text=True,
                                    timeout=15)
    require(re.search(r"^Pages:\s+7$", pages, re.MULTILINE) is not None and
            (gui / "visual-qa/positive-contact-sheet.png").is_file(),
            "seven-page positive visual-QA output missing")
    private = {
        "schema": "envloop-ppt-web-chart-caption-triad-private-v1",
        "status": "train_source_gui_calibrated_not_final_admission",
        "task_id": task["task_id"],
        "source_group": task["source_group"],
        "manifest_sha256": sha(raw_manifest),
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
                        for name, row in scored.items()},
        "near_miss_correct_targets": 3,
        "fresh_reset_byte_equal": True,
        "synthetic_negative_controls": synthetic,
        "positive_pdf_sha256": sha(pdf.read_bytes()),
        "visual_qa_pages": 7,
        "model_calls": 0,
        "official_final_admitted": 0,
    }
    private_raw = (json.dumps(private, sort_keys=True, indent=2) + "\n").encode()
    private_path = gui / "web-chart-caption-triad.private.json"
    write_new(private_path, private_raw, 0o600)
    public = {
        "schema": "envloop-ppt-web-chart-caption-triad-public-v1",
        "status": private["status"],
        "private_evidence_sha256": sha(private_raw),
        "train_source_workflow_count": 1,
        "target_count": 4,
        "distinct_cloud_items": 4,
        "normalized_role_inputs_byte_identical": True,
        "source_semantic_readback_pass": True,
        "downloaded_positive_score": 1,
        "downloaded_near_miss_score": 0,
        "near_miss_correct_targets": 3,
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
