"""Independent read-only audit of Odoo v5 parse and physical dispatch guards.

The auditor reopens saved PNGs and durable intents. It does not use the v5
adapter's acceptance function, drive a browser, or expose private task text.
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from tools import audit_odoo_v066_current_candidate_first_failure_20260929 as pixels
from tools import odoo_v066_scale_protocol_v1 as protocol


PARSE_PROFILE = "pinned-noninteractive-border-parse-and-dispatch-2026-09-29-v5"
PARSE_ALT = "pinned_border_parse_equivalence_accepted"
PARSE_EXACT = "exact_parse_frame"
PINNED = "pinned_border_equivalence_accepted"
PIXELS = {(41, 419), (132, 419)}


class ParseAuditError(ValueError):
    pass


def need(ok: bool, code: str) -> None:
    if not ok:
        raise ParseAuditError(code)


def artifact(attempt: Path, ref: dict) -> bytes:
    try:
        return pixels.ref_bytes(attempt, ref)
    except (ValueError, OSError) as error:
        raise ParseAuditError("parse_audit_artifact_reference_invalid") from error


def _target_guard(action: dict, before: dict, after: dict,
                  controls: list[dict]) -> bool:
    target = action.get("target")
    if (action.get("type") != "click" or type(target) is not dict or
            set(target) != {"x", "y"} or
            type(target["x"]) is not int or type(target["y"]) is not int or
            any(abs(target["x"] - x) <= 8 and
                abs(target["y"] - y) <= 8 for x, y in PIXELS) or
            type(before) is not dict or type(after) is not dict or
            before != after or after.get("visible") is not True or
            after.get("enabled") is not True or
            after.get("purchase_rfq_view") is not True):
        return False
    bounds = after.get("bounds")
    if (type(bounds) is not list or len(bounds) != 4 or
            not all(isinstance(value, (int, float)) for value in bounds) or
            not (bounds[0] <= target["x"] <= bounds[2] and
                 bounds[1] <= target["y"] <= bounds[3]) or
            any(bounds[0] - 8 <= x <= bounds[2] + 8 and
                bounds[1] - 8 <= y <= bounds[3] + 8 for x, y in PIXELS)):
        return False
    matching = [item for item in controls
                if type(item) is dict and
                all(item.get(key) == after.get(key)
                    for key in ("ref", "role", "label")) and
                item.get("visible") is True and
                item.get("enabled") is True]
    return len(matching) == 1


def audit_action(attempt: Path, trace: dict, row: dict,
                 index: int) -> dict:
    actions = trace.get("actions")
    samples = trace.get("exact_return_guard_samples")
    need(type(actions) is list and type(samples) is list and
         0 <= index < len(actions), "parse_audit_trace_or_index_invalid")
    item = actions[index]
    frame = artifact(attempt, item["frame"])
    frame_sha = sha256(frame).hexdigest()
    contract = item.get("contract_receipt")
    need(item.get("step") == index and
         item.get("phase") in ("positive", "negative") and
         type(contract) is dict and
         contract.get("screenshot", {}).get("sha256") == frame_sha and
         contract.get("task_binding_sha256") == row["package_sha256"] and
         contract.get("task_id_sha256") ==
         sha256(row["task_id"].encode()).hexdigest(),
         "parse_audit_action_contract_unbound")
    candidates = sorted((attempt / "actions").glob(
        f"step-{index:03d}*-intent.private.json"))
    results = sorted((attempt / "actions").glob(
        f"step-{index:03d}*-result.private.json"))
    need(len(candidates) == len(results) == 1,
         "parse_audit_intent_or_result_not_unique")
    intent = json.loads(candidates[0].read_bytes())
    result = json.loads(results[0].read_bytes())
    need(result.get("intent_sha256") ==
         sha256(candidates[0].read_bytes()).hexdigest() and
         result.get("contract_receipt") == contract and
         intent.get("task_id") == row["task_id"] and
         intent.get("task_binding_sha256") == row["package_sha256"] and
         intent.get("frame_sha256") == frame_sha and
         intent.get("normalized_action") == result.get("applied_action") and
         intent.get("dispatch_state") ==
         "intent_durable_before_gui_action",
         "parse_audit_durable_intent_or_result_unbound")
    parse = contract.get("parse_guard")
    dispatch = contract.get("physical_dispatch_guard")
    frame_id_sha = contract.get("frame_id_sha256")
    need(type(parse) is dict and type(dispatch) is dict and
         parse.get("profile") == PARSE_PROFILE and
         parse.get("observed_frame_sha256") == frame_sha and
         parse.get("observed_frame_id_sha256") == frame_id_sha and
         parse.get("observed_url") == intent.get("observed_url") and
         parse.get("physical_url") == intent.get("observed_url") and
         dispatch.get("observed_frame_sha256") == frame_sha and
         dispatch.get("observed_frame_id_sha256") == frame_id_sha and
         dispatch.get("observed_url") == intent.get("observed_url") and
         dispatch.get("physical_url") == intent.get("observed_url") and
         dispatch.get("target_point") ==
         intent.get("normalized_action", {}).get("target"),
         "parse_audit_guard_frame_url_or_action_unbound")
    parse_samples = [s for s in samples if s.get("step") == index and
                     s.get("stage") == "parse" and
                     s.get("observed_frame_id_sha256") == frame_id_sha]
    classification = parse.get("classification")
    if classification == PARSE_EXACT:
        need(parse.get("sample_count") == 1 and
             len(parse_samples) == 1 and
             parse_samples[0].get("classification") == "exact_return" and
             parse_samples[0].get("observed_frame_sha256") == frame_sha and
             artifact(attempt, parse_samples[0]["sampled_frame_ref"]) == frame and
             artifact(attempt, parse["physical_frame_ref"]) == frame,
             "parse_audit_exact_frame_guard_invalid")
    elif classification == PARSE_ALT:
        action = intent.get("normalized_action")
        controls = intent.get("observation_controls")
        target = parse.get("target_point")
        url = parse.get("physical_url")
        need(type(url) is str and
             re.fullmatch(r"/odoo/purchase/[0-9]+",
                          urlsplit(url).path) is not None and
             type(controls) is list and
             target == action.get("target") and
             parse.get("sample_count") == 6 and
             parse.get("pinned_pixel_coordinates") ==
             [[41, 419], [132, 419]] and
             parse.get("target_control_after") ==
             intent.get("observed_target_control") and
             _target_guard(action, parse.get("target_control_before"),
                           parse.get("target_control_after"), controls) and
             len(parse_samples) == 6 and
             [s.get("sample") for s in parse_samples] == list(range(6)) and
             all(s.get("classification") ==
                 "one_recurring_micro_raster_alternate" and
                 s.get("observed_frame_sha256") == frame_sha
                 for s in parse_samples),
             "parse_audit_alternate_route_control_or_samples_invalid")
        physicals = [artifact(attempt, s["sampled_frame_ref"])
                     for s in parse_samples]
        final = artifact(attempt, parse["physical_frame_ref"])
        need(len({sha256(raw).hexdigest() for raw in physicals}) == 1 and
             all(raw == final and pixels.two_pixel_alternate(frame, raw)
                 for raw in physicals),
             "parse_audit_alternate_physical_png_not_two_pixel_bound")
    else:
        raise ParseAuditError("parse_audit_unknown_parse_classification")
    physical = artifact(attempt, dispatch["physical_frame_ref"])
    if dispatch.get("classification") == "exact_physical_frame":
        need(physical == frame and
             dispatch.get("target_control") is None and
             dispatch.get("pinned_pixel_coordinates") == [],
             "parse_audit_exact_dispatch_invalid")
    elif dispatch.get("classification") == PINNED:
        need(pixels.two_pixel_alternate(frame, physical) and
             dispatch.get("pinned_pixel_coordinates") ==
             [[41, 419], [132, 419]] and
             _target_guard(intent["normalized_action"],
                           intent.get("observed_target_control"),
                           dispatch.get("target_control"),
                           intent.get("observation_controls", [])),
             "parse_audit_pinned_dispatch_invalid")
    else:
        raise ParseAuditError("parse_audit_unknown_dispatch_classification")
    return {"step": index, "parse_classification": classification,
            "dispatch_classification": dispatch["classification"]}


def audit_trace(attempt: Path, trace: dict, row: dict) -> dict:
    need(trace.get("task_binding_sha256") == row["task_binding_sha256"] and
         trace.get("sft_examples_written") == 0 and
         type(trace.get("actions")) is list and
         1 <= len(trace["actions"]) <= 90,
         "parse_audit_trace_holdout_boundary_invalid")
    rows = [audit_action(attempt, trace, row, index)
            for index in range(len(trace["actions"]))]
    count = sum(row["parse_classification"] == PARSE_ALT for row in rows)
    return {"status": "all_saved_parse_and_dispatch_guards_verified",
            "actions": len(rows),
            "pinned_border_parse_exceptions": count,
            "official_final_tasks_admitted": 0,
            "model_attempts": 0}


__all__ = ["audit_action", "audit_trace", "ParseAuditError"]
