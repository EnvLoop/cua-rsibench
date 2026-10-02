"""Read-only audit of a train-only original-Odoo attachment-route control."""

from __future__ import annotations

import argparse
from datetime import datetime
from hashlib import sha1
import json
from pathlib import Path
import re
import stat

from cursibench.scale_vision_proxy import Limits, image_from_bytes
from enterprise_fallback.odoo18 import verify
from enterprise_fallback.odoo18.odoo_v066_scale_exact_return_adapter import (
    _micro_raster_alternate,
)
from enterprise_fallback.odoo18.odoo_v066_train_attachment_route_adapter_v2 import (
    PROFILE,
)
from enterprise_fallback.odoo18.odoo_v066_train_attachment_route_adapter_v3 import (
    PROFILE as VIEWER_PROFILE,
)
from tools import odoo_v066_scale_protocol_v1 as protocol
from tools import odoo_v066_train_attachment_calibration_v6 as calibration
from tools import record_odoo_v066_train_gui_v1 as recorder


AUDIT_SCHEMA = "envloop-odoo-train-attachment-calibration-audit-v6"
REVIEW_SCHEMA = "envloop-odoo-train-attachment-independent-visual-review-v6"
HEX = re.compile(r"[0-9a-f]{64}\Z")


class CalibrationAuditError(ValueError):
    pass


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise CalibrationAuditError(reason)


def _private(path: Path, *, directory: bool = False) -> None:
    require(not path.is_symlink() and
            (path.is_dir() if directory else path.is_file()) and
            stat.S_IMODE(path.stat().st_mode) & 0o077 == 0,
            "audit_private_file_or_mode_invalid")


def _json(path: Path) -> dict:
    _private(path)
    require(path.stat().st_size <= 8_000_000,
            "audit_private_json_too_large")
    try:
        value = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise CalibrationAuditError("audit_json_invalid") from None
    require(type(value) is dict, "audit_json_invalid")
    return value


def _ref(out: Path, ref: dict, *, image: bool = False) -> tuple[Path, bytes]:
    require(type(ref) is dict and set(ref) == {"path", "sha256"} and
            type(ref["path"]) is str and
            type(ref["sha256"]) is str and
            HEX.fullmatch(ref["sha256"]) is not None,
            "audit_ref_invalid")
    relative = Path(ref["path"])
    require(not relative.is_absolute() and relative.parts and
            len(relative.parts) <= 2 and
            all(part not in (".", "..") for part in relative.parts),
            "audit_ref_path_unsafe")
    path = out / relative
    require(path.resolve().is_relative_to(out.resolve()),
            "audit_ref_path_unsafe")
    _private(path)
    if path.parent != out:
        _private(path.parent, directory=True)
    raw = path.read_bytes()
    require(protocol.digest(raw) == ref["sha256"],
            "audit_ref_bytes_changed")
    if image:
        try:
            _image, metadata = image_from_bytes(raw, Limits())
        except Exception:
            raise CalibrationAuditError("audit_png_invalid") from None
        require(metadata["format"] == "png" and
                (metadata["width"], metadata["height"]) == (1440, 1000),
                "audit_png_viewport_changed")
    return path, raw


def _artifact(out: Path, ref: dict) -> dict:
    _path, raw = _ref(out, ref)
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise CalibrationAuditError("audit_artifact_json_invalid") from None
    require(type(value) is dict, "audit_artifact_json_invalid")
    return value


def _time(raw: object) -> datetime:
    require(type(raw) is str, "audit_timestamp_invalid")
    try:
        value = datetime.fromisoformat(raw)
    except ValueError:
        raise CalibrationAuditError("audit_timestamp_invalid") from None
    require(value.tzinfo is not None, "audit_timestamp_invalid")
    return value


