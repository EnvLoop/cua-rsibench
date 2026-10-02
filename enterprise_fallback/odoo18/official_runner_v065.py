"""Fail-closed Odoo official-task dispatch gate for the six-cell study.

No provider, browser or hidden-task read occurs until a ratified, SHA-bound
six-cell pre-campaign plan, common v0.6.5 action bundle, Odoo runtime/hidden
controls, base checkpoint and append-only budget gate all validate. Even then an
explicit --execute flag is required. The runner preserves a candidate verifier
result but never promotes it to an official score before billing and the
global result ledger reconcile. It cannot run a selected checkpoint yet.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import time

from cursibench import full_study_pre_campaign_v1 as pre_campaign
from cursibench import full_study_matrix_v1 as matrix
from cursibench import scale_action_contract, scale_action_output_v062
from cursibench import scale_action_output_v064, scale_action_output_v065
from cursibench import scale_final_v06 as cell_final
from cursibench import scale_vision_proxy
from cursibench.factory_budget import Budget


SCHEMA = "cua-odoo-v065-official-dispatch-freeze-v1"
ACTION_SCHEMA = "cua-shared-action-output-bundle-v065"
RUNTIME_SCHEMA = "cua-odoo-native-runtime-bundle-v065"
BUDGET_SCHEMA = "cua-odoo-v065-budget-authority-v1"
CAMPAIGN_ID = re.compile(r"[a-z][a-z0-9-]{2,63}\Z")


class FreezeError(ValueError):
    """Public-safe code; never include private task or reference text."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _source(path: Path) -> str:
    return digest(path.read_bytes())


def _referenced_json(root: Path, reference: dict, label: str) -> tuple[dict, str]:
    try:
        _, raw = cell_final.evidence_file(root, reference, label)
        value = json.loads(raw)
    except (ValueError, OSError, KeyError, TypeError):
        raise FreezeError("invalid_frozen_reference") from None
    if type(value) is not dict:
        raise FreezeError("invalid_frozen_reference")
    return value, digest(raw)


def _preflight_protocol(freeze: dict, root: Path) -> tuple[dict, dict, dict, dict]:
    try:
        relative = freeze["pre_campaign_manifest"]["path"]
        at_root = isinstance(relative, str) and Path(relative).parent == Path(".")
    except (KeyError, TypeError):
        at_root = False
    if not at_root:
        raise FreezeError("protocol_manifest_must_be_at_freeze_root")
    protocol, protocol_hash = _referenced_json(root, freeze["pre_campaign_manifest"],
                                                "six-cell pre-campaign manifest")
    plan, plan_hash = _referenced_json(root, freeze["pre_campaign_plan"],
                                      "six-cell prepared plan")
    if (protocol.get("schema") != pre_campaign.SCHEMA
            or plan.get("schema") != pre_campaign.PLAN_SCHEMA
            or plan.get("protocol_manifest_sha256") != protocol_hash):
        raise FreezeError("six_cell_plan_missing_or_changed")
    try:
        recalculated = pre_campaign.build(protocol, root, protocol_hash)
    except (ValueError, OSError, KeyError, TypeError):
        raise FreezeError("six_cell_qualification_incomplete") from None
    if cell_final.json_bytes(recalculated) != cell_final.json_bytes(plan):
        raise FreezeError("six_cell_plan_not_reproducible")
    if (plan.get("campaign_count") != 24
            or plan.get("distinct_official_task_identities") != 600
            or plan.get("provider_dispatch_enabled") is not False
            or plan.get("scores_present") is not False):
        raise FreezeError("six_cell_plan_not_pre_result")
    odoo = next((row for row in plan["cells"] if row["cell_id"] == "odoo-community"), None)
    if odoo is None or odoo["official_task_count"] != 100 or odoo["selection_task_count"] != 20:
        raise FreezeError("odoo_cell_not_qualified")
    odoo_protocol = next(cell for cell in protocol["cells"]
                         if cell["cell_id"] == "odoo-community")
    try:
        base = matrix._slot(root, odoo_protocol["base_manifest"],
                            cell_id="odoo-community", researcher_id="shared-base",
                            role="base")
    except (ValueError, OSError, KeyError, TypeError):
        raise FreezeError("odoo_base_manifest_not_qualified") from None
    if base["manifest_sha256"] != odoo["base_manifest_sha256"]:
        raise FreezeError("odoo_base_manifest_changed")
    return protocol, plan, odoo, base


