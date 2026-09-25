"""Bounded trusted native save for private final Impress candidate baselines.

One E2B Desktop instance normalizes at most `--max-items` PPTX inputs. It is
trusted setup, never a model/actor result. Items are adopted into the candidate
inventory only after the sandbox is verified terminated; failures are retained.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import time

if __package__:
    from .adopt_normalized_impress import adopt
    from .verify import pptx_shape_structure, pptx_slide_shapes
else:
    from adopt_normalized_impress import adopt
    from verify import pptx_shape_structure, pptx_slide_shapes


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def window_title(sandbox) -> str:
    return sandbox.commands.run("xdotool getactivewindow getwindowname 2>/dev/null || true").stdout.strip()


def wait_open(sandbox, filename: str, *, seconds: int = 35) -> str:
    last = ""
    for _ in range(seconds):
        last = window_title(sandbox)
        if filename in last and "LibreOffice Impress" in last:
            return last
        if last.startswith("Tip of the Day"):
            sandbox.left_click(880, 535)
        time.sleep(1)
    raise TimeoutError("Impress input did not become the visible active window")


def neutral_save(sandbox, task_id: str, source: bytes, output_dir: Path) -> dict:
    filename = task_id + ".pptx"
    remote = "/home/user/" + filename
    output_dir.mkdir(parents=True, exist_ok=False)
    receipt = {"schema": "cua-native-impress-trusted-normalization-v1",
               "status": "started", "original_sha256": digest(source)}
    try:
        sandbox.files.write(remote, source)
        if bytes(sandbox.files.read(remote, format="bytes")) != source:
            raise ValueError("Trusted input upload/readback differed")
        sandbox.open(remote)
        receipt["opened_window"] = wait_open(sandbox, filename)
        # Native Office may display the first-run tip after the file title first
        # becomes active. Wait for the GUI to settle and dismiss it if present.
        time.sleep(2)
        if window_title(sandbox).startswith("Tip of the Day"):
            sandbox.left_click(880, 535)
            time.sleep(1)
        if filename not in window_title(sandbox):
            raise ValueError("Wrong active Impress document")
        (output_dir / "opened.png").write_bytes(bytes(sandbox.screenshot()))
        sandbox.press(["ctrl", "s"])
        time.sleep(1.5)
        title = window_title(sandbox)
        if title.startswith("Tip of the Day"):
            sandbox.left_click(880, 535)
            time.sleep(1)
            sandbox.press(["ctrl", "s"])
            time.sleep(1.5)
            title = window_title(sandbox)
        if title == "Confirm File Format":
            sandbox.left_click(790, 519)
            time.sleep(2)
        receipt["saved_window"] = window_title(sandbox)
        if filename not in receipt["saved_window"]:
            raise ValueError("Native save did not return to input file")
        normalized = bytes(sandbox.files.read(remote, format="bytes"))
        if normalized == source:
            raise ValueError("Native save did not reserialize the input")
        if pptx_slide_shapes(source) != pptx_slide_shapes(normalized):
            raise ValueError("Neutral save changed slide text or order")
        if pptx_shape_structure(source) != pptx_shape_structure(normalized):
            raise ValueError("Neutral save changed drawable object structure")
        (output_dir / "normalized.pptx").write_bytes(normalized)
        receipt["normalized_sha256"] = digest(normalized)
        receipt["status"] = "neutral_save_observed"
    except Exception as exc:
        receipt["status"] = "normalization_failed"
        receipt["error_type"] = type(exc).__name__
    return receipt


def execute(candidate_root: Path, output_root: Path, *, max_items: int,
            lease_seconds: int, max_reserved_usd: float, usd_per_hour_upper: float) -> dict:
    if not os.environ.get("E2B_API_KEY"):
        raise ValueError("E2B_API_KEY missing")
    if output_root.exists():
        raise ValueError("Refusing to overwrite a normalization batch")
    if not 1 <= max_items <= 25 or not 180 <= lease_seconds <= 1200:
        raise ValueError("Invalid item/lease bound")
    if usd_per_hour_upper <= 0 or max_reserved_usd <= 0:
        raise ValueError("Positive cost caps required")
    reserve = lease_seconds / 3600 * usd_per_hour_upper
    if reserve > max_reserved_usd:
        raise ValueError("Worst-case sandbox lease exceeds configured USD cap")
    inventory = json.loads((candidate_root / "candidate-inventory.json").read_bytes())
    if inventory.get("design_revision") != "v2-distinct-structures":
        raise ValueError("Expected v2 distinct-template candidate inventory")
    rows = [r for r in inventory["tasks"] if r["split"] == "final_candidate"
            and r["workflow"] == "impress-deck" and "normalization" not in r]
    rows.sort(key=lambda row: row["task_id"])
    rows = rows[:max_items]
    if not rows:
        raise ValueError("No unnormalized final Impress candidates")
    output_root.mkdir(parents=True)
    from e2b_desktop import Sandbox
    sandbox = None
    batch = {"schema": "cua-native-impress-batch-normalization-v1", "status": "started",
             "max_items": max_items, "lease_seconds": lease_seconds,
             "usd_per_hour_upper": usd_per_hour_upper, "reserved_usd_upper": reserve,
             "sdk_version": importlib.metadata.version("e2b-desktop"), "items": []}
    per_item = {}
    started = time.monotonic()
    try:
        sandbox = Sandbox.create(template="desktop", resolution=(1280, 800),
                                 timeout=lease_seconds, allow_internet_access=False)
        batch["sandbox_id_sha256"] = digest(sandbox.sandbox_id.encode())
        probe = sandbox.commands.run("libreoffice --version; sha256sum /usr/bin/libreoffice")
        if probe.exit_code != 0 or "LibreOffice 7.3.7.2" not in probe.stdout:
            raise ValueError("LibreOffice runtime mismatch")
        batch["runtime_probe"] = probe.stdout.strip()
        resources = sandbox.commands.run("nproc; awk '/MemTotal:/ {print $2}' /proc/meminfo")
        try:
            cpu_text, memory_kib_text = resources.stdout.strip().splitlines()[:2]
            cpu_count, memory_kib = int(cpu_text), int(memory_kib_text)
        except (TypeError, ValueError):
            raise ValueError("Desktop CPU/RAM shape not measurable") from None
        batch["resource_probe"] = {"vcpu_visible": cpu_count,
                                   "memory_kib_visible": memory_kib}
        if cpu_count > 8 or memory_kib > 8 * 1024 * 1024:
            raise ValueError("Desktop shape exceeds priced 8-vCPU/8-GiB planning bound")
        # Official E2B 2026-09-25 table: 8 vCPU $0.000112/s and 8 GiB
        # $0.000036/s, or $0.5328/h before any plan charges or credits.
        if usd_per_hour_upper < 0.5328:
            raise ValueError("USD/hour upper is below published 8-vCPU/8-GiB usage rate")
        for row in rows:
            if time.monotonic() - started > lease_seconds - 45:
                batch["stop_reason"] = "lease_headroom_exhausted"
                break
            task_id = row["task_id"]
            path = candidate_root / "final_candidate" / task_id / (task_id + ".pptx")
            source = path.read_bytes()
            if digest(source) != row["input_sha256"]:
                batch["items"].append({"task_id": task_id, "status": "input_hash_changed"})
                continue
            item_dir = output_root / task_id
            receipt = neutral_save(sandbox, task_id, source, item_dir)
            receipt.update({"sandbox_id_sha256": batch["sandbox_id_sha256"],
                            "runtime_probe": batch["runtime_probe"]})
            per_item[task_id] = (item_dir, receipt)
            batch["items"].append({"task_id": task_id, "status": receipt["status"],
                                   "original_sha256": receipt["original_sha256"],
                                   "normalized_sha256": receipt.get("normalized_sha256")})
    except Exception as exc:
        batch["error_type"] = type(exc).__name__
        batch["status"] = "error"
    finally:
        if sandbox is not None:
            try:
                batch["kill_returned"] = bool(sandbox.kill())
                batch["is_running_after_kill"] = bool(sandbox.is_running(request_timeout=8))
            except Exception as exc:
                batch["kill_error_type"] = type(exc).__name__
        batch["elapsed_seconds"] = round(time.monotonic() - started, 3)
        clean = batch.get("kill_returned") is True and batch.get("is_running_after_kill") is False
        for task_id, (item_dir, receipt) in per_item.items():
            receipt["kill_returned"] = batch.get("kill_returned")
            receipt["is_running_after_kill"] = batch.get("is_running_after_kill")
            if not clean:
                receipt["status"] = "cleanup_unverified"
            (item_dir / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        if clean:
            for task_id, (item_dir, receipt) in per_item.items():
                if receipt["status"] == "neutral_save_observed":
                    try:
                        adopt(candidate_root, task_id, item_dir)
                        batch.setdefault("adopted_task_ids", []).append(task_id)
                    except Exception as exc:
                        batch.setdefault("adoption_errors", []).append({"task_id": task_id,
                                                                         "error_type": type(exc).__name__})
        batch["status"] = ("finished" if clean and "error_type" not in batch else
                           "cleanup_unverified" if not clean else "error")
        (output_root / "batch-receipt.json").write_text(json.dumps(batch, indent=2, sort_keys=True) + "\n")
    return batch


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-items", type=int, default=24)
    parser.add_argument("--lease-seconds", type=int, default=900)
    parser.add_argument("--max-reserved-usd", type=float, default=0.30)
    parser.add_argument("--usd-per-hour-upper", type=float, default=1.00)
    args = parser.parse_args()
    result = execute(args.candidate_root, args.out, max_items=args.max_items,
                     lease_seconds=args.lease_seconds,
                     max_reserved_usd=args.max_reserved_usd,
                     usd_per_hour_upper=args.usd_per_hour_upper)
    print(json.dumps({"status": result["status"], "attempted": len(result["items"]),
                      "native_saves": sum(x["status"] == "neutral_save_observed" for x in result["items"]),
                      "adopted": len(result.get("adopted_task_ids", [])),
                      "reserved_usd_upper": result["reserved_usd_upper"]}, sort_keys=True))
    if result["status"] != "finished" or result.get("adoption_errors"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
