"""Fail-closed prospective Desktop v0.6.6 freeze and separate lane reserve.

No ratification or reservation file is shipped. An evaluator must first bind
all six cells to the same shared source hashes, then record a separate $60
full-lease planning ceiling. Merely creating either file does not admit a task.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re

from cursibench import (scale_action_contract, scale_action_contract_v066,
                        scale_action_output_v065, scale_action_output_v066,
                        scale_vision_proxy)
from cursibench.full_study_matrix_v1 import CELLS

from . import qwen_v066_adapter
from .official_scorer_freeze import scorer_bundle


RATE_USD_PER_HOUR_UPPER = Decimal("1")
LANE_CAP_USD = Decimal("60")
LEASE_SECONDS = 600
INITIAL_SANDBOX_COUNT = 300
MAX_SANDBOX_COUNT = 360
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def source_hashes() -> dict[str, str]:
    modules = {
        "full_action_validator_v06": scale_action_contract,
        "full_action_extension_v066": scale_action_contract_v066,
        "minimal_output_v065_dependency": scale_action_output_v065,
        "minimal_output_v066": scale_action_output_v066,
        "qwen_vision_proxy": scale_vision_proxy,
    }
    return {key: digest(Path(module.__file__).read_bytes())
            for key, module in modules.items()}


def validate_ratification(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    value = json.loads(raw)
    expected_hashes = source_hashes()
    if (type(value) is not dict
            or set(value) != {"schema", "status", "ratified_utc", "action_profile",
                              "common_source_sha256s", "cell_profiles",
                              "base_and_selected_identical", "hidden_final_model_attempts_before_ratification"}
            or value["schema"] != "cua-six-cell-action-profile-v066-ratification-v1"
            or value["status"] != "ratified_pre_result"
            or value["action_profile"] != "scale-action-profile-v0.6.6"
            or value["common_source_sha256s"] != expected_hashes
            or value["base_and_selected_identical"] is not True
            or value["hidden_final_model_attempts_before_ratification"] != 0):
        raise ValueError("Common six-cell v0.6.6 profile is not ratified")
    try:
        ratified = datetime.fromisoformat(value["ratified_utc"])
    except (TypeError, ValueError):
        raise ValueError("Ratification timestamp is invalid") from None
    if (ratified.tzinfo is None or ratified.astimezone(timezone.utc) >
            datetime.now(timezone.utc)):
        raise ValueError("Ratification timestamp is absent or in the future")
    profiles = value["cell_profiles"]
    if type(profiles) is not dict or set(profiles) != set(CELLS):
        raise ValueError("Ratification must name exactly the six study cells")
    for cell, profile in profiles.items():
        if (type(profile) is not dict
                or set(profile) != {"common_source_sha256s", "adapter_sha256"}
                or profile["common_source_sha256s"] != expected_hashes
                or type(profile["adapter_sha256"]) is not str
                or not _HEX64.fullmatch(profile["adapter_sha256"])):
            raise ValueError("A cell is not bound to the common action source")
        if (cell == "desktop-native" and profile["adapter_sha256"] !=
                digest(Path(qwen_v066_adapter.__file__).read_bytes())):
            raise ValueError("The native Desktop adapter changed after ratification")
    return value, digest(raw)


def _source_bindings(candidate_root: Path, guest_public: Path,
                     profile_private: Path, fair_public: Path) -> dict[str, str]:
    fair = json.loads(fair_public.read_bytes())
    scorer_sha, _files = scorer_bundle()
    if fair.get("scorer_bundle_sha256") != scorer_sha:
        raise ValueError("The fair saved-artifact scorer changed")
    guest = json.loads(guest_public.read_bytes())
    if (guest.get("scoped_guest_content_identity_passed") is not True
            or guest.get("official_desktop_final_admissions") != 0):
        raise ValueError("The scoped guest reference is not a pre-result identity")
    profiles = json.loads(profile_private.read_bytes())
    inventory = json.loads((candidate_root / "candidate-inventory.json").read_bytes())
    if (profiles.get("candidate_inventory_sha256") !=
            digest((candidate_root / "candidate-inventory.json").read_bytes())
            or len(profiles.get("accepted", [])) != 100
            or inventory.get("design_revision") != "v2-distinct-structures"):
        raise ValueError("The 100 task-bound profiles or final inventory changed")
    rights_path = (Path(__file__).resolve().parent.parent / "docs" / "evidence" /
                   "native-wdi-v065-final-admission-preflight-2026-09-27.json")
    rights_raw = rights_path.read_bytes()
    rights = json.loads(rights_raw)
    if (rights.get("candidate_inventory_sha256") !=
            digest((candidate_root / "candidate-inventory.json").read_bytes())
            or rights.get("inputs_with_world_bank_ccby_and_derived_attribution") != 100
            or rights.get("source_license") != "CC BY 4.0"
            or rights.get("qualified_under_current_v065") != 0):
        raise ValueError("The 100 task source/attribution preflight changed")
    return {
        "candidate_inventory_sha256": digest((candidate_root / "candidate-inventory.json").read_bytes()),
        "guest_identity_public_sha256": digest(guest_public.read_bytes()),
        "profile_private_sha256": digest(profile_private.read_bytes()),
        "fair_scorer_public_sha256": digest(fair_public.read_bytes()),
        "fair_scorer_bundle_sha256": scorer_sha,
        "source_rights_preflight_public_sha256": digest(rights_raw),
    }


def prepare_lane(*, ratification: Path, reservation: Path, candidate_root: Path,
                 guest_public: Path, profile_private: Path, fair_public: Path) -> dict:
    if reservation.exists():
        raise ValueError("Refusing to replace an E2B final-control lane reservation")
    _ratified, ratification_sha = validate_ratification(ratification)
    bindings = _source_bindings(candidate_root, guest_public,
                                profile_private, fair_public)
    value = {
        "schema": "cua-native-wdi-v066-final-control-lane-reservation-v1",
        "status": "reserved_before_first_final_control_create",
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "ratification_sha256": ratification_sha,
        "source_bindings": bindings,
        "lease_seconds_each": LEASE_SECONDS,
        "planning_rate_usd_per_hour_upper": str(RATE_USD_PER_HOUR_UPPER),
        "initial_sandbox_count": INITIAL_SANDBOX_COUNT,
        "initial_full_lease_reserved_usd": "50",
        "maximum_attempt_count_including_manual_recovery": MAX_SANDBOX_COUNT,
        "lane_cap_usd": str(LANE_CAP_USD),
        "actual_provider_billed_usd": None,
        "official_hidden_final_model_attempts": 0,
    }
    reservation.parent.mkdir(parents=True, exist_ok=True)
    reservation.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    reservation.chmod(0o600)
    return value


def validate_lane(*, ratification: Path, reservation: Path, candidate_root: Path,
                  guest_public: Path, profile_private: Path, fair_public: Path) -> dict:
    _ratified, ratification_sha = validate_ratification(ratification)
    bindings = _source_bindings(candidate_root, guest_public,
                                profile_private, fair_public)
    lane = json.loads(reservation.read_bytes())
    if (type(lane) is not dict
            or set(lane) != {"schema", "status", "recorded_utc", "ratification_sha256",
                             "source_bindings", "lease_seconds_each",
                             "planning_rate_usd_per_hour_upper", "initial_sandbox_count",
                             "initial_full_lease_reserved_usd",
                             "maximum_attempt_count_including_manual_recovery",
                             "lane_cap_usd", "actual_provider_billed_usd",
                             "official_hidden_final_model_attempts"}
            or lane["schema"] != "cua-native-wdi-v066-final-control-lane-reservation-v1"
            or lane["status"] != "reserved_before_first_final_control_create"
            or lane["ratification_sha256"] != ratification_sha
            or lane["source_bindings"] != bindings
            or lane["lease_seconds_each"] != LEASE_SECONDS
            or lane["planning_rate_usd_per_hour_upper"] != str(RATE_USD_PER_HOUR_UPPER)
            or lane["initial_sandbox_count"] != INITIAL_SANDBOX_COUNT
            or lane["initial_full_lease_reserved_usd"] != "50"
            or lane["maximum_attempt_count_including_manual_recovery"] != MAX_SANDBOX_COUNT
            or lane["lane_cap_usd"] != str(LANE_CAP_USD)
            or lane["actual_provider_billed_usd"] is not None
            or lane["official_hidden_final_model_attempts"] != 0):
        raise ValueError("Separate $60 full-lease control reservation is absent or changed")
    return lane


def intent_budget(attempts_root: Path, *, proposed_new: int = 0) -> dict:
    paths = sorted(attempts_root.glob("*/*/intent.json"))
    if not 0 <= proposed_new <= INITIAL_SANDBOX_COUNT:
        raise ValueError("Proposed new sandbox count exceeds 300")
    for path in paths:
        row = json.loads(path.read_bytes())
        if (row.get("schema") != "cua-native-wdi-v066-final-control-intent-v1"
                or row.get("lease_seconds") != LEASE_SECONDS
                or row.get("task_id") != path.parent.parent.name
                or row.get("attempt") != path.parent.name):
            raise ValueError("A private E2B final-control intent changed")
    total = len(paths) + proposed_new
    reserve = Decimal(total * LEASE_SECONDS) / 3600 * RATE_USD_PER_HOUR_UPPER
    if total > MAX_SANDBOX_COUNT or reserve > LANE_CAP_USD:
        raise ValueError("Separate $60 full-lease final-control lane exceeded")
    return {
        "existing_intents": len(paths),
        "proposed_new_intents": proposed_new,
        "combined_intents": total,
        "combined_full_lease_reserved_usd": str(reserve),
        "lane_cap_usd": str(LANE_CAP_USD),
        "actual_provider_billed_usd": None,
    }