def _preflight_action_bundle(freeze: dict, root: Path, plan: dict) -> str:
    bundle, bundle_hash = _referenced_json(root, freeze["action_bundle"],
                                           "cell-neutral action bundle")
    if (bundle.get("schema") != ACTION_SCHEMA
            or bundle.get("output_version") != scale_action_output_v065.OUTPUT_VERSION
            or bundle.get("same_for_base_and_selected_all_six_cells") is not True
            or any(cell["matched_bindings"]["action_contract"] != bundle_hash
                   for cell in plan["cells"])):
        raise FreezeError("shared_action_bundle_not_uniform")
    expected = {
        "full_validator": digest(Path(scale_action_contract.__file__).read_bytes()),
        "minimal_v062": digest(Path(scale_action_output_v062.__file__).read_bytes()),
        "minimal_v064": digest(Path(scale_action_output_v064.__file__).read_bytes()),
        "minimal_v065": digest(Path(scale_action_output_v065.__file__).read_bytes()),
        "vision_proxy": digest(Path(scale_vision_proxy.__file__).read_bytes()),
    }
    if bundle.get("source_sha256s") != expected:
        raise FreezeError("shared_action_source_bytes_changed")
    return bundle_hash


def _preflight_odoo_evidence(freeze: dict, root: Path, odoo_plan: dict,
                             worker_dir: Path) -> tuple[dict, dict]:
    runtime, runtime_hash = _referenced_json(root, freeze["odoo_runtime_bundle"],
                                             "Odoo runtime bundle")
    boundary, _ = _referenced_json(root, freeze["hidden_boundary_public"],
                                   "Odoo hidden boundary")
    gui, _ = _referenced_json(root, freeze["hidden_gui_public"],
                              "Odoo 100-task GUI audit")
    code_dir = Path(__file__).parent
    expected_sources = {name: _source(code_dir / name) for name in (
        "compose.yaml", "odoo_native_adapter.py", "reset.py", "verify.py",
        "worker_lease.py", "gui_controls.py", "hidden_factory.py",
        "partition_factory.py", "official_runner_v065.py",
    )}
    compose_text = (code_dir / "compose.yaml").read_text()
    if (runtime.get("schema") != RUNTIME_SCHEMA
            or odoo_plan["matched_bindings"]["runtime"] != runtime_hash
            or runtime.get("worker_partition") != "official_hidden"
            or runtime.get("source_sha256s") != expected_sources
            or not isinstance(runtime.get("odoo_image"), str)
            or not isinstance(runtime.get("postgres_image"), str)
            or re.fullmatch(r"odoo@sha256:[0-9a-f]{64}", runtime["odoo_image"]) is None
            or re.fullmatch(r"postgres@sha256:[0-9a-f]{64}", runtime["postgres_image"]) is None
            or runtime.get("odoo_image") not in compose_text
            or runtime.get("postgres_image") not in compose_text):
        raise FreezeError("odoo_runtime_not_frozen")
    taskset_hash = runtime.get("task_set_manifest_sha256")
    if (boundary.get("schema") != "envloop-odoo-hidden-boundary-public-v1"
            or boundary.get("official_hidden_candidates") != 100
            or boundary.get("v06_split_validator_passed") is not True
            or boundary.get("task_set_manifest_sha256") != taskset_hash
            or boundary.get("model_attempts") != 0
            or gui.get("candidate_cases") != 100
            or gui.get("cases_with_all_per_id_controls") != 100
            or gui.get("task_set_manifest_sha256") != taskset_hash
            or gui.get("final_database_and_physical_filestore_reset_exact") is not True
            or gui.get("actor_role_scoped_no_admin_group") is not True
            or gui.get("evaluator_select_only_on_scored_tables") is not True
            or gui.get("exclusive_worker_lease_interval_verified") is not True
            or gui.get("all_sources_visible_in_native_gui") is not True
            or gui.get("model_attempts") != 0):
        raise FreezeError("odoo_hidden_gui_or_source_gate_missing")
    if os.environ.get("ENVLOOP_ODOO_WORKER_DIR") != str(worker_dir):
        raise FreezeError("official_worker_not_selected")
    env_path = worker_dir / ".env"
    if not env_path.is_file() or env_path.is_symlink():
        raise FreezeError("official_worker_not_ready")
    env_fields = dict(line.split("=", 1) for line in env_path.read_text().splitlines()
                      if "=" in line and line.split("=", 1)[0] in (
                          "ODOO_PARTITION", "ODOO_PROJECT", "ODOO_PORT"))
    if env_fields.get("ODOO_PARTITION") != "official_hidden":
        raise FreezeError("official_worker_not_selected")
    private_taskset = worker_dir / "private" / "task_set_manifest.json"
    if not private_taskset.is_file() or private_taskset.is_symlink():
        raise FreezeError("official_taskset_unavailable")
    task_sets = json.loads(private_taskset.read_bytes())
    canonical_taskset_hash = digest(json.dumps(task_sets, sort_keys=True).encode())
    if (canonical_taskset_hash != taskset_hash
            or len(task_sets.get("official", [])) != 100
            or len(task_sets.get("selection", [])) != 20):
        raise FreezeError("official_taskset_changed")
    try:
        cell_final.validate_splits(task_sets)
    except ValueError:
        raise FreezeError("official_taskset_split_invalid") from None
    checkpoint = json.loads((worker_dir / "private" / "checkpoint_receipt.json").read_bytes())
    if (checkpoint.get("db_sha256") != runtime.get("db_checkpoint_sha256")
            or checkpoint.get("filestore_sha256") != runtime.get("filestore_checkpoint_sha256")):
        raise FreezeError("official_checkpoint_changed")
    return runtime, task_sets


