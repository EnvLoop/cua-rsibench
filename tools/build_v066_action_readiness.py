"""Publish reproducible *candidate* v0.6.6 source and adapter readiness.

Only public source files and synthetic unit tests are read. No provider,
browser, E2B session, private task inventory or hidden final is touched.
Neither output is a ratified six-cell pre-campaign manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from cursibench import shared_action_bundle_v066 as shared


SCHEMA = "cua-six-cell-v066-adapter-readiness-proposed-v1"
TEST_MODULES = (
    "tests.test_scale_action_contract_v066",
    "tests.test_scale_action_output_v066",
    "tests.test_native_desktop_v066_adapter",
    "tests.test_shared_v066_train_adapters",
    "tests.test_shared_action_bundle_v066",
)
SOURCE_GROUPS = {
    "powerpoint-web": (
        "tools/office_web_e2b_v066_train_adapter.py",
        "tools/office_web_e2b_train_runner_v1.py",
    ),
    "excel-web": (
        "tools/excel_web_e2b_v066_train_adapter.py",
        "tools/excel_web_e2b_train_runner_v1.py",
    ),
    "desktop-native": (
        "native_desktop_factory/qwen_v066_adapter.py",
        "native_desktop_factory/qwen_v064_adapter.py",
        "native_desktop_factory/v066_control_plan.py",
    ),
    "odoo-community": (
        "enterprise_fallback/odoo18/odoo_v066_train_adapter.py",
        "enterprise_fallback/odoo18/odoo_native_adapter.py",
        "enterprise_fallback/odoo18/official_runner_v065.py",
    ),
    "gitlab": (),
    "magento-admin": (
        "tools/magento_v066_train_adapter.py",
        "tools/run_magento_model_pilot_v063.py",
        "tools/run_magento_model_pilot_v06.py",
    ),
}
PROPOSED_ADAPTER = {
    "powerpoint-web": "tools/office_web_e2b_v066_train_adapter.py",
    "excel-web": "tools/excel_web_e2b_v066_train_adapter.py",
    "desktop-native": "native_desktop_factory/qwen_v066_adapter.py",
    "odoo-community": "enterprise_fallback/odoo18/odoo_v066_train_adapter.py",
    "gitlab": None,
    "magento-admin": "tools/magento_v066_train_adapter.py",
}


def _hash(path: Path) -> str:
    if not path.is_file() or path.is_symlink():
        raise ValueError("public_source_missing_or_symlink")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def synthetic_tests(repo_root: Path) -> dict:
    root = Path(repo_root).resolve()
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join((str(root), str(root / "src")))
    command = [sys.executable, "-m", "unittest", *TEST_MODULES]
    result = subprocess.run(command, cwd=root, env=environment,
                            capture_output=True, text=True, timeout=90,
                            check=False)
    output = result.stdout + result.stderr
    match = re.search(r"Ran (\d+) tests? in ", output)
    if result.returncode or match is None or "\nOK\n" not in output:
        raise ValueError("v066_synthetic_tests_failed")
    return {
        "test_modules": list(TEST_MODULES),
        "test_count": int(match.group(1)),
        "status": "passed_synthetic_only",
        "provider_calls": 0,
        "live_application_actions": 0,
        "test_source_sha256s": {
            "tests/" + module.rsplit(".", 1)[-1] + ".py":
                _hash(root / ("tests/" + module.rsplit(".", 1)[-1] + ".py"))
            for module in TEST_MODULES
        },
    }


def build(repo_root: Path) -> tuple[dict, dict]:
    root = Path(repo_root).resolve()
    bundle = shared.build(root)
    tests = synthetic_tests(root)
    cells = []
    for cell in shared.CELLS:
        sources = {path: _hash(root / path) for path in SOURCE_GROUPS[cell]}
        proposed = PROPOSED_ADAPTER[cell]
        cells.append({
            "cell_id": cell,
            "adapter_source_sha256s": sources,
            "v066_adapter_source": proposed,
            "v066_parser_and_gui_mapping_synthetic":
                "passed" if proposed is not None else "not_implemented_in_this_branch",
            "historical_runner_wired_to_v066": False,
            "live_v066_train_or_selection_smoke": "not_verified",
            "cloud_or_guest_source_binding_v066": "not_verified",
            "fresh_v066_final_gui_control_trios": 0,
            "official_final_admissions": 0,
            "official_model_outcomes": 0,
        })
    ledger = {
        "schema": SCHEMA,
        "status": "development_evidence_only_not_ratified",
        "shared_action_bundle_sha256": bundle["bundle_sha256"],
        "shared_action_output_version": bundle["output_version"],
        "test_evidence": tests,
        "cell_ids": list(shared.CELLS),
        "cells": cells,
        "adapter_ledger_builder_sha256": _hash(
            root / "tools/build_v066_action_readiness.py"),
        "six_cell_live_smokes_complete": False,
        "pre_campaign_action_profile_ratified": False,
        "official_final_identities": 0,
        "researcher_campaigns": 0,
    }
    return bundle, ledger


def markdown(bundle: dict, ledger: dict) -> str:
    states = []
    for cell in ledger["cells"]:
        name = cell["cell_id"]
        tested = cell["v066_parser_and_gui_mapping_synthetic"]
        states.append(f"| {name} | {tested} | No | Not verified | 0 |")
    return (
        "# Proposed shared v0.6.6 action profile and adapter readiness\n\n"
        "**Status: unratified development evidence.** This source-byte binding "
        "does not authorize hidden-final observations, model selection or training. "
        "The historical v0.6.5 Tinker bundle and provider receipts are unchanged.\n\n"
        f"Shared candidate bundle SHA-256: `{bundle['bundle_sha256']}`. "
        f"The bundle binds {len(bundle['source_sha256s'])} shared source files, "
        "the Qwen renderer/preprocessor identifiers and the exact v0.6.6 "
        "model-action prompt bytes. It is regenerated from tracked source.\n\n"
        f"{ledger['test_evidence']['test_count']} synthetic contract/adapter "
        "tests passed with zero provider calls and zero live application "
        "actions. These tests prove local parser/dispatch mapping only.\n\n"
        "| Cell | Synthetic v0.6.6 mapping | Historical runner wired | "
        "Live v0.6.6 smoke | Fresh final GUI trios |\n"
        "| --- | --- | --- | --- | ---: |\n"
        + "\n".join(states) + "\n\n"
        "The PowerPoint-web and Excel-web modules are bounded train-only E2B "
        "mappings; neither historical runner selects them. Odoo's v0.6.5 "
        "official gate remains closed and unchanged. Magento's older pinned "
        "pilot remains unchanged. The Desktop module has a prospective grammar "
        "plan, but no fresh v0.6.6 per-ID GUI trios. GitLab has no adapter "
        "mapping in this branch and is being audited separately.\n\n"
        "Before ratification, each application needs a source-bound live "
        "train/selection smoke under the same prompt, parser and physical-frame "
        "checks; source/runtime and budget freezes remain separate gates. "
        "All 600 official identities, 24 researcher campaigns and final model "
        "outcomes remain unstarted.\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path,
                        default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-prefix", type=Path, required=True)
    args = parser.parse_args()
    root = args.repo_root.resolve()
    bundle, ledger = build(root)
    prefix = args.output_prefix.resolve()
    if not prefix.is_relative_to(root / "docs/evidence"):
        raise ValueError("public_evidence_output_required")
    prefix.parent.mkdir(parents=True, exist_ok=True)
    files = {
        prefix.with_name(prefix.name + "-bundle.json"): shared.canonical(bundle),
        prefix.with_name(prefix.name + "-ledger.json"): shared.canonical(ledger),
        prefix.with_name(prefix.name + "-readiness.md"):
            markdown(bundle, ledger).encode(),
    }
    for path in files:
        if path.exists() or path.is_symlink():
            raise FileExistsError("proposed_v066_evidence_already_exists")
    for path, content in files.items():
        path.write_bytes(content)
    print(json.dumps({"bundle_sha256": bundle["bundle_sha256"],
                      "synthetic_test_count": ledger["test_evidence"]["test_count"],
                      "official_final_identities": 0, "campaigns": 0},
                     sort_keys=True))


if __name__ == "__main__":
    main()
