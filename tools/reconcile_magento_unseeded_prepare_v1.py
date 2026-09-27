"""Identity-check and retire an exact unseeded failed Magento prepare pair.

Use only after a stopped sweep and a separate read-only native-sidecar
adoption receipt proves the pinned app/search state. This never seeds a task,
retries an indexer, or credits a candidate.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import time

from magento_catalog_factory.plan import ROOT, require
from magento_catalog_factory.seed import IMAGE
from magento_catalog_factory.verify import NATIVE_SEARCH_IMAGE
from tools.sweep_magento_original_gui_controls_v1 import (
    APP, SEARCH, SEARCH_SHA, append_event, assert_absent, sha, write_new,
)


CONTEXT = "colima-cua-scale"


def inspect(name: str) -> dict:
    result = subprocess.run(["docker", "--context", CONTEXT, "inspect", name],
                            check=True, capture_output=True, timeout=30)
    rows = json.loads(result.stdout)
    require(len(rows) == 1 and rows[0]["Name"] == "/" + name,
            "container identity changed")
    return rows[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sweep-dir", type=Path, required=True)
    parser.add_argument("--index", type=int, required=True)
    parser.add_argument("--adoption", type=Path, required=True)
    parser.add_argument("--audit-only", action="store_true",
                        help="validate the stopped unseeded pair without cleanup")
    args = parser.parse_args()
    private = (ROOT / "work").resolve()
    sweep, adoption_path = args.sweep_dir.resolve(), args.adoption.resolve()
    require(sweep.is_relative_to(private) and
            adoption_path.is_relative_to(sweep) and
            adoption_path.is_file(),
            "private stopped sweep and adoption receipt required")
    journal = sweep / "events.private.jsonl"
    events = [json.loads(line) for line in journal.read_bytes().splitlines()]
    require(events and events[-1]["event"] == "sweep_stopped" and
            any(row.get("event") == "step_finished" and
                row.get("index") == args.index and
                row.get("step") == "positive-prepare" and
                row.get("exit_code") != 0 for row in events) and
            not any(row.get("index") == args.index and
                    row.get("step", "").endswith("-seed") for row in events),
            "failure was not a pre-task positive prepare stop")
    adoption_raw = adoption_path.read_bytes()
    adoption = json.loads(adoption_raw)
    require(adoption["status"] == "clone_and_sidecar_prepared_no_task_seeded" and
            adoption["preparation_mode"] == "read_only_adoption_after_reindex_retry" and
            adoption["application_clone"]["image_sha256"] == IMAGE and
            adoption["application_clone"]["mount_count"] == 0 and
            adoption["search_sidecar_image_sha256"] == NATIVE_SEARCH_IMAGE and
            adoption["search_document_count"] == 181 and
            adoption["search_documents_sha256"] == SEARCH_SHA and
            adoption["official_final_tasks_admitted"] == 0,
            "read-only adoption did not prove exact unseeded source")
    lock_path = ROOT / "work/magento-original/exclusive-worker.lock"
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        app, search = inspect(APP), inspect(SEARCH)
        app_hash = sha(app["Id"].encode())
        search_hash = sha(search["Id"].encode())
        require(app_hash == adoption["application_clone"]["container_id_sha256"] and
                search_hash == adoption["search_sidecar_id_sha256"] and
                app["Image"] == IMAGE and search["Image"] == NATIVE_SEARCH_IMAGE and
                not app["Mounts"] and not search["Mounts"],
                "cleanup refused a changed image, container, or mount")
        if args.audit_only:
            print(json.dumps({"status": "identity_bound_unseeded_pair_audited",
                              "index": args.index,
                              "task_seeded": False,
                              "official_final_admitted": 0}, sort_keys=True))
            return
        processes = []
        for name in (APP, SEARCH):
            for action, timeout in (("stop", 60), ("rm", 30)):
                result = subprocess.run(["docker", "--context", CONTEXT,
                                         action, name], capture_output=True,
                                        timeout=timeout, check=False)
                processes.append({"name": name, "action": action,
                                  "exit_code": result.returncode,
                                  "stdout_sha256": sha(result.stdout),
                                  "stderr_sha256": sha(result.stderr)})
                require(result.returncode == 0,
                        "identity-bound container cleanup failed; inspect before retry")
        assert_absent()
        cleanup = {"schema": "envloop-magento-unseeded-prepare-cleanup-private-v1",
                   "index": args.index,
                   "adoption_sha256": sha(adoption_raw),
                   "app_container_id_sha256": app_hash,
                   "sidecar_container_id_sha256": search_hash,
                   "steps": processes,
                   "task_seeded": False,
                   "both_containers_cleaned": True,
                   "official_final_admitted": 0}
        receipt_path = sweep / f"case-{args.index:03d}/positive/recovery-cleanup.private.json"
        receipt_sha = write_new(receipt_path, cleanup)
        append_event(journal, {
            "event": "operator_reconciled_pre_task_prepare_failure",
            "index": args.index, "time": time.time(),
            "task_seeded": False,
            "both_containers_cleaned": True,
            "adoption_sha256": sha(adoption_raw),
            "cleanup_receipt_sha256": receipt_sha,
            "official_final_admitted": 0,
        })
        print(json.dumps({"status": "unseeded_prepare_failure_reconciled",
                          "cleanup_receipt_sha256": receipt_sha,
                          "official_final_admitted": 0}, sort_keys=True))
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


if __name__ == "__main__":
    main()
