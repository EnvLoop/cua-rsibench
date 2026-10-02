"""Self-contained, public-source WDI split fixture for Desktop worker tests.

Only the three committed Mexico *train* packages are copied. Remaining rows
are synthetic identities to exercise the 20/20/100 split gate, never gold or
hidden final packages. The fixture is built inside a temporary directory.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

from native_desktop_factory.factory import EXPECTED_COUNTS, json_bytes
from native_desktop_factory.source import COUNTRIES, EXPECTED_SHA256


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "native_desktop_factory/dev-fixtures"
WORKFLOWS = ("calc-growth", "calc-risk", "impress-deck", "writer-brief")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def make_fixture(root: Path) -> tuple[Path, Path]:
    countries = ["MEX", *[country for country in COUNTRIES if country != "MEX"]]
    mapping = {
        "schema": "cua-native-wdi-private-map-v1",
        "train": countries[:5], "selection": countries[5:10],
        "final_candidate": countries[10:], "variant_salt": "a" * 64,
    }
    private_map = root / "private-map.json"
    private_map.write_bytes(json_bytes(mapping))
    private_map.chmod(0o600)
    candidate_root = root / "candidate-packages"
    candidate_root.mkdir()
    rows = []
    for split in ("train", "selection", "final_candidate"):
        for country in mapping[split]:
            for workflow in WORKFLOWS:
                public_id = "wdi-native-mex-" + workflow
                source = PUBLIC / public_id
                if split == "train" and country == "MEX" and source.is_dir():
                    row = json.loads((source / "package.json").read_bytes())
                    target = candidate_root / "train" / row["task_id"]
                    shutil.copytree(source, target)
                    # Public development packages contain controls, which are
                    # evaluator-only. The actor cannot access this filesystem.
                else:
                    task_id = f"offline-{split}-{country.lower()}-{workflow}"
                    row = {
                        "task_id": task_id,
                        "package_sha256": _sha(task_id.encode()),
                        "workflow": workflow,
                        "source_groups": [f"wdi-country:{country}"],
                        "template_group": f"{split}:offline-{workflow}",
                        "instance_group": task_id,
                        "split": split,
                    }
                rows.append(row)
    inventory = {
        "schema": "cua-native-wdi-candidate-inventory-v1",
        "design_revision": "v2-distinct-structures",
        "source_sha256": EXPECTED_SHA256,
        "private_map_sha256": _sha(private_map.read_bytes()),
        "counts": EXPECTED_COUNTS,
        "status": "offline_test_fixture_not_runtime_admitted",
        "tasks": rows,
    }
    (candidate_root / "candidate-inventory.json").write_bytes(
        json_bytes(inventory))
    return candidate_root, private_map
