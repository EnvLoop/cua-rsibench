"""Publish aggregate proof that the exhausted v2 attempt-1 pair was retired.

This reopens immutable private audit, cleanup intent/receipt and four exact
Docker action receipts. It does not run Docker mutation or authorize a retry.
"""

from __future__ import annotations

import json
from pathlib import Path

from tools import magento_resumable_100_v2 as v2
from tools import retire_magento_v2_retry_runtime_failure_v1 as retire


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "work/magento-original/cron-resumable-100-v2"
OUT = ROOT / "docs/evidence/magento-v2-retry-runtime-retired-2026-09-28.json"


def audit() -> dict:
    paths = retire._paths(RUN)
    original, original_sha = v2.read_json(paths["audit"])
    public, _ = v2.read_json(paths["public"])
    intent, intent_sha = v2.read_json(paths["intent"])
    receipt, receipt_sha = v2.read_json(paths["receipt"])
    retire.require(original_sha == public.get("private_audit_sha256") and
                   original.get("source_sha256") ==
                   v2.sha(Path(retire.__file__).read_bytes()) and
                   original.get("cleanup_authorized") is False and
                   original.get("third_attempt_authorized") is False and
                   intent.get("audit_sha256") == original_sha and
                   intent.get("containers") == original.get("containers") and
                   receipt.get("audit_sha256") == original_sha and
                   receipt.get("cleanup_intent_sha256") == intent_sha and
                   receipt.get("both_containers_absent") is True and
                   receipt.get("third_attempt_authorized") is False and
                   receipt.get("model_calls") ==
                   receipt.get("official_final_admitted") == 0 and
                   len(original.get("containers", [])) == 2,
                   "exhausted v2 audit or exact cleanup chain changed")
    result_shas = []
    for container in original["containers"]:
        name = container["name"]
        for action in ("stop", "rm"):
            start = paths["intent"].with_name(
                f"operator-runtime-{name}-{action}.private.json")
            finish = start.with_name(
                f"operator-runtime-{name}-{action}-result.private.json")
            started, _ = v2.read_json(start)
            finished, finish_sha = v2.read_json(finish)
            retire.require(started.get("container_id_sha256") ==
                           container["container_id_sha256"] and
                           started.get("image_sha256") ==
                           container["image_sha256"] and
                           started.get("cleanup_intent_sha256") == intent_sha and
                           finished.get("name") == name and
                           finished.get("action") == action and
                           finished.get("cleanup_intent_sha256") == intent_sha and
                           v2._docker_inspect(name) is None,
                           "exact pair step or terminal absence changed")
            result_shas.append(finish_sha)
    v2.old_sweep.assert_absent()
    events = v2.read_journal(RUN / "journal.private.jsonl")
    retire.require(events[-1].get("event") == "attempt_stopped" and
                   events[-1].get("index") == 14 and
                   events[-1].get("attempt") == 1 and
                   len([x for x in events if x.get("event") ==
                        "case_completed"]) == 14 and
                   len([x for x in events if x.get("event") ==
                        "attempt_reconciled"]) == 1,
                   "frozen v2 failed-run history changed")
    return {
        "schema": "envloop-magento-v2-retry-runtime-retired-public-v1",
        "status": "exhausted_v2_control_run_retired_before_new_full100",
        "completed_distinct_evaluator_controls": 14,
        "failed_attempts_same_fifteenth_task": 2,
        "retired_disposable_containers": 2,
        "exact_cleanup_step_receipts": 4,
        "cleanup_result_chain_sha256":
            v2.sha(("\n".join(result_shas) + "\n").encode()),
        "private_runtime_audit_sha256": original_sha,
        "private_cleanup_intent_sha256": intent_sha,
        "private_cleanup_receipt_sha256": receipt_sha,
        "stopped_journal_sha256": v2.sha(
            (RUN / "journal.private.jsonl").read_bytes()),
        "publisher_source_sha256": v2.sha(Path(__file__).read_bytes()),
        "all_disposable_pair_containers_absent": True,
        "third_same_id_retry_authorized": False,
        "new_full100_source_freeze_required": True,
        "official_final_admitted": 0,
        "model_calls": 0,
    }


def main() -> None:
    retire.require(not OUT.exists() and not OUT.is_symlink(),
                   "new public retirement receipt path required")
    result = audit()
    raw = (json.dumps(result, sort_keys=True, indent=2) + "\n").encode()
    with OUT.open("xb") as stream:
        stream.write(raw)
    print(json.dumps({"status": result["status"],
                      "completed_distinct_evaluator_controls": 14,
                      "official_final_admitted": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
