"""One-shot, no-replay Tinker runner for the separate real-GUI diagnostic.

The run needs task-disjoint public-train GUI episodes and an immutable public
plan witness. It is never an official researcher campaign or final evaluation.
Every external operation receives a durable private intent before invocation.
An interrupted/ambiguous operation remains charged and is never replayed.
"""

from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import time
from typing import Callable
import urllib.request

from . import full_study_qwen_runtime_gate_v1 as runtime_gate
from . import qwen38_real_gui_diagnostic_v1 as diagnostic


WITNESS_SCHEMA = "cua-qwen38-real-gui-diagnostic-freeze-v1"
WITNESS_PATH = "docs/evidence/qwen38-real-gui-diagnostic-freeze.json"
RUN_SCHEMA = "cua-qwen38-real-gui-diagnostic-run-v1"
PRIVATE_RESULT_SCHEMA = "cua-qwen38-real-gui-diagnostic-result-private-v1"
PUBLIC_RESULT_SCHEMA = "cua-qwen38-real-gui-diagnostic-result-public-v1"
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
MAX_BYTES = 8_000_000


class RunError(ValueError):
    """Fixed labels; no provider text, task instructions or URI escapes."""


def require(ok: bool, code: str) -> None:
    if not ok:
        raise RunError(code)


def _write_new(path: Path, raw: bytes, *, mode: int = 0o600) -> None:
    require(not path.exists() and not path.is_symlink() and
            len(raw) <= MAX_BYTES,
            "diagnostic_private_output_exists_or_oversized")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def immutable_witness(*, public_commit: str, plan_sha256: str,
                      prereg_sha256: str,
                      fetcher: Callable[[str], bytes] | None = None) -> str:
    require(type(public_commit) is str and
            HEX40.fullmatch(public_commit) is not None,
            "diagnostic_immutable_commit_required")
    url = ("https://raw.githubusercontent.com/EnvLoop/cua-rsibench/" +
           public_commit + "/" + WITNESS_PATH)
    if fetcher is None:
        request = urllib.request.Request(url, headers={
            "User-Agent": "EnvLoop-Qwen38-diagnostic-freeze/1.0"})
        with urllib.request.urlopen(request, timeout=20) as response:
            require(response.url == url, "diagnostic_public_witness_redirected")
            raw = response.read(MAX_BYTES + 1)
    else:
        raw = fetcher(url)
    require(type(raw) is bytes and 0 < len(raw) <= MAX_BYTES,
            "diagnostic_public_witness_missing_or_oversized")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RunError("diagnostic_public_witness_invalid_json") from None
    require(value == {
        "schema": WITNESS_SCHEMA,
        "status": "frozen_before_diagnostic_paid_dispatch",
        "plan_sha256": plan_sha256,
        "prereg_sha256": prereg_sha256,
        "student_model": diagnostic.MODEL,
        "eligible_split": "train",
        "task_disjoint_holdout": True,
        "minimum_distinct_workflows": 3,
        "optimizer_steps": 64,
        "pricing_quote_is_dispatch_gate": False,
        "diagnostic_only": True,
        "selection_and_final_task_access": False,
        "paid_diagnostic_calls_before_freeze": 0,
        "official_researcher_campaigns_before_freeze": 0,
        "official_final_model_attempts_before_freeze": 0,
    }, "diagnostic_public_witness_not_exact_pre_result_freeze")
    return diagnostic.digest(raw)


