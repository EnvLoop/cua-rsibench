"""RSIBench-Data-shaped orchestration with explicit provider boundaries.

The default providers are local fakes so CI is deterministic. Real providers are intentionally
not silently enabled: a future adapter must provide Tinker/E2B credentials and return the same
artifact contract before a paid run can be called an official evaluation.
"""

from dataclasses import dataclass
from pathlib import Path
import json
import os
from typing import Any, Protocol


@dataclass(frozen=True)
class RunConfig:
    base_model: str = "computer-use-base-v0"
    max_tokens: int = 2048
    temperature: float = 1.0
    top_p: float = 0.95
    eval_step_limit: int = 40
    n_tasks: int = 4


class TinkerBackend(Protocol):
    def train_lora(self, train_messages: list[dict[str, Any]], config: RunConfig) -> str: ...
    def sample(self, model_path: str, prompt: str, config: RunConfig) -> str: ...


class E2BBackend(Protocol):
    def create_sandbox(self, template: str) -> str: ...
    def run(self, sandbox_id: str, command: str) -> dict[str, Any]: ...


class HarborBackend(Protocol):
    def evaluate(self, dataset: str, model_path: str, config: RunConfig) -> dict[str, Any]: ...


class LocalTinker:
    def train_lora(self, train_messages: list[dict[str, Any]], config: RunConfig) -> str:
        return f"local://sampler_weights/{len(train_messages)}"

    def sample(self, model_path: str, prompt: str, config: RunConfig) -> str:
        return f"sampled:{model_path}:{prompt[:24]}"


class LocalE2B:
    def create_sandbox(self, template: str) -> str:
        return f"local-sandbox:{template}"

    def run(self, sandbox_id: str, command: str) -> dict[str, Any]:
        return {"sandbox_id": sandbox_id, "command": command, "status": "completed"}


class LocalHarbor:
    def evaluate(self, dataset: str, model_path: str, config: RunConfig) -> dict[str, Any]:
        return {"dataset": dataset, "model_path": model_path, "score": 1.0, "harbor_errors": []}


def run_service_chain(
    run_dir: str | Path,
    train_messages: list[dict[str, Any]],
    dataset: str = "cua-rsibench/local",
    config: RunConfig | None = None,
    tinker: TinkerBackend | None = None,
    e2b: E2BBackend | None = None,
    harbor: HarborBackend | None = None,
) -> dict[str, Any]:
    """Run the fixed chain and persist an auditable manifest.

    Chain: train_messages -> Tinker LoRA checkpoint -> E2B proxy sandbox -> Harbor evaluation.
    """
    config = config or RunConfig()
    tinker = tinker or LocalTinker()
    e2b = e2b or LocalE2B()
    harbor = harbor or LocalHarbor()
    out = Path(run_dir)
    out.mkdir(parents=True, exist_ok=True)
    # This file represents the output of the data-generation agent. In a real run it
    # would be produced by the research harness after inspecting allowed seed factories.
    data_generation = {
        "agent": "local-data-generation-agent",
        "strategy": "visible-task demonstrations with tool-call traces",
        "records": len(train_messages),
    }
    (out / "data_generation_agent.json").write_text(
        json.dumps(data_generation, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (out / "train_messages.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in train_messages), encoding="utf-8"
    )
    checkpoint = tinker.train_lora(train_messages, config)
    sandbox = e2b.create_sandbox("cua-rsibench-tinker-proxy")
    proxy = e2b.run(sandbox, "start fixed tool-call proxy")
    evaluation = harbor.evaluate(dataset, checkpoint, config)
    scored_attempt = {
        "attempt_id": f"attempt-{len(train_messages)}",
        "checkpoint": checkpoint,
        "harbor": evaluation,
        "status": "scored" if not evaluation.get("harbor_errors") else "scored_with_errors",
    }
    (out / "scored_attempt.json").write_text(
        json.dumps(scored_attempt, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    final_submission = {
        "selected_attempt": scored_attempt["attempt_id"],
        "model_path": checkpoint,
        "score": evaluation.get("score"),
        "eligible": not bool(evaluation.get("harbor_errors")),
    }
    (out / "final_submission.json").write_text(
        json.dumps(final_submission, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    manifest = {
        "chain": [
            "data_generation_agent",
            "train_messages.jsonl",
            "tinker_lora_sft",
            "tinker_sampler_checkpoint",
            "e2b_tool_call_proxy",
            "harbor_benchmark_eval",
            "scored_attempt",
            "final_submission",
        ],
        "data_generation": data_generation,
        "checkpoint": checkpoint,
        "sandbox": sandbox,
        "proxy": proxy,
        "evaluation": evaluation,
        "scored_attempt": scored_attempt,
        "final_submission": final_submission,
        "config": config.__dict__,
        "official_provider_keys_present": bool(os.getenv("TINKER_API_KEY") and os.getenv("E2B_API_KEY")),
        "provider_mode": "local-fake" if checkpoint.startswith("local://") else "external",
    }
    (out / "result.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest
