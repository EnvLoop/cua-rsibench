"""Reopen the real additive WDI source and metadata-only cohort replacement."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import stat

from . import factory as base, factory_v2 as factory
from . import v066_post_enter_source_intake_v9 as intake
from .train_transfer_analogues import _controls
from tools.build_ppt_wdi_reserve_replacement_v1 import facts_from_official_response
from tools.extract_wdi_country_csv_reserve_v1 import extract


def _private(path):
    intake.require(path.is_file() and not path.is_symlink() and
                   stat.S_IMODE(path.stat().st_mode)==0o600,"v9_private_evidence_mode_invalid")
    return path.read_bytes()


def audit(private_root: Path, *, write_controls: bool=False):
    receipt_raw=_private(private_root/"intake-receipt.private.json")
    receipt=json.loads(receipt_raw)
    priority_raw=_private(private_root/"priority.private.json")
    priority=json.loads(priority_raw)
    intake.require(receipt.get("schema")==intake.SCHEMA and receipt.get("status")=="one_official_source_four_new_packages_whole_family_replaced" and
                   receipt.get("priority_sha256")==base.digest(priority_raw) and
                   priority.get("source_boundary")==receipt.get("source_boundary") and
                   receipt.get("retired_roster_index")==12,
                   "v9_intake_receipt_or_priority_invalid")
    intake.check_boundary(receipt["source_boundary"])
    excluded=set(intake.wdi.COUNTRIES)
    for row in receipt["source_boundary"]:excluded.update(row["source_memberships"])
    eligible=[iso for iso in intake.PRIORITY if iso not in excluded]
    intake.require(priority.get("excluded_union")==sorted(excluded) and priority.get("eligible_priority_iso3")==eligible,
                   "v9_identity_only_priority_changed")
    chosen=receipt["source"]["iso3"]
    intake.require(chosen not in excluded and chosen in eligible and
                   [row["iso3"] for row in receipt["rejected_sources"]]+[chosen]==eligible[:len(receipt["rejected_sources"])+1],
                   "v9_reserve_not_first_complete_priority")
    for row in receipt["rejected_sources"]:
        raw=_private(private_root/"rejected"/(row["iso3"]+".zip"))
        intake.require(base.digest(raw)==row["zip_sha256"],"v9_rejected_zip_changed")
        try:extract(raw,row["iso3"])
        except ValueError as exc:intake.require(str(exc)==row["reason"],"v9_rejection_reason_changed")
        else:raise ValueError("v9_complete_source_was_rejected")
    source_root=private_root/"official-source"
    source_dir=source_root/chosen
    raw=_private(source_root/(chosen+"-country.private.zip"))
    snapshot=_private(source_dir/"source-snapshot.private.json")
    provenance_raw=_private(source_dir/"source-provenance.private.json")
    provenance=json.loads(provenance_raw)
    meta=json.loads(_private(source_dir/"response-metadata.private.json"))
    extracted,detail=extract(raw,chosen)
    intake.require(extracted==snapshot and base.digest(raw)==receipt["source"]["zip_sha256"]==provenance.get("zip_sha256")==meta.get("zip_sha256") and
                   base.digest(snapshot)==receipt["source"]["snapshot_sha256"]==provenance.get("snapshot_sha256") and
                   base.digest(provenance_raw)==receipt["provenance_sha256"] and
                   provenance.get("official_download_url")==meta.get("requested_url")==f"https://api.worldbank.org/v2/en/country/{chosen}?downloadformat=csv" and
                   provenance.get("catalog_license")=="CC BY 4.0" and
                   provenance.get("data_last_updated")==detail["data_last_updated"] and
                   provenance.get("retrieved_at_utc")==meta.get("retrieved_at_utc") and
                   detail["numeric_observation_count"]==30,
                   "v9_official_source_provenance_changed")
    original=Path(receipt["original_root"])
    old,old_raw=intake.checked_inventory(original)
    intake.require(base.digest(old_raw)==receipt["prior_inventory_sha256"],"v9_original_inventory_changed")
    final=sorted((row for row in old["tasks"] if row["split"]=="final_candidate"),key=lambda r:r["task_id"])
    group=final[12]["source_groups"]
    retired=[r for r in final if r["source_groups"]==group]
    intake.require(retired==receipt["retired_package_metadata"] and len(retired)==4 and
                   receipt["retired_source_groups"]==group,"v9_whole_family_retirement_changed")
    cohort=Path(receipt["cohort_root"])
    inventory_raw=_private(cohort/"candidate-inventory.json")
    inventory=json.loads(inventory_raw)
    intake.require(base.digest(inventory_raw)==receipt["revised_inventory_sha256"],"v9_revised_inventory_changed")
    intake.check_splits(inventory)
    retained=[r for r in old["tasks"] if r not in retired]
    replacements=receipt["replacements"]
    intake.require(len(retained)==136 and len(replacements)==4 and inventory["tasks"]==[*retained,*replacements] and
                   {row["workflow"] for row in replacements}==set(base.WORKFLOWS) and
                   all(row["source_groups"]==[f"wdi-country:{chosen}"] for row in replacements) and
                   not set(row["task_id"] for row in retired)&{row["task_id"] for row in inventory["tasks"]},
                   "v9_exact_136_plus_four_projection_changed")
    for row in retained:
        before=original/row["split"]/row["task_id"]
        after=cohort/row["split"]/row["task_id"]
        expected=receipt["retained_package_trees"][row["task_id"]]
        intake.require({str(p.relative_to(after)):base.digest(_private(p)) for p in after.rglob("*") if p.is_file()}==expected and
                       {str(p.relative_to(before)):base.digest(p.read_bytes()) for p in before.rglob("*") if p.is_file()}==expected,
                       "v9_retained_sealed_package_bytes_changed")
    mapping_raw=_private(private_root/"private-map.private.json")
    mapping=json.loads(mapping_raw)
    intake.require(base.digest(mapping_raw)==receipt["new_private_map_sha256"]==inventory["private_map_sha256"],
                   "v9_new_private_map_changed")
    controls=[]
    facts=facts_from_official_response(snapshot)
    for row in replacements:
        directory=cohort/"final_candidate"/row["task_id"]
        # Only newly authored reserve oracles are parsed. All old ones above
        # remain sealed and are merely copied/rehashed.
        oracle_raw=_private(directory/"oracle.json")
        oracle=json.loads(oracle_raw)
        instruction=_private(directory/"actor_task.txt")
        suffix=".xlsx" if row["workflow"].startswith("calc-") else ".pptx" if row["workflow"]=="impress-deck" else ".docx"
        inputs=list(directory.glob("*"+suffix))
        intake.require(len(inputs)==1,"v9_one_reserve_input_required")
        baseline=_private(inputs[0])
        intake.require(base.digest(baseline)==row["input_sha256"]==oracle["input_sha256"] and
                       base.digest(oracle_raw)==row["oracle_sha256"] and base.digest(instruction)==row["actor_task_sha256"] and
                       row["package_sha256"]==base.digest(base.json_bytes({k:v for k,v in row.items() if k!="package_sha256"})) and
                       json.loads(_private(directory/"package.json"))==row and
                       oracle.get("country_iso3")==facts["iso3"] and oracle.get("source_sha256")==base.digest(snapshot) and
                       oracle.get("edits")==3 and len(oracle["targets"])==3 and
                       row["template_group"]==factory.TEMPLATES["final_candidate"][row["workflow"]] and
                       b"CC BY 4.0" in instruction,
                       "v9_new_reserve_package_source_or_target_shape_changed")
        results,outputs=_controls(baseline,oracle,mapping["variant_salt"])
        if write_controls:
            for polarity,saved in outputs.items():
                intake.private_write(private_root/"offline-controls"/row["task_id"]/(polarity+suffix),saved)
        controls.append({"package_sha256":row["package_sha256"],"workflow":row["workflow"],
                         "positive_passed":results["positive"]["passed"],
                         "near_miss_rejected":not results["near_miss"]["passed"],
                         "unrelated_change_rejected":not results["unrelated_change"]["passed"]})
    return {"schema":"cua-native-wdi-whole-family-source-independent-audit-public-v9",
            "status":"one_real_official_source_four_packages_reopened_new_20_20_100_cohort",
            "private_intake_receipt_sha256":base.digest(receipt_raw),"priority_sha256":base.digest(priority_raw),
            "new_inventory_sha256":base.digest(inventory_raw),"original_inventory_sha256":base.digest(old_raw),
            "source_zip_sha256":base.digest(raw),"source_snapshot_sha256":base.digest(snapshot),
            "source_provenance_sha256":base.digest(provenance_raw),"source_license":"CC BY 4.0",
            "official_country_csv_zips_reopened":1,"numeric_observations_reopened":30,
            "source_boundary_metadata_files_checked":len(receipt["source_boundary"]),
            "source_collision_count_against_frozen_boundary":0,"whole_retired_source_families":1,"retired_task_packages":4,
            "replacement_task_packages":4,"retained_packages_byte_identical":136,
            "counts":{"train":20,"selection":20,"final_candidate":100},
            "source_family_counts":{"train":5,"selection":5,"final_candidate":25},
            "offline_positive_artifact_controls_passed":sum(r["positive_passed"] for r in controls),
            "offline_target_near_miss_controls_rejected":sum(r["near_miss_rejected"] for r in controls),
            "offline_unrelated_change_controls_rejected":sum(r["unrelated_change_rejected"] for r in controls),
            "old_selection_final_oracle_content_inspected":False,"new_reserve_oracles_authored_by_trusted_evaluator":True,
            "historical_controls_carried_into_new_epoch":0,"native_controls_qualified":0,"official_final_admissions":0,"model_calls":0}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--private-root",type=Path,required=True);p.add_argument("--public-out",type=Path,required=True)
    p.add_argument("--write-offline-controls",action="store_true");a=p.parse_args()
    value=audit(a.private_root,write_controls=a.write_offline_controls)
    a.public_out.parent.mkdir(parents=True,exist_ok=True)
    fd=__import__("os").open(a.public_out,__import__("os").O_WRONLY|__import__("os").O_CREAT|__import__("os").O_EXCL,0o644)
    with __import__("os").fdopen(fd,"wb") as stream:stream.write(base.json_bytes(value))
    print(json.dumps(value,sort_keys=True))


if __name__=="__main__":main()
