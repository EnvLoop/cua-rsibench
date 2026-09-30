"""One opaque GitLab FINAL task through the existing full-study dispatcher.

FinalGate owns the 24-campaign/3000-result protocol and one dispatched dollar
envelope. This worker reuses the selection actor loop, sampler, GUI dispatcher
and cold-reset backend. The common FullGitBackend owns saved Git readback and
formal scoring before reset. Construction reads source/freeze metadata only.
"""

from __future__ import annotations

from contextlib import contextmanager
import copy
from decimal import Decimal, ROUND_CEILING
import importlib
import json
import math
import os
from pathlib import Path
import time
from types import FunctionType, SimpleNamespace

from cursibench import full_study_final_dispatch_v1 as final
from cursibench import full_study_matrix_v1 as matrix
from . import bootstrap, factory, operators, reset, runtime, verify
from . import selection_worker_v066 as selection


PARTITION = "final_candidate_unsealed"
COMMAND_FIELDS = {
    "schema", "study_id", "cell_id", "owner_slot", "task_id", "package_sha256",
    "checkpoint_sha256", "sampler_path", "expected_initial_state_sha256",
    "attempt_id", "retry_index", "retry_rule_sha256", "action_profile", "sampling",
    "max_actions", "max_wall_seconds", "matched_bindings", "reserve_usd",
}
COMMON_MODULE = "gitlab_world.full_git_model_workers_v1"


class GitLabFinalWorkerError(ValueError):
    """Fixed labels only; no task, oracle, credential or provider contents."""


def require(ok: bool, code: str) -> None:
    if not ok:
        raise GitLabFinalWorkerError(code)


def _amount(raw, *, positive=True) -> Decimal:
    require(type(raw) is str, "final_decimal_string_required")
    try:
        value = Decimal(raw)
    except Exception:
        raise GitLabFinalWorkerError("final_decimal_invalid") from None
    require(value.is_finite() and (value > 0 if positive else value >= 0), "final_decimal_invalid")
    return value


def _private_dict(path: Path) -> dict:
    path = Path(path)
    require(path.is_file() and not path.is_symlink() and path.stat().st_mode & 0o077 == 0
            and 0 < path.stat().st_size <= final.MAX_PRIVATE_BYTES,
            "final_private_json_unsafe")
    try:
        value = json.loads(path.read_bytes())
    except (ValueError, UnicodeDecodeError):
        raise GitLabFinalWorkerError("final_private_json_invalid") from None
    require(type(value) is dict, "final_private_json_invalid")
    return value


def _write(root: Path, name: str, value) -> dict:
    path = root / name
    final.private_write_new(path, final.canonical(value))
    return final.reference(root, path)


def _baseline_only(task, before, after):
    # The frozen final grader's first predicate rejects an unchanged persisted
    # business state. This callback is used only in the existing pre-reset gate.
    require(task.get("partition") == PARTITION and before == after and
            type(before.get("business_sha256")) is str and
            before.get("schema") == verify.SCHEMA,
            "final_baseline_only_gate_invalid")
    verdict = verify.evaluate_final_task(task, before, after, inspect_live_git=True)
    require(type(verdict.get("score")) is float and verdict["score"] == 0.0 and
            verdict.get("no_regression") is False, "final_original_baseline_verdict_invalid")
    return {"reward": verdict["score"]}


def _function(function, scope):
    copied = FunctionType(function.__code__, scope, function.__name__,
                          function.__defaults__, function.__closure__)
    copied.__kwdefaults__ = function.__kwdefaults__
    return copied


