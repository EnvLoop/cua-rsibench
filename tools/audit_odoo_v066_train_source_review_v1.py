"""Hash-bind independent visual review of one original Odoo train source frame.

This auditor regenerates the evaluator-private PDF and its page rendering,
checks the saved GUI PNG/reviewer artifacts, and publishes only aggregate
provenance. The content match itself is a recorded human visual judgment.
No Docker, browser, provider, model, or task mutation occurs.
"""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import io
import json
from pathlib import Path
import stat
import subprocess

from PIL import Image


SCHEMA = "envloop-odoo-v066-independent-source-visual-review-audit-v1"
EXPECTED_SECTIONS = (
    "document_title", "rfq_reference", "supplier_identity",
    "three_line_skus_and_descriptions",
    "three_line_quantities_and_unit_prices",
    "three_line_promised_dates", "source_preservation_instruction",
)


class SourceReviewAuditError(ValueError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise SourceReviewAuditError(code)


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _private(path: Path, *, directory: bool = False) -> None:
    require(not path.is_symlink() and
            (path.is_dir() if directory else path.is_file()) and
            stat.S_IMODE(path.stat().st_mode) & 0o077 == 0,
            "source_review_private_path_missing_or_permissive")


def _json(path: Path) -> dict:
    _private(path)
    try:
        value = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise SourceReviewAuditError("source_review_json_invalid") from None
    require(type(value) is dict, "source_review_json_invalid")
    return value


def _utc(value: str) -> datetime:
    try:
        timestamp = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise SourceReviewAuditError("source_review_timestamp_invalid") from None
    require(timestamp.tzinfo is not None, "source_review_timestamp_invalid")
    return timestamp


def _render_pdf(raw: bytes) -> bytes:
    result = subprocess.run(
        ["pdftoppm", "-f", "1", "-l", "1", "-singlefile", "-png", "-"],
        input=raw, capture_output=True, check=True, timeout=30)
    require(result.stdout.startswith(b"\x89PNG\r\n\x1a\n"),
            "private_source_pdf_render_failed")
    return result.stdout


def audit(*, attempt_dir: Path, train_private: Path,
          pilot_binding_path: Path) -> dict:
    attempt = Path(attempt_dir)
    train = Path(train_private)
    _private(attempt, directory=True)
    _private(train, directory=True)
    binding = _json(pilot_binding_path)
    draft = _json(attempt / "draft.private.json")
    sealed = _json(attempt / "attempt.private.json")
    review = _json(attempt / "source-review-v2.json")
    support = _json(attempt / "source-review-support-v2.private.json")
    old_review_path = attempt / "source_review.json"
    old_support_path = attempt / "source-review-support.private.json"
    _private(old_review_path)
    _private(old_support_path)
    task = binding.get("task")
    require(type(task) is dict and
            binding.get("schema") == "envloop-odoo-v066-train-pilot-binding-v2" and
            binding.get("selection_or_hidden_task_values_included") is False and
            binding.get("official_final_tasks_admitted") == 0 and
            task.get("split") == "train" and task.get("family") == "purchase" and
            draft.get("task_id") == task.get("task_id") and
            draft.get("status") == "awaiting_independent_source_frame_review" and
            sealed.get("status") == "completed_with_raw_evaluator_evidence" and
            sealed.get("refs", {}).get("source_review") == {
                "path": "source-review-v2.json",
                "sha256": digest((attempt / "source-review-v2.json").read_bytes())} and
            sealed.get("refs", {}).get("source_frame") ==
            draft.get("refs", {}).get("source_frame"),
            "source_review_task_or_seal_unbound")
    source_ref = draft["refs"]["source_frame"]
    source_path = attempt / source_ref["path"]
    require(source_path.resolve().is_relative_to(attempt.resolve()) and
            source_path.parent == attempt / "frames",
            "source_frame_path_unsafe")
    _private(source_path)
    source_png = source_path.read_bytes()
    require(digest(source_png) == source_ref["sha256"],
            "source_frame_bytes_changed")
    with Image.open(io.BytesIO(source_png)) as opened:
        opened.verify()
    with Image.open(io.BytesIO(source_png)) as opened:
        dimensions = list(opened.size)
    require(dimensions == [1440, 1000], "source_frame_viewport_changed")
    world = _json(train / "partition_cases.json")
    require(world.get("split") == "train", "source_world_not_train")
    cases = [case for case in world["cases"]["purchase"]
             if case["id"] == task["task_id"]]
    require(len(cases) == 1, "source_case_not_unique")
    from enterprise_fallback.odoo18.partition_factory import source_asset
    source_pdf = source_asset(cases[0], world)
    source_sha = digest(source_pdf)
    render_sha = digest(_render_pdf(source_pdf))
    require(source_sha == task["source_asset_sha256"] and
            review.get("schema") ==
            "envloop-odoo-v066-independent-source-frame-review-v1" and
            review.get("decision") == "source_visible_in_original_odoo_gui" and
            review.get("reviewer_role") ==
            "independent_visual_source_reviewer" and
            review.get("reviewer_id_sha256") !=
            sealed.get("controller_id_sha256") and
            review.get("source_frame_sha256") == source_ref["sha256"] and
            review.get("source_asset_sha256") == source_sha and
            review.get("source_label") == task["source_label"] and
            _utc(review.get("reviewed_at_utc")) >=
            _utc(draft.get("finished_at_utc")),
            "source_review_independent_frame_binding_invalid")
    require(support.get("schema") ==
            "envloop-odoo-v066-source-visual-review-support-v2" and
            support.get("review_method") ==
            "manual_side_by_side_original_odoo_frame_and_regenerated_private_source_pdf" and
            support.get("source_frame_sha256") == source_ref["sha256"] and
            support.get("source_asset_sha256") == source_sha and
            support.get("source_pdf_render_sha256") == render_sha and
            support.get("source_frame_dimensions") == dimensions and
            support.get("matched_sections") == list(EXPECTED_SECTIONS) and
            support.get("reviewer_id_sha256") == review["reviewer_id_sha256"] and
            support.get("reviewed_at_utc") == review["reviewed_at_utc"] and
            support.get("source_values_publicly_disclosed") is False and
            review.get("support_receipt_sha256") ==
            digest((attempt / "source-review-support-v2.private.json").read_bytes()) and
            support.get("supersedes_prior_support_sha256") ==
            digest(old_support_path.read_bytes()) and
            support.get("prior_review_retained_sha256") ==
            digest(old_review_path.read_bytes()) and
            review.get("supersedes_prior_review_sha256") ==
            digest(old_review_path.read_bytes()),
            "corrected_visual_review_support_unbound")
    return {
        "schema": SCHEMA,
        "status": "independent_visual_source_review_attested_and_hash_bound",
        "source_frame_sha256": source_ref["sha256"],
        "source_asset_sha256": source_sha,
        "source_pdf_render_sha256": render_sha,
        "private_corrected_review_sha256":
            digest((attempt / "source-review-v2.json").read_bytes()),
        "private_corrected_support_sha256":
            digest((attempt / "source-review-support-v2.private.json").read_bytes()),
        "private_attempt_sha256": digest((attempt / "attempt.private.json").read_bytes()),
        "visual_sections_attested": len(EXPECTED_SECTIONS),
        "manual_visual_match_is_review_attestation_not_pixel_equivalence": True,
        "earlier_incomplete_review_artifacts_retained_and_superseded": True,
        "official_final_tasks_admitted": 0,
        "model_attempts": 0,
        "source_auditor_sha256": digest(Path(__file__).read_bytes()),
    }


if __name__ == "__main__":
    import argparse
    import os

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt-dir", type=Path, required=True)
    parser.add_argument("--train-private", type=Path, required=True)
    parser.add_argument("--pilot-binding", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    result = audit(attempt_dir=args.attempt_dir,
                   train_private=args.train_private,
                   pilot_binding_path=args.pilot_binding)
    raw = (json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n").encode()
    fd = os.open(args.public_out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps({"schema": result["schema"], "status": result["status"],
                      "visual_sections_attested": result["visual_sections_attested"],
                      "official_final_tasks_admitted": 0}, sort_keys=True))
