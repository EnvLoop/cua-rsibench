"""Read-only, pre-result audit of a stopped Desktop caret episode.

This derives the failed logical ID from its private batch journal; no final
task text or ID is exported.  It never creates an E2B guest or treats a
counterfactual v4 frame acceptance as a passed saved-artifact control.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from hashlib import sha256
import io
import json
import os
from pathlib import Path

from PIL import Image, ImageChops

from . import qwen_v066_adapter as old_adapter
from . import qwen_v066_adapter_v4 as new_adapter
from .v066_caret_train_replay import replay_train_shape


def _digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _read_ref(root: Path, record: dict) -> bytes:
    relative = record.get("private_path")
    if type(relative) is not str:
        raise ValueError("Raw Desktop reference path missing")
    candidate = root / relative
    path = candidate.resolve()
    if not path.is_relative_to(root.resolve()) or candidate.is_symlink():
        raise ValueError("Raw Desktop reference escaped evidence root")
    raw = path.read_bytes()
    if len(raw) != record.get("bytes") or _digest(raw) != record.get("sha256"):
        raise ValueError("Raw Desktop frame differs from immutable receipt")
    return raw


def _rgb(raw: bytes) -> Image.Image:
    with Image.open(io.BytesIO(raw)) as opened:
        if opened.size != (1280, 800):
            raise ValueError("Raw Desktop frame shape changed")
        return opened.convert("RGB")


def _app(raw: bytes) -> bytes:
    return _rgb(raw).crop((0, 27, 1280, 780)).tobytes()


def _difference(first: bytes, second: bytes) -> tuple[int, tuple[int, ...]]:
    changed = ImageChops.difference(_rgb(first), _rgb(second)).convert("RGB")
    bounds = changed.getbbox()
    pixels = sum(any(pixel) for pixel in changed.getdata())
    return pixels, bounds or ()


def _caret_shape(first: bytes, second: bytes) -> bool:
    a, b = _rgb(first), _rgb(second)
    bounds = ImageChops.difference(a.crop((0, 27, 1280, 780)),
                                   b.crop((0, 27, 1280, 780))).getbbox()
    if bounds is None:
        return False
    left, top, right, bottom = bounds
    height = bottom - top
    if right - left != 1 or not 10 <= height <= 45:
        return False
    pairs = Counter((a.getpixel((left, y + 27)),
                     b.getpixel((left, y + 27)))
                    for y in range(top, bottom))
    return (all(before != after for before, after in pairs) and
            len(pairs) <= 3 and pairs.most_common(1)[0][1] >= height - 2)


def _train_corrob(train_root: Path) -> tuple[dict, int]:
    shape = replay_train_shape(train_root)
    repeated_applied = 0
    for directory in sorted(train_root.glob("v066-train-primitive-smoke-*")):
        receipt = json.loads((directory / "receipt.json").read_bytes())
        grouped = defaultdict(list)
        for row in receipt.get("physical_frame_resamples", []):
            step, attempt = row["step"], row["frame_attempt"]
            observed = (directory / f"frame-{step:02d}-{attempt}.png").read_bytes()
            changed = (directory / f"drift-{step:02d}-{attempt}.png").read_bytes()
            if _caret_shape(observed, changed):
                grouped[step].append((_app(observed), _app(changed)))
        applied = {row["step"] for row in receipt.get("steps", [])
                   if row.get("status") == "applied"}
        for step, pairs in grouped.items():
            if (step in applied and len(pairs) >= 2 and
                    pairs[0] == pairs[1]):
                repeated_applied += 1
    return shape, repeated_applied


def audit(*, run_dir: Path, attempts_root: Path,
          train_root: Path) -> tuple[dict, dict]:
    run_raw = (run_dir / "run-receipt.json").read_bytes()
    run = json.loads(run_raw)
    outcomes = run.get("task_outcomes", [])
    if (run.get("schema") !=
            "cua-native-wdi-v066-durable-continuation-run-private-v3" or
            run.get("status") != "stopped_for_reconciliation" or
            len(run.get("selected_private_task_ids", [])) != 2 or
            len(outcomes) != 1 or
            outcomes[0].get("status") !=
            "stopped_after_invalid_or_uncertain_attempt" or
            len(outcomes[0].get("attempts", [])) != 2 or
            [item.get("attempt") for item in outcomes[0]["attempts"]] !=
            ["positive", "near-miss"] or
            run.get("official_final_model_attempts") != 0 or
            run.get("official_final_admissions") != 0):
        raise ValueError("Stopped v3 batch journal changed")
    task_id = run["selected_private_task_ids"][0]
    if outcomes[0].get("private_task_id") != task_id:
        raise ValueError("Stopped batch task identity changed")
    if (attempts_root / run["selected_private_task_ids"][1]).exists():
        raise ValueError("Second selected ID is no longer untouched")
    positive_path = attempts_root / task_id / "positive" / "receipt.json"
    failed_path = attempts_root / task_id / "near-miss" / "receipt.json"
    positive_raw, failed_raw = positive_path.read_bytes(), failed_path.read_bytes()
    positive, failed = json.loads(positive_raw), json.loads(failed_raw)
    if (positive.get("status") != "control_passed" or
            positive.get("is_running_after_kill") is not False or
            positive.get("fair_verifier", {}).get("passed") is not True or
            not positive.get("saved_artifact") or
            failed.get("status") != "control_failed_or_infrastructure_invalid" or
            failed.get("error_type") != "PhysicalFrameDrift" or
            failed.get("contract_error_code") != "stale_frame" or
            failed.get("is_running_after_kill") is not False or
            failed.get("saved_artifact") is not None or
            failed.get("fair_verifier") is not None or
            failed.get("native_adapter_sha256") !=
            _digest(Path(old_adapter.__file__).read_bytes()) or
            len(failed.get("actor_steps", [])) != 15 or
            failed.get("official_final_admissions") != 0 or
            failed.get("official_hidden_final_model_attempts") != 0):
        raise ValueError("Old partial receipt changed or is not evaluator-only")
    _read_ref(attempts_root, positive["saved_artifact"])
    for row in failed["actor_steps"]:
        _read_ref(attempts_root, row["observation"])
        _read_ref(attempts_root, row["predispatch"])
    pairs = []
    for row in failed["physical_frame_resamples"]:
        pairs.append((row["step"], row["attempt"],
                      _read_ref(attempts_root, row["observed"]),
                      _read_ref(attempts_root, row["changed"])))
    failed_step = len(failed["actor_steps"])
    terminal = [(n, a, b) for step, n, a, b in pairs if step == failed_step]
    if (len(terminal) != 5 or [n for n, _a, _b in terminal] !=
            list(range(5))):
        raise ValueError("Terminal caret sample count/order changed")
    first_a, first_b = _app(terminal[0][1]), _app(terminal[0][2])
    if (not _caret_shape(terminal[0][1], terminal[0][2]) or
            any(_app(a) != first_a or _app(b) != first_b or
                not _caret_shape(a, b)
                for _n, a, b in terminal)):
        raise ValueError("Terminal application states are not one exact caret pair")
    first_pixel_count, first_bounds = _difference(
        terminal[0][1], terminal[0][2])
    if (first_pixel_count != 18 or
            (first_bounds[2] - first_bounds[0],
             first_bounds[3] - first_bounds[1]) != (1, 18)):
        raise ValueError("Terminal caret geometry changed")
    chrome = max(_difference(terminal[0][1], a)[0]
                 for _n, a, _b in terminal)
    if chrome != 151:
        raise ValueError("Window-chrome-only state count changed")
    train, repeated_applied = _train_corrob(train_root)
    if (train["train_attempts"] != 5 or
            train["train_drift_pairs"] != 28 or
            train["narrow_caret_shape_pairs"] != 9 or
            train["material_or_other_pairs_rejected"] != 19 or
            repeated_applied < 2):
        raise ValueError("Train-only source corroboration changed")
    private = {
        "schema": "cua-native-wdi-v066-caret-liveness-private-audit-v4",
        "status": "counterfactual_frame_guard_only_no_control_admission",
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "old_batch_run_receipt_sha256": _digest(run_raw),
        "old_positive_receipt_sha256": _digest(positive_raw),
        "old_failed_receipt_sha256": _digest(failed_raw),
        "private_task_id": task_id,
        "failed_action_step": failed_step,
        "applied_actions_before_failure": len(failed["actor_steps"]),
        "terminal_observation_alternate_pairs": len(terminal),
        "terminal_caret_bbox_xyxy": list(first_bounds),
        "terminal_first_pair_changed_pixels": first_pixel_count,
        "maximum_nonapplication_chrome_changed_pixels": chrome,
        "all_raw_failure_pairs_reopened": len(pairs),
        "train_only_shape_replay": train,
        "train_repeated_two_state_steps_with_applied_action": repeated_applied,
        "old_failed_attempt_preserved_and_charged": True,
        "old_negative_saved_state_available": False,
        "old_cold_reset_available": False,
        "fresh_full_trio_required_for_same_id": True,
        "at_most_one_fresh_full_trio_retry_eligible": True,
        "retry_dispatch_authorized": False,
        "provider_active_now_verified": False,
        "official_final_admissions": 0,
        "official_model_results": 0,
    }
    public = {
        "schema": "cua-native-wdi-v066-caret-liveness-public-audit-v4",
        "status": private["status"],
        "old_partial_positive_attempts": 1,
        "old_partial_near_miss_failures": 1,
        "old_partial_cold_resets": 0,
        "applied_actions_before_failure": private[
            "applied_actions_before_failure"],
        "terminal_observation_alternate_pairs": len(terminal),
        "application_difference_pixels": first_pixel_count,
        "application_difference_shape_px": [1, 18],
        "additional_window_chrome_pixels_outside_application": chrome,
        "all_raw_failure_pairs_reopened": len(pairs),
        "train_only_drift_pairs_reopened": train["train_drift_pairs"],
        "train_only_caret_shape_pairs": train["narrow_caret_shape_pairs"],
        "train_only_material_or_other_pairs_rejected": train[
            "material_or_other_pairs_rejected"],
        "train_repeated_two_state_steps_with_applied_action": repeated_applied,
        "v4_adapter_sha256": _digest(Path(new_adapter.__file__).read_bytes()),
        "old_adapter_sha256": _digest(Path(old_adapter.__file__).read_bytes()),
        "old_batch_run_receipt_sha256": _digest(run_raw),
        "old_failed_receipt_sha256": _digest(failed_raw),
        "at_most_one_fresh_full_trio_retry_eligible": True,
        "retry_dispatch_authorized": False,
        "new_e2b_creates": 0,
        "official_final_admissions": 0,
        "official_model_results": 0,
    }
    return private, public


def _write_new(path: Path, data: dict, *, private: bool) -> str:
    if path.exists():
        raise ValueError("Exclusive dated evidence path required")
    path.parent.mkdir(parents=True, exist_ok=True,
                      mode=0o700 if private else 0o755)
    if private:
        path.parent.chmod(0o700)
    raw = (json.dumps(data, sort_keys=True,
                      separators=(",", ":") if private else None,
                      indent=None if private else 2) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                 0o600 if private else 0o644)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return _digest(raw)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("run-dir", "attempts-root", "train-root",
                 "private-out", "public-out"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    if args.private_out.exists() or args.public_out.exists():
        raise ValueError("One-use evidence paths already exist")
    private, public = audit(run_dir=args.run_dir,
                            attempts_root=args.attempts_root,
                            train_root=args.train_root)
    public["v4_audit_source_sha256"] = _digest(Path(__file__).read_bytes())
    public["private_audit_sha256"] = _write_new(
        args.private_out, private, private=True)
    _write_new(args.public_out, public, private=False)
    print(json.dumps({key: public[key] for key in (
        "status", "all_raw_failure_pairs_reopened",
        "train_only_drift_pairs_reopened", "official_final_admissions")},
                     sort_keys=True))


if __name__ == "__main__":
    main()
