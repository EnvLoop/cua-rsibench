"""Publish English aggregate-only Desktop 20-selection worker evidence.

The mandatory suite uses fake E2B/Tinker providers and committed public WDI
development files. Optional private candidate paths permit a read-only audit
of the actual 20 selection packages; IDs, gold, files, and frames stay local.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from decimal import Decimal

from native_desktop_factory import selection_worker_v066 as worker
from native_desktop_factory import selection_profile_calibration_v066 as profiles


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (ROOT / "docs/evidence/"
          "native-wdi-v066-selection-worker-offline-2026-09-28.json")
TEST_PATH = ROOT / "tests/test_native_desktop_selection_worker_v066.py"
PROFILE_TEST_PATH = (ROOT /
    "tests/test_native_desktop_selection_profile_calibration_v066.py")


def _sha(path: Path) -> str:
    if not path.is_file() or path.is_symlink():
        raise ValueError("selection_offline_source_missing_or_symlink")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(*, candidate_root: Path | None = None,
          private_map: Path | None = None) -> dict:
    if (candidate_root is None) != (private_map is None):
        raise ValueError("Private candidate and split-map paths must be paired")
    result = subprocess.run(
        [sys.executable, "-m", "unittest",
         "tests.test_native_desktop_selection_worker_v066",
         "tests.test_native_desktop_selection_profile_calibration_v066",
         "-q"],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
        env={**os.environ,
             "PYTHONPATH": str(ROOT) + os.pathsep + str(ROOT / "src") +
             os.pathsep + os.environ.get("PYTHONPATH", ""),
             "E2B_API_KEY": "", "TINKER_API_KEY": "",
             "OPENAI_API_KEY": ""},
        check=False)
    output = result.stdout + result.stderr
    match = re.search(r"Ran (\d+) tests? in ", output)
    if (result.returncode or match is None or
            "\nOK\n" not in output or "skipped=" in output):
        raise ValueError("native_selection_synthetic_tests_failed_or_skipped")
    private_audit = {"status": "not_supplied_in_public_checkout",
                     "selection_package_count": None,
                     "application_counts": None,
                     "candidate_inventory_sha256": None}
    if candidate_root is not None:
        root = Path(candidate_root)
        raw = (root / "candidate-inventory.json").read_bytes()
        inventory = json.loads(raw)
        identities = [{key: row[key] for key in
                       ("task_id", "package_sha256")}
                      for row in inventory["tasks"]
                      if row["split"] == "selection"]
        packages = worker._load_selection_packages(
            root, Path(private_map), identities,
            hashlib.sha256(raw).hexdigest())
        private_audit = {
            "status": "read_only_actual_wdi_v2_selection_preflight_passed",
            "selection_package_count": len(packages),
            "application_counts": dict(sorted(Counter(
                "Calc" if item.filename.endswith(".xlsx") else
                "Impress" if item.filename.endswith(".pptx") else
                "Writer" for item in packages).items())),
            "candidate_inventory_sha256": hashlib.sha256(raw).hexdigest(),
        }
    return {
        "schema": "cua-native-wdi-v066-selection-worker-offline-public-v1",
        "checked_date": "2026-09-28",
        "status": "implemented_fake_provider_only_not_live",
        "cell_id": "desktop-native",
        "action_profile": worker.ACTION_PROFILE_VERSION,
        "original_software": "LibreOffice Calc, Impress and Writer",
        "selection_result_schema": worker.RESULT_SCHEMA,
        "private_paid_task_ledger_schema": worker.LEDGER_SCHEMA,
        "fake_complete_selection_task_count": worker.MAX_TASKS,
        "fake_complete_task_bound_e2b_paid_attempts": 2 * worker.MAX_TASKS,
        "fake_complete_task_bound_tinker_paid_attempts": 2 * worker.MAX_TASKS,
        "fake_complete_tinker_setup_paid_attempts": 1,
        "fake_complete_paid_coverage_passed": True,
        "live_task_bound_selection_profile_manifest_present": False,
        "offline_selection_profile_plan_task_count": profiles.MAX_TASKS,
        "offline_selection_profile_new_lease_reserve_usd": str(
            profiles.LEASE_RESERVE_USD * Decimal(profiles.MAX_TASKS)),
        "selection_profile_separate_lane_cap_usd": str(profiles.LANE_CAP_USD),
        "selection_profile_controller_source_sha256": _sha(
            ROOT / "native_desktop_factory/selection_profile_calibration_v066.py"),
        "actual_private_source_preflight": private_audit,
        "runtime_sha256": worker.runtime_sha256(),
        "verifier_sha256": worker.verifier_sha256(),
        "adapter_sha256": worker.adapter_sha256(),
        "runtime_source_sha256s": worker.source_hashes(),
        "test_source_sha256": _sha(TEST_PATH),
        "profile_test_source_sha256": _sha(PROFILE_TEST_PATH),
        "receipt_builder_sha256": _sha(Path(__file__)),
        "test_count": int(match.group(1)),
        "test_status": "passed_fake_provider_only",
        "new_e2b_sandbox_creates": 0,
        "new_tinker_model_calls": 0,
        "new_selection_scores_registered": 0,
        "official_final_admissions": 0,
        "provider_invoice_reconciled": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path)
    parser.add_argument("--private-map", type=Path)
    parser.add_argument("--out", type=Path, default=OUTPUT)
    args = parser.parse_args()
    if args.out.exists() or args.out.is_symlink():
        raise FileExistsError("Refusing to overwrite selection offline evidence")
    value = build(candidate_root=args.candidate_root,
                  private_map=args.private_map)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: value[key] for key in (
        "test_count", "fake_complete_selection_task_count",
        "new_e2b_sandbox_creates", "new_tinker_model_calls",
        "new_selection_scores_registered")}, sort_keys=True))


if __name__ == "__main__":
    main()
