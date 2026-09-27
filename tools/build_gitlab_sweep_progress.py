"""Publish aggregate-only GitLab 10-ID admission progress after demo restore."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from gitlab_world import failure_ledger, runtime, sweep


ROOT = Path(__file__).resolve().parents[1]
PRIVATE = runtime.PRIVATE
OUTPUT_JSON = ROOT / "docs/evidence/gitlab-scoped-gui-progress-2026-09-27.json"
OUTPUT_MD = ROOT / "docs/evidence/gitlab-scoped-gui-progress-2026-09-27.md"
FIRST = ROOT / "docs/evidence/gitlab-scoped-gui-development-2026-09-27.json"
SENSITIVE = re.compile(
    r"glpat-|GITLAB_ROOT_PASSWORD|@benchmark\.invalid|"
    r"(?:sk-[a-z0-9]{16,})|(?:e2b_[a-z0-9]{16,})|(?:tml-[a-z0-9]{16,})|"
    r"(?:localhost|127\.0\.0\.1):8014|/work/gitlab-full-world/|"
    r"GLW-\d{2}-\d{2}|portfolio-[0-9a-f]{10}|INV-[0-9A-F]{8}", re.I)


def read(path: Path) -> dict:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise RuntimeError("GitLab progress source is not an object")
    return value


def build() -> tuple[dict, str]:
    first = read(FIRST)
    initial = first["evaluator_private_bounded_sweep"]
    if (initial.get("individually_attempted_ids") != 5 or
            initial.get("development_gui_trio_passed") != 5):
        raise RuntimeError("five-ID initial GitLab milestone changed")
    completed = read(PRIVATE / "bounded-v3-next10-summary.json")
    durable = sweep.public_summary(sweep._load())
    if completed != durable or completed["individually_attempted_ids"] != 15:
        raise RuntimeError("ten-ID bounded batch incomplete or differs from private index")
    if completed["attempted_source_family_count"] != 15:
        raise RuntimeError("second batch did not expand to 15 distinct project sources")
    ledger = failure_ledger.audit()
    if completed["append_only_failure_ledger"] != ledger or not ledger[
            "all_records_hash_chained"]:
        raise RuntimeError("append-only GitLab failure ledger mismatch")
    if ledger["entry_count"] != completed["retained_prior_failed_attempts"]:
        raise RuntimeError("private failed attempts are not all in append-only ledger")
    restored = read(PRIVATE / "demo-restoration-next10-receipt.json")
    if not (restored.get("demo_healthy") and restored.get("demo_identity_preserved")
            and restored.get("same_container_id") and restored.get("world_removed")):
        raise RuntimeError("pre-existing GitLab demo was not restored after next batch")
    current = {"schema": "envloop-gitlab-sweep-progress-public-v1",
               "date": "2026-09-27", "cell": "gitlab",
               "previous_public_receipt_sha256": hashlib.sha256(FIRST.read_bytes()).hexdigest(),
               "cumulative": completed,
               "new_bounded_batch": {"attempted_ids": 10,
                                     "new_source_families": 10,
                                     "new_passed_ids": completed["development_gui_trio_passed"] - 5,
                                     "new_failed_or_invalid_ids":
                                         15 - completed["development_gui_trio_passed"],
                                     "prior_passes_preserved": 5},
               "append_only_failure_ledger": ledger,
               "pre_existing_demo_restored_same_identity_healthy": True,
               "model_calls": 0, "official_final_admitted": 0,
               "researcher_campaigns_executed": 0,
               "interpretation": "Evaluator-private native GUI admission controls only; no official exam or model score."}
    passed = completed["development_gui_trio_passed"]
    failed = 15 - passed
    md = f"""# GitLab scoped-GUI admission progress — 2026-09-27

The earlier [five-ID aggregate control receipt](gitlab-scoped-gui-development-2026-09-27.md) defines the original GitLab CE 18.5 world, pinned CC0 advisory source, non-admin partition ACLs, independent PostgreSQL/Git oracle, cold-reset method, and shared Qwen action boundary. This update is another evaluator-private deterministic GUI admission batch, **not a student-model result or an official final-set freeze**. It publishes no task ID, prompt, answer, project identity, screenshot, credential, or raw action trace.

| Cumulative clean final-candidate controls | Count |
| --- | ---: |
| Distinct IDs attempted | 15 / 100 |
| Distinct project source families attempted | 15 / 20 |
| Native-GUI correct / plausible wrong / repeated correct trios passed | {passed} |
| Failed or infrastructure-invalid IDs | {failed} |
| Unattempted IDs | 85 |
| Cold resets bound to passed IDs | {completed['verified_cold_resets_for_passed_ids']} |
| Official final IDs admitted | **0** |

The latest bounded batch added ten IDs from ten previously untested project source families while preserving the first five passes. Across all fifteen attempts, the per-workflow attempted/pass/failure counts are in the [machine-readable aggregate](gitlab-scoped-gui-progress-2026-09-27.json). Every completed passing ID had native GUI positive, plausible negative, and repeated positive scores of 1/0/1, independent saved-state and no-regression readback, and three fresh cold resets. A failed GUI/verification/reset attempt is appended to a mode-0600 SHA-chained private ledger before its mutable index is updated. The public ledger contains only count and head digest; failures are never silently retried, turned into model failures, or omitted from the denominator. The original demo was restored healthy with its pre-stop container identity after this batch.

The remaining **85** candidates still lack a per-ID control. The deterministic DOM-located qualification operator is separate from Qwen's screenshot-only action policy; the v0.6.4 adapter has only a read-only native-GUI smoke. No paid Qwen training, selection feedback, or researcher campaign is included here. CI YAML persistence is checked, while runner execution remains unproven. The GitLab cell therefore stays **0/100 officially admitted** until all per-ID and global pre-campaign gates pass.
"""
    serialized = json.dumps(current, indent=2, sort_keys=True) + "\n" + md
    if SENSITIVE.search(serialized):
        raise RuntimeError("GitLab progress report includes a sensitive pattern")
    return current, md


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    public, md = build()
    if args.write:
        OUTPUT_JSON.write_text(json.dumps(public, indent=2, sort_keys=True) + "\n")
        OUTPUT_MD.write_text(md)
    else:
        print(json.dumps({"attempted": public["cumulative"]["individually_attempted_ids"],
                          "official_final_admitted": public["official_final_admitted"]},
                         indent=2))


if __name__ == "__main__":
    main()
