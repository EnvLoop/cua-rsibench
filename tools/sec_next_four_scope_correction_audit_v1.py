"""Second-person readback of corrected SEC TRAIN XBRL dimension metadata.

The historical v3 and corrected v4b reviews remain immutable. This audit
first reruns the independent raw-source/value parser, then checks each new
dimension axis/member pair against the original inline XBRL context and
classifies every byte-level JSON change between the two private reviews.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from lxml import html

from . import sec_next_four_second_person_audit_v1 as original_audit


OLD_REVIEW_SHA256 = "657fb74cb1cef2e0130d570b319dcf7d1a054257fd8c8aa48a78506adf531d77"
NEW_REVIEW_SHA256 = "b8eb2d73511ff19f7b68aa2fae67e309e21d51d2ee4e317ad974f48d500fdf72"


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def need(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def classify_json_changes(old, new, path: tuple = ()) -> dict:
    """Only an added member list or a corrected member count may differ."""
    result = {"member_lists_added": 0, "dimension_counts_changed": 0,
              "direct_field_counts_changed": 0,
              "nested_component_counts_changed": 0}

    def walk(left, right, location):
        if isinstance(left, dict) and isinstance(right, dict):
            extra = set(right) - set(left)
            missing = set(left) - set(right)
            need(not missing and extra <= {"dimension_members"} and
                 (not extra or location[-1:] == ("context_period",)),
                 "unexpected_review_key_change")
            if "dimension_members" in extra:
                need(type(right["dimension_members"]) is list,
                     "new_dimension_members_not_list")
                result["member_lists_added"] += 1
            for key in left:
                if key == "dimension_member_count" and left[key] != right[key]:
                    need(type(left[key]) is int and type(right[key]) is int and
                         location[-1:] == ("context_period",),
                         "unexpected_dimension_count_change")
                    result["dimension_counts_changed"] += 1
                    bucket = ("nested_component_counts_changed" if
                              "components" in location else
                              "direct_field_counts_changed")
                    result[bucket] += 1
                else:
                    walk(left[key], right[key], location + (key,))
        elif isinstance(left, list) and isinstance(right, list):
            need(len(left) == len(right), "review_list_length_changed")
            for index, (a, b) in enumerate(zip(left, right)):
                walk(a, b, location + (index,))
        else:
            need(type(left) is type(right) and left == right,
                 "non_scope_review_value_changed")

    walk(old, new, path)
    return result


def original_members(context) -> list[dict]:
    """Read the actual lowercased HTML DOM, including the dimension axis."""
    result = []
    for node in context.xpath('.//*[contains(name(),"explicitmember")]'):
        axis = node.get("dimension")
        member = " ".join(" ".join(node.itertext()).split())
        need(bool(axis and member), "original_dimension_axis_or_member_missing")
        result.append({"axis": axis, "member": member})
    return result


def context_map_for_case(raw_root: Path, case: dict) -> dict[str, object]:
    source = case["source"]
    document = source["document"]
    directory = raw_root / f"source-{case['case_index']:02}"
    tree = html.fromstring((directory / document).read_bytes())
    contexts = tree.xpath('//*[name()="xbrli:context" and @id]')
    if not contexts:
        tree = html.fromstring((directory / "10k.html").read_bytes())
        contexts = tree.xpath('//*[name()="xbrli:context" and @id]')
    mapping = {node.get("id"): node for node in contexts}
    need(len(mapping) == len(contexts) and mapping,
         "original_xbrl_context_set_changed")
    return mapping


def field_contexts(case: dict):
    for period in case["periods"]:
        for field in period["fields"].values():
            if field.get("context_period") is not None:
                yield field
            for component in field.get("components", []):
                if component.get("context_period") is not None:
                    yield component


def audit(*, raw_root: Path, source_plan: Path, old_review: Path,
          new_review: Path) -> tuple[dict, dict]:
    old_raw, new_raw = old_review.read_bytes(), new_review.read_bytes()
    need(digest(old_raw) == OLD_REVIEW_SHA256 and
         digest(new_raw) == NEW_REVIEW_SHA256,
         "old_or_corrected_private_review_sha_changed")
    old, new = json.loads(old_raw), json.loads(new_raw)
    classified = classify_json_changes(old, new)
    need(classified == {
        "member_lists_added": 60,
        "dimension_counts_changed": 40,
        "direct_field_counts_changed": 32,
        "nested_component_counts_changed": 8,
    }, "correction_change_scope_not_exact")
    # This source-level audit does not import the author review builder.
    independent_private, independent_public = original_audit.audit(
        raw_root=raw_root, source_plan=source_plan,
        author_review=new_review)
    need(independent_public["numeric_and_presence_fields_compared"] == 64 and
         independent_public["mismatches"] == 0 and
         independent_public["bank_same_accession_companyfacts_checks"] == 20,
         "corrected_review_original_numeric_source_check_failed")
    checked = 0
    case_counts = []
    for case in new["cases"]:
        contexts = context_map_for_case(raw_root, case)
        count = 0
        for field in field_contexts(case):
            cid = field["context_ref"]
            need(cid in contexts, "corrected_context_reference_missing")
            actual = original_members(contexts[cid])
            recorded = field["context_period"]
            need(recorded.get("dimension_members") == actual and
                 recorded.get("dimension_member_count") == len(actual),
                 "corrected_dimension_members_differ_from_original_xbrl")
            count += 1
            checked += 1
        case_counts.append({"profile": case["profile"],
                            "context_entries_checked": count})
    need(checked == 60, "corrected_context_denominator_changed")
    private = {
        "schema": "envloop.sec_excel_train_next_four_scope_correction.private.v1",
        "status": "corrected_scope_metadata_independently_verified",
        "old_review_sha256": OLD_REVIEW_SHA256,
        "corrected_review_sha256": NEW_REVIEW_SHA256,
        "source_plan_sha256": independent_private["source_plan_sha256"],
        "independent_source_parser_sha256": digest(Path(
            original_audit.__file__).read_bytes()),
        "change_classification": classified,
        "case_context_counts": case_counts,
        "original_context_member_entries_checked": checked,
        "official_final_admissions": 0,
    }
    public = {
        "schema": "envloop.sec_excel_train_next_four_scope_correction.public.v1",
        "status": private["status"],
        "old_review_sha256": OLD_REVIEW_SHA256,
        "corrected_review_sha256": NEW_REVIEW_SHA256,
        "source_plan_sha256": private["source_plan_sha256"],
        "independent_source_parser_sha256":
            private["independent_source_parser_sha256"],
        "field_value_and_presence_mappings_rechecked": 64,
        "same_accession_bank_companyfacts_checks": 20,
        "dimension_member_lists_verified_from_original_xbrl": checked,
        "dimension_counts_corrected": classified["dimension_counts_changed"],
        "direct_field_dimension_counts_corrected":
            classified["direct_field_counts_changed"],
        "nested_reconciliation_dimension_counts_corrected":
            classified["nested_component_counts_changed"],
        "other_review_data_changes": 0,
        "remaining_source_mismatches": 0,
        "excel_web_gui_controls": 0,
        "model_calls": 0,
        "official_final_admissions": 0,
    }
    return private, public


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--source-plan", type=Path, required=True)
    parser.add_argument("--old-review", type=Path, required=True)
    parser.add_argument("--new-review", type=Path, required=True)
    parser.add_argument("--private-out", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    if args.private_out.exists() or args.public_out.exists():
        raise ValueError("Exclusive corrected-review audit outputs required")
    private, public = audit(
        raw_root=args.raw_root, source_plan=args.source_plan,
        old_review=args.old_review, new_review=args.new_review)
    private_sha = original_audit.write_new(args.private_out, private, public=False)
    public["private_correction_audit_sha256"] = private_sha
    public_sha = original_audit.write_new(args.public_out, public, public=True)
    print(json.dumps({"status": public["status"],
                      "public_sha256": public_sha,
                      "remaining_source_mismatches": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
