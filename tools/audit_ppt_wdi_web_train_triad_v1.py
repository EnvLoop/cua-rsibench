"""Audit one private train-only PowerPoint-web saved-artifact control triad.

The browser actions and cloud item URLs are evaluator-private input evidence.
This audit independently reads downloaded PPTX bytes and never admits an
official final identity or a model outcome.
"""

from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import parse_qs, urlparse

from ppt_wdi_factory import verify
from tools import pptx_title_size_guard as packages


SLIDE = re.compile(r"ppt/slides/slide[1-7]\.xml\Z")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path: Path, value: dict, *, private: bool) -> str:
    raw = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                 0o600 if private else 0o644)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return hashlib.sha256(raw).hexdigest()


def zip_members(path: Path) -> dict[str, bytes]:
    return packages.package(path)[1]


def semantic_source_equal(first: Path, second: Path) -> dict:
    before, after = zip_members(first), zip_members(second)
    slides = sorted(name for name in before if SLIDE.fullmatch(name))
    require(len(slides) == 7 and all(name in after for name in slides),
            "seven slides are required in both files")
    def content_objects(data: bytes) -> list[tuple]:
        root = packages.xml(data)
        objects = []
        for element in root.iter():
            if element.tag == verify.P + "sp":
                identity = element.find(verify.P + "nvSpPr/" + verify.P + "cNvPr")
                require(identity is not None, "unnamed slide shape")
                objects.append(("shape", identity.get("id"), identity.get("name"),
                                "".join(node.text or "" for node in
                                        element.iter(verify.A + "t"))))
            elif element.tag == verify.P + "graphicFrame":
                identity = element.find(verify.P + "nvGraphicFramePr/" + verify.P + "cNvPr")
                require(identity is not None, "unnamed graphic frame")
                tables = list(element.iter(verify.A + "tbl"))
                require(len(tables) <= 1, "ambiguous native table")
                cells = tuple(tuple("".join(node.text or "" for node in
                                             cell.iter(verify.A + "t"))
                                    for cell in row.iter(verify.A + "tc"))
                              for row in tables[0].iter(verify.A + "tr")) if tables else ()
                # PowerPoint assigns a display name such as "Table 8" to an
                # unnamed imported graphic frame. Its stable object ID and
                # every visible table cell still have to match exactly.
                objects.append(("graphic_frame", identity.get("id"), cells))
        return objects
    for name in slides:
        require(content_objects(before[name]) == content_objects(after[name]),
                "visible slide shape/table content changed")
    chart_before, workbook_before = verify._chart_and_workbook_parts(before)
    chart_after, workbook_after = verify._chart_and_workbook_parts(after)
    # PowerPoint may re-pack the embedded XLSX ZIP without changing any member.
    # Compare every member's XML/content, so a data/formula edit still fails.
    require(verify._masked_workbook_equal(before[workbook_before],
                                          after[workbook_after], []),
            "embedded chart workbook content changed")
    def values(data: bytes) -> list[str]:
        return [node.text or "" for node in packages.xml(data).iter(verify.C + "v")]
    left, right = values(before[chart_before]), values(after[chart_after])
    require(bool(left) and len(left) == len(right),
            "native chart cache changed shape")
    for a, b in zip(left, right):
        try:
            equal = abs(Decimal(a) - Decimal(b)) <= Decimal("0.000000001")
        except InvalidOperation:
            equal = a == b
        require(equal, "native chart label/value changed")
    return {"slide_count": 7, "slide_text_equal": True,
            "embedded_workbook_bytes_equal":
            before[workbook_before] == after[workbook_after],
            "embedded_workbook_members_equal": True,
            "native_chart_cache_semantically_equal": True,
            "native_chart_cache_values_checked": len(left)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--raw-reset", type=Path, required=True)
    parser.add_argument("--normalized-baseline", type=Path, required=True)
    parser.add_argument("--positive", type=Path, required=True)
    parser.add_argument("--near-miss", type=Path, required=True)
    parser.add_argument("--fresh-reset", type=Path, required=True)
    parser.add_argument("--cloud-items", type=Path, required=True)
    parser.add_argument("--private-out", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    require(not args.private_out.exists() and not args.public_out.exists(),
            "fresh outputs required")
    task = json.loads(args.task.read_bytes())
    require(task["split"] == "train", "only a train-source development control is supported")
    verify.freeze(args.source, task)
    source_sha = digest(args.source)
    require(digest(args.raw_reset) == source_sha,
            "untouched cloud copy differs from source")
    office = verify.freeze(args.normalized_baseline, task,
                           office_web_normalized=True)
    require(digest(args.normalized_baseline) != source_sha,
            "neutral native save was not observed")
    source_equivalence = semantic_source_equal(args.source, args.normalized_baseline)
    fresh_equivalence = semantic_source_equal(args.normalized_baseline, args.fresh_reset)
    files = {"positive": args.positive, "near_miss": args.near_miss,
             "fresh_reset": args.fresh_reset}
    expected = {"positive": (1.0, True),
                "near_miss": (0.0, False),
                "fresh_reset": (0.0, False)}
    checks = {}
    for label, path in files.items():
        report = verify.verify(args.normalized_baseline, path, office)
        score, target = expected[label]
        require(report["status"] == "scored" and report["score"] == score and
                report["target_correct"] is target and
                report["preservation_pass"] is True and
                not report["unexpected_parts"],
                f"{label} saved-state control failed")
        checks[label] = {"download_sha256": digest(path),
                         "score": score, "target_correct": target,
                         "no_regression": True}
    require(len({row["download_sha256"] for row in checks.values()}) == 3,
            "three distinct downloaded artifacts required")
    urls = json.loads(args.cloud_items.read_bytes())
    require(set(urls) == {"baseline", "positive", "near_miss", "fresh_reset"},
            "four cloud item roles required")
    require(len(set(urls.values())) == 4, "four distinct cloud items required")
    fragments = {"baseline": "reset", "positive": "positive",
                 "near_miss": "nearmiss", "fresh_reset": "freshreset"}
    for key, url in urls.items():
        parsed = urlparse(url)
        require(parsed.scheme == "https" and parsed.hostname == "onedrive.live.com",
                "cloud item host changed")
        filename = parse_qs(parsed.query).get("file", [""])[0]
        require(filename.endswith(".pptx") and
                fragments[key] in filename.replace("-", "").lower(),
                "cloud item filename changed")
    url_hashes = {key: hashlib.sha256(value.encode()).hexdigest()
                  for key, value in urls.items()}
    private = {"schema": "envloop-ppt-wdi-web-train-triad-private-v1",
               "task_id": task["task_id"], "source_sha256": source_sha,
               "raw_reset_sha256": digest(args.raw_reset),
               "normalized_baseline_sha256": digest(args.normalized_baseline),
               "normalized_oracle_sha256": hashlib.sha256(
                   json.dumps(office, sort_keys=True).encode()).hexdigest(),
               "cloud_item_url_sha256": url_hashes,
               "source_equivalence": source_equivalence,
               "fresh_equivalence": fresh_equivalence,
               "checks": checks, "model_calls": 0,
               "official_final_tasks_admitted": 0}
    private_sha = write_new(args.private_out, private, private=True)
    public = {"schema": "envloop-ppt-wdi-web-train-triad-public-v1",
              "status": "one_train_source_gui_triad_not_final_admission",
              "original_source_sha256": source_sha,
              "normalized_baseline_sha256": private["normalized_baseline_sha256"],
              "independent_cloud_items": 4,
              "cloud_item_url_sha256": url_hashes,
              "saved_download_sha256": {key: row["download_sha256"]
                                        for key, row in checks.items()},
              "source_equivalence": source_equivalence,
              "fresh_equivalence": fresh_equivalence,
              "positive_saved_score": 1.0,
              "near_miss_saved_score": 0.0,
              "fresh_reset_saved_score": 0.0,
              "preservation_passed": True,
              "private_receipt_sha256": private_sha,
              "model_calls": 0, "official_final_tasks_admitted": 0,
              "researcher_campaigns": 0}
    write_new(args.public_out, public, private=False)
    print(json.dumps({"status": public["status"],
                      "private_receipt_sha256": private_sha,
                      "official_final_tasks_admitted": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
