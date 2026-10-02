"""Prove new Odoo hidden identities/assets are isolated from exposed pools.

Reads evaluator-private manifests and emits counts, hashes and booleans only.
The temporary evaluator-owned QA world may share the new causal rules because
its prompts, source values and gold never enter researcher/public contexts;
its task IDs, entities and source bytes still must not overlap final tasks.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from factory import CODE_DIR
from hidden_factory import hidden_split_audit
from partition_factory import validate_scale_splits
from reset import file_hash
from worker_lease import exclusive_worker_operation

WORKERS = CODE_DIR / "partition_workers"


def _json(path: Path) -> dict:
    return json.loads(path.read_text())


def _case_dims(private: Path) -> dict[str, set[str]]:
    world = _json(private / "partition_cases.json")
    cases = [case for rows in world["cases"].values() for case in rows]
    source_hashes = _json(private / "source_hashes.json")
    return {
        "task_ids": {case["id"] for case in cases},
        "partners": set(world["vendors"] + world["customers"]),
        "skus": {product["sku"] for product in world["products"]},
        "salespeople": set(world["salespeople"]),
        "source_sha256": set(source_hashes.values()),
        "instance_groups": {case["instance_group"] for case in cases
                            if "instance_group" in case},
        "template_groups": {case["template_group"] for case in cases
                            if "template_group" in case},
    }


def audit(*, public_output: Path,
          legacy_filestore_manifests: tuple[Path, ...] = ()) -> dict:
    final_private = WORKERS / "official_hidden" / "private"
    with exclusive_worker_operation("audit_hidden_boundary", root=final_private):
        train_seed = (WORKERS / "master-seed.txt").read_text().strip()
        hidden_seed = (WORKERS / "hidden-master-seed.txt").read_text().strip()
        qa_seed = (WORKERS / "hidden-qa-seed.txt").read_text().strip()
        seed_digests = {hashlib.sha256(seed.encode()).hexdigest()
                        for seed in (train_seed, hidden_seed, qa_seed)}
        if len(seed_digests) != 3:
            raise RuntimeError("Train, QA and final hidden seeds are not distinct")
        structural = hidden_split_audit(train_seed, hidden_seed)
        if not structural["strict_identity_source_template_disjoint"]:
            raise RuntimeError("Hidden source/entity/template leaked into train, selection or exposed final")
        final = _case_dims(final_private)
        names = {
            "train": WORKERS / "train" / "private",
            "selection": WORKERS / "selection" / "private",
            "exposed_development_final": WORKERS / "evaluation_candidate" / "private",
            "hidden_rule_qa_untagged": WORKERS / "hidden_qa" / "private",
            "hidden_rule_qa_tagged": WORKERS / "hidden_qa_tagged" / "private",
        }
        for path in WORKERS.glob("archive-*/private"):
            if (path / "partition_cases.json").exists():
                names[path.parent.name] = path
        compared = {}
        for name, private in names.items():
            if not (private / "partition_cases.json").exists():
                raise RuntimeError(f"Expected exposed or QA manifest unavailable: {name}")
            dims = _case_dims(private)
            compared[name] = {key: len(final[key] & dims[key]) for key in final}
        exposed = {name: values for name, values in compared.items()
                   if not name.startswith("hidden_rule_qa")
                   and "hidden_qa" not in name}
        if any(value for values in exposed.values() for value in values.values()):
            raise RuntimeError("Official hidden pool overlaps an exposed development pool")
        qa = {name: values for name, values in compared.items() if name not in exposed}
        non_template_keys = set(final) - {"template_groups"}
        if any(values[key] for values in qa.values() for key in non_template_keys):
            raise RuntimeError("Official hidden task/source/entity overlaps evaluator-private QA")
        if not all(values["template_groups"] == 4 for values in qa.values()):
            raise RuntimeError("QA should share the four reviewed rules, not source identities")
        receipt_paths = [WORKERS / split / "private" / "partition_receipt.json"
                         for split in ("train", "selection", "official_hidden")]
        receipts = [_json(path) for path in receipt_paths]
        manifests = {row["task_set_manifest_sha256"] for row in receipts}
        code = {json.dumps(row["pinned_code_and_runtime_sha256"], sort_keys=True)
                for row in receipts}
        if len(manifests) != 1 or len(code) != 1:
            raise RuntimeError("Three hidden-study worlds do not bind one taskset and runtime")
        for filename, digest in receipts[0]["pinned_code_and_runtime_sha256"].items():
            if file_hash(CODE_DIR / filename) != digest:
                raise RuntimeError(f"Pinned hidden study code drift: {filename}")
        task_sets = _json(final_private / "task_set_manifest.json")
        validate_scale_splits(task_sets)
        if {name: len(rows) for name, rows in task_sets.items()} != {
                "train": 20, "selection": 20, "official": 100}:
            raise RuntimeError("Wrong hidden-study task-set counts")
        old_worker_sources = []
        for manifest in legacy_filestore_manifests:
            if not manifest.is_file():
                raise RuntimeError("Declared legacy filestore manifest unavailable")
            old_worker_sources.append(set(_json(manifest).values()))
        if any(final["source_sha256"] & old for old in old_worker_sources):
            raise RuntimeError("Hidden source bytes match the earlier Odoo development filestore")
        private_report = {
            "schema": "envloop-odoo-hidden-boundary-private-v1",
            "status": "source_entity_template_boundary_passed_before_hidden_gui_admission",
            "train_seed_sha256": hashlib.sha256(train_seed.encode()).hexdigest(),
            "qa_seed_sha256": hashlib.sha256(qa_seed.encode()).hexdigest(),
            "hidden_seed_sha256": hashlib.sha256(hidden_seed.encode()).hexdigest(),
            "compared_pool_overlap_counts": compared,
            "legacy_filestore_manifests_compared": len(old_worker_sources),
            "task_set_manifest_sha256": next(iter(manifests)),
            "pinned_code_and_runtime_sha256": receipts[0]["pinned_code_and_runtime_sha256"],
            "boundary_auditor_sha256": file_hash(CODE_DIR / "audit_hidden_boundary.py"),
            "official_hidden_candidates": 100,
            "official_final_tasks_admitted": 0,
        }
        private_path = final_private / "hidden_boundary_audit.json"
        private_path.write_text(json.dumps(private_report, indent=2) + "\n")
        private_path.chmod(0o600)
        public = {
            "schema": "envloop-odoo-hidden-boundary-public-v1",
            "status": private_report["status"],
            "candidate_counts": {"train": 20, "selection": 20, "official_hidden": 100},
            "exposed_development_pools_compared": len(exposed),
            "evaluator_private_qa_pools_compared": len(qa),
            "source_entity_instance_overlap_with_any_compared_pool": 0,
            "legacy_filestore_manifests_compared": len(old_worker_sources),
            "causal_template_overlap_with_exposed_development": 0,
            "causal_template_overlap_with_evaluator_private_qa": 4,
            "qa_prompts_gold_and_sources_researcher_exposed": False,
            "v06_split_validator_passed": True,
            "three_worlds_bind_same_taskset_and_runtime": True,
            "task_set_manifest_sha256": private_report["task_set_manifest_sha256"],
            "boundary_auditor_sha256": private_report["boundary_auditor_sha256"],
            "private_boundary_audit_sha256": file_hash(private_path),
            "official_hidden_candidates": 100,
            "official_final_tasks_admitted": 0,
            "model_attempts": 0,
        }
        public_output.parent.mkdir(parents=True, exist_ok=True)
        public_output.write_text(json.dumps(public, indent=2) + "\n")
        return public


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("public_output", type=Path)
    parser.add_argument("--legacy-filestore-manifest", type=Path,
                        action="append", default=[])
    args = parser.parse_args()
    print(json.dumps(audit(public_output=args.public_output,
                           legacy_filestore_manifests=tuple(args.legacy_filestore_manifest)),
                     indent=2))