def _lease(path: Path, pid: int, start: datetime, finish: datetime) -> None:
    _private(path)
    rows = [json.loads(line) for line in path.read_bytes().splitlines()]
    operation = "v066_train_attachment_calibration"
    acquire = [i for i, row in enumerate(rows)
               if row.get("operation") == operation and
               row.get("event") == "acquired" and row.get("pid") == pid and
               _time(row.get("at_utc")) <= start]
    require(len(acquire) == 1, "audit_exclusive_train_lease_missing")
    releases = [row for row in rows[acquire[0] + 1:]
                if row.get("operation") == operation and
                row.get("event") == "released" and row.get("pid") == pid and
                _time(row.get("at_utc")) >= finish]
    require(len(releases) == 1, "audit_exclusive_train_lease_release_missing")
    require(not any(start <= _time(row.get("at_utc")) <= finish and
                    (row.get("pid") != pid or
                     row.get("operation") != operation)
                    for row in rows),
            "audit_overlapping_worker_lease")


def _score(task_id: str, gold: dict, baseline: dict, observed: dict,
           frozen: dict, physical: dict, paths: dict) -> dict:
    base = verify.evaluate(task_id, gold, baseline, observed)
    differences = list(base["difference_codes"])
    differences += verify.protected_source_file_differences(
        baseline, frozen, physical)
    differences += verify.protected_source_store_path_differences(
        baseline, paths)
    differences = sorted(set(differences))
    return {"reward": 0.0 if differences else 1.0,
            "difference_codes": differences}


def _require_full_post_web_manifest(frozen: dict, observed: dict) -> None:
    require(type(frozen) is dict and type(observed) is dict and
            observed == frozen,
            "audit_full_post_web_filestore_manifest_changed")


def _guard(out: Path, action: dict, intent: dict, result: dict,
           label: str, samples: list[dict]) -> tuple[set[str], int]:
    receipt = action["contract_receipt"]
    parse = receipt.get("attachment_parse_guard")
    dispatch = receipt.get("attachment_dispatch_guard")
    if parse is None and dispatch is None:
        return set(), 0
    require(type(parse) is dict and type(dispatch) is dict and
            action["phase"] == "positive" and
            receipt.get("action_type") == "click" and
            intent.get("normalized_action", {}).get("type") == "click" and
            parse.get("stage") == "parse" and
            dispatch.get("stage") == "dispatch" and
            parse.get("profile") == dispatch.get("profile") == PROFILE and
            parse.get("source_label_sha256") ==
            dispatch.get("source_label_sha256") ==
            protocol.digest(label.encode()) and
            parse.get("observed_frame_sha256") ==
            dispatch.get("observed_frame_sha256") ==
            action["frame"]["sha256"] and
            parse.get("observed_frame_id_sha256") ==
            dispatch.get("observed_frame_id_sha256") ==
            protocol.digest(intent["frame_id"].encode()) and
            parse.get("target_point") ==
            dispatch.get("target_point") ==
            intent["normalized_action"]["target"] and
            parse.get("target_identity") == dispatch.get("target_identity") and
            parse.get("target_identity") ==
            intent.get("observed_target_control") and
            parse["target_identity"].get("label") == label and
            parse.get("observed_url") == dispatch.get("observed_url") ==
            intent.get("observed_url") and
            re.search(r"/odoo/(purchase|sales|crm)/[0-9]+\Z",
                      intent["observed_url"]) is not None,
            "audit_attachment_guard_identity_or_route_invalid")
    frame = _ref(out, action["frame"], image=True)[1]
    refs = set()
    for item in (parse, dispatch):
        stage = item["stage"]
        classification = item.get("classification")
        require(classification in ("two_frame_observed_confirmed",
                                   "two_frame_alternate_confirmed"),
                "audit_attachment_guard_classification_invalid")
        first_ref, second_ref = (item.get("first_final_frame_ref"),
                                 item.get("second_final_frame_ref"))
        first_path, first = _ref(out, first_ref, image=True)
        second_path, second = _ref(out, second_ref, image=True)
        refs.update((str(first_path), str(second_path)))
        require(first == second and
                ((classification == "two_frame_observed_confirmed" and
                  first == frame) or
                 (classification == "two_frame_alternate_confirmed" and
                  _micro_raster_alternate(frame, first))),
                "audit_attachment_guard_physical_frames_invalid")
        require(type(item.get("base_sample_count")) is int and
                1 <= item["base_sample_count"] <= 6,
                "audit_attachment_guard_base_count_invalid")
        base_samples = [sample for sample in samples
                        if sample.get("step") == action["step"] and
                        sample.get("stage") == stage]
        finals = [sample for sample in samples
                  if sample.get("step") == action["step"] and
                  sample.get("stage") == stage + "_final"]
        require(len(base_samples) == item["base_sample_count"] and
                len(finals) == 2 and
                [sample.get("sample") for sample in base_samples] ==
                list(range(len(base_samples))) and
                [sample.get("sample") for sample in finals] ==
                [len(base_samples), len(base_samples) + 1] and
                finals[0].get("sampled_frame_ref") == first_ref and
                finals[1].get("sampled_frame_ref") == second_ref and
                finals[1].get("classification") == classification,
                "audit_attachment_guard_sample_sequence_invalid")
        base_raw = [_ref(out, sample["sampled_frame_ref"], image=True)[1]
                    for sample in base_samples]
        exact_return = base_samples[-1].get("classification") == "exact_return"
        prior = base_samples[:-1] if exact_return else base_samples
        require(not exact_return or base_raw[-1] == frame,
                "audit_attachment_exact_return_sample_invalid")
        if prior:
            require(len({protocol.digest(raw) for raw in base_raw[:len(prior)]}) == 1 and
                    _micro_raster_alternate(frame, base_raw[0]) and
                    all(sample.get("classification") ==
                        "one_recurring_micro_raster_alternate"
                        for sample in prior),
                    "audit_attachment_alternate_base_samples_invalid")
        require(exact_return or len(base_samples) == 6,
                "audit_attachment_base_no_exact_or_six_alternates")
        require(all(sample.get("observed_frame_sha256") ==
                    action["frame"]["sha256"] and
                    sample.get("observed_frame_id_sha256") ==
                    protocol.digest(intent["frame_id"].encode())
                    for sample in base_samples + finals),
                "audit_attachment_sample_frame_binding_invalid")
    require(result.get("contract_receipt") == receipt,
            "audit_attachment_guard_result_changed")
    return refs, 1


