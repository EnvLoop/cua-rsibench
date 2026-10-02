"""Publish a field-limited PowerPoint-web chart-edit feasibility receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def write_new(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-receipt", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raw = args.private_receipt.read_bytes()
    receipt = json.loads(raw)
    require(receipt["schema"] == "envloop-ppt-web-chart-legend-feasibility-private-v1" and
            receipt["selected_native_chart"] is True and
            receipt["observed_edit_data"] is False and
            receipt["observed_edit_in_excel"] is False and
            receipt["observed_chart_design_tab"] is False and
            receipt["observed_context_menu_edit_data"] is False and
            receipt["download_exactly_unchanged"] is True and
            receipt["model_calls"] == receipt["official_final_admitted"] ==
            receipt["task_scores"] == 0,
            "Private train-source GUI feasibility observation changed")
    public = {
        "schema": "envloop-ppt-web-chart-feasibility-public-v1",
        "status": "imported_train_source_native_chart_edit_control_not_observed",
        "checked_utc": receipt["checked_utc"],
        "private_receipt_sha256": hashlib.sha256(raw).hexdigest(),
        "native_chart_selected": True,
        "edit_data_or_excel_control_observed": False,
        "downloaded_deck_unchanged": True,
        "scope": "one imported native chart in one dedicated personal PowerPoint-web account",
        "pre_result_workflow_revision": "chart_series_relabel_to_chart_caption_reconciliation",
        "old_workflow_final_candidate_count": 10,
        "model_calls": 0,
        "official_final_admitted": 0,
    }
    write_new(args.out, (json.dumps(public, indent=2, sort_keys=True) + "\n").encode())
    print(json.dumps({"status": public["status"],
                      "private_receipt_sha256": public["private_receipt_sha256"],
                      "official_final_admitted": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
