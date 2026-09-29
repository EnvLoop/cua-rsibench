"""Read-only audit of the first preserved current-candidate Odoo GUI failure.

This auditor does not modify the frozen evaluator, replay an action, or start
Odoo. Its public projection excludes task IDs, instructions, source content,
credentials, and the private run nonce.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path

from PIL import Image, ImageChops

from tools import audit_odoo_v066_current_candidate_no_gui_gate_v4 as gate_audit
from tools import odoo_v066_current_candidate_one_selection_v4 as runner
from tools import odoo_v066_scale_controller_v1 as controller
from tools import odoo_v066_scale_protocol_v1 as protocol


SCHEMA = "envloop-odoo-v066-current-candidate-first-gui-failure-audit-v1"
PUBLIC_PATH = (protocol.ROOT / "docs/evidence" /
               "odoo-v066-current-candidate-first-gui-terminal-failure-audit-2026-09-29.json")
PIXELS = {(41, 419), (132, 419)}
RGB = {(235, 237, 239), (235, 237, 240)}


class FailureAuditError(ValueError):
    pass


def need(ok: bool, code: str) -> None:
    if not ok:
        raise FailureAuditError(code)


def read(path: Path) -> dict:
    need(path.is_file() and not path.is_symlink(), "failure_audit_file_missing")
    value = json.loads(path.read_bytes())
    need(type(value) is dict, "failure_audit_json_not_object")
    return value


def digest(path: Path) -> str:
    need(path.is_file() and not path.is_symlink(), "failure_audit_file_missing")
    return sha256(path.read_bytes()).hexdigest()


def ref_bytes(attempt: Path, ref: dict) -> bytes:
    need(type(ref) is dict and type(ref.get("path")) is str and
         type(ref.get("sha256")) is str and
         not Path(ref["path"]).is_absolute() and
         ".." not in Path(ref["path"]).parts,
         "failure_audit_artifact_reference_invalid")
    path = attempt / ref["path"]
    need(path.is_file() and not path.is_symlink(),
         "failure_audit_artifact_missing_or_symlink")
    raw = path.read_bytes()
    need(sha256(raw).hexdigest() == ref["sha256"],
         "failure_audit_artifact_hash_changed")
    return raw


def two_pixel_alternate(first: bytes, second: bytes) -> bool:
    with Image.open(BytesIO(first)) as observed, Image.open(BytesIO(second)) as current:
        if observed.format != "PNG" or current.format != "PNG" or \
           observed.mode != "RGB" or current.mode != "RGB" or \
           observed.size != (1440, 1000) or current.size != observed.size:
            return False
        a, b = observed.copy(), current.copy()
    bbox = ImageChops.difference(a, b).getbbox()
    if bbox is None:
        return False
    changed: set[tuple[int, int]] = set()
    for y in range(bbox[1], bbox[3]):
        for x in range(bbox[0], bbox[2]):
            old, new = a.getpixel((x, y)), b.getpixel((x, y))
            if old == new:
                continue
            if old not in RGB or new not in RGB or old == new:
                return False
            changed.add((x, y))
            if len(changed) > 2:
                return False
    return changed == PIXELS


def audit(*, worker_dir: Path, historical_root: Path,
          private_plan: Path, public_plan: Path,
          old_private_plan: Path, old_public_plan: Path) -> dict:
    worker = worker_dir.resolve()
    gate = gate_audit.audit(
        worker_dir=worker, historical_root=historical_root,
        private_plan=private_plan, public_plan=public_plan,
        old_private_plan=old_private_plan, old_public_plan=old_public_plan,
        allow_current_run=True)
    need(gate["status"] ==
         "no_gui_current_sql_full_filestore_gate_independently_verified",
         "failure_audit_preceding_gate_not_verified")
    plan = protocol.private_json(private_plan)
    private = protocol._worker_split(worker, "selection")
    run_dir = private / "v066_scale_controls" / plan["fresh_run_directory_name"]
    attempt = run_dir / "attempt-000"
    batch = read(run_dir / "batch-intent.private.json")
    batch_sha = digest(run_dir / "batch-intent.private.json")
    row = plan["tasks"][0]
    need(batch.get("schema") == runner.BATCH_SCHEMA and
         batch.get("expected_case_count") == 1 and
         batch.get("private_plan_sha256") == digest(private_plan) and
         batch.get("public_plan_sha256") == digest(public_plan) and
         batch.get("current_candidate_private_sha256") ==
         plan["current_candidate_private_sha256"] and
         batch.get("no_gui_gate_sha256") == gate["gate_sha256"] and
         batch.get("automatic_replay_authorized") is False and
         batch.get("official_final_tasks_admitted") == 0 and
         batch.get("model_attempts") == 0,
         "failure_audit_batch_intent_unbound")
    events, _, count = controller.read_journal(run_dir / "journal.private.jsonl")
    failure_path = attempt / "failure.private.json"
    need(count == 2 and
         [e["event"] for e in events] == ["case_started", "case_failed"] and
         all(e.get("task_id") == row["task_id"] and
             e.get("package_sha256") == row["package_sha256"] and
             e.get("run_intent_sha256") == batch_sha and
             e.get("attempt_dir") == "attempt-000" for e in events) and
         events[-1].get("failure_receipt_sha256") == digest(failure_path) and
         not (attempt / "attempt.private.json").exists(),
         "failure_audit_terminal_journal_unbound")
    failure = read(failure_path)
    need(failure.get("status") ==
         "failed_preserve_original_attempt_manual_review_required" and
         failure.get("stage") == "source_gui" and
         failure.get("error_type") == "ContractError" and
         failure.get("error_code") == "stale_frame" and
         failure.get("reset_exact") is True and
         failure.get("services_restored") is True and
         failure.get("current_candidate_private_sha256") ==
         plan["current_candidate_private_sha256"] and
         failure.get("no_gui_gate_sha256") == gate["gate_sha256"] and
         failure.get("run_nonce_sha256") ==
         protocol.digest(bytes.fromhex(plan["run_nonce_hex"])) and
         failure.get("official_final_tasks_admitted") == 0 and
         failure.get("model_attempts") == 0,
         "failure_audit_failure_receipt_unbound")
    post = read(attempt / "post_restore.json")
    need(post.get("business_snapshot_equal") is True and
         post.get("physical_filestore_equal_before_web_restart") is True and
         read(attempt / "restored_sql.json") ==
         protocol.private_json(private / "baseline_snapshot.json") and
         read(attempt / "restored_filestore.json") ==
         protocol.private_json(private / "baseline-filestore-manifest.json") and
         controller._running_services_without_compose_blank(worker) == set(),
         "failure_audit_restore_or_services_not_exact")
    trace = read(attempt / "gui_trace.json")
    need(trace.get("schema") == controller.TRACE_SCHEMA and
         trace.get("task_binding_sha256") == row["task_binding_sha256"] and
         trace.get("sft_examples_written") == 0 and
         type(trace.get("actions")) is list and
         len(trace["actions"]) == 3 and
         [(a.get("phase"), a.get("step")) for a in trace["actions"]] ==
         [("positive", 0), ("positive", 1), ("positive", 2)] and
         len(trace.get("pre_intent_rejections", [])) == 3,
         "failure_audit_action_trace_unbound")
    for index in range(3):
        prefix = f"step-{index:03d}"
        intent = read(attempt / "actions" / f"{prefix}-intent.private.json")
        result = read(attempt / "actions" / f"{prefix}-result.private.json")
        need(intent.get("step") == index and result.get("step") == index and
             intent.get("task_id") == row["task_id"] and
             intent.get("task_binding_sha256") == row["package_sha256"] and
             result.get("intent_sha256") ==
             digest(attempt / "actions" / f"{prefix}-intent.private.json") and
             trace["actions"][index]["frame"]["sha256"] ==
             digest(attempt / "frames" / f"{prefix}.png"),
             "failure_audit_prior_action_not_dispatched")
    samples = trace.get("exact_return_guard_samples")
    need(type(samples) is list and len(samples) == 24 and
         [(s.get("step"), s.get("stage"), s.get("classification"))
          for s in samples[:6]] ==
         [(i, stage, "exact_return") for i in range(3)
          for stage in ("parse", "dispatch")],
         "failure_audit_prior_physical_guard_changed")
    observed_hashes: list[str] = []
    sampled_hashes: list[str] = []
    target = None
    for observation_attempt in range(3):
        prefix = ("step-003" if observation_attempt == 0 else
                  f"step-003-resample-{observation_attempt:02d}")
        rejection = read(attempt / "actions" /
                         f"{prefix}-rejection.private.json")
        ref = trace["pre_intent_rejections"][observation_attempt]
        need(ref_bytes(attempt, ref) ==
             (attempt / "actions" /
              f"{prefix}-rejection.private.json").read_bytes() and
             rejection.get("step") == 3 and
             rejection.get("phase") == "positive" and
             rejection.get("observation_attempt") == observation_attempt and
             rejection.get("error_code") == "stale_frame" and
             rejection.get("pre_dispatch_intent_created") is False and
             rejection.get("gui_action_dispatched") is False and
             not (attempt / "actions" /
                  f"{prefix}-intent.private.json").exists() and
             not (attempt / "actions" /
                  f"{prefix}-result.private.json").exists(),
             "failure_audit_rejection_or_dispatch_boundary_changed")
        observed = ref_bytes(attempt, rejection["observed_frame_ref"])
        assistant = json.loads(ref_bytes(attempt, rejection["assistant_action_ref"]))
        need(assistant.get("type") == "click" and
             type(assistant.get("target")) is dict and
             set(assistant["target"]) == {"x", "y"},
             "failure_audit_rejected_action_changed")
        target = target or assistant["target"]
        need(assistant["target"] == target and
             (target["x"], target["y"]) not in PIXELS,
             "failure_audit_target_or_border_changed")
        observed_hashes.append(sha256(observed).hexdigest())
        block = samples[6 + observation_attempt * 6:
                        12 + observation_attempt * 6]
        need(len(block) == 6 and
             [(s.get("step"), s.get("stage"), s.get("sample"),
               s.get("classification")) for s in block] ==
             [(3, "parse", i, "one_recurring_micro_raster_alternate")
              for i in range(6)],
             "failure_audit_parse_guard_samples_changed")
        actuals = [ref_bytes(attempt, s["sampled_frame_ref"]) for s in block]
        need(all(s.get("observed_frame_sha256") == observed_hashes[-1]
                 for s in block) and
             len({sha256(raw).hexdigest() for raw in actuals}) == 1 and
             all(two_pixel_alternate(observed, raw) for raw in actuals),
             "failure_audit_two_pixel_border_alternate_not_verified")
        sampled_hashes.append(sha256(actuals[0]).hexdigest())
        current = rejection.get("current_frame_ref")
        need(current is not None and
             sha256(ref_bytes(attempt, current)).hexdigest() ==
             sampled_hashes[-1],
             "failure_audit_rejected_current_frame_changed")
    need(len(set(observed_hashes + sampled_hashes)) == 2 and
         all(observed_hashes[i] == sampled_hashes[(i + 1) % 2]
             for i in range(2)) and
         all(observed_hashes[i] != sampled_hashes[i]
             for i in range(3)),
         "failure_audit_two_frame_alternation_changed")
    lease = private / "worker-lease-events.jsonl"
    raw = lease.read_bytes()
    last = [json.loads(line) for line in raw.splitlines()[-2:]]
    need([x.get("event") for x in last] == ["acquired", "released"] and
         all(x.get("operation") == controller.LEASE_OPERATION for x in last) and
         last[0].get("pid") == last[1].get("pid"),
         "failure_audit_original_worker_lease_not_released")
    return {
        "schema": SCHEMA,
        "status": "one_original_current_candidate_gui_failure_independently_verified_no_replay",
        "preceding_gate_sha256": gate["gate_sha256"],
        "batch_intent_sha256": batch_sha,
        "journal_sha256": digest(run_dir / "journal.private.jsonl"),
        "failure_receipt_sha256": digest(failure_path),
        "failure_stage": "source_gui",
        "failure_error_code": "stale_frame",
        "completed_preceding_gui_actions": 3,
        "rejected_action_step": 3,
        "pre_intent_rejections": 3,
        "alternate_parse_samples": 18,
        "raster_difference_pixels": 2,
        "target_action_type": "click",
        "target_point_outside_alternate_pixels": True,
        "target_control_dom_observed": False,
        "parse_exact_return_required": True,
        "pinned_border_dispatch_guard_reached": False,
        "rejected_action_intent_created": False,
        "rejected_action_dispatched": False,
        "baseline_sql_and_full_filestore_restored_exact": True,
        "original_worker_services_stopped": True,
        "original_worker_lease_released": True,
        "source_visual_review_pending": True,
        "automatic_replay_authorized": False,
        "control_dispatch_authorized": False,
        "campaign_dispatch_authorized": False,
        "official_final_tasks_admitted": 0,
        "model_attempts": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker-dir", required=True, type=Path)
    parser.add_argument("--historical-root", required=True, type=Path)
    parser.add_argument("--private-plan", required=True, type=Path)
    parser.add_argument("--public-plan", required=True, type=Path)
    parser.add_argument("--old-private-plan", required=True, type=Path)
    parser.add_argument("--old-public-plan", required=True, type=Path)
    parser.add_argument("--write-public-audit", action="store_true")
    args = parser.parse_args()
    value = audit(worker_dir=args.worker_dir,
                  historical_root=args.historical_root,
                  private_plan=args.private_plan,
                  public_plan=args.public_plan,
                  old_private_plan=args.old_private_plan,
                  old_public_plan=args.old_public_plan)
    if args.write_public_audit:
        need(not PUBLIC_PATH.exists() and not PUBLIC_PATH.is_symlink(),
             "failure_audit_public_receipt_already_exists")
        protocol.write_new(PUBLIC_PATH, value, private=False)
    print(json.dumps(value, sort_keys=True))


if __name__ == "__main__":
    main()
