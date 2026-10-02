"""Reproducible, *proposed* six-cell v0.6.6 action-source binding.

This is a source inventory, not a campaign freeze or dispatch authority. The
historical v0.6.5 Tinker preflight and any prior provider receipts are left as
they were. A future pre-campaign manifest must independently ratify this exact
bundle hash and bind every cell's runner, renderer and checkpoint lineage.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import scale_action_contract as base
from . import scale_action_contract_v066 as profile
from . import scale_action_output_v066 as output
from . import scale_vision_proxy as vision


SCHEMA = "cua-shared-action-output-bundle-v066-proposed-v1"
SOURCE_PATHS = (
    "src/cursibench/scale_action_contract.py",
    "src/cursibench/scale_action_contract_v066.py",
    "src/cursibench/scale_action_output_v062.py",
    "src/cursibench/scale_action_output_v064.py",
    "src/cursibench/scale_action_output_v065.py",
    "src/cursibench/scale_action_output_v066.py",
    "src/cursibench/scale_vision_proxy.py",
    "src/cursibench/shared_action_bundle_v066.py",
)
CELLS = (
    "powerpoint-web", "excel-web", "desktop-native",
    "odoo-community", "gitlab", "magento-admin",
)


def canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def build(repo_root: Path) -> dict:
    """Bind the exact shared source bytes without reading private tasks."""
    root = Path(repo_root).resolve()
    files = {}
    for relative in SOURCE_PATHS:
        path = root / relative
        if not path.is_file() or path.is_symlink():
            raise ValueError("shared_action_source_missing_or_symlink")
        files[relative] = digest(path.read_bytes())
    if (base.VERSION != "scale-computer-use-v0.6"
            or profile.ACTION_PROFILE_VERSION != "scale-action-profile-v0.6.6"
            or output.OUTPUT_VERSION != "scale-action-output-v0.6.6"
            or vision.MODEL != "Qwen/Qwen3.8-27B"):
        raise ValueError("shared_action_version_mismatch")
    payload = {
        "schema": SCHEMA,
        "status": "proposed_unratified_no_dispatch_authority",
        "trusted_action_version": base.VERSION,
        "action_profile_version": profile.ACTION_PROFILE_VERSION,
        "output_version": output.OUTPUT_VERSION,
        "model": vision.MODEL,
        "renderer": vision.RENDERER,
        "image_processor": vision.PROCESSOR,
        "model_prompt_sha256": digest(output.MODEL_ACTION_CONTRACT.encode()),
        "cell_ids": list(CELLS),
        "source_sha256s": files,
        "base_and_selected_profile_uniformity_verified": False,
        "six_cell_adapter_live_v066_verified": False,
        "official_final_attempts": 0,
        "researcher_campaigns": 0,
    }
    return {**payload, "bundle_sha256": digest(canonical(payload))}


def verify(repo_root: Path, proposed: dict) -> None:
    if type(proposed) is not dict or proposed != build(repo_root):
        raise ValueError("shared_action_bundle_source_or_field_mismatch")
