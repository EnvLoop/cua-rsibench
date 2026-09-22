from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Task:
    task_id: str
    split: str
    instruction: str
    initial: dict[str, Any]
    expected: dict[str, Any]
    budget: int = 8


@dataclass
class Trajectory:
    task_id: str
    actions: list[dict[str, Any]] = field(default_factory=list)
    final_state: dict[str, Any] | None = None
    score: float = 0.0
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Candidate:
    name: str
    policy: str