class _SealedFinalBackend(selection.RealGitLabSelectionBackend):
    """Private lookup occurs only inside the paid, gated application open."""

    def __init__(self, identities: list[dict]):
        self._sealed = {row["task_id"]: row["package_sha256"] for row in identities}
        require(len(identities) == len(self._sealed) == 100, "final_sealed_view_requires_100")

    def _load_selection_task(self, identity):
        require(type(identity) is dict and set(identity) == {"task_id", "package_sha256"} and
                self._sealed.get(identity["task_id"]) == identity["package_sha256"],
                "task_not_in_sealed_final_view")
        private = runtime.PRIVATE
        needed = (bootstrap.WORLD_FILE, bootstrap.PROGRESS_FILE, operators.CREDENTIALS,
                  operators.RECEIPT, private / "baseline-persisted-state.json", reset.STATE_FILE,
                  private / "cohort-plan.private.json", private / "native-acl.private.json")
        require(selection.train._mode_private(private, directory=True) and
                all(selection.train._mode_private(path, directory=False) for path in needed),
                "final_private_cohort_or_operator_missing")
        world_raw = bootstrap.WORLD_FILE.read_bytes()
        world = bootstrap.world()
        tasks = bootstrap.all_tasks(world)
        matches = [row for row in tasks if row["task_id"] == identity["task_id"]]
        require(len(matches) == 1 and matches[0]["partition"] == PARTITION,
                "final_task_not_unique_or_cross_partition")
        original = matches[0]
        plan = _private_dict(private / "cohort-plan.private.json")
        roster = plan.get("task_roster")
        require(type(roster) is list and len(roster) == 100 and
                {row["task_id"]: row["package_sha256"] for row in roster} == self._sealed,
                "sealed_final_view_differs_from_qualified_cohort")
        row = next(row for row in roster if row["task_id"] == identity["task_id"])
        baseline = _private_dict(private / "baseline-persisted-state.json")
        package = {
            "world_sha256": final.sha(world_raw),
            "baseline_business_sha256": baseline["business_sha256"],
            "native_acl_sha256": final.sha((private / "native-acl.private.json").read_bytes()),
            "task": original,
        }
        require(row.get("task_object_sha256") == final.sha(factory.canonical(original)) and
                identity["package_sha256"] == final.sha(factory.canonical(package)) and
                plan.get("world_sha256") == package["world_sha256"] and
                plan.get("native_acl_sha256") == package["native_acl_sha256"],
                "final_task_package_or_cohort_binding_changed")
        projects = [row for row in bootstrap.all_projects(world)
                    if row["full_path"] == original["project_family"]]
        require(len(projects) == 1 and projects[0]["partition"] == PARTITION,
                "final_project_not_in_sealed_partition")
        credentials = _private_dict(operators.CREDENTIALS)
        operator = _private_dict(operators.RECEIPT)
        progress = _private_dict(bootstrap.PROGRESS_FILE)
        own = operator.get("identities", {}).get(PARTITION, {})
        actor = credentials.get(PARTITION)
        require(set(credentials) == set(operators.PARTITIONS) and type(actor) is dict and
                type(actor.get("username")) is str and type(actor.get("password")) is str and
                bool(actor["password"]) and operator.get("root_admin_is_actor") is False and
                own.get("group_id") == progress["groups"].get(projects[0]["group_path"]),
                "final_scoped_non_admin_operator_invalid")
        task = {**identity, "visible_instruction": original["prompt"]}
        return original, projects[0], actor, task

    @contextmanager
    def open(self, identity):
        original_open = selection.RealGitLabSelectionBackend.open.__wrapped__
        scope = dict(original_open.__globals__)
        scope["oracle"] = SimpleNamespace(evaluate_selection_task=_baseline_only)
        isolated = _function(original_open, scope)
        with contextmanager(isolated)(self, identity) as active:
            yield active


