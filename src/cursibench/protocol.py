"""Frozen benchmark protocol and audit metadata."""

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class BenchmarkSpec:
    name: str = "cua-rsibench"
    version: str = "0.2.0"
    domains: tuple[str, ...] = ("office", "browser", "files", "cross_app")
    repeats: int = 3
    rounds: int = 5
    max_steps: int = 40
    wall_seconds: int = 900
    token_budget: int = 12000
    train_visible_to_improver: bool = True
    test_visible_to_improver: bool = False
    frozen_surfaces: tuple[str, ...] = ("tasks", "environment_image", "reset", "verifier", "budgets", "sampling_config")
    editable_surfaces: tuple[str, ...] = ("prompt", "rules", "skills", "hooks", "mcp_adapters", "workflow")
    controls: tuple[str, ...] = ("frozen_baseline", "nonrecursive_optimizer", "initial_only_candidates")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_spec(spec: BenchmarkSpec) -> None:
    if spec.repeats < 3:
        raise ValueError("RSIBench-style scoring requires at least avg@3")
    if spec.rounds < 1:
        raise ValueError("rounds must be positive")
    if set(spec.frozen_surfaces) & set(spec.editable_surfaces):
        raise ValueError("frozen and editable surfaces overlap")
    if spec.test_visible_to_improver:
        raise ValueError("test must not be visible to improver")
    if "verifier" not in spec.frozen_surfaces:
        raise ValueError("verifier must remain fixed")


@dataclass
class Ledger:
    run_id: str
    spec: dict[str, Any]
    parent: str | None = None
    candidate: str = "A0"
    changed_modules: list[str] = field(default_factory=list)
    attempts: list[dict[str, Any]] = field(default_factory=list)
    rejected_candidates: list[str] = field(default_factory=list)
    costs: dict[str, float] = field(default_factory=lambda: {"usd": 0.0, "tokens": 0.0, "wall_seconds": 0.0})

    def append_attempt(self, attempt: dict[str, Any]) -> None:
        self.attempts.append(attempt)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
