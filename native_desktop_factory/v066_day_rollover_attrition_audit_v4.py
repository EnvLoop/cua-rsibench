"""Independent read-only audit of Desktop v4 untouched-ID controls.

The old 35-file runtime, first eight complete trios, two original quarantines,
and stopped v3 partial remain immutable.  New v4 trios must appear in exact
roster order and pass saved OOXML, negative/no-regression, reset, profile,
durable-intent, and raw A/B/A/B frame checks before the next ID can start.
"""

from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path
from unittest.mock import patch

from . import qwen_v066_adapter_v4_strict as strict
from . import v066_day_rollover_continuation_v2 as v2
from . import v066_day_rollover_continuation_v3 as v3
from . import v066_scoped_profile_final_audit as profile_audit
from .v066_day_rollover_durable_audit_v3 import audit as audit_durable
from .v066_caret_full100_preflight import _read_only_storage, _tree_digest
from .v066_day_rollover_bridge import combined_budget
from .v066_day_rollover_reference import validate as validate_reference
from .v066_final_control_audit import _bound_file, _validate_trio
from .v066_final_freeze import digest, intent_budget
from .v066_scoped_profile_final_controller import _final_rows


ATTEMPTS = ("positive", "near-miss", "cold-reset")


def _raw(path: Path) -> bytes:
    if not path.is_file() or path.is_symlink() or path.stat().st_mode & 0o077:
        raise ValueError("Private Desktop evidence is missing or nonprivate")
    return path.read_bytes()


def _guard_frames(root: Path, receipt: dict) -> int:
    """Reopen each drift and action frame; accept only an exact A/B/A/B witness."""
    grouped: dict[int, list[tuple[bytes, bytes]]] = {}
    attempt_root = root / receipt["task_id"] / receipt["attempt"]
    expected_manifests = set()
    for sample in receipt.get("physical_frame_resamples", []):
        step = sample.get("step")
        frame_attempt = sample.get("attempt")
        if type(step) is not int or type(frame_attempt) is not int:
            raise ValueError("Unbound v4 frame-resample step")
        a = _bound_file(root, sample["observed"])
        b = _bound_file(root, sample["changed"])
        if not strict.prototype.v3._single_caret_column(a, b):
            raise ValueError("v4 attempt contains a material drift retry")
        manifest_name = f"probe-step-{step:02d}-{frame_attempt:02d}.json"
        manifest_path = attempt_root / manifest_name
        if (not manifest_path.is_file() or manifest_path.is_symlink() or
                manifest_path.stat().st_mode & 0o077):
            raise ValueError("v4 internal-probe manifest is absent")
        manifest = json.loads(manifest_path.read_bytes())
        frames = [_bound_file(root, item)
                  for item in manifest.get("sample_frames", [])]
        observed_application = strict.prototype._application_sha(a)
        alternate_application = strict.prototype._application_sha(b)
        if (manifest.get("schema") !=
                "cua-native-wdi-v066-internal-caret-probe-private-v4" or
                manifest.get("status") != "pending_exact_alternate" or
                manifest.get("step") != step or
                manifest.get("frame_attempt") != frame_attempt or
                manifest.get("observed_sha256") != digest(a) or
                len(frames) != 6 or
                manifest.get("sample_application_sha256s") !=
                [alternate_application] * 6 or
                any(strict.prototype._application_sha(frame) !=
                    alternate_application or
                    not strict.prototype.v3._single_caret_column(a, frame)
                    for frame in frames) or
                digest(frames[-1]) != digest(b) or
                observed_application == alternate_application):
            raise ValueError("v4 internal probes do not prove a stable caret alternate")
        expected_manifests.add(manifest_name)
        grouped.setdefault(step, []).append((a, b))
    if {path.name for path in attempt_root.glob("probe-step-*.json")} != expected_manifests:
        raise ValueError("v4 internal-probe manifests are unbound to receipt")
    witnesses = 0
    for step, row in enumerate(receipt.get("actor_steps", [])):
        a = _bound_file(root, row["observation"])
        b = _bound_file(root, row["predispatch"])
        prior = grouped.pop(step, [])
        if prior:
            manifest_name = f"probe-step-{step:02d}-00.json"
            manifest = json.loads((attempt_root / manifest_name).read_bytes())
            if manifest.get("action_sha256") != row.get("action_payload_sha256"):
                raise ValueError("v4 internal caret probe action changed")
        if len(prior) > 1:
            raise ValueError("v4 attempt retried the same action more than once")
        if (strict.prototype._application_sha(a) !=
                strict.prototype._application_sha(b)):
            if (len(prior) != 1 or
                    not strict.prototype.v3._single_caret_column(a, b) or
                    strict.prototype._application_sha(prior[0][0]) !=
                    strict.prototype._application_sha(a) or
                    strict.prototype._application_sha(prior[0][1]) !=
                    strict.prototype._application_sha(b)):
                raise ValueError("v4 action lacks exact A/B/A/B liveness evidence")
            witnesses += 1
    if grouped:
        raise ValueError("v4 attempt has unapplied or out-of-order frame retries")
    return witnesses


