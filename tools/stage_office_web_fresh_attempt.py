"""Stage evaluator-owned fresh Office inputs without claiming a web GUI run.

All copies and receipts belong in an ignored private work directory. The tool
does not operate Microsoft Office, accept credentials, or know cloud item URLs.
Downloaded artifacts can later be bound by hash, but their GUI provenance and
task-specific semantic scores require separate independent verification.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
from zipfile import ZipFile, BadZipFile

SCHEMA = "office-web-fresh-copy-controller-v1"
SLOTS = ("untouched", "positive", "partial_negative", "collateral_negative", "fresh_reset")
SUFFIXES = {"powerpoint-web": ".pptx", "excel-web": ".xlsx"}
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    h = sha256()
    with path.open("rb") as reader:
        for chunk in iter(lambda: reader.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def valid_office_package(path: Path, suffix: str) -> None:
    if path.suffix.lower() != suffix:
        raise ValueError("Office artifact has the wrong extension")
    try:
        with ZipFile(path) as archive:
            names = set(archive.namelist())
            if archive.testzip() is not None or "[Content_Types].xml" not in names:
                raise ValueError("Office package failed archive validation")
            expected = "ppt/presentation.xml" if suffix == ".pptx" else "xl/workbook.xml"
            if expected not in names:
                raise ValueError("Office package lacks its main document part")
    except BadZipFile as error:
        raise ValueError("Office package is not a valid ZIP archive") from error


def private_copy(source: Path, destination: Path) -> None:
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as output, source.open("rb") as reader:
            shutil.copyfileobj(reader, output, 1024 * 1024)
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        destination.unlink(missing_ok=True)
        raise


def write_private_json(path: Path, data: dict) -> None:
    payload = (json.dumps(data, indent=2, sort_keys=True) + "\n").encode()
    temp = path.with_name(path.name + ".new")
    descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp, path)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise


def stage(source: Path, expected_sha256: str, cell_id: str,
          task_id: str, root: Path) -> dict:
    if cell_id not in SUFFIXES:
        raise ValueError("unsupported Office web cell")
    source = source.resolve(strict=True)
    suffix = SUFFIXES[cell_id]
    valid_office_package(source, suffix)
    source_sha = digest(source)
    if source_sha != expected_sha256:
        raise ValueError("Office-normalized source hash differs from the frozen pin")
    try:
        local_path = root.resolve().relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        pass  # An external evaluator-owned private path is acceptable.
    else:
        if not local_path.parts or local_path.parts[0] != "work":
            raise ValueError("Office source copies inside the checkout must stay under ignored work/")
    if root.exists():
        raise ValueError("attempt directory already exists; never reuse a prior attempt")
    root.mkdir(parents=True, mode=0o700)
    inputs = root / "inputs"
    inputs.mkdir(mode=0o700)
    records = {}
    for slot in SLOTS:
        target = inputs / f"{slot}{suffix}"
        private_copy(source, target)
        records[slot] = {"path": str(target.relative_to(root)), "sha256": digest(target),
                         "size_bytes": target.stat().st_size,
                         "device": target.stat().st_dev, "inode": target.stat().st_ino}
    manifest = {
        "schema": SCHEMA, "status": "local_fresh_inputs_staged_no_gui_credit",
        "cell_id": cell_id, "task_id": task_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "evaluator_source_path": str(source), "source_sha256": source_sha,
        "source_size_bytes": source.stat().st_size,
        "slots": records, "downloads": {},
        "cloud_upload_verified": False, "saved_file_readback_verified": False,
        "gui_positive_verified": False, "gui_negatives_verified": False,
        "fresh_cloud_reset_verified": False, "official_final_credit": 0,
        "note": "Byte-distinct local copies only. No Microsoft cloud item, actor action, or task score is attested.",
    }
    write_private_json(root / "controller.json", manifest)
    verify_staged(root)
    return manifest


def _slot_path(root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("unsafe controller relative path")
    full = (root / path).resolve()
    try:
        full.relative_to(root.resolve())
    except ValueError as error:
        raise ValueError("controller path escapes private root") from error
    return full


def verify_staged(root: Path) -> dict:
    manifest = json.loads((root / "controller.json").read_text())
    if manifest.get("schema") != SCHEMA or manifest.get("cell_id") not in SUFFIXES:
        raise ValueError("unrecognized controller manifest")
    source = Path(manifest["evaluator_source_path"])
    if not source.is_file() or digest(source) != manifest["source_sha256"]:
        raise ValueError("frozen Office source was changed or removed")
    suffix = SUFFIXES[manifest["cell_id"]]
    slots = manifest.get("slots") or {}
    if set(slots) != set(SLOTS):
        raise ValueError("controller slots are incomplete")
    identities = set()
    for name in SLOTS:
        record = slots[name]
        path = _slot_path(root, record["path"])
        if not path.is_file() or digest(path) != record["sha256"] or record["sha256"] != manifest["source_sha256"]:
            raise ValueError("fresh input changed or is missing: " + name)
        valid_office_package(path, suffix)
        identity = (path.stat().st_dev, path.stat().st_ino)
        if identity in identities or identity != (record["device"], record["inode"]):
            raise ValueError("fresh inputs are not independently copied files")
        identities.add(identity)
    if (source.stat().st_dev, source.stat().st_ino) in identities:
        raise ValueError("an input aliases the immutable source")
    for name, record in manifest.get("downloads", {}).items():
        if name not in SLOTS:
            raise ValueError("download bound to an unknown slot")
        path = _slot_path(root, record["path"])
        if not path.is_file() or digest(path) != record["sha256"]:
            raise ValueError("downloaded artifact changed or is missing: " + name)
        valid_office_package(path, suffix)
    return {"status": "local_byte_integrity_pass_gui_provenance_unverified",
            "fresh_input_count": len(SLOTS), "download_binding_count": len(manifest.get("downloads", {})),
            "gui_admitted": False, "official_final_credit": 0}


def bind_operator_download(root: Path, slot: str, downloaded: Path) -> dict:
    if slot not in SLOTS:
        raise ValueError("unknown controller slot")
    verified = verify_staged(root)
    manifest_path = root / "controller.json"
    manifest = json.loads(manifest_path.read_text())
    if slot in manifest["downloads"]:
        raise ValueError("slot already has a bound download; create a new attempt to retry")
    suffix = SUFFIXES[manifest["cell_id"]]
    downloaded = downloaded.resolve(strict=True)
    valid_office_package(downloaded, suffix)
    destination = root / "downloads" / f"{slot}{suffix}"
    destination.parent.mkdir(mode=0o700, exist_ok=True)
    private_copy(downloaded, destination)
    manifest["downloads"][slot] = {
        "path": str(destination.relative_to(root)), "sha256": digest(destination),
        "bound_at_utc": datetime.now(timezone.utc).isoformat(),
        "provenance": "operator_supplied_file_not_independent_cloud_proof",
    }
    write_private_json(manifest_path, manifest)
    result = verify_staged(root)
    assert result["download_binding_count"] == verified["download_binding_count"] + 1
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    stage_args = actions.add_parser("stage")
    stage_args.add_argument("--source", type=Path, required=True)
    stage_args.add_argument("--source-sha256", required=True)
    stage_args.add_argument("--cell-id", choices=sorted(SUFFIXES), required=True)
    stage_args.add_argument("--task-id", required=True)
    stage_args.add_argument("--root", type=Path, required=True)
    verify_args = actions.add_parser("verify")
    verify_args.add_argument("--root", type=Path, required=True)
    bind_args = actions.add_parser("bind-download")
    bind_args.add_argument("--root", type=Path, required=True)
    bind_args.add_argument("--slot", choices=SLOTS, required=True)
    bind_args.add_argument("--download", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "stage":
        result = stage(args.source, args.source_sha256, args.cell_id, args.task_id, args.root)
        print(json.dumps({"status": result["status"], "source_sha256": result["source_sha256"],
                          "fresh_input_count": len(result["slots"]), "official_final_credit": 0}))
    elif args.action == "verify":
        print(json.dumps(verify_staged(args.root)))
    else:
        print(json.dumps(bind_operator_download(args.root, args.slot, args.download)))


if __name__ == "__main__":
    main()
