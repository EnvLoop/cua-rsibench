"""Pin two public Office task pools without admitting untested web-GUI tasks.

The private manifest contains source task identities and stays outside Git. The
public receipt contains aggregate counts and source pins, never task text,
answer files, source workbook/deck bytes, or evaluator contracts. Neither
output is an official final benchmark or a GUI execution trace.
"""

from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prepare_hard_excel_v2_split as excel_source

PPT_COMMIT = "1b8b55a29e48fdc65d423689b6f2370ad91beeea"
PPT_REGISTRY_SHA256 = "aef4fdba6c70ff30946c8391e82e673cf17efc81f078d3ec825bed279de4fa51"
PPT_RANK_PREFIX = "envloop-scale-v1:23:"
PPT_GUI_SELECTION_ID = "4._Pre-Colonial_Filipino_Culture-001"
PPT_GUI_RECEIPT = "docs/evidence/ppt-eval-office-web-gate-2026-09-24.json"
EXCEL_GUI_RECEIPT = "docs/evidence/sec-retail-working-capital-excel-web-controls-2026-09-24.json"
ARTIFACT_BINDINGS = (
    "source_input", "office_normalized_baseline", "oracle_freeze", "gui_action_trace",
    "positive_saved", "wrong_answer_saved", "collateral_edit_saved", "same_file_reset_saved",
    "fresh_copy_reset_saved", "oracle_receipt",
)
EVALUATOR_CHECKS = (
    "original_software_gui_observed", "isolated_attempt", "saved_reloaded_and_downloaded",
    "target_positive_pass", "positive_no_regression_pass", "wrong_answer_rejected",
    "collateral_edit_rejected", "same_file_reset_restored", "fresh_copy_reset_restored",
    "source_template_entity_overlap_reviewed", "reference_hidden_from_actor",
)


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def canonical_digest(value: object) -> str:
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":")).encode())


def rank(value: str) -> str:
    return digest((PPT_RANK_PREFIX + value).encode())


def ppt_functions(node: dict):
    code = (node.get("scorer") or {}).get("function_code")
    if code:
        yield code
    for child in node.get("children", []):
        yield from ppt_functions(child)


def scoring_dependency(rubric: dict) -> str:
    calls = set()
    for code in ppt_functions(rubric["root"]):
        for node in ast.walk(ast.parse(code)):
            if isinstance(node, ast.Call):
                name = (node.func.id if isinstance(node.func, ast.Name) else
                        node.func.attr if isinstance(node.func, ast.Attribute) else "")
                if name in {"vlm_call", "llm_call"}:
                    calls.add(name)
    return "VLM" if "vlm_call" in calls else "LLM" if "llm_call" in calls else "programmatic"


