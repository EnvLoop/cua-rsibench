"""Build an OFFLINE, non-scored OSWorld native LibreOffice admission backlog.

Run against a checkout of the pinned OSWorld revision. This tool only reads
public task configurations; it never starts a desktop or downloads task assets.
The resulting IDs are provisional and must not be reported as a final suite.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


SOURCE_COMMIT = "b138d348256078fa634fc3b73567a7337c793e6b"
INDEX_SHA256 = "9ebc5187cbd727ef26c24626820076b102fff812863c640a67c467fea9542ab5"
SINGLE_APPS = ("libreoffice_calc", "libreoffice_impress", "libreoffice_writer")
ALLOWED_MULTI_APPS = set(SINGLE_APPS) | {"os"}
SELECTION_QUOTAS = {"libreoffice_calc": 8, "libreoffice_impress": 8, "libreoffice_writer": 4}
SPLIT_SALT = "envloop-osworld-native-office-admission-v1"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_key(task_id: str) -> str:
    return sha256(f"{SPLIT_SALT}:{task_id}".encode("ascii"))


def result_types(result: object) -> set[str]:
    """Return evaluator result channels without exposing evaluator gold."""
    if isinstance(result, dict):
        value = result.get("type")
        return {value} if isinstance(value, str) else set()
    if isinstance(result, list):
        return set().union(*(result_types(item) for item in result))
    return set()


def read_task(root: Path, domain: str, task_id: str) -> dict:
    path = root / "evaluation_examples" / "examples" / domain / f"{task_id}.json"
    raw = path.read_bytes()
    task = json.loads(raw)
    if task.get("id") != task_id:
        raise ValueError(f"Task ID mismatch: {domain}/{task_id}")
    evaluator = task.get("evaluator", {})
    apps = sorted({str(app).lower() for app in task.get("related_apps", [])})
    downloads = sum(
        len(step.get("parameters", {}).get("files", []))
        for step in task.get("config", [])
        if step.get("type") == "download"
    )
    source_text = task.get("source") or ""
    return {
        "id": task_id,
        "domain": domain,
        "snapshot": task.get("snapshot"),
        "related_apps": apps,
        "task_config_sha256": sha256(raw),
        "setup_step_types": [step.get("type") for step in task.get("config", [])],
        "download_asset_references": downloads,
        "evaluator_function": evaluator.get("func"),
        "evaluator_result_types": sorted(result_types(evaluator.get("result"))),
        "source_group_sha256": sha256(source_text.encode("utf-8")),
    }


def eligible_rows(source_root: Path) -> tuple[list[dict], dict[str, int]]:
    index_path = source_root / "evaluation_examples" / "test_all.json"
    raw_index = index_path.read_bytes()
    observed_hash = sha256(raw_index)
    if observed_hash != INDEX_SHA256:
        raise ValueError(f"Unexpected OSWorld task index SHA-256: {observed_hash}")
    index = json.loads(raw_index)
    counts = {domain: len(ids) for domain, ids in index.items()}
    if len(index) != 10 or sum(counts.values()) != 369:
        raise ValueError(f"Unexpected OSWorld index shape: {counts}")
    seen_ids: set[str] = set()
    rows = []
    for domain in (*SINGLE_APPS, "multi_apps"):
        for task_id in index[domain]:
            if task_id in seen_ids:
                raise ValueError(f"Duplicate task ID: {task_id}")
            seen_ids.add(task_id)
            row = read_task(source_root, domain, task_id)
            if "vm_file" not in row["evaluator_result_types"]:
                continue
            if domain == "multi_apps":
                apps = set(row["related_apps"])
                if not apps or not apps.issubset(ALLOWED_MULTI_APPS) or not apps.intersection(SINGLE_APPS):
                    continue
            rows.append(row)
    return rows, counts


def split_rows(rows: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    source_sizes = Counter(row["source_group_sha256"] for row in rows)
    for row in rows:
        row["source_group_size_in_candidate_pool"] = source_sizes[row["source_group_sha256"]]
    selected = []
    for domain, quota in SELECTION_QUOTAS.items():
        choices = sorted(
            (row for row in rows if row["domain"] == domain and row["source_group_size_in_candidate_pool"] == 1),
            key=lambda row: stable_key(row["id"]),
        )
        if len(choices) < quota:
            raise ValueError(f"Only {len(choices)} source-unique {domain} choices for quota {quota}")
        selected.extend(choices[:quota])
    selection_ids = {row["id"] for row in selected}
    remaining_single = sorted(
        (row for row in rows if row["domain"] in SINGLE_APPS and row["id"] not in selection_ids),
        key=lambda row: (row["domain"], stable_key(row["id"])),
    )
    multi = sorted(
        (row for row in rows if row["domain"] == "multi_apps"),
        key=lambda row: ("os" in row["related_apps"], stable_key(row["id"])),
    )
    need_multi = 100 - len(remaining_single)
    if need_multi < 0 or len(multi) < need_multi:
        raise ValueError(f"Cannot construct 100 final candidates from {len(remaining_single)} single-app and {len(multi)} multi-app rows")
    final = remaining_single + multi[:need_multi]
    reserve = multi[need_multi:]
    if len(selected) != 20 or len(final) != 100:
        raise AssertionError("Incorrect 20/100 split")
    selected_sources = {row["source_group_sha256"] for row in selected}
    if selected_sources & {row["source_group_sha256"] for row in final}:
        raise AssertionError("Exact source-string overlap between selection and provisional final")
    ids = [row["id"] for row in selected + final + reserve]
    if len(ids) != len(set(ids)) or len(ids) != len(rows):
        raise AssertionError("Split lost or duplicated task identities")
    return selected, final, reserve


def build_manifest(source_root: Path) -> dict:
    rows, source_counts = eligible_rows(source_root)
    selection, final, reserve = split_rows(rows)
    return {
        "schema": "envloop-osworld-native-office-offline-candidates-v1",
        "source": {
            "repository": "https://github.com/xlang-ai/OSWorld",
            "commit": SOURCE_COMMIT,
            "test_all_sha256": INDEX_SHA256,
            "source_domain_counts": source_counts,
        },
        "identity": "Linux LibreOffice Calc, Impress, and Writer plus selected original OSWorld multi-app tasks; not Microsoft Excel, PowerPoint, or Word",
        "status": "offline_provisional_candidates_not_runtime_admitted",
        "selection_policy": {
            "salt": SPLIT_SALT,
            "single_app_quotas": SELECTION_QUOTAS,
            "selection_exact_source_string_disjoint_from_final": True,
            "warning": "Source strings and public task IDs do not establish asset-family or answer isolation; all evaluator configs are upstream-public.",
        },
        "counts": {
            "source_ids": sum(source_counts.values()),
            "offline_file_evaluator_candidates": len(rows),
            "selection_candidates": len(selection),
            "provisional_final_candidates": len(final),
            "reserve_candidates": len(reserve),
            "runtime_admitted_final_tasks": 0,
            "official_scored_final_tasks": 0,
        },
        "required_runtime_gates": [
            "pinned_native_image_and_application_versions",
            "asset_fetch_and_hash_injection",
            "screenshot_and_gui_action",
            "saved_artifact_readback",
            "upstream_evaluator_baseline_negative_and_oracle_positive",
            "independent_preservation_guard",
            "destroy_recreate_reset_with_hash_and_profile_checks",
            "100_distinct_task_setup_and_verifier_admissions",
        ],
        "selection": selection,
        "provisional_final": final,
        "reserve": reserve,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True, help="Extracted OSWorld pinned source root")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = build_manifest(args.source_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest["counts"], sort_keys=True))


if __name__ == "__main__":
    main()