def _preflight_budget(freeze: dict, root: Path, protocol: dict, odoo_plan: dict) -> dict:
    budget, _ = _referenced_json(root, freeze["budget_authority"],
                                 "atomic campaign budget authority")
    if (budget.get("schema") != BUDGET_SCHEMA
            or budget.get("status") != "funded_and_metered_before_dispatch"
            or budget.get("currency") != "USD"
            or budget.get("atomic_append_ledger_enabled") is not True
            or budget.get("provider_invoice_reconciliation_required") is not True
            or budget.get("cost_basis") !=
                "all_in_including_provider_compute_inference_storage_and_licenses"
            or type(budget.get("per_task_usd_micro_upper")) is not int
            or budget["per_task_usd_micro_upper"] <= 0
            or type(budget.get("campaign_usd_micro_ceiling")) is not int
            or budget["campaign_usd_micro_ceiling"] <
                100 * budget["per_task_usd_micro_upper"]
            or type(budget.get("available_balance_usd_micro")) is not int
            or budget["available_balance_usd_micro"] < budget["campaign_usd_micro_ceiling"]
            or not cell_final.is_hash(budget.get("pricing_source_sha256"))
            or not cell_final.is_hash(budget.get("provider_billing_authority_sha256"))
            or not cell_final.is_hash(budget.get("user_authorization_receipt_sha256"))
            or type(budget.get("max_model_samples_per_task")) is not int
            or not 1 <= budget["max_model_samples_per_task"] <= 90
            or type(budget.get("campaign_model_sample_cap")) is not int
            or budget["campaign_model_sample_cap"] <
                100 * budget["max_model_samples_per_task"]
            or type(budget.get("max_output_tokens_per_sample")) is not int
            or budget["max_output_tokens_per_sample"] <= 0
            or type(budget.get("campaign_output_token_cap")) is not int
            or budget["campaign_output_token_cap"] <
                budget["campaign_model_sample_cap"] * budget["max_output_tokens_per_sample"]
            or type(budget.get("max_wall_seconds_per_task")) is not int
            or not 1 <= budget["max_wall_seconds_per_task"] <= 720):
        raise FreezeError("atomic_budget_authority_missing")
    if (Decimal(budget["campaign_usd_micro_ceiling"]) / 1_000_000 !=
            cell_final.amount(protocol["budget"]["per_campaign_all_in_ceiling_usd"],
                              "campaign cap")):
        raise FreezeError("campaign_budget_mismatch")
    if (budget.get("max_actions_per_task") != odoo_plan["execution"]["max_actions_per_task"]
            or budget.get("max_output_tokens_per_sample") !=
            odoo_plan["sampling"]["max_output_tokens"]
            or budget["max_wall_seconds_per_task"] !=
            odoo_plan["execution"]["max_wall_seconds_per_task"]
            or budget["max_model_samples_per_task"] < budget["max_actions_per_task"]):
        raise FreezeError("task_action_or_token_budget_mismatch")
    ledger_name = budget.get("ledger_filename")
    if (not isinstance(ledger_name, str) or not ledger_name.endswith(".jsonl")
            or Path(ledger_name).name != ledger_name
            or (root / ledger_name).is_symlink()):
        raise FreezeError("atomic_budget_ledger_path_invalid")
    return budget


