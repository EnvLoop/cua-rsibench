"""Pre-result six-cell selection environment cost classification.

The original-software deployment surface determines which real resource must
be reserved after a selection attempt starts. Self-hosted applications are
charged to the frozen storage/application-service planning budget; they do not
pretend to create an E2B sandbox or claim a provider invoice. This mapping is
source-bound with the campaign dispatcher before any official attempt.
"""

from __future__ import annotations

from hashlib import sha256
import json

from .full_study_matrix_v1 import CELLS


SCHEMA = "cua-full-study-selection-environment-v1"
BY_CELL = {
    "powerpoint-web": "e2b",
    "excel-web": "e2b",
    "desktop-native": "e2b",
    "odoo-community": "storage_application",
    "gitlab": "storage_application",
    "magento-admin": "storage_application",
}
if set(BY_CELL) != set(CELLS):
    raise RuntimeError("Selection environment map differs from six study cells")


def category(cell_id: str) -> str:
    try:
        return BY_CELL[cell_id]
    except KeyError:
        raise ValueError("Unknown full-study cell") from None


def paid_categories_valid(cell_id: str, categories: set[str]) -> bool:
    required = category(cell_id)
    return (type(categories) is set and
            {"tinker", required} <= categories and
            (required == "e2b" or "e2b" not in categories))


def binding_sha256() -> str:
    raw = (json.dumps({"schema": SCHEMA, "by_cell": BY_CELL},
                      sort_keys=True, separators=(",", ":")) + "\n").encode()
    return sha256(raw).hexdigest()
