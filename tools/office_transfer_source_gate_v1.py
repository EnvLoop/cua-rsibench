"""Pre-result, source-only gate for *additional* Office training analogues.

The public output contains counts and commitments only.  It never copies a
selection/final task, answer, filing accession, issuer, or private graph name.
No case becomes training material until its separately frozen artifact and
independent positive/near-miss/no-regression controls have passed.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
from concurrent.futures import ThreadPoolExecutor

from ppt_wdi_factory import verify as ppt_verify
from ppt_wdi_factory.build import (
    DEFAULT_MODULES, DEFAULT_NODE, DEFAULT_PYTHON, DEFAULT_SKILL,
)

from native_desktop_factory import source as wdi
from ppt_wdi_factory import plan as ppt
from tools.build_ppt_wdi_train_calibration_80_v1 import (
    PLAN_SHA, QUEUE_SHA, blind_heldout_collision,
)
from tools.audit_ppt_wdi_train_calibration_80_v1 import historical_collision
from tools.build_ppt_wdi_reserve_replacement_v1 import facts_from_official_response
from tools.extract_wdi_country_csv_reserve_v1 import extract


PPT_SCHEMA = "envloop-ppt-wdi-transfer-source-plan-private-v1"
EXCEL_SCHEMA = "envloop-sec-excel-transfer-skill-cards-private-v1"
EXCEL_CASE_SCHEMA = "envloop-sec-excel-transfer-analogues-private-v1"
EXCEL_SPLIT_SHA = "3459c1e2fbc4a02dbece31379849c28d52d12bf17b3d188a709590c1ee7df937"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
ACCESSION = re.compile(r"^\d{10}-\d{2}-\d{6}$")
RIGHTS_WDI = "wdi_cc_by_4_0_facts_plus_authored_simulation"
RIGHTS_SEC = "original_sec_filing_facts_plus_authored_scenario_derived_facts_only"


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError(reason)


def private_read(path: Path) -> tuple[dict, bytes]:
    raw = path.read_bytes()
    value = json.loads(raw)
    require(isinstance(value, dict), "private_json_must_be_object")
    return value, raw


def ppt_transfer_plan(seed: bytes, official_csv_root: Path,
                      original_train_plan: Path, heldout_plan: Path,
                      future_queue: Path, calibration_manifest: Path,
                      historical_plan_dir: Path) -> dict:
    """Make 80 distinct-country, four-target *specs*; never read held-out gold.

    Eight new official CSV source families are required.  The prior 80-case
    calibration inventory is treated as evaluation data and cannot be reused.
    """
    require(len(seed) == 32, "private_seed_must_have_32_bytes")
    original, original_raw = private_read(original_train_plan)
    calibration, calibration_raw = private_read(calibration_manifest)
    require(original.get("schema") == ppt.SCHEMA and
            original.get("sets", {}).keys() == {"train", "selection", "final_candidate"} and
            len(original["sets"]["train"]) == 20 and
            len(original["sets"]["selection"]) == 20 and
            len(original["sets"]["final_candidate"]) == 100,
            "original_20_20_100_anchor_changed")
    require(digest(original_raw) == PLAN_SHA and
            original_train_plan.resolve() == heldout_plan.resolve(),
            "active_v13_plan_hash_or_path_changed")
    require(calibration.get("schema") ==
            "envloop-ppt-wdi-train-calibration-80-private-v1" and
            len(calibration.get("rows", [])) == 80,
            "calibration_80_manifest_missing_or_changed")
    rows = calibration["rows"]
    require(len({row["source_group"] for row in rows}) == 8 and
            all(row.get("calibration_role") ==
                "nonfinal_train_only_four_target_analogue" for row in rows),
            "calibration_pool_role_or_sources_changed")
    blocked_sources = ({row["source_group"] for row in rows} |
                       {row["source_group"] for row in original["sets"]["train"]})
    csv_dirs = sorted(path for path in official_csv_root.iterdir() if path.is_dir())
    require(len(csv_dirs) == 8, "eight_new_official_wdi_country_csvs_required")
    sources = []
    for directory in csv_dirs:
        iso = directory.name
        require(re.fullmatch(r"[A-Z]{3}", iso) is not None and
                iso not in wdi.COUNTRIES and iso not in blocked_sources,
                "transfer_country_reuses_original_or_calibration_source")
        zip_raw = (official_csv_root / f"{iso}-country.private.zip").read_bytes()
        snapshot_raw = (directory / "source-snapshot.private.json").read_bytes()
        provenance_raw = (directory / "source-provenance.private.json").read_bytes()
        provenance = json.loads(provenance_raw)
        extracted, detail = extract(zip_raw, iso)
        require(extracted == snapshot_raw and
                provenance.get("schema") ==
                "envloop-wdi-official-country-csv-extract-private-v1" and
                provenance.get("country_iso") == iso and
                provenance.get("catalog_license") == "CC BY 4.0" and
                provenance.get("zip_sha256") == digest(zip_raw) and
                provenance.get("snapshot_sha256") == digest(snapshot_raw) and
                detail["numeric_observation_count"] == 30,
                "official_wdi_csv_provenance_or_values_changed")
        facts = facts_from_official_response(snapshot_raw)
        require(facts["iso3"] == iso and facts["name"] == provenance["country_name"],
                "official_csv_country_identity_changed")
        sources.append((iso, facts, provenance, snapshot_raw, zip_raw, provenance_raw))
    proposed = {item[0] for item in sources}
    collision = blind_heldout_collision(heldout_plan, future_queue, proposed)
    require(not collision["any_collision"], "transfer_country_hits_heldout_or_reserve")
    historical = historical_collision(historical_plan_dir, proposed)
    require(historical["historical_plan_revisions_checked"] >= 12 and
            historical["historical_final_source_collision_count"] == 0,
            "transfer_country_hits_historical_final_or_history_incomplete")
    require(proposed.isdisjoint(blocked_sources),
            "transfer_country_hits_anchor_or_calibration")
    result = []
    for workflow in ppt.WORKFLOWS:
        coordinate = next((i, slot) for i in range(25) for slot in range(4)
                          if ppt.workflow_for("final_candidate", i, slot) == workflow)
        for iso, facts, provenance, snapshot_raw, zip_raw, provenance_raw in sources:
            row = ppt.task(seed, "final_candidate", iso, *coordinate, facts)
            require(row["workflow"] == workflow and len(row["target_keys"]) == 4 and
                    len(set(row["target_keys"])) == 4 and
                    all(row["correct"][key] != row["draft"][key]
                        for key in row["target_keys"]),
                    "ppt_four_distinct_faulted_targets_required")
            identifier = "ppt-wdi-transfer-" + ppt.keyed(
                seed, f"train-transfer-v1:{iso}:{workflow}").hex()[:16]
            row.update({"task_id": identifier, "instance_group": identifier,
                        "split": "train_policy_development",
                        "development_source_split": "train",
                        "analogue_role": "additional_train_only_after_private_control_admission",
                        "template_group": f"ppt-transfer-brief-v1:{workflow}",
                        "presentation_template": "ppt_wdi_factory/build_train_transfer_deck.mjs",
                        "heading": f"{facts['name']} | evidence review | {row['calculation']['window']}",
                        "source_scope": "private_wdi_country_csv_reserve_v1",
                        "source_snapshot_sha256": digest(snapshot_raw),
                        "source_zip_sha256": digest(zip_raw),
                        "source_provenance_sha256": digest(provenance_raw),
                        "source_snapshot_date": provenance["download_date"],
                        "source_csv_data_last_updated": provenance["data_last_updated"],
                        "rights_tier": RIGHTS_WDI,
                        "official_final_credit": 0})
            result.append(row)
    require(len(result) == 80 and len({r["task_id"] for r in result}) == 80 and
            set(Counter(r["workflow"] for r in result).values()) == {8} and
            all(len({r["source_group"] for r in result if r["workflow"] == wf}) == 8
                for wf in ppt.WORKFLOWS),
            "ppt_80_case_balance_failed")
    return {"schema": PPT_SCHEMA, "status": "spec_only_unadmitted",
            "original_plan_sha256": digest(original_raw),
            "calibration_manifest_sha256": digest(calibration_raw),
            "future_queue_sha256": QUEUE_SHA,
            "seed_commitment_sha256": digest(seed),
            "source_overlap_counts": {"original_train": 0, "calibration": 0,
                                      "selection_final": 0, "future_reserve": 0,
                                      "historical_final": 0},
            "historical_plan_revisions_checked":
                historical["historical_plan_revisions_checked"],
            "rows": result, "offline_control_passed": 0,
            "office_web_gui_admitted": 0, "official_final_admitted": 0}


def ppt_public_receipt(plan: dict) -> dict:
    require(plan.get("schema") == PPT_SCHEMA and len(plan.get("rows", [])) == 80,
            "ppt_private_plan_not_ready")
    return {"schema": "envloop-office-transfer-ppt-source-public-v1",
            "status": "80_train_only_specs_source_checked_artifacts_unbuilt",
            "original_20_20_100_anchors_unchanged": True,
            "analogue_specs": 80, "workflows": 10,
            "cases_per_workflow": 8, "new_source_country_families": 8,
            "target_fields_per_case": 4,
            "source_overlap_counts": plan["source_overlap_counts"],
            "rights_tier": RIGHTS_WDI,
            "private_plan_sha256": digest(ppt.canonical(plan)),
            "offline_control_passed": 0, "office_web_gui_admitted": 0,
            "official_final_admitted": 0, "model_calls": 0}


def ppt_source_preflight(original_v13_plan: Path, calibration_manifest: Path | None,
                         official_csv_root: Path | None) -> dict:
    """Publish missing inputs without exposing private countries or task data."""
    original_ok = original_v13_plan.is_file() and digest(
        original_v13_plan.read_bytes()) == PLAN_SHA
    calibration_ok = calibration_manifest is not None and calibration_manifest.is_file()
    source_dirs = (sum(path.is_dir() for path in official_csv_root.iterdir())
                   if official_csv_root is not None and official_csv_root.is_dir() else 0)
    errors = []
    if not original_ok:
        errors.append("active_v13_20_20_100_plan_missing_or_changed")
    if not calibration_ok:
        errors.append("private_calibration_80_manifest_missing")
    if source_dirs != 8:
        errors.append("eight_new_official_wdi_csv_source_families_missing")
    return {"schema": "envloop-office-transfer-ppt-preflight-public-v1",
            "status": "source_inputs_present_full_validation_pending" if not errors else "blocked",
            "active_v13_plan_sha256_matches": original_ok,
            "amendment_did_not_modify_original_anchors": True,
            "existing_calibration_cases_retained_as_calibration": 80,
            "expected_additional_train_source_families": 8,
            "new_source_dirs_present_unverified": source_dirs,
            "additional_train_specs_built": 0,
            "offline_controls_passed": 0,
            "office_web_gui_admitted": 0,
            "official_final_admitted": 0,
            "rights_tier": RIGHTS_WDI,
            "errors": errors}


def materialize_ppt_transfer(plan: dict, csv_root: Path, private_out: Path,
                             *, workers: int = 2) -> list[dict]:
    """Build editable decks and independent direct-file controls, never Office UI."""
    from tools.build_ppt_wdi_train_calibration_80_v1 import build_one

    require(plan.get("schema") == PPT_SCHEMA and len(plan.get("rows", [])) == 80 and
            1 <= workers <= 4 and
            private_out.resolve().is_relative_to((Path.cwd() / "work").resolve()),
            "private_ppt_plan_or_output_invalid")
    build_dir = private_out / "artifact-tool-transfer-build"
    build_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    builder = build_dir / "build_train_transfer_deck.mjs"
    source_builder = Path("ppt_wdi_factory/build_train_transfer_deck.mjs").resolve()
    shutil.copyfile(source_builder, builder)
    link = build_dir / "node_modules"
    if not link.exists():
        link.symlink_to(DEFAULT_MODULES, target_is_directory=True)
    require(link.samefile(DEFAULT_MODULES), "bundled_node_dependency_changed")
    csv_sources = {}
    for directory in sorted(path for path in csv_root.iterdir() if path.is_dir()):
        iso = directory.name
        provenance = json.loads((directory / "source-provenance.private.json").read_bytes())
        raw_snapshot = (directory / "source-snapshot.private.json").read_bytes()
        csv_sources[iso] = (facts_from_official_response(raw_snapshot), provenance,
                            (csv_root / f"{iso}-country.private.zip").read_bytes(),
                            raw_snapshot,
                            (directory / "source-provenance.private.json").read_bytes())
    require(set(csv_sources) == {row["source_group"] for row in plan["rows"]},
            "source_dir_differs_from_frozen_transfer_plan")
    env = {**os.environ, "NODE_OPTIONS": "--max-old-space-size=4096",
           "PRESENTATIONS_SKILL_DIR": str(DEFAULT_SKILL),
           "RUNTIME_PYTHON": str(DEFAULT_PYTHON),
           "RUNTIME_NODE": str(DEFAULT_NODE),
           "RUNTIME_NODE_MODULES": str(DEFAULT_MODULES)}
    finalizer = Path("ppt_wdi_factory/finalize_deck.mjs").resolve()
    tool_dir = DEFAULT_SKILL / "container_tools"
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(
            lambda row: build_one(private_out, row, csv_sources, builder,
                                  finalizer, env, tool_dir), plan["rows"]))
    require(len(results) == 80 and all(result["task_id"] for result in results),
            "ppt_transfer_offline_controls_incomplete")
    return results


def excel_transfer_screen(split_registry: dict | None,
                          skill_cards: dict | None,
                          case_pool: dict | None,
                          *, split_sha256: str | None = None) -> dict:
    """Require an evaluator-authored graph-to-skill map; names stay private.

    The aggregate 13-graph receipt cannot establish which causal dependencies
    a new workbook must exercise.  Missing cards therefore block admission.
    """
    errors: list[str] = []
    if split_registry is None or split_sha256 != EXCEL_SPLIT_SHA:
        errors.append("missing_or_changed_private_140_slot_registry")
        slots = []
    else:
        slots = split_registry.get("slots", [])
        counts = Counter(row.get("split") for row in slots)
        if len(slots) != 140 or counts != {"train": 20, "selection": 20,
                                           "final": 100}:
            errors.append("original_excel_20_20_100_anchors_changed")
    final_graphs = {row.get("semantic_template_reservation") for row in slots
                    if row.get("split") == "final"}
    if len(final_graphs) != 13 or None in final_graphs:
        errors.append("private_final_graph_count_not_13")
    cards = skill_cards.get("cards", []) if isinstance(skill_cards, dict) else []
    if not isinstance(skill_cards, dict) or skill_cards.get("schema") != EXCEL_SCHEMA or len(cards) != 13:
        errors.append("missing_private_graph_to_skill_mapping")
    card_by_graph = {}
    for card in cards:
        if not isinstance(card, dict):
            errors.append("invalid_skill_card")
            continue
        key = card.get("final_graph_reservation")
        atoms = card.get("causal_skill_atoms")
        edges = card.get("dependency_edges")
        signature = card.get("skill_signature_sha256")
        final_template_sha = card.get("final_template_sha256")
        if (not isinstance(key, str) or not isinstance(atoms, list) or
                len(atoms) < 2 or not all(isinstance(a, str) and a for a in atoms) or
                not isinstance(edges, list) or not edges or
                not all(isinstance(edge, list) and len(edge) == 2 and
                        all(isinstance(node, str) and node for node in edge)
                        for edge in edges) or
                not isinstance(signature, str) or not HEX64.fullmatch(signature) or
                not isinstance(final_template_sha, str) or
                not HEX64.fullmatch(final_template_sha) or
                not isinstance(card.get("minimum_target_edits"), int) or
                card["minimum_target_edits"] < 2 or
                card.get("independent_skill_review") is not True):
            errors.append("incomplete_or_unreviewed_graph_skill_card")
        elif signature != digest(ppt.canonical({"causal_skill_atoms": atoms,
                                                "dependency_edges": edges})):
            errors.append("graph_skill_signature_does_not_bind_dependencies")
        if key in card_by_graph:
            errors.append("duplicate_graph_skill_card")
        card_by_graph[key] = card
    if final_graphs != set(card_by_graph):
        errors.append("graph_to_skill_map_does_not_cover_exact_final_13")
    signatures = [card.get("skill_signature_sha256") for card in cards
                  if isinstance(card, dict)]
    if len(signatures) != len(set(signatures)):
        errors.append("distinct_final_graph_skills_collapsed_to_one_signature")
    cases = case_pool.get("cases", []) if isinstance(case_pool, dict) else []
    if not isinstance(case_pool, dict) or case_pool.get("schema") != EXCEL_CASE_SCHEMA:
        errors.append("missing_private_train_only_analogue_pool")
    counts = Counter(case.get("final_graph_reservation") for case in cases
                     if isinstance(case, dict))
    if len(cases) < 104 or set(counts) != final_graphs or any(counts[key] < 8 for key in final_graphs):
        errors.append("eight_train_analogues_per_final_graph_required")
    heldout_ciks = {row.get("issuer_cik") for row in slots}
    heldout_accessions = {row.get("original_filing_accession") for row in slots}
    heldout_templates = {row.get("semantic_template_reservation") for row in slots}
    case_ids: set[str] = set()
    sources: set[tuple] = set()
    templates: set[str] = set()
    source_hashes: set[str] = set()
    actor_hashes: set[str] = set()
    reference_hashes: set[str] = set()
    final_template_hashes = {card.get("final_template_sha256") for card in cards
                             if isinstance(card, dict)}
    per_graph_issuers: dict[str, set] = defaultdict(set)
    for case in cases:
        if not isinstance(case, dict):
            errors.append("invalid_analogue_case")
            continue
        graph = case.get("final_graph_reservation")
        card = card_by_graph.get(graph)
        issuer = case.get("issuer_cik")
        accession = case.get("original_filing_accession")
        template = case.get("train_template_family")
        case_id = case.get("analogue_id")
        if (not isinstance(case_id, str) or not case_id or case_id in case_ids or
                not isinstance(issuer, int) or issuer <= 0 or
                not isinstance(accession, str) or not ACCESSION.fullmatch(accession) or
                not isinstance(template, str) or not template):
            errors.append("missing_or_duplicate_analogue_identity_or_source")
        case_ids.add(case_id)
        if (issuer in heldout_ciks or accession in heldout_accessions or
                template in heldout_templates or
                case.get("train_template_sha256") in final_template_hashes):
            errors.append("train_source_or_template_overlaps_original_split")
        if (issuer, accession) in sources:
            errors.append("train_accession_reused_across_analogues")
        sources.add((issuer, accession))
        templates.add(template)
        per_graph_issuers[graph].add(issuer)
        if (card is None or case.get("skill_signature_sha256") !=
                card.get("skill_signature_sha256") or
                not isinstance(case.get("target_formula_edits"), int) or
                case["target_formula_edits"] < card.get("minimum_target_edits", 10**9)):
            errors.append("analogue_skill_or_target_depth_unverified")
        if (case.get("rights_tier") != RIGHTS_SEC or
                case.get("source_provenance_tier") !=
                "independently_verified_exact_facts" or
                case.get("independent_verifier_review") is not True):
            errors.append("rights_source_or_independent_review_missing")
        for check in ("positive_reference_pass", "near_miss_rejected",
                      "hardcode_rejected", "collateral_source_rejected",
                      "source_counterfactual_pass", "scenario_counterfactual_pass",
                      "fresh_reset_exact"):
            if case.get(check) is not True:
                errors.append("near_miss_no_regression_or_reset_control_missing")
        for field in ("source_excerpt_sha256", "train_template_sha256",
                      "actor_sha256", "reference_sha256", "verifier_sha256"):
            if not isinstance(case.get(field), str) or not HEX64.fullmatch(case[field]):
                errors.append("case_artifact_commitment_missing")
        for field, seen in (("source_excerpt_sha256", source_hashes),
                            ("actor_sha256", actor_hashes),
                            ("reference_sha256", reference_hashes)):
            if isinstance(case.get(field), str):
                if case[field] in seen:
                    errors.append("source_or_workbook_bytes_reused")
                seen.add(case[field])
    if any(len(per_graph_issuers[graph]) < 2 for graph in final_graphs):
        errors.append("two_train_issuer_families_per_graph_required")
    if len(templates) < 13:
        errors.append("distinct_train_template_families_missing")
    errors = sorted(set(errors))
    return {"schema": "envloop-office-transfer-excel-public-gate-v1",
            "status": "source_contract_complete_artifact_replay_pending" if not errors else "blocked",
            "original_20_20_100_anchors_unchanged": bool(slots) and
                "original_excel_20_20_100_anchors_changed" not in errors,
            "final_graphs_declared_in_private_registry": len(final_graphs),
            "independently_reviewed_skill_cards": len(cards),
            "train_only_analogues_submitted": len(cases),
            "graph_to_skill_contract_coverage": len(final_graphs) if not errors else 0,
            "source_issuer_overlap_count": len({c.get("issuer_cik") for c in cases
                                               if isinstance(c, dict)} & heldout_ciks),
            "source_accession_overlap_count": len({c.get("original_filing_accession") for c in cases
                                                  if isinstance(c, dict)} & heldout_accessions),
            "template_family_overlap_count": len(templates & heldout_templates),
            "rights_tier": RIGHTS_SEC,
            "errors": errors,
            "independently_replayed_saved_ooxml_controls": 0,
            "excel_web_gui_admitted": 0, "official_final_admitted": 0,
            "model_calls": 0}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="mode", required=True)
    excel = sub.add_parser("excel-screen")
    excel.add_argument("--private-split-registry", type=Path)
    excel.add_argument("--private-skill-cards", type=Path)
    excel.add_argument("--private-case-pool", type=Path)
    excel.add_argument("--public-out", type=Path, required=True)
    powerpoint = sub.add_parser("ppt-plan")
    powerpoint.add_argument("--official-csv-root", type=Path, required=True)
    powerpoint.add_argument("--original-v13-plan", type=Path, required=True)
    powerpoint.add_argument("--future-reserve-queue", type=Path, required=True)
    powerpoint.add_argument("--historical-plan-dir", type=Path, required=True)
    powerpoint.add_argument("--calibration-80-manifest", type=Path, required=True)
    powerpoint.add_argument("--private-out", type=Path, required=True)
    powerpoint.add_argument("--public-out", type=Path, required=True)
    powerpoint.add_argument("--materialize-offline", action="store_true")
    powerpoint.add_argument("--workers", type=int, default=2)
    preflight = sub.add_parser("ppt-preflight")
    preflight.add_argument("--original-v13-plan", type=Path, required=True)
    preflight.add_argument("--calibration-80-manifest", type=Path)
    preflight.add_argument("--official-csv-root", type=Path)
    preflight.add_argument("--public-out", type=Path, required=True)
    args = p.parse_args()
    if args.mode == "excel-screen":
        split = private_read(args.private_split_registry) if args.private_split_registry else None
        cards = private_read(args.private_skill_cards)[0] if args.private_skill_cards else None
        cases = private_read(args.private_case_pool)[0] if args.private_case_pool else None
        result = excel_transfer_screen(split[0] if split else None, cards, cases,
                                       split_sha256=digest(split[1]) if split else None)
        args.public_out.parent.mkdir(parents=True, exist_ok=True)
        args.public_out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"status": result["status"], "errors": result["errors"],
                          "official_final_admitted": 0}, sort_keys=True))
        raise SystemExit(0 if result["status"] != "blocked" else 1)
    if args.mode == "ppt-plan":
        private_out = args.private_out.resolve()
        require(private_out.is_relative_to((Path.cwd() / "work").resolve()) and
                not private_out.exists() and not args.public_out.exists(),
                "fresh_ignored_private_output_and_public_receipt_required")
        seed = secrets.token_bytes(32)
        plan = ppt_transfer_plan(seed, args.official_csv_root,
                                 args.original_v13_plan, args.original_v13_plan,
                                 args.future_reserve_queue,
                                 args.calibration_80_manifest,
                                 args.historical_plan_dir)
        private_out.mkdir(parents=True, mode=0o700)
        (private_out / "seed.private").write_bytes(seed)
        (private_out / "seed.private").chmod(0o600)
        raw = ppt.canonical(plan)
        (private_out / "manifest.private.json").write_bytes(raw)
        (private_out / "manifest.private.json").chmod(0o600)
        result = ppt_public_receipt(plan)
        if args.materialize_offline:
            rows = materialize_ppt_transfer(plan, args.official_csv_root,
                                            private_out, workers=args.workers)
            receipt = {"schema": "envloop-ppt-transfer-offline-controls-private-v1",
                       "plan_sha256": digest(raw),
                       "builder_sha256": digest(Path(
                           "ppt_wdi_factory/build_train_transfer_deck.mjs").read_bytes()),
                       "verifier_sha256": digest(Path(ppt_verify.__file__).read_bytes()),
                       "results": rows, "offline_controls_passed": 80,
                       "office_web_gui_admitted": 0}
            receipt_raw = ppt.canonical(receipt)
            (private_out / "offline-controls.private.json").write_bytes(receipt_raw)
            (private_out / "offline-controls.private.json").chmod(0o600)
            result.update({"status": "80_train_only_offline_controls_passed_not_gui_admitted",
                           "offline_control_passed": 80,
                           "private_offline_receipt_sha256": digest(receipt_raw)})
        args.public_out.parent.mkdir(parents=True, exist_ok=True)
        args.public_out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"status": result["status"], "analogue_specs": 80,
                          "offline_control_passed": result["offline_control_passed"],
                          "official_final_admitted": 0}, sort_keys=True))
    if args.mode == "ppt-preflight":
        result = ppt_source_preflight(args.original_v13_plan,
                                      args.calibration_80_manifest,
                                      args.official_csv_root)
        args.public_out.parent.mkdir(parents=True, exist_ok=True)
        args.public_out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"status": result["status"], "errors": result["errors"],
                          "official_final_admitted": 0}, sort_keys=True))
        raise SystemExit(0 if result["status"] != "blocked" else 1)


if __name__ == "__main__":
    main()
