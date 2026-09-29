"""Independent offline audit of prospective Odoo selection reserve packages.

This auditor does not import the generator or connect to Odoo. The saved-state
controls here are synthetic logic checks, not native-GUI admission evidence.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
from pathlib import Path

from pypdf import PdfReader


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(path: Path) -> object:
    return json.loads(path.read_text())


def saved_state_score(case: dict, baseline: dict, observed: dict) -> dict[str, bool]:
    """Read-only logical scorer over saved state; all non-target bytes protected."""
    target_id = case["id"]
    if set(observed.get("orders", {})) != set(baseline["orders"]):
        return {"target_exact": False, "protected_exact": False, "source_exact": False}
    actual = observed["orders"][target_id]
    original = baseline["orders"][target_id]
    expected_target = copy.deepcopy(original)
    index = case["target_line_index"]
    expected_target["lines"][index]["qty"] = case["lines"][index]["expected"]["qty"]
    expected_target["lines"][index]["price"] = case["lines"][index]["expected"]["price"]
    protected = (all(observed["orders"][key] == value for key, value in baseline["orders"].items()
                     if key != target_id)
                 and all(actual[key] == original[key] for key in original if key != "lines")
                 and all(actual["lines"][position] == line
                         for position, line in enumerate(original["lines"]) if position != index)
                 and all(actual["lines"][index].get(key) == original["lines"][index].get(key)
                         for key in ("sku", "date")))
    return {"target_exact": actual == expected_target,
            "protected_exact": protected,
            "source_exact": actual.get("attachment_sha256") == case["source_sha256"]}


def _source_visible(case: dict, pdf: bytes) -> dict:
    reader = PdfReader(io.BytesIO(pdf))
    if len(reader.pages) != 1:
        raise ValueError("Source PDF must be one page")
    text = reader.pages[0].extract_text()
    line = case["lines"][case["target_line_index"]]
    expected = line["expected"]
    required = (
        case["source_title"], f"Authorized RFQ: {case['id']}",
        f"Supplier account: {case['vendor']}",
        f"Record status: {case['authority_token'].upper()}",
        f"Line SKU: {line['sku']}",
        f"{case['quantity_label']}: {expected['qty']}",
        f"{case['price_label']} (USD): {expected['price']:.2f}",
        *(item["sku"] for item in case["lines"]),
    )
    if any(item not in text for item in required):
        raise ValueError("Source PDF does not visibly support private oracle")
    if "SUPPLIER CONFIRMATION" in text:
        raise ValueError("Retired source layout was reused")
    return {"one_page": True, "source_facts_visible": True,
            "retired_heading_absent": True}


def _case_structure(case: dict) -> None:
    if case["family"] != "purchase" or case["partition"] != "selection":
        raise ValueError("Replacement left the frozen purchase selection workflow")
    if len(case["lines"]) != 3 or case["target_line_index"] not in range(3):
        raise ValueError("Replacement task depth differs from retired selection")
    if not case["id"].startswith("ELPO-RSV-") or not case["decoy"]["id"].endswith("-NEAR"):
        raise ValueError("Reserve identity or wrong-object negative missing")
    faults = []
    for position, line in enumerate(case["lines"]):
        if line["initial"]["date"] != line["expected"]["date"]:
            raise ValueError("Promised date is not protected")
        for field in ("qty", "price"):
            if line["initial"][field] != line["expected"][field]:
                faults.append((position, field))
    if set(faults) != {(case["target_line_index"], "qty"),
                       (case["target_line_index"], "price")}:
        raise ValueError("Replacement does not have exactly two same-line edits")
    if len(case["decoy"]["lines"]) != 3 or case["decoy"]["vendor"] != case["vendor"]:
        raise ValueError("Nearby wrong RFQ is not comparable")


def _split_disjoint(cases: list[dict], inventory: dict, manifest: dict,
                    train_world: dict, selection_world: dict) -> dict:
    if tuple(len(manifest[part]) for part in ("train", "selection", "official")) != (20, 20, 100):
        raise ValueError("Original split denominator changed")
    if inventory["status"] != "not_admitted" or inventory["prospective_count"] != 20:
        raise ValueError("Prospective inventory incorrectly treated as admitted")
    if len(inventory["retained_selection"]) != 15 or len(inventory["new_selection"]) != 5:
        raise ValueError("Replacement changed declared selection count")
    existing = [row for part in ("train", "selection", "official") for row in manifest[part]]
    fields = ("task_id", "package_sha256", "template_group", "instance_group")
    for field in fields:
        prior = {row[field] for row in existing}
        new = [row[field] for row in inventory["new_selection"]]
        if len(new) != len(set(new)) or prior.intersection(new):
            raise ValueError(f"Existing/new {field} overlap")
    prior_sources = {group for row in existing for group in row["source_groups"]}
    new_sources = [group for row in inventory["new_selection"] for group in row["source_groups"]]
    if len(new_sources) != len(set(new_sources)) or prior_sources.intersection(new_sources):
        raise ValueError("Existing/new source group overlap")
    original_entities = set()
    for world in (train_world, selection_world):
        original_entities.update(world["vendors"])
        original_entities.update(world["customers"])
        original_entities.update(item["sku"] for item in world["products"])
        original_entities.update(world["salespeople"])
    new_entities = [case["vendor"] for case in cases]
    new_entities += [line["sku"] for case in cases for line in case["lines"]]
    new_entities += [case["decoy"]["id"] for case in cases]
    if len(new_entities) != len(set(new_entities)) or original_entities.intersection(new_entities):
        raise ValueError("Development entity overlap")
    if any(not entity.startswith("EL-RSV-") for entity in new_entities[5:20]):
        raise ValueError("Reserve SKU namespace not isolated")
    retained = [row for row in manifest["selection"]
                if row["task_id"] not in set(inventory["retired_ids_in_order"])]
    if inventory["retained_selection"] != retained:
        raise ValueError("Retained selection identities changed")
    return {"existing_task_id_overlap": 0, "existing_package_overlap": 0,
            "existing_source_group_overlap": 0, "existing_template_group_overlap": 0,
            "existing_instance_group_overlap": 0, "development_entity_overlap": 0,
            "official_hidden_gold_read": False}


def audit(*, manifest_path: Path, correlation_path: Path,
          train_world_path: Path, selection_world_path: Path,
          generator_path: Path, private_freeze_path: Path,
          public_freeze_path: Path, cohort_dir: Path) -> dict:
    public = load(public_freeze_path)
    private = load(private_freeze_path)
    input_paths = {"task_manifest": manifest_path, "retirement_audit": correlation_path,
                   "train_world": train_world_path, "selection_world": selection_world_path}
    if {name: digest(path.read_bytes()) for name, path in input_paths.items()} != public["input_sha256"]:
        raise ValueError("Frozen input drift")
    if digest(generator_path.read_bytes()) != public["generator_sha256"]:
        raise ValueError("Frozen generator drift")
    if digest(private["seed"].encode()) != public["seed_sha256"]:
        raise ValueError("Private seed no longer matches public commitment")
    if digest(canonical(public)) != private["public_freeze_sha256"]:
        raise ValueError("Private/public freeze mismatch")
    manifest = load(manifest_path)
    correlation = load(correlation_path)
    if [row["task_id"] for row in correlation["case_identities"]] != private["retired_ids_in_order"]:
        raise ValueError("Retirement identity order drift")
    cases = load(cohort_dir / "cases.private.json")
    baseline = load(cohort_dir / "baseline-state.private.json")
    inventory = load(cohort_dir / "prospective-inventory.private.json")
    material = load(cohort_dir / "materialization.private.json")
    if len(cases) != 5 or len(set(case["source_kind"] for case in cases)) != 5:
        raise ValueError("Reserve count or source-template diversity changed")
    if [case["reserve_slot"] for case in cases] != [1, 2, 3, 4, 5]:
        raise ValueError("Frozen slot order changed")
    if inventory["campaign_dispatch_authorized"] or inventory["model_selection_authorized"]:
        raise ValueError("Unadmitted reserve authorized a campaign")
    inventory = dict(inventory, retired_ids_in_order=private["retired_ids_in_order"])
    disjoint = _split_disjoint(cases, inventory, manifest,
                               load(train_world_path), load(selection_world_path))
    if material["cohort_count"] != 5 or material["source_pdf_count"] != 5:
        raise ValueError("Materialization receipt count mismatch")
    if material["public_freeze_sha256"] != digest(public_freeze_path.read_bytes()):
        raise ValueError("Materialization did not bind frozen public receipt")
    if len(baseline["orders"]) != 10:
        raise ValueError("Five target and five wrong-object RFQs required")
    controls = []
    for slot, case in enumerate(cases, 1):
        _case_structure(case)
        private_case = load(cohort_dir / f"slot-{slot:02d}" / "case.private.json")
        if private_case != case:
            raise ValueError("Aggregate and slot private cases differ")
        pdf = (cohort_dir / f"slot-{slot:02d}" / case["source_filename"]).read_bytes()
        source = _source_visible(case, pdf)
        if digest(pdf) != case["source_sha256"]:
            raise ValueError("Source PDF hash mismatch")
        if digest(canonical({k: v for k, v in case.items() if k != "package_sha256"})
                  + b"\n" + pdf) != case["package_sha256"]:
            raise ValueError("Candidate package hash mismatch")
        if material["case_package_sha256"][slot - 1] != case["package_sha256"]:
            raise ValueError("Private materialization package commitment mismatch")
        if inventory["new_selection"][slot - 1]["task_id"] != case["id"]:
            raise ValueError("Prospective inventory slot mismatch")
        expected_row = {"task_id": case["id"], "package_sha256": case["package_sha256"],
                        "source_groups": [f"odoo-source-{case['source_sha256']}"],
                        "template_group": case["template_group"],
                        "instance_group": case["instance_group"]}
        if inventory["new_selection"][slot - 1] != expected_row:
            raise ValueError("Prospective inventory package commitment mismatch")
        target = baseline["orders"][case["id"]]
        if target["attachment_sha256"] != case["source_sha256"]:
            raise ValueError("Baseline source commitment missing")
        for line, original in zip(case["lines"], target["lines"]):
            if original != {"sku": line["sku"], **line["initial"]}:
                raise ValueError("Synthetic saved baseline does not match case")
        decoy = baseline["orders"][case["decoy"]["id"]]
        expected_decoy = {"vendor": case["decoy"]["vendor"], "state": "draft",
                          "attachment_sha256": None,
                          "lines": [{"sku": line["sku"], **line["initial"]}
                                    for line in case["decoy"]["lines"]]}
        if decoy != expected_decoy:
            raise ValueError("Nearby wrong-object baseline differs from source package")
        positive = copy.deepcopy(baseline)
        idx = case["target_line_index"]
        target_line = positive["orders"][case["id"]]["lines"][idx]
        target_line["qty"] = case["lines"][idx]["expected"]["qty"]
        target_line["price"] = case["lines"][idx]["expected"]["price"]
        positive_score = saved_state_score(case, baseline, positive)
        wrong = copy.deepcopy(positive)
        wrong["orders"][case["decoy"]["id"]]["lines"][0]["qty"] += 1
        wrong_score = saved_state_score(case, baseline, wrong)
        partial = copy.deepcopy(positive)
        partial["orders"][case["id"]]["lines"][idx]["price"] = (
            case["lines"][idx]["initial"]["price"])
        partial_score = saved_state_score(case, baseline, partial)
        reset = copy.deepcopy(baseline)
        if positive_score != {"target_exact": True, "protected_exact": True,
                              "source_exact": True}:
            raise ValueError("Saved-state positive rejected")
        if wrong_score["protected_exact"] or partial_score["target_exact"]:
            raise ValueError("Offline negative escaped verifier")
        if reset != baseline or saved_state_score(case, baseline, reset)["target_exact"]:
            raise ValueError("Offline reset/baseline control failed")
        controls.append({"slot": slot, **source,
                         "positive_accept": True, "wrong_object_reject": True,
                         "partial_reject": True, "reset_exact": True,
                         "source_sha256": case["source_sha256"],
                         "package_sha256": case["package_sha256"]})
    return {
        "schema": "envloop-odoo-selection-reserve-v1-independent-offline-audit",
        "as_of_date": "2026-09-29",
        "status": "five_prospective_offline_packages_checked_not_gui_admitted",
        "public_freeze_sha256": digest(public_freeze_path.read_bytes()),
        "generator_sha256": public["generator_sha256"],
        "cohort_count": 5, "selection_denominator_unchanged": 20,
        "source_documents_checked": 5,
        "offline_positive_controls": 5,
        "offline_wrong_object_negative_controls": 5,
        "offline_partial_negative_controls": 5,
        "offline_reset_controls": 5,
        "disjointness": disjoint,
        "slots": controls,
        "native_gui_controls": 0, "independent_saved_sql_controls": 0,
        "physical_filestore_controls": 0,
        "selection_admissions": 0, "model_attempts": 0,
        "official_final_admissions": 0,
        "hidden_gold_read": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("manifest", "correlation", "train-world", "selection-world",
                "generator", "private-freeze", "public-freeze", "cohort-dir", "public-out"):
        parser.add_argument("--" + arg, type=Path, required=True)
    args = parser.parse_args()
    report = audit(manifest_path=args.manifest, correlation_path=args.correlation,
                   train_world_path=args.train_world, selection_world_path=args.selection_world,
                   generator_path=args.generator, private_freeze_path=args.private_freeze,
                   public_freeze_path=args.public_freeze, cohort_dir=args.cohort_dir)
    if args.public_out.exists():
        raise FileExistsError("Independent audit report already exists")
    args.public_out.parent.mkdir(parents=True, exist_ok=True)
    args.public_out.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "cohort_count": report["cohort_count"]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