class RunJournal:
    """Fsync/hash-chain every provider intent and result; never resume a run."""

    def __init__(self, directory: Path, header: dict):
        self.directory = Path(directory)
        self.path = self.directory / "events.private.jsonl"
        self.header = header
        self.next_operation = 1
        core = {"schema": RUN_SCHEMA, "kind": "header",
                "data": header, "previous": None}
        _write_new(self.path, diagnostic.canonical({
            **core, "hash": diagnostic.digest(diagnostic.canonical(core))}))

    @classmethod
    def audit_existing(cls, directory: Path) -> "RunJournal":
        path = Path(directory) / "events.private.jsonl"
        require(path.is_file() and not path.is_symlink() and
                path.stat().st_mode & 0o077 == 0,
                "diagnostic_journal_missing_or_unsafe")
        try:
            header = json.loads(path.read_bytes().splitlines()[0])
        except (IndexError, UnicodeDecodeError, json.JSONDecodeError):
            raise RunError("diagnostic_journal_invalid_json") from None
        require(type(header) is dict and header.get("kind") == "header" and
                type(header.get("data")) is dict,
                "diagnostic_journal_header_invalid")
        instance = cls.__new__(cls)
        instance.directory = Path(directory)
        instance.path = path
        instance.header = header["data"]
        instance.next_operation = 0
        instance.rows()
        return instance

    @contextmanager
    def locked(self):
        path = self.directory / ".run.lock"
        require(not path.is_symlink(), "diagnostic_run_lock_unsafe")
        fd = os.open(path, os.O_WRONLY | os.O_CREAT, 0o600)
        with os.fdopen(fd, "w") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            yield

    def rows(self) -> list[dict]:
        require(self.path.is_file() and not self.path.is_symlink() and
                self.path.stat().st_mode & 0o077 == 0,
                "diagnostic_journal_missing_or_unsafe")
        try:
            rows = [json.loads(line) for line in
                    self.path.read_bytes().splitlines()]
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise RunError("diagnostic_journal_invalid_json") from None
        require(bool(rows), "diagnostic_journal_empty")
        previous = None
        intents = {}
        terminal = set()
        for index, row in enumerate(rows):
            require(type(row) is dict and row.get("previous") == previous,
                    "diagnostic_journal_chain_broken")
            core = {key: value for key, value in row.items() if key != "hash"}
            require(row.get("hash") == diagnostic.digest(
                diagnostic.canonical(core)),
                "diagnostic_journal_chain_broken")
            if index == 0:
                require(core == {"schema": RUN_SCHEMA, "kind": "header",
                                 "data": self.header, "previous": None},
                        "diagnostic_journal_header_changed")
            else:
                operation = row.get("operation")
                require(row.get("sequence") == index and
                        type(operation) is int and operation > 0 and
                        row.get("kind") in {"intent", "completed", "uncertain"},
                        "diagnostic_journal_event_invalid")
                if row["kind"] == "intent":
                    require(operation not in intents,
                            "diagnostic_journal_duplicate_intent")
                    request_path = (self.directory /
                                    f"operation-{operation:04d}.request.private.json")
                    require(request_path.is_file() and
                            not request_path.is_symlink() and
                            request_path.stat().st_mode & 0o077 == 0 and
                            diagnostic.digest(request_path.read_bytes()) ==
                            row["data"].get("request_sha256"),
                            "diagnostic_provider_request_bytes_changed")
                    intents[operation] = row
                else:
                    require(operation in intents and operation not in terminal,
                            "diagnostic_journal_terminal_without_intent")
                    if row["kind"] == "completed":
                        result_path = (self.directory /
                                       f"operation-{operation:04d}.result.private.json")
                        require(result_path.is_file() and
                                not result_path.is_symlink() and
                                result_path.stat().st_mode & 0o077 == 0 and
                                diagnostic.digest(result_path.read_bytes()) ==
                                row["data"].get("result_sha256"),
                                "diagnostic_provider_result_bytes_changed")
                    terminal.add(operation)
            previous = row["hash"]
        return rows

    def append(self, kind: str, operation: int, data: dict) -> dict:
        with self.locked():
            rows = self.rows()
            core = {"schema": RUN_SCHEMA, "kind": kind,
                    "sequence": len(rows), "operation": operation,
                    "data": data, "previous": rows[-1]["hash"]}
            row = {**core, "hash": diagnostic.digest(
                diagnostic.canonical(core))}
            fd = os.open(self.path, os.O_WRONLY | os.O_APPEND)
            with os.fdopen(fd, "ab") as stream:
                stream.write(diagnostic.canonical(row))
                stream.flush()
                os.fsync(stream.fileno())
            return row

    def call(self, name: str, request: dict,
             provider: Callable[[], dict]) -> dict:
        operation = self.next_operation
        self.next_operation += 1
        require(type(name) is str and type(request) is dict and
                callable(provider), "diagnostic_operation_invalid")
        request_raw = diagnostic.canonical(request)
        _write_new(self.directory /
                   f"operation-{operation:04d}.request.private.json",
                   request_raw)
        self.append("intent", operation, {
            "name": name,
            "request_sha256": diagnostic.digest(request_raw),
            "epoch_seconds": int(time.time()),
        })
        try:
            result = provider()
            require(type(result) is dict,
                    "diagnostic_provider_result_not_object")
            raw = diagnostic.canonical(result)
            _write_new(self.directory /
                       f"operation-{operation:04d}.result.private.json", raw)
            self.append("completed", operation, {
                "result_sha256": diagnostic.digest(raw),
                "epoch_seconds": int(time.time()),
            })
            return result
        except Exception as exc:
            self.append("uncertain", operation, {
                "exception_type": type(exc).__name__,
                "epoch_seconds": int(time.time()),
            })
            raise RunError("diagnostic_provider_uncertain_no_replay") from None

    def snapshot(self) -> dict:
        rows = self.rows()
        intents = {row["operation"] for row in rows
                   if row["kind"] == "intent"}
        terminal = {row["operation"] for row in rows
                    if row["kind"] in {"completed", "uncertain"}}
        return {"provider_intents": len(intents),
                "completed_operations": sum(row["kind"] == "completed"
                                            for row in rows),
                "uncertain_operations": sum(row["kind"] == "uncertain"
                                            for row in rows),
                "open_intents_after_interruption": len(intents - terminal),
                "automatic_replay_authorized": False}