class _FinalEnvelope:
    """Durable sub-operation intents inside the existing final reservation."""

    def __init__(self, command, directory: Path, storage_cap: str):
        self.command, self.directory = command, directory
        self.intent = {"storage_application_usd_cap": storage_cap}
        self.ceiling = _amount(command["reserve_usd"])
        self.allocated = Decimal(0)
        self.calls = []

    def dispatch_paid(self, *, attempt_id, category, work, request, reserve_usd,
                      resource_reservation, provider):
        quote = _amount(reserve_usd)
        require(category in {"storage_application", "tinker"} and resource_reservation == {} and
                type(attempt_id) is str and attempt_id.startswith(self.command["attempt_id"] + "-") and
                not any(row["attempt_id"] == attempt_id for row in self.calls) and
                self.allocated + quote <= self.ceiling and callable(provider),
                "final_suboperation_reservation_invalid_or_exhausted")
        prefix = f"suboperation-{len(self.calls):03d}"
        intent = {
            "schema": "envloop-gitlab-final-suboperation-intent-v1",
            "parent_attempt_id": self.command["attempt_id"], "attempt_id": attempt_id,
            "parent_command_sha256": final.sha(final.canonical(self.command)),
            "category": category, "reserve_usd": reserve_usd,
            "request_sha256": final.sha(final.canonical(request)),
            "work_sha256": final.sha(final.canonical(work)),
            "uses_existing_final_reservation": True, "automatic_replay_authorized": False,
        }
        _write(self.directory, prefix + "-intent.private.json", intent)
        self.allocated += quote
        self.calls.append(intent)
        try:
            result = provider(request)
        except BaseException as error:
            _write(self.directory, prefix + "-uncertain.private.json", {
                "schema": "envloop-gitlab-final-suboperation-uncertain-v1",
                "attempt_id": attempt_id, "error_type": type(error).__name__,
                "automatic_replay_authorized": False,
            })
            raise
        result_sha = final.sha(selection._canonical(result))
        _write(self.directory, prefix + "-result.private.json", {
            "schema": "envloop-gitlab-final-suboperation-result-v1",
            "attempt_id": attempt_id, "result_sha256": result_sha, "result": result,
        })
        return {"result": result, "result_sha256": result_sha,
                "billing_state": "published_rate_nominal_inside_final_envelope"}


class _ExpectedInitialBackend:
    def __init__(self, backend, initial_sha):
        self.backend, self.initial_sha = backend, initial_sha
        self.proof_context = None

    def set_output_root(self, root):
        return self.backend.set_output_root(root)

    @contextmanager
    def open(self, identity):
        with self.backend.open(identity) as active:
            require(active.pre_restore_exact is True and
                    active.baseline_semantic["business_snapshot"]["business_sha256"] == self.initial_sha,
                    "final_qualified_initial_state_mismatch_before_model")
            project, progress = verify._context(active.original_task)
            self.proof_context = copy.deepcopy({"task": active.original_task, "project": project,
                                               "progress": progress,
                                               "before": active.baseline_semantic["business_snapshot"]})
            yield active


