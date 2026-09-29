"""Independent read-only audit of Odoo v6 two-frame dispatch guards.

The auditor reopens every indexed PNG and durable intent. It does not call
the v6 adapter's acceptance function or drive a browser.
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
V6_PROFILE = "rfq-two-frame-final-dispatch-2026-09-29-v6"
TWO_OBSERVED = "two_frame_observed_confirmed"
TWO_ALTERNATE = "two_frame_alternate_confirmed"
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
    visible_ref = intent.get("visible_text_ref")
    need(type(visible_ref) is dict,
         "parse_audit_visible_controls_reference_missing")
    visible = json.loads(artifact(attempt, visible_ref))
    controls = intent.get("observation_controls")
    need(result.get("intent_sha256") ==
         sha256(candidates[0].read_bytes()).hexdigest() and
         result.get("contract_receipt") == contract and
         intent.get("task_id") == row["task_id"] and
         intent.get("task_binding_sha256") == row["package_sha256"] and
         intent.get("frame_sha256") == frame_sha and
         intent.get("normalized_action") == result.get("applied_action") and
         intent.get("dispatch_state") ==
         "intent_durable_before_gui_action" and
         type(controls) is list and
         controls == visible.get("controls") and
         visible.get("screenshot", {}).get("sha256") == frame_sha and
         len(controls) == contract.get("control_count") and
         len({item.get("ref") for item in controls
              if type(item) is dict}) == len(controls),
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
    final_samples = [s for s in samples if s.get("step") == index and
                     s.get("stage") == "parse_final" and
                     s.get("observed_frame_id_sha256") == frame_id_sha]
    classification = parse.get("classification")
    if classification == PARSE_EXACT:
        need(parse.get("sample_count") == 1 and
             final_samples == [] and
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
             len(final_samples) == 1 and
             final_samples[0].get("sample") == 6 and
             final_samples[0].get("classification") == PARSE_ALT and
             final_samples[0].get("observed_frame_sha256") == frame_sha and
             final_samples[0].get("sampled_frame_ref") ==
             parse.get("physical_frame_ref") and
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
    elif dispatch.get("classification") in (TWO_OBSERVED, TWO_ALTERNATE):
        first = artifact(attempt, dispatch["first_final_frame_ref"])
        second = artifact(attempt, dispatch["second_final_frame_ref"])
        action = intent["normalized_action"]
        controls = intent.get("observation_controls", [])
        before = dispatch.get("target_control_before")
        after = dispatch.get("target_control_after")
        need(dispatch.get("profile") == V6_PROFILE and
             dispatch.get("physical_frame_ref") ==
             dispatch.get("second_final_frame_ref") and
             physical == second == first and
             dispatch.get("target_control") == after and
             before == after and
             _target_guard(action, intent.get("observed_target_control"),
                           before, controls) and
             _target_guard(action, intent.get("observed_target_control"),
                           after, controls) and
             dispatch.get("pinned_pixel_coordinates") ==
             [[41, 419], [132, 419]] and
             type(dispatch.get("base_dispatch_samples")) is int and
             1 <= dispatch["base_dispatch_samples"] <= 6 and
             re.fullmatch(r"/odoo/purchase/[0-9]+",
                          urlsplit(intent["observed_url"]).path) is not None,
             "parse_audit_two_frame_target_url_or_refs_invalid")
        if dispatch["classification"] == TWO_OBSERVED:
            need(second == frame,
                 "parse_audit_two_frame_observed_not_exact")
        else:
            need(pixels.two_pixel_alternate(frame, second),
                 "parse_audit_two_frame_alternate_not_pinned")
    else:
        raise ParseAuditError("parse_audit_unknown_dispatch_classification")
    return {"step": index, "parse_classification": classification,
            "dispatch_classification": dispatch["classification"]}


def _audit_all_guard_samples(attempt: Path, trace: dict) -> None:
    """Account for every indexed physical capture, including stale retries.

    A successful action's receipt alone cannot prove that the saved trace did
    not also contain a third frame or an out-of-order parse/dispatch sample.
    This check deliberately reopens every PNG independently of the adapter.
    """
    actions = trace["actions"]
    rejections = trace.get("pre_intent_rejections")
    samples = trace["exact_return_guard_samples"]
    need(type(rejections) is list and type(samples) is list and samples,
         "parse_audit_guard_chain_missing")
    by_step: dict[int, list[dict]] = {step: [] for step in range(len(actions))}
    for ref in rejections:
        rejection = json.loads(artifact(attempt, ref))
        step = rejection.get("step")
        need(type(step) is int and step in by_step and
             rejection.get("phase") == actions[step].get("phase") and
             rejection.get("schema") ==
             "envloop-odoo-v066-pre-intent-frame-rejection-v1" and
             rejection.get("error_code") == "stale_frame" and
             rejection.get("pre_dispatch_intent_created") is False and
             rejection.get("gui_action_dispatched") is False and
             type(rejection.get("observation_attempt")) is int and
             type(rejection.get("frame_id_sha256")) is str and
             re.fullmatch(r"[0-9a-f]{64}",
                          rejection["frame_id_sha256"]) is not None,
             "parse_audit_rejection_identity_invalid")
        observed = artifact(attempt, rejection["observed_frame_ref"])
        artifact(attempt, rejection["assistant_action_ref"])
        if rejection.get("current_frame_ref") is not None:
            artifact(attempt, rejection["current_frame_ref"])
        rejection["_reference_path"] = ref["path"]
        rejection["_observed_sha256"] = sha256(observed).hexdigest()
        rejection["_observed_png"] = observed
        by_step[step].append(rejection)

    ordered: list[tuple[tuple[int, str, str], str, bytes, dict | None]] = []
    for step, item in enumerate(actions):
        rejected = by_step[step]
        need(len(rejected) <= 2 and
             [row["observation_attempt"] for row in rejected] ==
             list(range(len(rejected))),
             "parse_audit_rejection_attempt_order_invalid")
        for row in rejected:
            prefix = (f"step-{step:03d}" if row["observation_attempt"] == 0
                      else f"step-{step:03d}-resample-"
                           f"{row['observation_attempt']:02d}")
            need(row["_reference_path"] ==
                 f"actions/{prefix}-rejection.private.json",
                 "parse_audit_rejection_path_unbound")
            ordered.append(((step, row["frame_id_sha256"],
                             row["_observed_sha256"]), "rejected",
                            row["_observed_png"], None))
        candidates = list((attempt / "actions").glob(
            f"step-{step:03d}*-intent.private.json"))
        need(len(candidates) == 1,
             "parse_audit_successful_intent_not_unique")
        intent = json.loads(candidates[0].read_bytes())
        observed = artifact(attempt, item["frame"])
        prefix = (f"step-{step:03d}" if not rejected else
                  f"step-{step:03d}-resample-{len(rejected):02d}")
        need(intent.get("frame_ref") == item["frame"] and
             intent.get("frame_sha256") == sha256(observed).hexdigest() and
             type(intent.get("frame_id")) is str and
             candidates[0].name == prefix + "-intent.private.json" and
             intent.get("pre_intent_stale_resamples") == len(rejected),
             "parse_audit_successful_frame_or_retry_count_unbound")
        ordered.append(((step, sha256(intent["frame_id"].encode()).hexdigest(),
                         intent["frame_sha256"]), "successful", observed,
                        item["contract_receipt"]))
    keys = [row[0] for row in ordered]
    need(len(set(keys)) == len(keys),
         "parse_audit_observation_frame_identity_reused")
    positions = {key: position for position, key in enumerate(keys)}
    groups: dict[tuple[int, str, str], list[tuple[dict, bytes]]] = {
        key: [] for key in keys}
    prior_position = -1
    for index, sample in enumerate(samples):
        need(type(sample) is dict and type(sample.get("step")) is int and
             sample.get("stage") in (
                 "parse", "parse_final", "dispatch", "dispatch_final") and
             type(sample.get("sample")) is int and
             type(sample.get("observed_frame_id_sha256")) is str and
             type(sample.get("observed_frame_sha256")) is str and
             type(sample.get("sampled_frame_ref")) is dict and
             sample["sampled_frame_ref"].get("path") ==
             f"frames/guard-{index:04d}.png",
             "parse_audit_indexed_guard_sample_invalid")
        key = (sample["step"], sample["observed_frame_id_sha256"],
               sample["observed_frame_sha256"])
        need(key in groups and positions[key] >= prior_position,
             "parse_audit_guard_sample_or_order_unbound")
        prior_position = positions[key]
        groups[key].append((sample, artifact(attempt,
                                             sample["sampled_frame_ref"])))

    for key, kind, observed, contract in ordered:
        group = groups[key]
        if kind == "rejected":
            need(all(sample["stage"] in ("parse", "parse_final")
                     for sample, _ in group),
                 "parse_audit_rejected_observation_dispatched")
            parse = [(sample, raw) for sample, raw in group
                     if sample["stage"] == "parse"]
            final = [(sample, raw) for sample, raw in group
                     if sample["stage"] == "parse_final"]
            need(len(parse) <= 6 and
                 [sample["sample"] for sample, _ in parse] ==
                 list(range(len(parse))) and
                 all(sample["classification"] in (
                     "one_recurring_micro_raster_alternate",
                     "third_or_material_frame_rejected")
                     for sample, _ in parse) and
                 sum(sample["classification"] ==
                     "third_or_material_frame_rejected"
                     for sample, _ in parse) <= 1 and
                 (not parse or parse[-1][0]["classification"] ==
                  "third_or_material_frame_rejected" or
                  all(sample["classification"] ==
                      "one_recurring_micro_raster_alternate"
                      for sample, _ in parse)) and
                 (not final or
                  (len(parse) == 6 and len(final) == 1 and
                   group[-1] == final[0] and final[0][0]["sample"] == 6 and
                   final[0][0]["classification"] ==
                   "parse_final_rejected")),
                 "parse_audit_rejected_parse_sequence_invalid")
        else:
            parse = [(sample, raw) for sample, raw in group
                     if sample["stage"] == "parse"]
            final = [(sample, raw) for sample, raw in group
                     if sample["stage"] == "parse_final"]
            dispatch = [(sample, raw) for sample, raw in group
                        if sample["stage"] == "dispatch"]
            dispatch_final = [(sample, raw) for sample, raw in group
                              if sample["stage"] == "dispatch_final"]
            parse_receipt = contract["parse_guard"]
            dispatch_receipt = contract["physical_dispatch_guard"]
            if parse_receipt["classification"] == PARSE_EXACT:
                need(len(parse) == 1 and not final and
                     parse[0][0]["sample"] == 0 and
                     parse[0][0]["classification"] == "exact_return" and
                     parse[0][0]["sampled_frame_ref"] ==
                     parse_receipt["physical_frame_ref"],
                     "parse_audit_successful_exact_parse_sequence_invalid")
            else:
                need(len(parse) == 6 and len(final) == 1 and
                     [sample["sample"] for sample, _ in parse] ==
                     list(range(6)) and
                     all(sample["classification"] ==
                         "one_recurring_micro_raster_alternate"
                         for sample, _ in parse) and
                     final[0][0]["sample"] == 6 and
                     final[0][0]["classification"] == PARSE_ALT and
                     final[0][0]["sampled_frame_ref"] ==
                     parse_receipt["physical_frame_ref"],
                     "parse_audit_successful_alternate_parse_sequence_invalid")
            if dispatch_receipt["classification"] in (
                    TWO_OBSERVED, TWO_ALTERNATE):
                base_count = dispatch_receipt.get("base_dispatch_samples")
                need(type(base_count) is int and
                     1 <= base_count <= 6 and
                     len(dispatch) == base_count and
                     [sample["sample"] for sample, _ in dispatch] ==
                     list(range(base_count)) and
                     len(dispatch_final) == 2 and
                     [sample["sample"] for sample, _ in dispatch_final] ==
                     [base_count, base_count + 1] and
                     all(sample["classification"] ==
                         "one_recurring_micro_raster_alternate"
                         for sample, _ in dispatch[:-1]) and
                     dispatch[-1][0]["classification"] in (
                         "exact_return",
                         "one_recurring_micro_raster_alternate") and
                     (dispatch[-1][0]["classification"] ==
                      "exact_return" or base_count == 6) and
                     dispatch_final[0][0]["classification"] ==
                     ("two_frame_candidate_observed" if
                      dispatch_receipt["classification"] == TWO_OBSERVED else
                      "two_frame_candidate_alternate") and
                     dispatch_final[1][0]["classification"] ==
                     dispatch_receipt["classification"] and
                     dispatch_final[0][0]["sampled_frame_ref"] ==
                     dispatch_receipt["first_final_frame_ref"] and
                     dispatch_final[1][0]["sampled_frame_ref"] ==
                     dispatch_receipt["second_final_frame_ref"] and
                     dispatch_final[0][1] == dispatch_final[1][1],
                     "parse_audit_two_frame_dispatch_sequence_invalid")
                if dispatch_receipt["classification"] == TWO_ALTERNATE:
                    need(base_count == 6 and
                         all(sample["classification"] ==
                             "one_recurring_micro_raster_alternate"
                             for sample, _ in dispatch) and
                         dispatch_final[0][1] == dispatch[-1][1],
                         "parse_audit_alternate_not_proven_before_final")
            elif dispatch_receipt["classification"] == "exact_physical_frame":
                need(1 <= len(dispatch) <= 6 and
                     [sample["sample"] for sample, _ in dispatch] ==
                     list(range(len(dispatch))) and
                     all(sample["classification"] ==
                         "one_recurring_micro_raster_alternate"
                         for sample, _ in dispatch[:-1]) and
                     dispatch[-1][0]["classification"] == "exact_return",
                     "parse_audit_successful_exact_dispatch_sequence_invalid")
            else:
                need(len(dispatch) == 7 and
                     [sample["sample"] for sample, _ in dispatch] ==
                     list(range(7)) and
                     all(sample["classification"] ==
                         "one_recurring_micro_raster_alternate"
                         for sample, _ in dispatch[:-1]) and
                     dispatch[-1][0]["classification"] == PINNED,
                     "parse_audit_successful_pinned_dispatch_sequence_invalid")
            need(not dispatch_final or dispatch_receipt["classification"] in
                 (TWO_OBSERVED, TWO_ALTERNATE),
                 "parse_audit_unbound_dispatch_final_samples")
            need(dispatch[-1][0]["sampled_frame_ref"] ==
                 dispatch_receipt["physical_frame_ref"]
                 if not dispatch_final else
                 dispatch_final[-1][0]["sampled_frame_ref"] ==
                 dispatch_receipt["physical_frame_ref"],
                 "parse_audit_final_dispatch_reference_unbound")
            need(
                 [sample["stage"] for sample, _ in group] ==
                 (["parse"] * len(parse) + ["parse_final"] * len(final) +
                  ["dispatch"] * len(dispatch) +
                  ["dispatch_final"] * len(dispatch_final)),
                 "parse_audit_successful_guard_stage_or_receipt_unbound")
        alternate_sha = None
        for sample, raw in group:
            classification = sample["classification"]
            if classification == "exact_return":
                need(raw == observed, "parse_audit_exact_sample_png_changed")
            elif classification in (
                    "one_recurring_micro_raster_alternate", PARSE_ALT,
                    PINNED, "two_frame_candidate_alternate", TWO_ALTERNATE):
                need(pixels.two_pixel_alternate(observed, raw),
                     "parse_audit_alternate_sample_png_changed")
                current_sha = sha256(raw).hexdigest()
                need(alternate_sha is None or alternate_sha == current_sha,
                     "parse_audit_third_alternate_png_present")
                alternate_sha = current_sha
            elif classification in (
                    "two_frame_candidate_observed", TWO_OBSERVED):
                need(raw == observed,
                     "parse_audit_two_frame_observed_sample_changed")
            elif classification == "third_or_material_frame_rejected":
                need(kind == "rejected" and raw != observed and
                     not pixels.two_pixel_alternate(observed, raw),
                     "parse_audit_rejected_third_png_invalid")
            elif classification == "parse_final_rejected":
                need(kind == "rejected",
                     "parse_audit_rejected_sample_in_successful_action")
            else:
                raise ParseAuditError("parse_audit_guard_sample_class_unknown")


def audit_trace(attempt: Path, trace: dict, row: dict) -> dict:
    need(trace.get("task_binding_sha256") == row["task_binding_sha256"] and
         trace.get("sft_examples_written") == 0 and
         type(trace.get("actions")) is list and
         1 <= len(trace["actions"]) <= 90,
         "parse_audit_trace_holdout_boundary_invalid")
    rows = [audit_action(attempt, trace, row, index)
            for index in range(len(trace["actions"]))]
    _audit_all_guard_samples(attempt, trace)
    count = sum(row["parse_classification"] == PARSE_ALT for row in rows)
    two_frame = sum(row["dispatch_classification"] in
                    (TWO_OBSERVED, TWO_ALTERNATE) for row in rows)
    return {"status": "all_saved_parse_and_dispatch_guards_verified",
            "actions": len(rows),
            "pinned_border_parse_exceptions": count,
            "two_frame_dispatches": two_frame,
            "official_final_tasks_admitted": 0,
            "model_attempts": 0}


__all__ = ["audit_action", "audit_trace", "ParseAuditError"]