class RealTinkerProvider:
    """Thin pinned-SDK adapter; all methods run inside RunJournal.call."""

    def __init__(self, vision, prereg: dict, run_id: str):
        self.vision, self.prereg, self.run_id = vision, prereg, run_id
        self.service = None
        self.client = None
        self.samplers = {}

    def open_service(self) -> dict:
        import tinker
        self.service = tinker.ServiceClient(user_metadata={
            "purpose": "envloop-real-gui-diagnostic-v1",
            "run_id": self.run_id, "split": "train",
            "formal_campaign": "false"})
        return {"status": "service_opened"}

    def open_training(self) -> dict:
        self.client = self.service.create_lora_training_client(
            base_model=diagnostic.MODEL,
            rank=self.prereg["lora_rank"], seed=self.prereg["model_seed"])
        return {"status": "fresh_base_lora_training_client_opened"}

    def forward_backward(self, datums: list) -> dict:
        result = self.client.forward_backward(
            datums, "cross_entropy").result(timeout=300)
        metrics = getattr(result, "metrics", None)
        return {"status": "completed", "metrics_present": metrics is not None}

    def optim_step(self) -> dict:
        from tinker import types
        self.client.optim_step(types.AdamParams(
            learning_rate=float(self.prereg["learning_rate"])))\
            .result(timeout=300)
        return {"status": "completed"}

    def save_state(self, step: int) -> dict:
        saved = self.client.save_state(
            f"envloop-diagnostic-{self.run_id}-step-{step:03d}")\
            .result(timeout=300)
        return {"status": "completed", "checkpoint_path": saved.path}

    def save_sampler(self) -> dict:
        saved = self.client.save_weights_for_sampler(
            f"envloop-diagnostic-{self.run_id}-final")\
            .result(timeout=300)
        return {"status": "completed", "checkpoint_path": saved.path}

    def open_sampler(self, kind: str, checkpoint_path: str | None) -> dict:
        require(kind in {"base", "lora"} and
                (checkpoint_path is None) == (kind == "base"),
                "diagnostic_sampler_kind_invalid")
        client = (self.service.create_sampling_client(
            base_model=diagnostic.MODEL) if kind == "base" else
            self.service.create_sampling_client(model_path=checkpoint_path))
        require(client.get_base_model() == diagnostic.MODEL,
                "diagnostic_sampler_base_model_changed")
        self.samplers[kind] = client
        return {"status": "completed", "reported_base_model":
                diagnostic.MODEL}

    def sample(self, kind: str, prompt) -> dict:
        from tinker import types
        response = self.samplers[kind].sample(
            prompt=prompt, num_samples=1,
            sampling_params=types.SamplingParams(
                max_tokens=self.prereg["sampling_max_tokens"],
                temperature=float(self.prereg["sampling_temperature"]),
                seed=self.prereg["sampling_seed"],
                stop=self.vision.renderer.get_stop_sequences()))\
            .result(timeout=300)
        require(len(response.sequences) == 1,
                "diagnostic_sample_sequence_count_invalid")
        tokens = response.sequences[0].tokens
        require(isinstance(tokens, (list, tuple)) and
                all(type(token) is int and token >= 0 for token in tokens) and
                len(tokens) <= self.prereg["sampling_max_tokens"],
                "diagnostic_sample_tokens_invalid")
        stop_reason = getattr(response.sequences[0], "stop_reason", None)
        require(stop_reason is None or isinstance(stop_reason, str),
                "diagnostic_sample_stop_reason_invalid")
        return {"status": "completed", "text": self.vision.decode(tokens),
                "output_tokens": len(tokens),
                "stop_reason": stop_reason}

    def close(self, status: str) -> dict:
        if self.service is not None:
            self.service.close(status).result(timeout=30)
        return {"status": "closed"}