def audit(*, v3_freeze: Path, caret_freeze: Path,
          batch_one: Path, stopped_batch_two: Path,
          expected_first_eleven_trees: dict[str, str] | None = None,
          v4_wrapper_sha: str | None = None,
          active_run_dir: Path | None = None) -> tuple[dict, dict, dict, list[dict]]:
    v3_raw = _raw(v3_freeze)
    old = json.loads(v3_raw)
    if (old.get("schema") != v3.SCHEMA or
            old.get("status") != "frozen_before_durable_untouched_continuation" or
            old.get("source_sha256s") != v3._sources() or
            old.get("same_id_retry_authorized") is not False or
            old.get("official_final_admissions") != 0):
        raise ValueError("Preserved v3 source freeze changed")
    v2_freeze = Path(old["base_freeze_path"])
    if v3._verify_base_public(v2_freeze) != old["base_freeze_sha256"]:
        raise ValueError("Preserved v2/35-source lineage changed")
    v2_frozen = json.loads(_raw(v2_freeze))
    paths = v2._paths(v2_frozen["paths"])
    inventory_raw, rows = _final_rows(paths["candidate_root"])
    roster = [row["task_id"] for row in rows]
    if (len(rows) != 100 or
            digest((json.dumps(roster, separators=(",", ":")) + "\n").encode()) !=
            v2_frozen["roster_sha256"] or
            v2._prefix_trees(paths, roster) !=
            v2_frozen["original_nine_task_trees_sha256"]):
        raise ValueError("Frozen 100-ID roster or first-nine evidence changed")
    v2._reconciliation(paths, roster)
    first_trees = {str(i): _tree_digest(paths["attempts_root"] / roster[i])[0]
                   for i in range(11)}
    if (expected_first_eleven_trees is not None and
            first_trees != expected_first_eleven_trees):
        raise ValueError("Old eight complete/three partial task trees changed")
    first, second = json.loads(_raw(batch_one)), json.loads(_raw(stopped_batch_two))
    if (first.get("schema") != v3.RUN_SCHEMA or
            first.get("status") != "bounded_completed_and_audited" or
            first.get("selected_private_task_ids") != [roster[9]] or
            len(first.get("task_outcomes", [])) != 1 or
            first["task_outcomes"][0].get("status") != "provisional_trio_complete" or
            second.get("schema") != v3.RUN_SCHEMA or
            second.get("status") != "stopped_for_reconciliation" or
            second.get("selected_private_task_ids") != [roster[10], roster[11]] or
            len(second.get("task_outcomes", [])) != 1 or
            second["task_outcomes"][0].get("status") !=
            "stopped_after_invalid_or_uncertain_attempt" or
            len(second["task_outcomes"][0].get("attempts", [])) != 2 or
            first.get("freeze_sha256") != digest(v3_raw) or
            second.get("freeze_sha256") != digest(v3_raw) or
            first.get("official_final_admissions") != 0 or
            second.get("official_final_admissions") != 0):
        raise ValueError("Retained v3 batch terminals changed")
    caret = json.loads(_raw(caret_freeze))
    repo = Path(__file__).resolve().parents[1]
    caret_sources = caret.get("v4_source_sha256s", {})
    if (len(caret_sources) != 4 or
            any(digest((repo / name).read_bytes()) != expected
                for name, expected in caret_sources.items())):
        raise ValueError("Frozen v4 caret prototype source changed")
    failed_raw = _raw(paths["attempts_root"] / roster[10] /
                      "near-miss/receipt.json")
    positive = json.loads(_raw(paths["attempts_root"] / roster[10] /
                               "positive/receipt.json"))
    failed = json.loads(failed_raw)
    if (caret.get("schema") !=
            "cua-native-wdi-v066-caret-liveness-source-freeze-private-v4" or
            caret.get("status") != "frozen_pre_result_no_dispatch_authority" or
            caret.get("eligible_private_task_id") != roster[10] or
            caret.get("old_batch_run_receipt_sha256") !=
            digest(_raw(stopped_batch_two)) or
            caret.get("old_failed_receipt_sha256") != digest(failed_raw) or
            caret.get("same_id_retry_dispatch_authorized") is not False or
            positive.get("status") != "control_passed" or
            positive.get("fair_verifier", {}).get("passed") is not True or
            positive.get("is_running_after_kill") is not False or
            failed.get("status") != "control_failed_or_infrastructure_invalid" or
            failed.get("error_type") != "PhysicalFrameDrift" or
            failed.get("contract_error_code") != "stale_frame" or
            failed.get("saved_artifact") is not None or
            failed.get("fair_verifier") is not None or
            failed.get("is_running_after_kill") is not False or
            (paths["attempts_root"] / roster[10] / "cold-reset").exists() or
            (paths["attempts_root"] / roster[11]).exists()):
        raise ValueError("Partial v3 ID or never-intended next ID changed")
    audit_durable(
        attempts_root=paths["attempts_root"], roster=rows,
        initial_accepted=8, prior_intents=24,
        wrapper_sha=old["source_sha256s"][
            "native_desktop_factory/v066_day_rollover_durable_child_v3.py"])
    reference, reference_sha = validate_reference(
        path=paths["reference_path"],
        private_audit=paths["private_day_audit"],
        public_audit=paths["public_day_audit"])
    salt = json.loads(_raw(paths["private_map"])).get("variant_salt")
    if type(salt) is not str or len(salt) < 32:
        raise ValueError("Evaluator-private saved-state salt missing")
    common = {"profile_sha": digest(_raw(paths["profile_private"])),
              "guest_sha": digest(paths["guest_public"].read_bytes()),
              "private_salt": salt,
              "ratification_sha": digest(_raw(paths["action_ratification"])),
              "reservation_sha": digest(_raw(paths["reservation"]))}
    accepted = []
    untouched = []
    all_guest_ids = set()
    caret_witnesses = 0
    for index, row in enumerate(rows):
        root = paths["attempts_root"] / row["task_id"]
        if index in (7, 8, 10):
            continue
        if not root.exists():
            if index < 11:
                raise ValueError("Original complete Desktop trio disappeared")
            untouched.append(index)
            continue
        if index < 11 and index != 9:
            expected_adapter = None
        elif index == 9:
            expected_adapter = None
        else:
            expected_adapter = strict
        fair = _validate_trio(paths["candidate_root"], paths["attempts_root"],
                              row, **common)
        if expected_adapter is None:
            ids = profile_audit._profile_receipt(
                candidate_root=paths["candidate_root"],
                attempts_root=paths["attempts_root"], task_id=row["task_id"],
                workflow=row["workflow"], reference=reference,
                reference_sha=reference_sha,
                runtime_sha=digest(_raw(paths["runtime_freeze"])),
                bridge_sha=digest(_raw(paths["bridge_path"])))
        else:
            with patch.object(profile_audit, "qwen_v066_adapter", strict):
                ids = profile_audit._profile_receipt(
                    candidate_root=paths["candidate_root"],
                    attempts_root=paths["attempts_root"], task_id=row["task_id"],
                    workflow=row["workflow"], reference=reference,
                    reference_sha=reference_sha,
                    runtime_sha=digest(_raw(paths["runtime_freeze"])),
                    bridge_sha=digest(_raw(paths["bridge_path"])))
            if v4_wrapper_sha is None:
                raise ValueError("v4 child source hash required for new trio")
            for offset, attempt in enumerate(ATTEMPTS):
                attempt_root = root / attempt
                budget_raw = _raw(attempt_root / "budget.json")
                budget = json.loads(budget_raw)
                intent = json.loads(_raw(attempt_root / "intent.json"))
                receipt = json.loads(_raw(attempt_root / "receipt.json"))
                expected_total = 56 + 3 * (index - 11) + offset
                if (budget.get("schema") !=
                        "cua-native-wdi-v066-precreate-budget-private-v3" or
                        budget.get("status") != "fsynced_before_provider_create" or
                        budget.get("task_id") != row["task_id"] or
                        budget.get("attempt") != attempt or
                        budget.get("four_root_budget", {}).get(
                            "combined_full_lease_intents") != expected_total or
                        Decimal(budget["four_root_budget"][
                            "combined_conservative_reserved_usd"]) !=
                            Decimal(expected_total) / Decimal(6) or
                        budget.get("fresh_lane_budget", {}).get(
                            "combined_intents") != expected_total - 26 or
                        budget.get("provider_active_before_intent") != 0 or
                        budget.get("credential_present") is not True or
                        budget.get("power", {}).get("source") not in
                            ("AC Power", "Battery Power") or
                        intent.get("precreate_budget_sha256") != digest(budget_raw) or
                        intent.get("durable_child_wrapper_sha256") !=
                            v4_wrapper_sha or
                        receipt.get("native_adapter_sha256") !=
                            digest(Path(strict.__file__).read_bytes())):
                    raise ValueError("v4 durable budget/child/adapter binding changed")
                if attempt != "cold-reset":
                    caret_witnesses += _guard_frames(paths["attempts_root"], receipt)
        if any(item in all_guest_ids for item in ids):
            raise ValueError("Accepted Desktop trios reused an E2B guest")
        all_guest_ids.update(ids)
        accepted.append((index, fair))
    accepted_indices = [index for index, _fair in accepted]
    if (accepted_indices[:8] != list(range(7)) + [9] or
            accepted_indices[8:] != list(range(11, 11 + len(accepted) - 8)) or
            untouched != list(range(11 + len(accepted) - 8, 100))):
        raise ValueError("v4 continuation skipped or reordered the frozen roster")
    new = len(accepted) - 8
    fresh = intent_budget(paths["attempts_root"])
    budget = combined_budget(
        original_root=paths["old_original_root"],
        failed_root=paths["old_caret_root"],
        failed_scoped_root=paths["old_failed_scoped_root"],
        fresh_root=paths["attempts_root"], proposed_fresh_intents=0)
    if (fresh["existing_intents"] != 29 + 3 * new or
            budget["combined_full_lease_intents"] != 55 + 3 * new or
            len(untouched) != 89 - new or
            len(accepted) + len(untouched) + 3 != 100):
        raise ValueError("v4 exact attrition or charged full-lease count changed")
    private = {
        "schema": "cua-native-wdi-v066-untouched-attrition-audit-private-v4",
        "status": "provisional_controls_with_three_retained_partials",
        "candidate_inventory_sha256": digest(inventory_raw),
        "old_v3_freeze_sha256": digest(v3_raw),
        "old_batch_one_sha256": digest(_raw(batch_one)),
        "old_stopped_batch_two_sha256": digest(_raw(stopped_batch_two)),
        "old_caret_freeze_sha256": digest(_raw(caret_freeze)),
        "first_eleven_task_tree_sha256s": first_trees,
        "accepted_trios": accepted,
        "never_intended_roster_indices": untouched,
        "v4_cross_observation_caret_witnesses": caret_witnesses,
        "four_root_budget": budget,
        "raw_storage": _read_only_storage(paths["attempts_root"]),
        "same_id_retry_authorized": False,
        "official_final_admissions": 0,
        "official_model_results": 0,
    }
    public = {
        "schema": "cua-native-wdi-v066-untouched-attrition-audit-public-v4",
        "status": "provisional_controls_with_three_retained_partials",
        "candidate_final_count": 100,
        "original_quarantined_task_count": 2,
        "new_stopped_v3_partial_task_count": 1,
        "independently_accepted_complete_trios": len(accepted),
        "v4_new_complete_trios": new,
        "never_intended_task_count": len(untouched),
        "distinct_accepted_sandboxes": len(all_guest_ids),
        "v4_cross_observation_caret_witnesses": caret_witnesses,
        "four_root_full_lease_intents_charged":
            budget["combined_full_lease_intents"],
        "four_root_reserved_usd_upper":
            budget["combined_conservative_reserved_usd"],
        "same_id_retry_authorized": False,
        "official_final_admissions": 0,
        "official_model_results": 0,
    }
    return private, public, paths, rows