def _viewer_guard(out: Path, action: dict, intent: dict, result: dict,
                  label: str, samples: list[dict]) -> tuple[set[str], int]:
    receipt = action["contract_receipt"]
    parse = receipt.get("viewer_parse_guard")
    dispatch = receipt.get("viewer_dispatch_guard")
    returned = receipt.get("viewer_return_guard")
    if parse is None and dispatch is None and returned is None:
        return set(), 0
    target = intent.get("normalized_action", {}).get("target")
    frame_sha = action["frame"]["sha256"]
    frame_id_sha = protocol.digest(intent["frame_id"].encode())
    label_sha = protocol.digest(label.encode())
    require(type(parse) is dict and type(dispatch) is dict and
            type(returned) is dict and
            action["phase"] == "positive" and
            receipt.get("action_type") == "click" and
            intent.get("normalized_action", {}).get("type") == "click" and
            type(target) is dict and set(target) == {"x", "y"} and
            parse.get("stage") == "parse" and
            dispatch.get("stage") == "dispatch" and
            parse.get("profile") == dispatch.get("profile") ==
            returned.get("profile") == VIEWER_PROFILE and
            parse.get("classification") == dispatch.get("classification") ==
            "two_frame_observed_confirmed" and
            parse.get("source_label_sha256") ==
            dispatch.get("source_label_sha256") ==
            returned.get("source_label_sha256") == label_sha and
            parse.get("observed_frame_sha256") ==
            dispatch.get("observed_frame_sha256") == frame_sha and
            parse.get("observed_frame_id_sha256") ==
            dispatch.get("observed_frame_id_sha256") == frame_id_sha and
            parse.get("target_point") ==
            dispatch.get("target_point") == target and
            parse.get("observed_url") ==
            dispatch.get("observed_url") ==
            returned.get("returned_url") == intent.get("observed_url") and
            parse.get("physical_url") ==
            dispatch.get("physical_url") == intent.get("observed_url") and
            returned.get("task_binding_sha256") ==
            intent.get("task_binding_sha256") and
            returned.get("classification") ==
            "original_rfq_return_confirmed" and
            re.search(r"/odoo/purchase/[0-9]+\Z",
                      intent["observed_url"]) is not None,
            "audit_viewer_guard_binding_invalid")
    observed = parse.get("viewer_identity")
    require(type(observed) is dict and observed ==
            dispatch.get("viewer_identity") and
            observed.get("source_label") == label and
            observed.get("close_title") == "Close (Esc)" and
            type(observed.get("close_bounds")) is list and
            len(observed["close_bounds"]) == 4 and
            observed["close_bounds"][0] <= target["x"] <=
            observed["close_bounds"][2] and
            observed["close_bounds"][1] <= target["y"] <=
            observed["close_bounds"][3] and
            type(observed.get("iframe_bounds")) is list and
            len(observed["iframe_bounds"]) == 4 and
            type(observed.get("title_bounds")) is list and
            len(observed["title_bounds"]) == 4,
            "audit_viewer_observed_identity_invalid")
    observed_png = _ref(out, action["frame"], image=True)[1]
    refs = set()
    for item in (parse, dispatch):
        stage = item["stage"]
        require(item.get("base_sample_count") == 1,
                "audit_viewer_base_sample_count_invalid")
        base = [sample for sample in samples
                if sample.get("step") == action["step"] and
                sample.get("stage") == stage]
        finals = [sample for sample in samples
                  if sample.get("step") == action["step"] and
                  sample.get("stage") == stage + "_viewer_final"]
        require(len(base) == 1 and len(finals) == 2 and
                base[0].get("sample") == 0 and
                base[0].get("classification") == "exact_return" and
                [sample.get("sample") for sample in finals] == [1, 2] and
                [sample.get("classification") for sample in finals] ==
                    ["candidate_observed", "two_frame_observed_confirmed"] and
                finals[0].get("sampled_frame_ref") ==
                    item.get("first_final_frame_ref") and
                finals[1].get("sampled_frame_ref") ==
                    item.get("second_final_frame_ref"),
                "audit_viewer_physical_sample_sequence_invalid")
        for sample in base + finals:
            path, raw = _ref(out, sample["sampled_frame_ref"], image=True)
            refs.add(str(path))
            require(raw == observed_png and
                    sample.get("observed_frame_sha256") == frame_sha and
                    sample.get("observed_frame_id_sha256") == frame_id_sha,
                    "audit_viewer_physical_frame_changed")
    return_ref = returned.get("post_close_frame_ref")
    return_path, _return_png = _ref(out, return_ref, image=True)
    refs.add(str(return_path))
    return_rows = [sample for sample in samples
                   if sample.get("step") == action["step"] and
                   sample.get("stage") == "viewer_return"]
    require(len(return_rows) == 1 and
            return_rows[0].get("sample") == 0 and
            return_rows[0].get("classification") ==
            "original_rfq_return_confirmed" and
            return_rows[0].get("sampled_frame_ref") == return_ref and
            result.get("contract_receipt") == receipt,
            "audit_viewer_return_receipt_invalid")
    return refs, 1