def paired_summary(rows: list[dict]) -> dict:
    require(rows and all(set(row) == {"base", "lora", "reference_type"}
                         for row in rows),
            "diagnostic_matched_pair_incomplete")
    result = {"holdout_turns": len(rows)}
    for field in ("format_valid", "action_type_match",
                  "payload_exact_match"):
        result["base_" + field] = sum(row["base"][field] for row in rows)
        result["lora_" + field] = sum(row["lora"][field] for row in rows)
        result["paired_" + field + "_gain"] = sum(
            row["lora"][field] and not row["base"][field]
            for row in rows)
        result["paired_" + field + "_loss"] = sum(
            row["base"][field] and not row["lora"][field]
            for row in rows)
    non_wait = [row for row in rows if row["reference_type"] != "wait"]
    result["non_wait_reference_turns"] = len(non_wait)
    for kind in ("base", "lora"):
        result[kind + "_non_wait_action_type_match"] = sum(
            row[kind]["action_type_match"] for row in non_wait)
        result[kind + "_non_wait_payload_exact_match"] = sum(
            row[kind]["payload_exact_match"] for row in non_wait)
    return result


def run(*, repo_root: Path, manifest_path: Path, ratification_path: Path,
        plan_path: Path, public_commit: str, run_dir: Path,
        renderer_loader: Callable[[], object],
        provider_factory: Callable[[object, dict, str], object] = RealTinkerProvider,
        witness_fetcher: Callable[[str], bytes] | None = None,
        require_provider_key: bool = True) -> dict:
    """Execute once; no official selection/final identity is ever loaded."""
    root = Path(repo_root).resolve()
    try:
        runtime_gate.assert_active_worker(root)
    except runtime_gate.RuntimeGateError:
        raise RunError("diagnostic_active_worker_not_dedicated_runtime") from None
    require(os.environ.get("HF_HUB_OFFLINE") == "1" and
            os.environ.get("TRANSFORMERS_OFFLINE") == "1",
            "diagnostic_renderer_offline_mode_required")
    prereg, prereg_sha = diagnostic.load_prereg(root)
    expected, _proposal, train_batch, holdout_batch, holdout_turns, vision = \
        diagnostic.materialize_plan(
            root, manifest_path, ratification_path, renderer_loader)
    private, raw = diagnostic.private_json(plan_path, root / "work")
    require(raw == diagnostic.canonical(expected) and private == expected,
            "diagnostic_private_plan_not_exact_rebuild")
    plan_sha = diagnostic.digest(raw)
    witness_sha = immutable_witness(
        public_commit=public_commit, plan_sha256=plan_sha,
        prereg_sha256=prereg_sha, fetcher=witness_fetcher)
    try:
        runtime = runtime_gate.validate(
            repo_root=root, study_plan_sha256=plan_sha,
            private_toy_dir=root / runtime_gate.PRIVATE_TOY_RELATIVE)
        runtime_gate.assert_active_worker(root)
    except runtime_gate.RuntimeGateError:
        raise RunError("diagnostic_runtime_gate_failed") from None
    require(runtime["status"] ==
            "pre_dispatch_runtime_evidence_verified" and
            runtime["provider_calls"] == 0 and
            runtime["dispatch_authorized"] is False,
            "diagnostic_runtime_receipt_invalid")
    if require_provider_key:
        require(bool(os.environ.get("TINKER_API_KEY")),
                "diagnostic_tinker_key_missing")
    target = Path(run_dir).absolute()
    work = root / "work"
    require(not work.is_symlink() and not target.is_symlink() and
            target.parent.resolve().is_relative_to(work.resolve()) and
            not target.exists(), "diagnostic_run_directory_must_be_new")
    full_study = work / "full-study"
    require(not full_study.is_symlink() and
            full_study.resolve().is_relative_to(work.resolve()),
            "diagnostic_paid_registry_unsafe")
    registry = full_study / "qwen38-real-gui-diagnostic/paid-intents"
    require(not registry.parent.is_symlink() and
            not registry.is_symlink(),
            "diagnostic_paid_registry_unsafe")
    registry.mkdir(parents=True, exist_ok=True, mode=0o700)
    require(registry.resolve().is_relative_to(work.resolve()),
            "diagnostic_paid_registry_unsafe")
    registry.chmod(0o700)
    _write_new(registry / (plan_sha + ".private.json"),
               diagnostic.canonical({
                   "schema": "cua-qwen38-real-gui-diagnostic-paid-intent-v1",
                   "plan_sha256": plan_sha,
                   "immutable_public_witness_sha256": witness_sha,
                   "nominal_quote_usd": private["nominal_quote_usd"],
                   "pricing_quote_is_dispatch_gate": False,
                   "run_directory_sha256": diagnostic.digest(
                       str(target).encode()),
                   "automatic_replay_authorized": False,
                   "provider_invoice_usd": None,
               }))
    target.mkdir(parents=True, mode=0o700)
    target.chmod(0o700)
    header = {"plan_sha256": plan_sha,
              "prereg_sha256": prereg_sha,
              "immutable_public_witness_sha256": witness_sha,
              "nominal_quote_usd": private["nominal_quote_usd"],
              "pricing_quote_is_dispatch_gate": False,
              "runtime_spec_sha256": runtime["runtime_spec_sha256"],
              "toy_public_receipt_sha256":
                  runtime["toy_public_receipt_sha256"],
              "provider_invoice_usd": None,
              "official_campaign": False}
    journal = RunJournal(target, header)
    provider = provider_factory(vision, prereg, plan_sha[:16])
    status = "errored"
    try:
        journal.call("service_open", {"plan_sha256": plan_sha},
                     provider.open_service)
        journal.call("train_client_open", {
            "model": diagnostic.MODEL,
            "rank": prereg["lora_rank"],
            "seed": prereg["model_seed"]},
            provider.open_training)
        for ordinal, indexes in enumerate(private["batches"], 1):
            batch = [train_batch.datums[index] for index in indexes]
            request = {"step": ordinal, "batch_indexes": indexes,
                       "datum_token_lengths": [private[
                           "training_datum_lengths"][index]
                           for index in indexes],
                       "train_render_receipt_sha256": private[
                           "train_render_receipt_sha256"]}
            journal.call("forward_backward", request,
                         lambda batch=batch: provider.forward_backward(batch))
            journal.call("optimizer_step", {"step": ordinal,
                                              "learning_rate": prereg[
                                                  "learning_rate"]},
                         provider.optim_step)
            if ordinal in prereg["state_save_after_steps"]:
                journal.call("save_optimizer_state", {"step": ordinal},
                             lambda step=ordinal: provider.save_state(step))
        sampler = journal.call("save_sampler_weights", {
            "step": prereg["optimizer_steps"]}, provider.save_sampler)
        checkpoint_path = sampler.get("checkpoint_path")
        require(type(checkpoint_path) is str and
                runtime_gate.CHECKPOINT.fullmatch(checkpoint_path),
                "diagnostic_sampler_checkpoint_invalid")
        journal.call("base_sampler_open", {"model": diagnostic.MODEL},
                     lambda: provider.open_sampler("base", None))
        journal.call("lora_sampler_open", {
            "checkpoint_path_sha256": diagnostic.digest(
                checkpoint_path.encode())},
            lambda: provider.open_sampler("lora", checkpoint_path))
        pairs = []
        observed_sample_output_tokens = 0
        for index, turn in enumerate(holdout_turns):
            scored = {}
            # Alternating order prevents one model from always running first.
            kinds = ("base", "lora") if index % 2 == 0 else ("lora", "base")
            for kind in kinds:
                request = {"holdout_ordinal": index,
                           "kind": kind,
                           "prompt_length": private[
                               "holdout_prompt_lengths"][index],
                           "holdout_render_receipt_sha256": private[
                               "holdout_render_receipt_sha256"],
                           "max_tokens": prereg["sampling_max_tokens"],
                           "temperature": prereg["sampling_temperature"],
                           "seed": prereg["sampling_seed"]}
                sample = journal.call(
                    "matched_sample", request,
                    lambda kind=kind, prompt=holdout_batch.prompts[index]:
                        provider.sample(kind, prompt))
                require(sample.get("status") == "completed" and
                        type(sample.get("text")) is str and
                        type(sample.get("output_tokens")) is int,
                        "diagnostic_sample_result_invalid")
                observed_sample_output_tokens += sample["output_tokens"]
                scored[kind] = diagnostic.score_action_text(
                    sample["text"], turn["observation"], turn["action"])
            pairs.append({"reference_type": turn["action"]["type"],
                          **scored})
        summary = paired_summary(pairs)
        private_result = {
            "schema": PRIVATE_RESULT_SCHEMA,
            "status": "train_domain_action_format_diagnostic_completed",
            "plan_sha256": plan_sha,
            "checkpoint_path": checkpoint_path,
            "checkpoint_path_sha256": diagnostic.digest(
                checkpoint_path.encode()),
            "per_turn": pairs,
            "summary": summary,
            "usage": {
                "scheduled_training_tokens": private[
                    "scheduled_train_tokens"],
                "rendered_sampling_prompt_tokens": 2 * sum(
                    private["holdout_prompt_lengths"]),
                "observed_sample_output_tokens":
                    observed_sample_output_tokens,
                "provider_billed_tokens": None,
            },
            "provider_invoice_usd": None,
            "application_success_estimate": None,
            "benchmark_score": None,
        }
        private_raw = diagnostic.canonical(private_result)
        _write_new(target / "diagnostic-result.private.json", private_raw)
        status = "success"
        return {"schema": PUBLIC_RESULT_SCHEMA,
                "status": private_result["status"],
                "plan_sha256": plan_sha,
                "private_result_sha256": diagnostic.digest(private_raw),
                "checkpoint_path_sha256": private_result[
                    "checkpoint_path_sha256"],
                "task_disjoint_within_train_holdout": True,
                "optimizer_steps": prereg["optimizer_steps"],
                "training_datum_count": len(train_batch.datums),
                "scheduled_train_tokens": private[
                    "scheduled_train_tokens"],
                "rendered_sampling_prompt_tokens": 2 * sum(
                    private["holdout_prompt_lengths"]),
                "observed_sample_output_tokens":
                    observed_sample_output_tokens,
                "provider_billed_tokens": None,
                "nominal_quote_usd": private["nominal_quote_usd"],
                "pricing_quote_is_dispatch_gate": False,
                "provider_invoice_usd": None,
                "selection_tasks_used": 0, "final_tasks_used": 0,
                "official_researcher_campaign": False,
                "application_success_estimate": None,
                "benchmark_score": None,
                **summary}
    finally:
        if getattr(provider, "service", None) is not None:
            try:
                journal.call("service_close", {"status": status},
                             lambda: provider.close(status))
            except RunError:
                # The close uncertainty remains visible in the journal.
                if status == "success":
                    raise


__all__ = ["RunError", "RunJournal", "RealTinkerProvider",
           "immutable_witness", "paired_summary", "run"]
