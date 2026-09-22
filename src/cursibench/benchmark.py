from dataclasses import dataclass
from .harness import run_harness
from .model import Candidate, Task, Trajectory
from .tasks import make_tasks
from .verifier import verify


@dataclass
class Round:
    number: int
    candidate: str
    accepted: bool
    train_score: float
    reason: str


def score(tasks: list[Task], policy: str) -> tuple[float, list[Trajectory]]:
    trajectories: list[Trajectory] = []
    for task in tasks:
        trajectory = run_harness(task, policy)
        trajectory.score, trajectory.errors = verify(task, trajectory.final_state)
        trajectories.append(trajectory)
    return round(sum(t.score for t in trajectories) / len(trajectories), 4), trajectories


def run_benchmark(rounds: int = 5) -> dict:
    tasks = make_tasks()
    train = [t for t in tasks if t.split == "train"]
    test = [t for t in tasks if t.split == "test"]
    a0_train, _ = score(train, "naive")
    a0_test, _ = score(test, "naive")
    current = Candidate("A0", "naive")
    history: list[Round] = []
    for number in range(1, rounds + 1):
        # The improvement step is intentionally deterministic for this fixture: train failures
        # reveal the need for explicit object scoping, producing the scoped candidate.
        candidate = Candidate(f"A{number}", "scoped")
        candidate_train, trajectories = score(train, candidate.policy)
        anchors, _ = score([tasks[0]], candidate.policy)
        accepted = candidate_train > a0_train and anchors >= a0_train
        reason = "train improvement and anchor preserved" if accepted else "rejected by train gate"
        history.append(Round(number, candidate.name, accepted, candidate_train, reason))
        if accepted:
            current = candidate
            break
    final_test, final_trajectories = score(test, current.policy)
    passed = final_test > a0_test and all(not t.errors for t in final_trajectories)
    return {
        "a0_train": a0_train,
        "a0_test": a0_test,
        "final_candidate": current.name,
        "final_policy": current.policy,
        "final_test": final_test,
        "delta_rsi": round(final_test - a0_test, 4),
        "rounds": [r.__dict__ for r in history],
        "passed": passed,
    }