def preflight(freeze_path: Path, worker_dir: Path, task_id: str,
              output_dir: Path) -> dict:
    """Validate all shared gates before reading a hidden task or provider call."""
    if not freeze_path.is_file() or freeze_path.is_symlink():
        raise FreezeError("six_cell_freeze_missing")
    if freeze_path.stat().st_mode & 0o077:
        raise FreezeError("six_cell_freeze_not_private")
    try:
        raw = freeze_path.read_bytes()
        freeze = json.loads(raw)
        freeze = cell_final.exact(freeze, {
            "schema", "status", "cell_id", "output_version",
            "pre_campaign_manifest", "pre_campaign_plan", "action_bundle",
            "odoo_runtime_bundle", "hidden_boundary_public", "hidden_gui_public",
            "budget_authority", "ratified_utc", "provider_dispatch_enabled",
            "official_outcomes_before_ratification", "public_protocol_release_sha256",
            "campaign_id", "checkpoint",
        }, "Odoo official freeze")
    except (ValueError, UnicodeError, OSError, TypeError):
        raise FreezeError("six_cell_freeze_invalid") from None
    if (freeze["schema"] != SCHEMA or freeze["status"] != "ratified_pre_campaign"
            or freeze["cell_id"] != "odoo-community"
            or freeze["output_version"] != scale_action_output_v065.OUTPUT_VERSION
            or freeze["provider_dispatch_enabled"] is not True
            or freeze["official_outcomes_before_ratification"] != 0
            or not cell_final.is_hash(freeze["public_protocol_release_sha256"])
            or not isinstance(freeze["campaign_id"], str)
            or CAMPAIGN_ID.fullmatch(freeze["campaign_id"]) is None):
        raise FreezeError("six_cell_freeze_not_ratified")
    try:
        ratified = datetime.fromisoformat(freeze["ratified_utc"].replace("Z", "+00:00"))
        if ratified.tzinfo is None or ratified > datetime.now(timezone.utc):
            raise ValueError("invalid ratification time")
    except (ValueError, AttributeError, TypeError):
        raise FreezeError("six_cell_freeze_not_timestamped") from None
    root = freeze_path.parent
    protocol, plan, odoo_plan, odoo_base = _preflight_protocol(freeze, root)
    checkpoint = freeze["checkpoint"]
    if (type(checkpoint) is not dict or set(checkpoint) != {
            "role", "model_path", "checkpoint_sha256"}
            or checkpoint["role"] != "base"
            or checkpoint["model_path"] != matrix.STUDENT
            or checkpoint["checkpoint_sha256"] !=
            odoo_base["plan"]["bindings"]["checkpoint"]):
        raise FreezeError("base_checkpoint_not_frozen_or_selected_slot_unsupported")
    action_hash = _preflight_action_bundle(freeze, root, plan)
    budget = _preflight_budget(freeze, root, protocol, odoo_plan)
    worker_dir = worker_dir.resolve()
    if output_dir.exists() or output_dir.resolve().parent != (
            worker_dir / "private" / "official-model-attempts").resolve():
        raise FreezeError("official_output_path_not_private_or_new")
    runtime, task_sets = _preflight_odoo_evidence(freeze, root, odoo_plan,
                                                   worker_dir)
    official = {row["task_id"]: row for row in task_sets["official"]}
    if task_id not in official:
        raise FreezeError("task_not_in_frozen_official_set")
    if (sorted(task_sets["official"], key=lambda row: row["task_id"]) !=
            sorted(odoo_base["official"], key=lambda row: row["task_id"])):
        raise FreezeError("hidden_taskset_differs_from_six_cell_manifest")
    return {
        "status": "ready_for_separately_authorized_dispatch",
        "freeze_sha256": digest(raw),
        "plan_sha256": digest(cell_final.json_bytes(plan)),
        "action_bundle_sha256": action_hash,
        "runtime_bundle_sha256": freeze["odoo_runtime_bundle"]["sha256"],
        "task_id_sha256": digest(task_id.encode()),
        "package_sha256": official[task_id]["package_sha256"],
        "max_actions": budget["max_actions_per_task"],
        "max_output_tokens": budget["max_output_tokens_per_sample"],
        "per_task_usd_micro_upper": budget["per_task_usd_micro_upper"],
        "campaign_usd_micro_ceiling": budget["campaign_usd_micro_ceiling"],
        "campaign_model_sample_cap": budget["campaign_model_sample_cap"],
        "campaign_output_token_cap": budget["campaign_output_token_cap"],
        "max_model_samples": budget["max_model_samples_per_task"],
        "max_wall_seconds": budget["max_wall_seconds_per_task"],
        "sampling_seed": odoo_plan["sampling"]["seed"],
        "campaign_id": freeze["campaign_id"],
        "budget_ledger_path": str(root / budget["ledger_filename"]),
        "worker_dir": str(worker_dir),
        "private_task_id": task_id,
        "output_dir": str(output_dir),
        "provider_calls": 0,
        "hidden_task_model_observations": 0,
    }