def plan_ppt(source_root: Path) -> dict:
    source_root = source_root.resolve()
    commit = subprocess.run(["git", "-C", str(source_root), "rev-parse", "HEAD"],
                            check=True, text=True, capture_output=True).stdout.strip()
    if commit != PPT_COMMIT:
        raise ValueError("PPT-Eval checkout does not match the pinned revision")
    status = subprocess.run(["git", "-C", str(source_root), "status", "--porcelain"],
                            check=True, text=True, capture_output=True).stdout
    if status.strip():
        raise ValueError("PPT-Eval checkout is not clean")
    registry = source_root / "task_registry/tasks.json"
    raw = registry.read_bytes()
    if digest(raw) != PPT_REGISTRY_SHA256:
        raise ValueError("PPT-Eval registry hash changed")
    tasks = json.loads(raw)
    if len(tasks) != 120:
        raise ValueError("unexpected PPT-Eval task count")
    grouped = defaultdict(list)
    for task_id, task in tasks.items():
        if not str(task["file_path"]).startswith("data/files/PowerPoint/"):
            raise ValueError("unexpected PPT-Eval deck path")
        rubric_relative = Path(task["rubric_path"])
        if rubric_relative.is_absolute() or ".." in rubric_relative.parts:
            raise ValueError("unsafe rubric path")
        rubric_path = source_root / rubric_relative
        rubric_raw = rubric_path.read_bytes()
        rubric = json.loads(rubric_raw)
        deck = task["file_path"]
        grouped[deck].append({
            "task_id": task_id,
            "source_group": "ppt-deck:" + canonical_digest(deck),
            "template_group": "ppt-deck:" + canonical_digest(deck),
            "entity_group": "ppt-source-item-unresolved:" + canonical_digest(deck),
            "instance_group": "ppt-task:" + canonical_digest(task_id),
            "source_record_sha256": canonical_digest(task),
            "rubric_sha256": digest(rubric_raw),
            "difficulty": task["misc"]["difficulty"],
            "scoring_dependency": scoring_dependency(rubric),
            "source_deck": deck,
            "rubric_path": str(rubric_relative),
            "admission_status": "pending_individual_gui_and_oracle_controls",
        })
    if len(grouped) != 12 or any(len(rows) != 10 for rows in grouped.values()):
        raise ValueError("expected 12 PPT-Eval source decks with 10 tasks each")
    decks = sorted(grouped, key=rank)
    split = {
        "selection": sorted((row for deck in decks[:2] for row in grouped[deck]),
                            key=lambda row: rank(row["task_id"])),
        "provisional_final": sorted((row for deck in decks[2:] for row in grouped[deck]),
                                    key=lambda row: rank(row["task_id"])),
    }
    check_split(split, 2, 10)
    if PPT_GUI_SELECTION_ID not in {row["task_id"] for row in split["selection"]}:
        raise ValueError("previously controlled selection task moved")
    return {
        "cell_id": "powerpoint-web", "source": {
            "repository": "https://github.com/microsoft/ppteval", "revision": PPT_COMMIT,
            "registry_sha256": PPT_REGISTRY_SHA256,
            "published_task_instances": 120, "published_source_families": 12,
        }, "sets": split,
        "cluster_quality": {
            "source": "canonical deck path verified against the pinned registry",
            "template": "conservatively co-clustered within each deck; cross-deck template similarity unreviewed",
            "entity": "source-item identity unresolved; a deck-specific placeholder is not an entity de-duplication proof",
        },
        "prior_gui_control": {"task_id": PPT_GUI_SELECTION_ID,
                              "split": "selection", "status": "one narrow human GUI control",
                              "official_final_credit": 0},
    }


def plan_excel(archive: Path) -> dict:
    audited = excel_source.audit_archive(archive)
    source = audited["source"]
    if audited["counts"]["published_task_instances"] != 200:
        raise ValueError("unexpected SpreadsheetBench 2 source count")
    families = {row["family_id"]: row for row in audited["families"]}
    split = {}
    for name in ("selection", "provisional_final"):
        rows = []
        for row in audited["task_sets"][name]:
            family_id = row["family_id"]
            family = families[family_id]
            if family["screening_reasons"]:
                raise ValueError("screened-out workbook family selected")
            rows.append({
                "task_id": row["task_id"], "input_sha256": row["input_sha256"],
                "instruction_sha256": row["instruction_sha256"],
                "source_group": "excel-golden:" + canonical_digest(family_id),
                "template_group": "excel-golden:" + canonical_digest(family_id),
                "entity_group": "excel-entity-unresolved:" + canonical_digest(family_id),
                "instance_group": "excel-input:" + canonical_digest(row["input_sha256"]),
                "source_family": family_id, "category": family["category"],
                "structural_features_first_input": family["features_first_input"],
                "admission_status": "pending_individual_gui_and_oracle_controls",
            })
        split[name] = rows
    check_split(split, 3, 15)
    if len({row["input_sha256"] for name in split for row in split[name]}) != 120:
        raise ValueError("Excel task inputs are not byte-distinct across the split")
    return {
        "cell_id": "excel-web", "source": {
            "repository": "https://huggingface.co/datasets/KAKA22/SpreadsheetBench-v2",
            "revision": source["revision"], "archive_sha256": source["archive_sha256"],
            "published_task_instances": 200, "published_source_families": 30,
            "eligible_families_under_structural_triage": audited["counts"]["eligible_families"],
            "license_conflict": source["license_conflict"],
        }, "sets": split, "cluster_quality": {
            "source": "identical golden-response workbook paths grouped as one family",
            "template": "conservatively co-clustered within each golden workbook; cross-family template similarity unreviewed",
            "entity": "issuer/project identity cannot be reliably inferred from all source paths; a family-specific placeholder is not an entity de-duplication proof",
        }, "prior_gui_control": {
            "task_id": None, "split": "separate authored SEC development task",
            "status": "human GUI partial/full/manual-reset control on one distinct workbook",
            "official_final_credit": 0,
        },
    }


