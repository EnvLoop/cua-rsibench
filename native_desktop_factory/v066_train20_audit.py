"""Independent read-only audit of original WDI train GUI demonstrations.

The auditor reopens each current-frame PNG and actor-saved OOXML and derives
the score from the original oracle. It never treats scripted controls as a
model trial or final-task admission.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import replace
from datetime import date
import json
from pathlib import Path

from cursibench.scale_action_output_v066 import normalize_model_action

from . import admit, qwen_v066_adapter, runtime_fingerprint_probe
from . import v066_profile_scope_analysis as scope
from . import v066_scoped_profile_guard as profile_guard
from .v066_scoped_profile_reference import validate_reference, workflow_kind
from .v066_storage_budget import audit as storage_audit
from .v066_train20_plan import actions_for_train, digest, encode, validate_plan
from .verify import verify


def _private_json(path: Path) -> tuple[dict, bytes]:
    if (not path.is_file() or path.is_symlink() or
            path.stat().st_mode & 0o077):
        raise ValueError("Private train evidence JSON missing or unsafe")
    raw = path.read_bytes()
    return json.loads(raw), raw


def _bound_file(root: Path, reference: dict) -> bytes:
    name = reference.get("private_path")
    if (type(name) is not str or not name or
            Path(name).is_absolute() or ".." in Path(name).parts):
        raise ValueError("Unsafe private evidence reference")
    path = root / name
    if (not path.is_file() or path.is_symlink() or
            path.stat().st_mode & 0o077):
        raise ValueError("Raw private evidence file missing or unsafe")
    raw = path.read_bytes()
    if (len(raw) != reference.get("bytes") or
            digest(raw) != reference.get("sha256")):
        raise ValueError("Raw private evidence bytes changed")
    return raw


class _Frame:
    def __init__(self, raw: bytes):
        self.raw = raw

    def screenshot(self):
        return self.raw


def audit_one(*, candidate_root: Path, evidence_root: Path,
              plan: dict, plan_sha: str, row: dict,
              scoped_reference: Path,
              require_real_provider: bool = True) -> dict:
    task_id = row["task_id"]
    if evidence_root.is_symlink():
        raise ValueError("Private evidence root cannot be a symlink")
    if task_id not in plan["sft_task_ids"] or task_id in plan["holdout_task_ids"]:
        raise ValueError("Holdout data is excluded from SFT source audit")
    out = evidence_root / task_id
    if (not out.is_dir() or out.is_symlink() or
            out.stat().st_mode & 0o077):
        raise ValueError("Private per-ID evidence directory missing or unsafe")
    intent, intent_raw = _private_json(out / "intent.json")
    receipt, receipt_raw = _private_json(out / "receipt.json")
    from . import v066_train20_worker as worker
    if (intent.get("schema") != worker.INTENT_SCHEMA or
            intent.get("split") != "train" or
            intent.get("diagnostic_role") != "sft_source" or
            intent.get("task_id") != task_id or
            intent.get("plan_sha256") != plan_sha or
            intent.get("package_sha256") != row["package_sha256"] or
            intent.get("input_sha256") != row["input_sha256"] or
            intent.get("action_script_sha256") != row["action_script_sha256"] or
            intent.get("runner_sha256") != digest(Path(worker.__file__).read_bytes()) or
            intent.get("lease_seconds") != 600 or
            intent.get("automatic_replay_authorized") is not False or
            type(intent.get("battery_authorized")) is not bool or
            type(intent.get("host_power_before_intent")) is not dict or
            receipt.get("schema") != worker.RECEIPT_SCHEMA or
            receipt.get("purpose") != "evaluator_scripted_sft_source_no_model" or
            receipt.get("split") != "train" or
            receipt.get("task_id") != task_id or
            receipt.get("plan_sha256") != plan_sha or
            receipt.get("intent_sha256") != digest(intent_raw) or
            receipt.get("battery_authorized") != intent["battery_authorized"] or
            receipt.get("host_power_before_intent") !=
            intent["host_power_before_intent"] or
            receipt.get("package_sha256") != row["package_sha256"] or
            receipt.get("input_sha256") != row["input_sha256"] or
            receipt.get("action_script_sha256") != row["action_script_sha256"] or
            receipt.get("runner_sha256") != digest(Path(worker.__file__).read_bytes()) or
            receipt.get("adapter_sha256") !=
            digest(Path(qwen_v066_adapter.__file__).read_bytes()) or
            receipt.get("guest_identity_public_sha256") !=
            plan.get("guest_identity_public_sha256") or
            receipt.get("profile_guard_sha256") !=
            digest(Path(profile_guard.__file__).read_bytes()) or
            receipt.get("status") != "train_gui_positive_passed" or
            receipt.get("guest_content_attested") is not True or
            receipt.get("fresh_profile_absent") is not True or
            receipt.get("kill_returned") is not True or
            receipt.get("is_running_after_kill") is not False or
            receipt.get("official_final_admissions") != 0 or
            receipt.get("official_model_results") != 0 or
            type(receipt.get("sandbox_id_sha256")) is not str or
            len(receipt["sandbox_id_sha256"]) != 64):
        raise ValueError("Train GUI intent, source, status, or cleanup changed")
    if require_real_provider and receipt.get("provider_kind") != "e2b_desktop":
        raise ValueError("Fake provider data cannot enter real SFT source")
    power = intent["host_power_before_intent"]
    if (power.get("source") not in
            ("AC Power", "Battery Power", "test_unverified") or
            (power.get("source") == "Battery Power" and
             intent["battery_authorized"] is not True) or
            (require_real_provider and
             (power.get("source") == "test_unverified" or
              type(power.get("battery_percent")) is not int or
              not 0 <= power["battery_percent"] <= 100 or
              type(power.get("probe_sha256")) is not str or
              len(power["probe_sha256"]) != 64 or
              type(power.get("captured_utc")) is not str))):
        raise ValueError("Train-only battery authorization or telemetry is invalid")
    if receipt.get("provider_kind") not in ("e2b_desktop", "fake_test_only"):
        raise ValueError("Unknown Desktop provider kind")
    directory, baseline, oracle = admit._package(
        candidate_root,
        json.loads((candidate_root / row["relative_package_path"] /
                    "package.json").read_bytes()))
    if (digest(baseline) != row["input_sha256"] or
            row["package_sha256"] !=
            json.loads((directory / "package.json").read_bytes())["package_sha256"]):
        raise ValueError("Original training source differs from frozen plan")
    actions = actions_for_train(json.loads((directory / "package.json").read_bytes()),
                                oracle)
    if (digest(encode(actions)) != row["action_script_sha256"] or
            receipt.get("expected_actor_action_count") != len(actions) or
            len(receipt.get("actor_steps", [])) != len(actions)):
        raise ValueError("Original GUI train script or step count changed")
    reference, reference_sha = validate_reference(scoped_reference)
    kind = workflow_kind(row["workflow"])
    expected_profile = reference["applications"][kind]
    snapshots = receipt.get("task_profile_scoped_snapshots")
    if (receipt.get("scoped_reference_sha256") != reference_sha or
            receipt.get("profile_reference_private_sha256") != reference_sha or
            receipt.get("profile_application_kind") != kind or
            receipt.get("task_profile_scoped_attested") is not True or
            receipt.get("task_profile_scoped_self_stable") is not True or
            receipt.get("task_profile_scoped_matches_public_train") is not True or
            receipt.get("task_profile_scoped_sha256") != expected_profile or
            type(snapshots) is not list or len(snapshots) != 2):
        raise ValueError("Scoped task profile evidence is incomplete")
    tip_days = []
    for label, snapshot in zip(("first", "second"), snapshots):
        if (snapshot.get("label") != label or
                snapshot.get("profile_probe_script_sha256") !=
                digest(runtime_fingerprint_probe.PROFILE_FILE_PROBE.encode())):
            raise ValueError("Scoped profile capture order changed")
        manifest = _bound_file(evidence_root, snapshot["manifest"])
        registry = _bound_file(evidence_root, snapshot["registry"])
        _bound_file(evidence_root, snapshot["visible_frame"])
        observed = scope.scoped_profile(json.loads(manifest), registry)
        if (observed != expected_profile or
                observed != snapshot.get("scoped_profile_sha256")):
            raise ValueError("Raw scoped LibreOffice profile changed")
        if reference.get("current_public_tip_day") is not None:
            tip_days.append(scope.tip_calendar_day(registry))
    day_floor = reference.get("current_public_tip_day")
    if day_floor is not None:
        if (reference.get("prior_public_tip_day") != day_floor - 1 or
                tip_days != [receipt.get("task_profile_tip_calendar_day")] * 2 or
                receipt.get("task_profile_tip_day_reference_floor") != day_floor or
                receipt.get("task_profile_tip_day_matches_guest_clock") is not True or
                len(receipt.get("guest_calendar_probes", [])) != 2):
            raise ValueError("Train scoped tip day lacks public baseline binding")
        guest_days = set()
        for label, probe in zip(("before", "after"),
                                receipt["guest_calendar_probes"]):
            raw = _bound_file(evidence_root, probe["raw"])
            values = raw.decode().splitlines()
            if len(values) != 2 or probe.get("label") != label:
                raise ValueError("Raw train guest calendar probe changed")
            parsed = [(date.fromisoformat(item) - date(1970, 1, 1)).days
                      for item in values]
            if parsed != [probe.get("utc_day"), probe.get("local_day")]:
                raise ValueError("Train guest calendar receipt differs from raw")
            guest_days.update(parsed)
        if tip_days[0] < day_floor or tip_days[0] not in guest_days:
            raise ValueError("Train profile tip day differs from guest date")

    instruction = (directory / "actor_task.txt").read_text()
    previous = None
    for index, (step, minimal) in enumerate(zip(receipt["actor_steps"], actions)):
        attempt = step.get("frame_attempt")
        if (step.get("step") != index or type(attempt) is not int or
                not 0 <= attempt < 5 or step.get("status") != "applied" or
                step.get("dispatch_type") != minimal["type"] or
                step.get("action_payload_sha256") != digest(
                    json.dumps(minimal, separators=(",", ":")).encode())):
            raise ValueError("Observed GUI action sequence changed")
        frame_ref = step["observation"]
        pred_ref = step["predispatch"]
        if (frame_ref.get("private_path") !=
                f"{task_id}/frame-{index:02d}-{attempt}.png" or
                pred_ref.get("private_path") !=
                f"{task_id}/predispatch-{index:02d}-{attempt}.png"):
            raise ValueError("Current and predispatch frame names changed")
        frame_raw = _bound_file(evidence_root, frame_ref)
        pred_raw = _bound_file(evidence_root, pred_ref)
        if (qwen_v066_adapter.prior.application_frame_digest(frame_raw) !=
                qwen_v066_adapter.prior.application_frame_digest(pred_raw)):
            raise ValueError("Predispatch application frame differs")
        observation = qwen_v066_adapter.observe(
            _Frame(frame_raw), task_id=task_id,
            task_binding_sha256=row["package_sha256"],
            instruction=instruction, step=index,
            previous_action_result=previous, max_actions=worker.MAX_ACTIONS)
        payload = json.dumps(minimal, separators=(",", ":"))
        # Frame IDs are random per observation, even for identical PNG bytes.
        # Reuse the retained normalized envelope's nonce, then independently
        # validate every other task/step/action field against the raw frame.
        recorded = step.get("normalized_action")
        nonce = recorded.get("frame_id") if type(recorded) is dict else None
        if type(nonce) is not str:
            raise ValueError("Recorded current-frame nonce missing")
        observation = replace(observation, frame_id=nonce)
        checked = normalize_model_action(
            payload, observation, current_frame_id=nonce)
        if (step.get("frame_id_sha256") != digest(nonce.encode()) or
                step.get("normalized_action") != checked or
                step.get("normalized_action_sha256") != digest(encode(checked))):
            raise ValueError("Retained v0.6.6 action envelope changed")
        previous = {"status": "applied", "code": "ok"}
    for row_drift in receipt.get("physical_frame_resamples", []):
        if (type(row_drift.get("step")) is not int or
                not 0 <= row_drift["step"] < len(actions) or
                type(row_drift.get("frame_attempt")) is not int or
                not 0 <= row_drift["frame_attempt"] < 5):
            raise ValueError("Pre-intent frame resample metadata invalid")
        _bound_file(evidence_root, row_drift["observed"])
        _bound_file(evidence_root, row_drift["changed"])
    suffix = {"calc": ".xlsx", "impress": ".pptx", "writer": ".docx"}[kind]
    saved_ref = receipt.get("saved_artifact")
    if saved_ref.get("private_path") != f"{task_id}/saved{suffix}":
        raise ValueError("Actor saved-file location changed")
    saved = _bound_file(evidence_root, saved_ref)
    verdict = verify(baseline, saved, oracle)
    if (saved == baseline or digest(saved) != receipt.get("saved_sha256") or
            verdict.get("passed") is not True or
            receipt.get("independent_saved_verifier") != verdict):
        raise ValueError("Original actor-saved OOXML fails independent verifier")
    return {
        "task_id": task_id, "workflow": row["workflow"],
        "sandbox_id_sha256": receipt["sandbox_id_sha256"],
        "action_count": len(actions),
        "receipt_sha256": digest(receipt_raw),
        "saved_sha256": digest(saved),
        "status": "independently_audited_train_gui_positive",
    }


def audit_all(*, repo_root: Path, candidate_root: Path, evidence_root: Path,
              plan_path: Path, guest_public: Path,
              scoped_reference: Path, ratification: Path) -> dict:
    plan, plan_sha = validate_plan(
        private_path=plan_path, repo_root=repo_root,
        candidate_root=candidate_root, guest_public=guest_public,
        scoped_reference=scoped_reference, ratification=ratification)
    storage = storage_audit(evidence_root, verify_all_bytes=True)
    if storage["unresolved_write_count"]:
        raise ValueError("Private raw-frame write remains unresolved")
    by_id = {row["task_id"]: row for row in plan["train_rows"]}
    accepted, missing = [], []
    sandbox_ids = set()
    for task_id in plan["sft_task_ids"]:
        if not (evidence_root / task_id).exists():
            missing.append(task_id)
            continue
        outcome = audit_one(
            candidate_root=candidate_root, evidence_root=evidence_root,
            plan=plan, plan_sha=plan_sha, row=by_id[task_id],
            scoped_reference=scoped_reference)
        if outcome["sandbox_id_sha256"] in sandbox_ids:
            raise ValueError("Two train tasks reused one E2B guest")
        sandbox_ids.add(outcome["sandbox_id_sha256"])
        accepted.append(outcome)
    if any((evidence_root / task_id).exists() for task_id in plan["holdout_task_ids"]):
        raise ValueError("A holdout identity was touched by SFT collection")
    return {
        "schema": "cua-native-wdi-v066-train20-audit-public-v1",
        "status": "all_15_sft_gui_sources_audited" if len(accepted) == 15 else
                  "partial_training_evidence_only",
        "candidate_train_id_count": 20,
        "sft_candidate_count": 15, "holdout_candidate_count": 5,
        "independently_audited_real_gui_sft_ids": len(accepted),
        "missing_sft_ids": len(missing),
        "total_audited_gui_actions": sum(row["action_count"] for row in accepted),
        "audited_workflow_counts": dict(sorted(Counter(
            row["workflow"] for row in accepted).items())),
        "distinct_verified_guest_count": len(sandbox_ids),
        "raw_evidence_storage_bytes": storage["reserved_evidence_bytes"],
        "source_plan_sha256": plan_sha,
        "model_effect_measured": False,
        "official_final_admissions": 0, "official_model_results": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--guest-public", type=Path, required=True)
    parser.add_argument("--scoped-reference", type=Path, required=True)
    parser.add_argument("--ratification", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit_all(
        repo_root=args.repo_root, candidate_root=args.candidate_root,
        evidence_root=args.evidence_root, plan_path=args.plan,
        guest_public=args.guest_public,
        scoped_reference=args.scoped_reference, ratification=args.ratification),
        indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