def execute_frozen_base(plan: dict) -> dict:
    """One isolated official base task; callable only after full preflight.

    Its local ledger retains every full reservation on provider uncertainty.
    Selected checkpoints require a separate post-campaign matrix binding and
    are intentionally rejected by the base-only preflight above.
    """
    if not os.environ.get("TINKER_API_KEY"):
        raise FreezeError("provider_credential_missing_before_reservation")
    worker_dir = Path(plan["worker_dir"])
    task_id = plan["private_task_id"]
    out_dir = Path(plan["output_dir"])
    budget_path = Path(plan["budget_ledger_path"])
    limits = {
        "official_task_slots": 100,
        "model_samples": plan["campaign_model_sample_cap"],
        "output_tokens": plan["campaign_output_token_cap"],
        "all_in_usd_micro": plan["campaign_usd_micro_ceiling"],
    }
    budget = Budget(budget_path, limits)
    request = digest((plan["freeze_sha256"] + task_id +
                      str(out_dir.resolve())).encode())
    for resource, amount in (
        ("official_task_slots", 1),
        ("model_samples", plan["max_model_samples"]),
        ("output_tokens", plan["max_model_samples"] * plan["max_output_tokens"]),
        ("all_in_usd_micro", plan["per_task_usd_micro_upper"]),
    ):
        budget.reserve(resource, amount, f"{request}:{resource}")
    out_dir.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    out_dir.mkdir(mode=0o700)
    intent = {
        "schema": "cua-odoo-v065-official-task-intent-v1",
        "freeze_sha256": plan["freeze_sha256"],
        "task_id_sha256": plan["task_id_sha256"],
        "package_sha256": plan["package_sha256"],
        "request_sha256": request,
        "checkpoint_role": "base",
        "model": matrix.STUDENT,
        "provider_dispatch_started": False,
        "full_resource_reservation": {
            "model_samples": plan["max_model_samples"],
            "output_tokens": plan["max_model_samples"] * plan["max_output_tokens"],
            "all_in_usd_micro": plan["per_task_usd_micro_upper"],
        },
        "actual_provider_billed_usd": None,
    }
    intent_path = out_dir / "intent.json"
    intent_path.write_text(json.dumps(intent, sort_keys=True, indent=2) + "\n")
    intent_path.chmod(0o600)

    # Imports with worker-specific private state occur only after the six-cell
    # plan, hidden task set and resource reservation have passed.
    from playwright.sync_api import sync_playwright
    import tinker
    from factory import PRIVATE, local_config
    from gui_controls import browser_login
    from odoo_native_adapter import OdooNativeAdapter, VIEWPORT
    from reset import restore
    from verify import score
    from worker_lease import exclusive_worker_operation

    if PRIVATE.resolve() != (worker_dir / "private").resolve():
        raise FreezeError("official_worker_import_context_drifted")
    receipt = {**intent, "schema": "cua-odoo-v065-official-task-result-v1",
               "status": "started", "failure_class": None,
               "model_samples": [], "actions": [],
               "candidate_verifier_score": None, "official_score": None,
               "billing_reconciled": False, "independent_verifier": None,
               "started_utc": datetime.now(timezone.utc).isoformat()}

    def persist():
        path = out_dir / "result.json"
        path.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
        path.chmod(0o600)

    persist()
    service = None
    browser = None
    with exclusive_worker_operation("official_v065_base"):
        try:
            config = local_config()
            if config.get("ODOO_PARTITION") != "official_hidden":
                raise RuntimeError("Official worker partition changed")
            world = json.loads((PRIVATE / "partition_cases.json").read_bytes())
            matching = [case for family_cases in world["cases"].values()
                        for case in family_cases if case["id"] == task_id]
            if len(matching) != 1 or matching[0].get("partition") != "official_hidden":
                raise RuntimeError("Frozen official case unavailable")
            case = matching[0]
            credentials = json.loads((PRIVATE / "actor_credentials.json").read_bytes())
            before = restore()
            if not (before["business_snapshot_equal"] and
                    before["physical_filestore_equal_before_web_restart"]):
                raise RuntimeError("Official baseline restore differs")
            receipt["pre_model_reset_exact"] = True
            if score(task_id)["reward"] != 0.0:
                raise RuntimeError("Official task already solved at baseline")
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(viewport=VIEWPORT)
                browser_login(page, int(config["ODOO_PORT"]),
                              credentials["password"], credentials["login"])
                start_routes = {
                    "purchase": "purchase", "inventory": "inventory",
                    "sales": "sales", "crm": "crm",
                }
                family = case.get("family")
                if family not in start_routes:
                    raise RuntimeError("Unknown official Odoo workflow")
                page.goto(f"http://127.0.0.1:{config['ODOO_PORT']}/odoo/{start_routes[family]}")
                page.locator("body").wait_for()
                adapter = OdooNativeAdapter(page, task_id=task_id,
                    task_binding_sha256=plan["package_sha256"],
                    instruction=case["prompt"])
                renderer = scale_vision_proxy.QwenVisionRenderer.load()
                service = tinker.ServiceClient(user_metadata=
                    scale_vision_proxy.campaign_metadata(plan["campaign_id"]))
                backend = scale_vision_proxy.TinkerVisionBackend.from_service(
                    service, renderer, seed=plan["sampling_seed"])
                sampler = scale_vision_proxy.VisionSamplingAdapter(
                    backend, out_dir / "sampler-journal",
                    limits=scale_vision_proxy.Limits(
                        max_actions=plan["max_model_samples"],
                        output_tokens=plan["max_output_tokens"],
                        request_timeout_seconds=min(240, plan["max_wall_seconds"])))
                receipt["renderer_identity"] = renderer.identity
                receipt["sampler_binding_sha256"] = sampler.binding_sha256
                memory = ""
                wall_start = time.monotonic()
                for sample_index in range(plan["max_model_samples"]):
                    if time.monotonic() - wall_start > plan["max_wall_seconds"]:
                        receipt["status"] = "environment_wall_limit"
                        receipt["failure_class"] = "environment"
                        break
                    observation, _ = adapter.observe(memory=memory)
                    screenshot = observation.screenshot_bytes
                    (out_dir / f"frame-{sample_index}.png").write_bytes(screenshot)
                    rendered = scale_action_output_v065.render_for_model(observation)
                    request_id = "odoo-official-" + secrets.token_hex(16)
                    receipt["model_samples"].append({
                        "status": "intent_recorded_before_provider",
                        "request_id_sha256": digest(request_id.encode()),
                        "frame_sha256": digest(screenshot)})
                    persist()
                    receipt["provider_dispatch_intent_recorded"] = True
                    persist()
                    result = sampler.sample(request_id=request_id, **rendered)
                    receipt["provider_dispatch_started"] = bool(
                        result.get("new_dispatch") or result.get("dispatch_may_have_occurred"))
                    receipt["model_samples"][-1] = scale_vision_proxy.public_receipt(result)
                    persist()
                    if result["status"] != "completed":
                        receipt["status"] = "provider_sampling_error"
                        receipt["failure_class"] = "provider"
                        receipt["provider_error_subtype"] = result.get("error_subtype")
                        break
                    if (page.url != adapter.latest_url or
                            digest(page.screenshot(type="png")) !=
                            observation.screenshot["sha256"]):
                        receipt["status"] = "environment_frame_drift"
                        receipt["failure_class"] = "environment"
                        break
                    try:
                        action = scale_action_output_v065.normalize_model_action(
                            result["text"], observation,
                            current_frame_id=observation.frame_id)
                    except scale_action_contract.ContractError as exc:
                        receipt["actions"].append({"status": "model_output_rejected",
                                                   "code": exc.code})
                        receipt["status"] = "model_output_rejected"
                        receipt["failure_class"] = "model_interface"
                        break
                    try:
                        dispatched = adapter.dispatch(action)
                    except scale_action_contract.ContractError as exc:
                        receipt["actions"].append({"status": "gui_dispatch_rejected",
                                                   "code": exc.code})
                        receipt["status"] = "environment_dispatch_rejected"
                        receipt["failure_class"] = "environment"
                        break
                    receipt["actions"].append({
                        "status": "applied", "type": action["type"],
                        "contract_receipt": dispatched["public_contract_receipt"]})
                    persist()
                    memory = action["memory"]
                    if dispatched["finished"]:
                        receipt["status"] = "model_finished"
                        break
                    if sum(row["status"] == "applied" for row in receipt["actions"]) >= plan["max_actions"]:
                        receipt["status"] = "action_budget_reached"
                        break
                else:
                    receipt["status"] = "sample_budget_reached"
                browser.close()
                browser = None
            if receipt["failure_class"] not in ("provider", "environment"):
                verdict = score(task_id)
                receipt["independent_verifier"] = verdict
                receipt["candidate_verifier_score"] = 1 if verdict["reward"] == 1.0 else 0
        except Exception as exc:
            receipt["pre_reset_status"] = receipt["status"]
            receipt["status"] = "infrastructure_invalid"
            receipt["failure_class"] = "infrastructure"
            receipt["error_type"] = type(exc).__name__
        finally:
            if browser is not None:
                try: browser.close()
                except Exception as exc: receipt["browser_close_error_type"] = type(exc).__name__
            if service is not None:
                try:
                    service.close("success" if receipt["failure_class"] not in (
                        "provider", "infrastructure") else "errored").result(timeout=30)
                    receipt["tinker_session_closed"] = True
                except Exception as exc:
                    receipt["tinker_close_error_type"] = type(exc).__name__
            try:
                final_reset = restore()
                receipt["post_model_reset_exact"] = bool(
                    final_reset["business_snapshot_equal"] and
                    final_reset["physical_filestore_equal_before_web_restart"])
            except Exception as exc:
                receipt["post_model_reset_exact"] = False
                receipt["post_reset_error_type"] = type(exc).__name__
            if not receipt.get("post_model_reset_exact"):
                receipt["status"] = "infrastructure_invalid"
                receipt["failure_class"] = "infrastructure"
                receipt["candidate_verifier_score"] = None
            if receipt["failure_class"] in ("provider", "environment", "infrastructure"):
                receipt["candidate_verifier_score"] = None
            # The post-attempt billing and six-cell result ledger own official
            # promotion. This runner does not turn a readback into a paper score.
            receipt["official_score"] = None
            receipt["finished_utc"] = datetime.now(timezone.utc).isoformat()
            persist()
    return {"status": receipt["status"], "failure_class": receipt["failure_class"],
            "candidate_verifier_score": receipt["candidate_verifier_score"],
            "official_score": None,
            "task_id_sha256": plan["task_id_sha256"],
            "provider_calls": sum(sample.get("new_dispatch") is True
                                  for sample in receipt["model_samples"]),
            "post_model_reset_exact": receipt.get("post_model_reset_exact")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--worker-dir", type=Path, required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--execute", action="store_true",
                        help="Explicit dispatch after ratified six-cell freeze")
    args = parser.parse_args()
    try:
        result = preflight(args.freeze, args.worker_dir, args.task_id,
                           args.out_dir)
    except FreezeError as exc:
        print(json.dumps({"status": "blocked_before_provider_or_model_dispatch",
                          "reason_code": exc.code, "provider_calls": 0,
                          "hidden_task_model_observations": 0}, sort_keys=True))
        return 2
    except Exception:
        print(json.dumps({"status": "blocked_before_provider_or_model_dispatch",
                          "reason_code": "preflight_internal_error", "provider_calls": 0,
                          "hidden_task_model_observations": 0}, sort_keys=True))
        return 2
    if not args.execute:
        print(json.dumps({"status": "gate_ready_execute_flag_required",
                          "task_id_sha256": result["task_id_sha256"],
                          "provider_calls": 0,
                          "hidden_task_model_observations": 0}, sort_keys=True))
        return 2
    try:
        outcome = execute_frozen_base(result)
    except FreezeError as exc:
        print(json.dumps({"status": "blocked_before_provider_or_model_dispatch",
                          "reason_code": exc.code, "provider_calls": 0,
                          "hidden_task_model_observations": 0}, sort_keys=True))
        return 2
    print(json.dumps(outcome, sort_keys=True))
    return 0 if outcome["candidate_verifier_score"] is not None else 2


if __name__ == "__main__":
    raise SystemExit(main())
