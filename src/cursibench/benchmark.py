from dataclasses import dataclass
from .harness import run_harness
from .model import Candidate, Task, Trajectory
from .tasks import make_tasks
from .verifier import verify
from .protocol import BenchmarkSpec, Ledger, validate_spec


@dataclass
class Round:
    number: int
    candidate: str
    accepted: bool
    train_score: float
    reason: str


def score(tasks: list[Task], policy: str, repeats: int = 3) -> tuple[float, list[Trajectory]]:
    trajectories: list[Trajectory] = []
    for task in tasks:
        for _ in range(repeats):
            trajectory = run_harness(task, policy)
            trajectory.score, trajectory.errors = verify(task, trajectory.final_state)
            trajectories.append(trajectory)
    return round(sum(t.score for t in trajectories) / len(trajectories), 4), trajectories


def run_benchmark(rounds: int = 5) -> dict:
    spec = BenchmarkSpec(rounds=rounds)
    validate_spec(spec)
    tasks = make_tasks()
    train = [t for t in tasks if t.split == "train"]
    acceptance = [t for t in tasks if t.split == "acceptance"]
    test = [t for t in tasks if t.split == "test"]
    a0_train, _ = score(train, "naive", spec.repeats)
    a0_acceptance, _ = score(acceptance, "naive", spec.repeats)
    a0_test, _ = score(test, "naive", spec.repeats)
    current = Candidate("A0", "naive")
    incumbent_train = a0_train
    incumbent_anchors = a0_acceptance
    history: list[Round] = []
    ledger = Ledger("local-run", spec.to_dict())
    for number in range(1, rounds + 1):
        # The improvement step is intentionally deterministic for this fixture: train failures
        # reveal the need for explicit object scoping, producing the scoped candidate.
        candidate = Candidate(f"A{number}", "scoped")
        candidate_train, trajectories = score(train, candidate.policy, spec.repeats)
        anchors, _ = score(acceptance, candidate.policy, spec.repeats)
        accepted = candidate_train > incumbent_train and anchors >= incumbent_anchors
        reason = "train improvement and anchor preserved" if accepted else "rejected by train gate"
        history.append(Round(number, candidate.name, accepted, candidate_train, reason))
        ledger.append_attempt({"round": number, "candidate": candidate.name, "train_avg_at_3": candidate_train, "acceptance_avg_at_3": anchors, "accepted": accepted})
        if accepted:
            parent = current.name
            current = candidate
            incumbent_train = candidate_train
            incumbent_anchors = anchors
            ledger.candidate = candidate.name
            ledger.parent = parent
            ledger.changed_modules = ["workflow", "skills"]
        else:
            ledger.rejected_candidates.append(candidate.name)
    final_test, final_trajectories = score(test, current.policy, spec.repeats)
    passed = final_test > a0_test and all(not t.errors for t in final_trajectories)
    return {
        "evidence_kind": "deterministic_fixture_only",
        "official_submission_eligible": False,
        "spec": spec.to_dict(),
        "splits": {"train": len(train), "acceptance_anchors": len(acceptance), "test_hidden": len(test)},
        "controls": list(spec.controls),
        "ledger": ledger.to_dict(),
        "a0_train": a0_train,
        "a0_acceptance": a0_acceptance,
        "a0_test": a0_test,
        "final_candidate": current.name,
        "final_policy": current.policy,
        "final_test": final_test,
        "delta_rsi": round(final_test - a0_test, 4),
        "rounds": [r.__dict__ for r in history],
        "passed": passed,
    }