class GitLabFullGitFinalWorker:
    """Concrete TrustedFinalWorker; FinalController remains the only controller."""

    def __init__(self, *, gate: final.FinalGate, binding_path: Path,
                 binding_file_sha256: str, final_output_root: Path,
                 cohort_freeze_path: Path, enable_live: bool = False):
        require(type(gate) is final.FinalGate, "real_final_gate_required")
        self.gate = gate
        self.binding_path, self.binding_file_sha256 = Path(binding_path), binding_file_sha256
        self.final_output_root = Path(final_output_root).resolve()
        self.cohort_freeze_path = Path(cohort_freeze_path)
        _private_dict(self.cohort_freeze_path)
        self.cohort_source_file_sha256 = final.sha(self.cohort_freeze_path.read_bytes())
        self.enable_live = enable_live
        require(self.final_output_root.is_relative_to(gate.work_root.resolve()),
                "final_output_root_outside_gate_work")
        self.cell = next(row for row in gate.plan["cells"] if row["cell_id"] == "gitlab")
        common, binding = self._common_binding()
        slots = [self.cell["base"]] + list(self.cell["researcher_plans"].values())
        require(len(slots) == 5 and set(self.cell["execution_evidence_owner_by_slot"]) ==
                {"shared-base", *matrix.RESEARCHERS} and
                set(self.cell["execution_evidence_owner_by_slot"].values()) <= {"shared-base", *matrix.RESEARCHERS},
                "final_uniform_five_slot_source_policy_required")
        require(all(all(slot["bindings"][name] == self.cell["matched_bindings"][name]
                        for name in ("source_snapshot", "runtime", "action_contract", "verifier"))
                    for slot in slots), "final_five_slot_source_bindings_differ")
        identities = [row for chunk in self.cell["base"]["chunks"] for row in chunk["tasks"]]
        require(len(identities) == 100 and len({row["task_id"] for row in identities}) == 100,
                "final_factory_sealed_100_metadata_required")
        self.full_git_model_binding_sha256 = binding["binding_sha256"]
        self.runtime_sha256 = selection.runtime_sha256()
        self.verifier_sha256 = selection.verifier_sha256()
        self.adapter_sha256 = selection.adapter_sha256()
        self._identity = {
            "schema": final.WORKER_SCHEMA, "cell_id": "gitlab",
            "source_snapshot_sha256": self.cell["matched_bindings"]["source_snapshot"],
            "runtime_sha256": self.runtime_sha256,
            "action_contract_sha256": self.cell["matched_bindings"]["action_contract"],
            "verifier_sha256": self.verifier_sha256, "adapter_source_sha256": self.adapter_sha256,
            "action_profile": "scale-action-profile-v0.6.6", "observation_kind": "screenshot",
            "actor_capability": "current_frame_gui_actions_only", "evaluator_isolated": True,
            "cold_reset_supported": True, "saved_state_readback_supported": True,
        }
        final._worker_identity(self, self.cell, gate.frozen.ratification)

    @property
    def identity(self):
        return dict(self._identity)

    def _common_binding(self):
        common = importlib.import_module(COMMON_MODULE)
        value = _private_dict(self.binding_path)
        require(final.sha(self.binding_path.read_bytes()) == self.binding_file_sha256 and
                final.canonical(value) == final.canonical(common.public_binding()),
                "final_whole_proof_binding_changed")
        return common, value

    def _command(self, command, output_dir):
        require(self.enable_live is True, "final_explicit_live_required")
        common, binding = self._common_binding()
        require(final.sha(self.cohort_freeze_path.read_bytes()) == self.cohort_source_file_sha256,
                "final_uniform_cohort_source_changed")
        require(type(command) is dict and set(command) == COMMAND_FIELDS and
                command.get("schema") == final.COMMAND_SCHEMA and command.get("cell_id") == "gitlab" and
                command.get("study_id") == self.gate.plan["study_id"] and
                command.get("matched_bindings") == self.cell["matched_bindings"] and
                command.get("action_profile") == "scale-action-profile-v0.6.6" and
                self.runtime_sha256 == selection.runtime_sha256() and
                self.verifier_sha256 == selection.verifier_sha256() and
                self.adapter_sha256 == selection.adapter_sha256(),
                "final_command_or_legacy_source_binding_changed")
        owner = command["owner_slot"]
        require(owner in set(self.cell["execution_evidence_owner_by_slot"].values()), "final_owner_unknown")
        slot = self.cell["base"] if owner == "shared-base" else self.cell["researcher_plans"][owner]
        tasks = [row for chunk in self.cell["base"]["chunks"] for row in chunk["tasks"]]
        identities = [{"task_id": row["task_id"], "package_sha256": row["package_sha256"]} for row in tasks]
        identity = {"task_id": command["task_id"], "package_sha256": command["package_sha256"]}
        require(len(identities) == 100 and len({row["task_id"] for row in identities}) == 100 and
                identity in identities, "final_task_outside_sealed_100_view")
        ordinal = identities.index(identity)
        retry = command["retry_index"]
        require(type(retry) is int and retry in (0, 1) and
                command["attempt_id"] == f"final-{matrix.CELLS.index('gitlab'):02d}-{owner}-{ordinal:03d}-{retry}" and
                command["retry_rule_sha256"] == (final.RETRY_RULE_SHA256 if retry else None) and
                command["checkpoint_sha256"] == slot["bindings"]["checkpoint"] and
                command["sampling"] == slot["sampling"] and
                type(command["max_actions"]) is int and command["max_actions"] == slot["execution"]["max_actions_per_task"] and
                0 < command["max_actions"] <= 90 and
                type(command["max_wall_seconds"]) is int and command["max_wall_seconds"] == slot["execution"]["max_wall_seconds_per_task"] and
                0 < command["max_wall_seconds"] <= 2880 and
                command["expected_initial_state_sha256"] == self.gate.initial_state_by_task["gitlab"][identity["task_id"]],
                "final_checkpoint_policy_or_initial_state_changed")
        sampler = command["sampler_path"]
        require((owner == "shared-base" and sampler is None) or
                (owner != "shared-base" and type(sampler) is str and final.SAMPLER_PATH.fullmatch(sampler) is not None and
                 final.sha(sampler.encode()) == command["checkpoint_sha256"]), "final_sampler_not_bound")
        expected_category = "shared_base_final" if owner == "shared-base" else "selected_final"
        reserved = self.gate.budget.owner_attempts("gitlab:" + owner).get(command["attempt_id"])
        require(type(reserved) is dict and reserved.get("status") == "dispatched" and
                reserved.get("category") == expected_category and
                reserved.get("request_sha256") == final.sha(final.canonical(command)) and
                _amount(reserved["reserved_usd"]) == _amount(command["reserve_usd"]),
                "final_existing_dispatched_reservation_required")
        output_dir = Path(output_dir)
        require(output_dir.parent.resolve() == self.final_output_root and output_dir.name == command["attempt_id"] and
                selection.train._mode_private(output_dir, directory=True), "final_controller_output_binding_changed")
        return common, binding, identities

    def run_once(self, command: dict, output_dir: Path) -> dict:
        common, binding, identities = self._command(command, output_dir)
        output_dir = Path(output_dir)
        _write(output_dir, "worker-intent.private.json", {
            "schema": "envloop-gitlab-full-git-final-worker-intent-v1",
            "command_sha256": final.sha(final.canonical(command)),
            "whole_proof_binding_file_sha256": self.binding_file_sha256,
            "whole_proof_binding_sha256": binding["binding_sha256"],
            "task_view_identities_sha256": final.sha(final.canonical(identities)),
            "uniform_final_slot_model_source_binding_sha256": self.full_git_model_binding_sha256,
            "uniform_final_slot_cohort_source_file_sha256": self.cohort_source_file_sha256,
            "automatic_action_or_provider_retry": False,
        })
        return self._run_episode(command, output_dir, common, binding, identities)

    def _run_episode(self, command, output_dir, common, binding, identities):
        started_at = int(time.time())
        wall_started = time.monotonic()
        training, _training_sha = self.gate.frozen.student_training_configuration()
        sampling = command["sampling"]
        require(training.get("action_profile") == "scale-action-profile-v0.6.6" and training.get("model") == selection.MODEL and
                type(sampling.get("seed")) is int and type(sampling.get("max_output_tokens")) is int and
                0 < sampling["max_output_tokens"] <= 4096,
                "final_frozen_sampling_invalid")
        temperature = Decimal(str(sampling["temperature"]))
        require(temperature.is_finite() and 0 <= temperature <= 2, "final_sampling_temperature_invalid")
        policy = {**sampling, "temperature": float(temperature), "max_actions_per_task": command["max_actions"],
                  "max_wall_seconds_per_task": command["max_wall_seconds"]}
        cap_intents = self.gate.frozen.plan["campaign_intents"]
        owner = command["owner_slot"]
        cap_row = next(row for row in cap_intents if row["cell_id"] == "gitlab" and
                       (owner == "shared-base" or row["researcher_id"] == owner))
        cap = _amount(cap_row["storage_application_usd_cap"])
        app_quote = (cap * Decimal(command["max_wall_seconds"]) / Decimal(matrix.CAMPAIGN_HOURS * 3600)).quantize(
            Decimal("0.000000001"), rounding=ROUND_CEILING)
        session = _FinalEnvelope(command, output_dir, str(cap))
        episode = output_dir / "native-episode"
        core = object.__new__(selection.GitLabSelectionWorker)
        core.enable_live = True
        core.runtime_sha256, core.verifier_sha256, core.adapter_sha256 = (
            self.runtime_sha256, self.verifier_sha256, self.adapter_sha256)
        formal_backend = common.FullGitBackend(_SealedFinalBackend(identities), partition=PARTITION,
                                              binding=binding, cohort_freeze_path=self.cohort_freeze_path)
        core.backend = _ExpectedInitialBackend(formal_backend, command["expected_initial_state_sha256"])
        core.backend.set_output_root(episode)
        vision = core._load_vision()
        require(bool(os.environ.get("TINKER_API_KEY")), "final_tinker_key_missing_before_paid")
        sampler = selection._RealTinkerSampler(
            checkpoint_path=command["sampler_path"], checkpoint_sha256=command["checkpoint_sha256"],
            vision=vision, seed=policy["seed"], temperature=policy["temperature"],
            max_output_tokens=policy["max_output_tokens"],
            campaign_metadata={"study_id": command["study_id"], "cell_id": "gitlab",
                               "owner_slot": owner, "final_attempt_id": command["attempt_id"]})
        succeeded = False
        outcome = None
        try:
            item = core._task_episode(
                session=session, started={"attempt_id": command["attempt_id"]},
                identity={"task_id": command["task_id"], "package_sha256": command["package_sha256"]},
                ordinal=0, out_dir=episode, training=training, policy=policy,
                app_quote=app_quote, vision=vision, checkpoint_sha256=command["checkpoint_sha256"],
                sampler_provider=sampler)
            core._verify_task_receipt(output_dir, item)
            outcome = self._outcome(command, output_dir, episode, item, training, started_at, wall_started,
                                    core.backend.proof_context, common, binding)
            succeeded = True
        finally:
            sampler.close(success=succeeded)
        outcome["wall_time_ms"] = max(0, int((time.monotonic() - wall_started) * 1000))
        outcome["finished_at"] = int(time.time())
        require(outcome["wall_time_ms"] <= command["max_wall_seconds"] * 1000,
                "final_total_wall_including_sampler_close_exceeds_policy")
        return outcome

    def _outcome(self, command, output, episode, item, training, started_at, wall_started,
                 proof_context, common, binding):
        saved = _private_dict(episode / "saved-state.private.json")
        require(saved.get("full_git_tree_verified") is True and
                saved.get("full_git_model_binding_sha256") == binding["binding_sha256"] and
                saved.get("captured_boolean_is_authority") is False and type(proof_context) is dict,
                "final_formal_full_git_proof_missing")
        artifacts = episode / "artifacts"
        identity = {"task_id": command["task_id"], "package_sha256": command["package_sha256"]}
        require(final.sha(self.cohort_freeze_path.read_bytes()) == self.cohort_source_file_sha256,
                "final_cohort_source_changed_after_reset")
        audited = common._verify_saved_proof(artifacts, saved, identity, proof_context["before"], binding,
                                             cohort_source_file_sha256=self.cohort_source_file_sha256)
        require(audited["partition"] == PARTITION and audited["task_id"] == command["task_id"] and
                audited["verdict"] == saved["full_git_original_verdict"] and
                audited["reward"] == saved["independent_score"]["reward"],
                "final_formal_git_proof_rederivation_changed")
        common._write(artifacts, "full-git-post-reset-audit.private.json", common.canonical(audited))
        native_reset = _private_dict(episode / "reset.private.json")
        before_path, before_raw = final.private_reference(episode, native_reset["baseline_state_ref"], "baseline")
        after_path, after_raw = final.private_reference(episode, native_reset["restored_state_ref"], "restored")
        before, after = _private_dict(before_path), _private_dict(after_path)
        initial = command["expected_initial_state_sha256"]
        require(before == after and before_raw == after_raw and
                before["business_snapshot"]["business_sha256"] == initial,
                "final_initial_or_restored_semantic_state_changed")
        rows = json.loads((episode / "actions.private.json").read_bytes())
        require(type(rows) is list and rows, "final_actor_trace_missing")
        native = _private_dict(episode / "verifier.private.json")
        native_cost = _private_dict(episode / "cost.private.json")
        subtype = {"task_wall_timeout": "actor_wall_budget", "action_budget_exhausted": "actor_action_budget"}.get(
            native["model_outcome"], "none")
        score = 0 if subtype != "none" else item["result_row"]["score"]
        inputs = sum(row["usage"]["input_tokens"] for row in rows)
        images = sum(row["usage"]["image_tokens"] for row in rows)
        outputs = sum(row["usage"]["output_tokens"] for row in rows)
        model_cost = sum((_amount(selection.GitLabSelectionWorker._model_quote(
            training, row["usage"]["input_tokens"], row["usage"]["output_tokens"]), positive=False) for row in rows), Decimal(0))
        cost = model_cost + _amount(native_cost["application_nominal_metered_usd"], positive=False)
        require(cost <= _amount(command["reserve_usd"]), "final_cost_exceeds_existing_reservation")
        usage = _write(output, "provider-usage.private.json", {
            "schema": final.USAGE_SCHEMA, "attempt_id": command["attempt_id"],
            "cost_basis": "published_rate_nominal", "cost_usd": str(cost),
            "input_tokens": inputs, "image_tokens": images, "output_tokens": outputs,
            "provider_billed_tokens": None, "provider_invoice_sha256": None,
        })
        reset_ref = _write(output, "cold-reset.private.json", {
            "schema": final.RESET_SCHEMA, "task_id": command["task_id"], "package_sha256": command["package_sha256"],
            "attempt_id": command["attempt_id"], "fresh_environment": True, "restored_after_attempt": True,
            "initial_state_sha256": initial, "restored_state_sha256": initial,
        })
        observations = _write(output, "observations.private.json", {
            "schema": final.TRACE_SCHEMA, "attempt_id": command["attempt_id"], "kind": "observations",
            "action_profile": "scale-action-profile-v0.6.6", "count": len(rows), "screenshot_only": True,
        })
        action_count = sum(row["action"] is not None for row in rows)
        actions = _write(output, "actions.private.json", {
            "schema": final.TRACE_SCHEMA, "attempt_id": command["attempt_id"], "kind": "actions",
            "action_profile": "scale-action-profile-v0.6.6", "count": action_count, "current_frame_validated": True,
        })
        state = final.reference(output, episode / "saved-state.private.json")
        verifier_ref = _write(output, "independent-verifier.private.json", {
            "schema": final.VERIFIER_SCHEMA, "task_id": command["task_id"], "package_sha256": command["package_sha256"],
            "attempt_id": command["attempt_id"], "saved_state_sha256": state["sha256"], "score": score,
            "no_regression_checked": True, "no_regression_passed": native["persisted_oracle"]["checks_passed"],
            "independent_of_actor": True, "gold_withheld_from_actor": True,
        })
        wall_ms = max(0, int((time.monotonic() - wall_started) * 1000))
        latency_ms = sum(int(row["provider_elapsed_seconds"] * 1000) for row in rows)
        require(wall_ms <= command["max_wall_seconds"] * 1000 and latency_ms <= wall_ms,
                "final_complete_wall_or_provider_latency_exceeds_policy")
        return {
            "schema": final.OUTCOME_SCHEMA, "status": "scored", "score": score, "failure_type": None,
            "started_at": started_at, "finished_at": int(time.time()),
            "cost_basis": "published_rate_nominal", "cost_usd": str(cost), "usage": usage,
            "reset": reset_ref, "saved_state": state, "verifier": verifier_ref,
            "observation_trace": observations, "action_trace": actions,
            "action_count": action_count, "turn_count": len(rows), "wall_time_ms": wall_ms,
            "provider_latency_ms": latency_ms, "timeout_subtype": subtype,
            "action_profile": "scale-action-profile-v0.6.6",
        }


def final_worker_factory(*, gate: final.FinalGate, full_git_binding_path: Path,
                         full_git_binding_file_sha256: str, final_output_root: Path,
                         cohort_freeze_path: Path, enable_live: bool = False):
    """Construct one 100-task worker for all five existing gated final slots.

    Construction reads only the gate's sealed identity metadata and source
    binding. Hidden task bodies are read inside the original paid backend open.
    Pass the returned worker as the GitLab entry in FinalController's six-cell
    worker mapping; this factory never constructs or bypasses FinalGate.
    """
    return GitLabFullGitFinalWorker(
        gate=gate, binding_path=full_git_binding_path,
        binding_file_sha256=full_git_binding_file_sha256,
        final_output_root=final_output_root, cohort_freeze_path=cohort_freeze_path,
        enable_live=enable_live)


__all__ = ["GitLabFullGitFinalWorker", "GitLabFinalWorkerError", "final_worker_factory"]