def audit(*, worker_dir: Path, accepted_audit_path: Path,
          private_freeze_path: Path, public_freeze_path: Path,
          review_path: Path) -> dict:
    worker, private, freeze, case, _wrong = calibration._verify_freeze(
        worker_dir, accepted_audit_path, private_freeze_path,
        public_freeze_path)
    out = private / "v066_attachment_route_calibration" / calibration.RUN_NAME
    _private(out, directory=True)
    intent = _json(out / "intent.private.json")
    receipt_path = out / "attempt.private.json"
    receipt = _json(receipt_path)
    require(not (out / "failure.private.json").exists() and
            receipt.get("schema") == calibration.RECEIPT_SCHEMA and
            receipt.get("status") == "raw_train_only_control_review_pending" and
            receipt.get("split") == "train" and
            receipt.get("family") == "purchase" and
            receipt.get("task_id") == case["id"] and
            receipt.get("task_package_sha256") ==
            freeze["task_package_sha256"] and
            receipt.get("source_label") == f"{case['id']}-source.pdf" and
            receipt.get("private_freeze_sha256") ==
            protocol.digest(Path(private_freeze_path).read_bytes()) and
            receipt.get("run_nonce_sha256") ==
            protocol.digest(freeze["run_nonce"].encode()) and
            receipt.get("lease_operation") ==
            "v066_train_attachment_calibration" and
            receipt.get("service_state_restored_receipt") is True and
            receipt.get("selection_or_hidden_dispatch_authorized") is False and
            receipt.get("model_attempts") == 0 and
            receipt.get("official_final_tasks_admitted") == 0 and
            intent.get("schema") == calibration.SCHEMA and
            intent.get("status") ==
            "durable_before_first_docker_or_gui_action" and
            intent.get("run_nonce_sha256") ==
            protocol.digest(freeze["run_nonce"].encode()) and
            intent.get("task_package_sha256") ==
            freeze["task_package_sha256"],
            "audit_train_attempt_identity_invalid")
    start = _time(receipt["started_at_utc"])
    finish = _time(receipt["finished_at_utc"])
    stages = receipt.get("stage_timestamps")
    order = ("pre_restore", "source_observed", "positive_reload",
             "positive_sql", "negative_reload", "negative_sql",
             "post_restore")
    require(type(stages) is dict and set(stages) == set(order) and
            start <= _time(stages[order[0]]) and
            all(_time(stages[a]) <= _time(stages[b])
                for a, b in zip(order, order[1:])) and
            _time(stages[order[-1]]) <= finish,
            "audit_stage_order_invalid")
    _lease(private / "worker-lease-events.jsonl",
           receipt["worker_pid"], start, finish)
    refs = receipt.get("refs")
    names = {"db_readiness", "pre_restore", "baseline_sql", "source_frame",
             "positive_reload_frame", "positive_sql",
             "positive_filestore", "positive_store_paths",
             "negative_reload_frame", "negative_sql",
             "negative_filestore", "negative_store_paths",
             "post_restore", "restored_sql", "restored_filestore",
             "gui_trace"}
    require(type(refs) is dict and set(refs) == names,
            "audit_artifact_set_invalid")
    artifacts = {}
    for name, ref in refs.items():
        if name.endswith("frame"):
            _ref(out, ref, image=True)
        else:
            artifacts[name] = _artifact(out, ref)
    readiness = artifacts["db_readiness"]
    observations = readiness.get("observations")
    require(readiness.get("status") ==
            "postgres_health_and_select_1_ready" and
            readiness.get("query") == "SELECT 1" and
            type(readiness.get("probe_count")) is int and
            1 <= readiness["probe_count"] <= calibration.READINESS_MAX_PROBES and
            type(observations) is list and
            len(observations) == readiness["probe_count"] and
            observations[-1].get("services") == ["db"] and
            observations[-1].get("pg_isready_exit_code") == 0 and
            observations[-1].get("psql_exit_code") == 0,
            "audit_bounded_db_readiness_missing")
    baseline = _json(private / "baseline_snapshot.json")
    frozen = _json(private / "baseline-filestore-manifest.json")
    checkpoint = freeze["checkpoint"]
    require(artifacts["baseline_sql"] == baseline and
            artifacts["restored_sql"] == baseline and
            protocol.digest((private / "baseline_snapshot.json").read_bytes()) ==
            checkpoint["baseline_snapshot_sha256"] and
            protocol.digest((private / "baseline-filestore-manifest.json")
                            .read_bytes()) ==
            checkpoint["filestore_manifest_sha256"],
            "audit_baseline_or_restored_sql_changed")
    for stage in ("pre_restore", "post_restore"):
        reset = artifacts[stage]
        require(reset.get("status") == "restored" and
                reset.get("business_snapshot_equal") is True and
                reset.get("physical_filestore_equal_before_web_restart") is True and
                reset.get("db_sha256") == checkpoint["db_sha256"] and
                reset.get("filestore_sha256") == checkpoint["filestore_sha256"],
                "audit_full_cold_reset_not_exact")
    require(verify.protected_source_file_differences(
        baseline, frozen, artifacts["restored_filestore"]) == [],
        "audit_post_restart_source_changed")
    _require_full_post_web_manifest(frozen, artifacts["restored_filestore"])
    from enterprise_fallback.odoo18.partition_factory import source_asset
    world = _json(private / "partition_cases.json")
    source = source_asset(case, world)
    source_rows = [row for row in baseline["attachments"]
                   if row.get("name") == receipt["source_label"]]
    require(len(source_rows) == 1 and
            source_rows[0]["checksum"] == sha1(source).hexdigest() and
            source_rows[0]["file_size"] == len(source) and
            frozen.get("filestore/bench/" +
                       source_rows[0]["checksum"][:2] + "/" +
                       source_rows[0]["checksum"]) == protocol.digest(source),
            "audit_source_pdf_not_physically_bound")
    gold = _json(private / "development_gold.json")
    require(case["id"] in gold, "audit_train_gold_missing")
    baseline_paths = {
        str(row["id"]): row["checksum"][:2] + "/" + row["checksum"]
        for row in baseline["attachments"]}
    base = _score(case["id"], gold[case["id"]], baseline, baseline,
                  frozen, frozen, baseline_paths)
    positive = _score(case["id"], gold[case["id"]], baseline,
                      artifacts["positive_sql"], frozen,
                      artifacts["positive_filestore"],
                      artifacts["positive_store_paths"])
    negative = _score(case["id"], gold[case["id"]], baseline,
                      artifacts["negative_sql"], frozen,
                      artifacts["negative_filestore"],
                      artifacts["negative_store_paths"])
    require(base["reward"] == 0.0 and positive ==
            {"reward": 1.0, "difference_codes": []} and
            negative == {"reward": 0.0,
                         "difference_codes":
                         ["unrelated_order_line_changed"]} and
            artifacts["positive_sql"] != baseline and
            artifacts["negative_sql"] != artifacts["positive_sql"],
            "audit_independent_positive_or_wrong_object_failed")
    trace = artifacts["gui_trace"]
    actions = trace.get("actions")
    require(trace.get("schema") == recorder.GUI_SCHEMA and
            trace.get("task_binding_sha256") ==
            freeze["task_package_sha256"] and
            trace.get("sft_examples_written") == 0 and
            type(actions) is list and 2 <= len(actions) <= 90,
            "audit_gui_trace_invalid")
    link_count = 0
    viewer_count = 0
    referenced_guards = set()
    seen_negative = False
    for index, action in enumerate(actions):
        require(type(action) is dict and action.get("step") == index and
                action.get("phase") in ("positive", "negative"),
                "audit_gui_action_order_invalid")
        if action["phase"] == "negative":
            seen_negative = True
        else:
            require(not seen_negative, "audit_gui_positive_after_negative")
        frame = _ref(out, action["frame"], image=True)[1]
        matches = list((out / "actions").glob(
            f"step-{index:03d}*-intent.private.json"))
        require(len(matches) == 1, "audit_action_intent_missing_or_replayed")
        action_intent = _json(matches[0])
        result_path = matches[0].with_name(
            matches[0].name.replace("-intent.private.json",
                                      "-result.private.json"))
        result = _json(result_path)
        contract = action.get("contract_receipt")
        require(action_intent.get("phase") == action["phase"] and
                action_intent.get("step") == index and
                action_intent.get("task_id") == case["id"] and
                action_intent.get("task_binding_sha256") ==
                freeze["task_package_sha256"] and
                action_intent.get("frame_sha256") ==
                action["frame"]["sha256"] and
                result.get("intent_sha256") ==
                protocol.digest(matches[0].read_bytes()) and
                result.get("applied_action") ==
                action_intent.get("normalized_action") and
                result.get("contract_receipt") == contract and
                contract.get("task_binding_sha256") ==
                freeze["task_package_sha256"] and
                contract.get("screenshot", {}).get("sha256") ==
                protocol.digest(frame) and
                contract.get("error_code") is None,
                "audit_action_frame_intent_or_result_changed")
        guard_refs, count = _guard(out, action, action_intent, result,
                                   receipt["source_label"],
                                   trace.get("guard_samples", []))
        referenced_guards.update(guard_refs)
        link_count += count
        viewer_refs, count = _viewer_guard(
            out, action, action_intent, result,
            receipt["source_label"], trace.get("guard_samples", []))
        referenced_guards.update(viewer_refs)
        viewer_count += count
    require(seen_negative and link_count == 1 and viewer_count == 1 and
            sum(row["phase"] == "positive" for row in actions) > 0 and
            sum(row["phase"] == "negative" for row in actions) > 0,
            "audit_one_visible_link_or_dual_phase_missing")
    # Reopen every physical guard file, not only the two final ones.
    guard_samples = trace.get("guard_samples")
    require(type(guard_samples) is list and guard_samples,
            "audit_physical_guard_samples_missing")
    sample_paths = set()
    for sample in guard_samples:
        path, _raw = _ref(out, sample["sampled_frame_ref"], image=True)
        sample_paths.add(str(path))
    disk_paths = {str(path) for path in (out / "frames").glob("guard-*.png")}
    require(sample_paths == disk_paths and referenced_guards <= sample_paths,
            "audit_physical_guard_file_set_changed")
    review_file = Path(review_path)
    require(review_file.parent.resolve() == out.resolve(),
            "audit_visual_review_path_unsafe")
    review = _json(review_file)
    require(review.get("schema") == REVIEW_SCHEMA and
            review.get("decision") ==
            "source_visible_in_original_odoo_gui" and
            review.get("reviewer_role") ==
            "independent_visual_source_reviewer" and
            type(review.get("reviewer_id_sha256")) is str and
            HEX.fullmatch(review["reviewer_id_sha256"]) is not None and
            review.get("source_frame_sha256") ==
            refs["source_frame"]["sha256"] and
            review.get("source_asset_sha256") ==
            freeze["source_asset_sha256"] and
            review.get("source_label") == receipt["source_label"] and
            _time(review.get("reviewed_at_utc")) >= finish,
            "audit_independent_visual_review_missing")
    return {
        "schema": AUDIT_SCHEMA,
        "status": "train_only_original_gui_route_control_verified",
        "private_freeze_sha256":
            protocol.digest(Path(private_freeze_path).read_bytes()),
        "private_attempt_sha256": protocol.digest(receipt_path.read_bytes()),
        "independent_baseline_reward": base["reward"],
        "independent_positive_reward": positive["reward"],
        "independent_wrong_object_reward": negative["reward"],
        "source_attachment_physically_read_back": True,
        "bounded_db_readiness_verified": True,
        "full_pre_web_filestore_reset_exact": True,
        "full_post_web_filestore_manifest_exact": True,
        "protected_source_bytes_after_web_restart_equal": True,
        "native_attachment_link_dispatches_checked": link_count,
        "native_viewer_close_dispatches_checked": viewer_count,
        "physical_guard_pngs_checked": len(sample_paths),
        "model_attempts": 0, "official_final_tasks_admitted": 0,
        "selection_candidate_controls_qualified": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker-dir", type=Path, required=True)
    parser.add_argument("--accepted-audit", type=Path, required=True)
    parser.add_argument("--private-freeze", type=Path, required=True)
    parser.add_argument("--public-freeze", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    result = audit(
        worker_dir=args.worker_dir,
        accepted_audit_path=args.accepted_audit,
        private_freeze_path=args.private_freeze,
        public_freeze_path=args.public_freeze,
        review_path=args.review)
    protocol.write_new(args.public_out, result, private=False)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
