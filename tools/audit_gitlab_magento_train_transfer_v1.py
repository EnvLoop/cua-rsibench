"""Read-only independent reopening of staged train-transfer source packages.

Only aggregate counts and source hashes are printed. Private task content is
never printed or copied into the repository. This does not qualify a GUI task.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import stat

from gitlab_world import factory as gitlab_factory
from gitlab_world import train_transfer_analogues as gitlab_transfer
from magento_catalog_factory import train_transfer_analogues as magento_transfer


ROOT = Path(__file__).resolve().parents[1]


def _read_private(path: Path) -> dict:
    if (not path.is_file() or path.is_symlink() or
            stat.S_IMODE(path.stat().st_mode) != 0o600):
        raise ValueError("private transfer package must be a regular owner-only file")
    return json.loads(path.read_bytes())


def _same_public(path: Path, expected: dict) -> None:
    actual = json.loads(path.read_bytes())
    if actual != expected:
        raise ValueError("field-limited public transfer receipt differs from private source")


def audit(*, gitlab_world: Path, gitlab_private: Path, gitlab_public: Path,
          magento_inventory: Path, magento_seed: Path, magento_plan: Path,
          magento_private: Path, magento_public: Path) -> dict:
    world = _read_private(gitlab_world)
    staged_gitlab = _read_private(gitlab_private)
    gitlab_transfer.validate(staged_gitlab, world)
    gitlab_receipt = gitlab_transfer.public_receipt(staged_gitlab, world)
    _same_public(gitlab_public, gitlab_receipt)
    inventory_raw = magento_inventory.read_bytes()
    inventory = json.loads(inventory_raw)
    seed = magento_seed.read_text().strip()
    original = _read_private(magento_plan)
    staged_magento = _read_private(magento_private)
    magento_transfer.validate(staged_magento, inventory, sha256(inventory_raw).hexdigest(),
                              seed, original)
    magento_receipt = magento_transfer.public_receipt(
        staged_magento, inventory, sha256(inventory_raw).hexdigest(), seed, original)
    _same_public(magento_public, magento_receipt)
    if (sha256(inventory_raw).hexdigest() !=
            magento_receipt["source_binding"]["source_inventory_sha256"] or
            sha256(magento_plan.read_bytes()).hexdigest() !=
            json.loads(magento_transfer.SOURCE_RECEIPT.read_bytes())[
                "private_candidate_plan_sha256"] or
            world["source"]["excerpt_sha256"] != gitlab_factory.EXCERPT_SHA256):
        raise ValueError("pinned original source inputs differ")
    return {
        "schema": "envloop-gitlab-magento-train-transfer-reopen-audit-v1",
        "status": "source_only_private_reopen_passed_no_gui_or_model_result",
        "auditor_source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "gitlab_train_analogues": gitlab_receipt["supplemental_train_count"],
        "gitlab_workflow_counts": gitlab_receipt["workflow_counts"],
        "magento_train_analogues": magento_receipt["supplemental_train_count"],
        "magento_policy_counts": magento_receipt["policy_counts"],
        "magento_target_skus_per_case": magento_receipt["target_skus_per_case"],
        "protected_source_entity_overlap": 0,
        "gui_controls_passed": 0,
        "model_results": 0,
        "official_final_admitted": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gitlab-world", type=Path, required=True)
    parser.add_argument("--gitlab-private", type=Path, required=True)
    parser.add_argument("--gitlab-public", type=Path, default=ROOT / "docs/evidence/gitlab-train-transfer-two-per-skill-2026-09-29.json")
    parser.add_argument("--magento-inventory", type=Path, required=True)
    parser.add_argument("--magento-seed", type=Path, required=True)
    parser.add_argument("--magento-plan", type=Path, required=True)
    parser.add_argument("--magento-private", type=Path, required=True)
    parser.add_argument("--magento-public", type=Path, default=ROOT / "docs/evidence/magento-train-transfer-two-per-policy-v2-2026-09-29.json")
    args = parser.parse_args()
    print(json.dumps(audit(gitlab_world=args.gitlab_world,
                           gitlab_private=args.gitlab_private,
                           gitlab_public=args.gitlab_public,
                           magento_inventory=args.magento_inventory,
                           magento_seed=args.magento_seed,
                           magento_plan=args.magento_plan,
                           magento_private=args.magento_private,
                           magento_public=args.magento_public), sort_keys=True))


if __name__ == "__main__":
    main()