def check_split(split: dict, expected_selection_families: int,
                expected_final_families: int) -> None:
    selection, final = split["selection"], split["provisional_final"]
    if len(selection) != 20 or len(final) != 100:
        raise ValueError("expected 20 selection and 100 provisional final tasks")
    ids = [row["task_id"] for row in selection + final]
    if len(set(ids)) != 120:
        raise ValueError("task identities overlap or repeat")
    for field in ("source_group", "template_group", "instance_group"):
        if {row[field] for row in selection} & {row[field] for row in final}:
            raise ValueError(field + " crosses selection and final")
    if len({row["source_group"] for row in selection}) != expected_selection_families:
        raise ValueError("unexpected selection family count")
    if len({row["source_group"] for row in final}) != expected_final_families:
        raise ValueError("unexpected final family count")


def load_prior_control(root: Path, relative: str) -> dict:
    path = root / relative
    receipt = json.loads(path.read_text())
    return {"public_receipt": relative, "public_receipt_sha256": digest(path.read_bytes()),
            "evidence_kind": receipt["schema"]}


def summarize_cell(cell: dict, root: Path) -> dict:
    selection = cell["sets"]["selection"]
    final = cell["sets"]["provisional_final"]
    prior_path = PPT_GUI_RECEIPT if cell["cell_id"] == "powerpoint-web" else EXCEL_GUI_RECEIPT
    dependency = Counter(row.get("scoring_dependency", "task_specific_oracle_pending") for row in final)
    return {
        "cell_id": cell["cell_id"], "source": cell["source"],
        "counts": {
            "selection_candidate_tasks": 20,
            "selection_source_families": len({r["source_group"] for r in selection}),
            "provisional_final_tasks": 100,
            "provisional_final_source_families": len({r["source_group"] for r in final}),
            "individually_gui_admitted_final_tasks": 0,
            "official_hidden_final_tasks": 0,
            "selection_scoring_dependencies": dict(sorted(Counter(r.get("scoring_dependency", "task_specific_oracle_pending") for r in selection).items())),
            "final_scoring_dependencies": dict(sorted(dependency.items())),
        },
        "cluster_quality": cell["cluster_quality"],
        "candidate_identity_commitment_sha256": canonical_digest({
            "selection": [r["task_id"] for r in selection],
            "provisional_final": [r["task_id"] for r in final]}),
        "prior_gui_control": {**cell["prior_gui_control"], **load_prior_control(root, prior_path)},
        "admission_state": "offline_provisional_candidates_only",
        "public_answer_exposure": "Published upstream tasks and answers are discoverable; this split alone cannot be a sealed hidden exam.",
    }


def admission_contract() -> dict:
    return {
        "schema": "office-web-task-admission-contract-v1",
        "owner": "independent evaluator; actor cannot write contracts, reference files, or receipts",
        "per_task_evidence_required": [
            "pinned source and source-family lineage, including license review",
            "fresh isolated Microsoft web document created from source input; immutable original file hash",
            "untouched GUI open/edit-mode/save/reload/download and Office-normalized baseline hash",
            "frozen task-specific oracle, allowlisted normalizations, and output path before candidate action",
            "visible GUI known-positive action sequence with action/time budget and saved-file readback",
            "task-specific target outcome plus unrelated-content/structure preservation",
            "wrong-answer or partial-answer negative and unrelated-edit negative, both rejected",
            "changed same-file state restored to initial semantic state and independently re-read, followed by a fresh-copy reset test",
            "independent hidden input perturbation where a formula or data dependency is claimed",
            "source/template/entity overlap review against train and selection and prior published task exposure",
        ],
        "strongly_separate": {
            "actor_visible": ["task instruction", "source document in original Microsoft web app", "visible UI observations"],
            "evaluator_only": ["reference answer and output ranges", "original rubric and independent oracle",
                               "negative/perturbation cases", "normalized baseline", "save/readback/reset receipts",
                               "final candidate identities until task closure"],
            "public": ["source pins", "aggregate cluster and dependency counts", "admission criteria",
                       "redacted control receipts", "final results after completed evaluation"],
        },
        "result_policy": "Infrastructure failures remain unscored; no score is assigned from a screenshot or upstream rubric alone. Candidate count never substitutes for individually audited GUI admission.",
        "evidence_schema": "office-web-evaluator-task-evidence-v1",
        "required_byte_bindings": list(ARTIFACT_BINDINGS),
        "required_evaluator_checks": list(EVALUATOR_CHECKS),
        "preflight_policy": "Byte and declaration preflight remains pending independent origin and task-specific oracle audit; it cannot itself admit a task.",
        "qualification_status": "not_qualified",
    }


def preflight_task_evidence(cell_id: str, task: dict, receipt_path: Path,
                            evaluator_root: Path) -> dict:
    """Check private evidence bindings but never certify GUI or oracle truth.

    The calling evaluator must independently inspect the action trace and run
    its task-specific verifier. This generic preflight deliberately returns no
    admitted=True flag, even when the declaration is internally consistent.
    """
    root = evaluator_root.resolve()
    receipt = json.loads(receipt_path.read_text())
    if receipt.get("schema") != "office-web-evaluator-task-evidence-v1":
        raise ValueError("unknown evaluator evidence schema")
    if (receipt.get("cell_id"), receipt.get("task_id")) != (cell_id, task["task_id"]):
        raise ValueError("evidence identity does not match the candidate")
    expected_source_hash = task.get("input_sha256") or task.get("source_record_sha256")
    if receipt.get("source_identity_sha256") != expected_source_hash:
        raise ValueError("source identity hash does not match the candidate")
    artifacts = receipt.get("artifacts") or {}
    if set(artifacts) != set(ARTIFACT_BINDINGS):
        raise ValueError("incomplete or unexpected evaluator artifact bindings")
    for key in ARTIFACT_BINDINGS:
        binding = artifacts[key]
        relative = Path(binding["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("unsafe evaluator artifact path")
        path = (root / relative).resolve()
        try:
            path.relative_to(root)
        except ValueError as error:
            raise ValueError("evaluator artifact escapes private root") from error
        if not path.is_file() or digest(path.read_bytes()) != binding.get("sha256"):
            raise ValueError("evaluator artifact missing or hash mismatch: " + key)
    checks = receipt.get("evaluator_checks") or {}
    if set(checks) != set(EVALUATOR_CHECKS) or not all(checks.values()):
        raise ValueError("required evaluator declarations are incomplete")
    return {"status": "byte_bound_pending_independent_origin_and_oracle_audit",
            "task_id": task["task_id"], "artifact_count": len(ARTIFACT_BINDINGS),
            "gui_admitted": False, "official_final_credit": 0}


def produce(ppt_root: Path, excel_archive: Path, project_root: Path,
            private_out: Path, public_out: Path) -> dict:
    if private_out.resolve() == public_out.resolve():
        raise ValueError("public and evaluator-only output paths must differ")
    # A private candidate list accidentally placed under docs/ or tools/ would
    # be too easy to commit. Inside this checkout, permit only ignored work/.
    try:
        relative_private = private_out.resolve().relative_to(project_root.resolve())
    except ValueError:
        pass  # An external evaluator-controlled location is also acceptable.
    else:
        if not relative_private.parts or relative_private.parts[0] != "work":
            raise ValueError("evaluator-only output inside the checkout must be under ignored work/")
    cells = [plan_ppt(ppt_root), plan_excel(excel_archive)]
    private = {"schema": "office-web-20-100-evaluator-inventory-v1",
               "status": "offline_provisional_only_not_a_final_exam",
               "cells": cells, "contract": admission_contract()}
    public = {"schema": "office-web-20-100-public-screen-v1",
              "status": "offline_provisional_only_not_a_final_exam",
              "cells": [summarize_cell(cell, project_root) for cell in cells],
              "contract": admission_contract(),
              "no_source_document_or_answer_binaries_published": True,
              "no_model_attempt_or_full_study_score": True}
    private_out.parent.mkdir(parents=True, exist_ok=True)
    public_out.parent.mkdir(parents=True, exist_ok=True)
    private_out.write_text(json.dumps(private, indent=2, ensure_ascii=True) + "\n")
    private_out.chmod(0o600)
    public_out.write_text(json.dumps(public, indent=2, ensure_ascii=True) + "\n")
    return public


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ppt-root", type=Path, required=True)
    parser.add_argument("--excel-archive", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--private-out", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    report = produce(args.ppt_root, args.excel_archive, args.project_root,
                     args.private_out, args.public_out)
    print(json.dumps({cell["cell_id"]: cell["counts"] for cell in report["cells"]}))


if __name__ == "__main__":
    main()
