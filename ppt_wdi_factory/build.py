"""Build private PowerPoint candidates with the bundled Artifact Tool runtime."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import subprocess

from .plan import canonical, sha

HERE = Path(__file__).resolve().parent
DEFAULT_NODE = Path("/Users/xiaoyong/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node")
DEFAULT_MODULES = Path("/Users/xiaoyong/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules")
DEFAULT_PYTHON = Path("/Users/xiaoyong/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3")
DEFAULT_SKILL = Path("/Users/xiaoyong/.codex/plugins/cache/openai-primary-runtime/presentations/26.905.11957/skills/presentations")


def prepare_builder(private: Path, modules: Path) -> Path:
    build = private / "artifact-tool-build"
    build.mkdir(parents=True, exist_ok=True)
    builder = build / "build_deck.mjs"
    source = HERE / "build_deck.mjs"
    shutil.copyfile(source, builder)
    link = build / "node_modules"
    if not link.exists():
        link.symlink_to(modules, target_is_directory=True)
    if not link.samefile(modules):
        raise ValueError("Private Node dependency link points outside bundled runtime")
    return builder


def run(private: Path, node: Path, modules: Path, *, limit: int | None = None,
        runtime_python: Path = DEFAULT_PYTHON, skill_dir: Path = DEFAULT_SKILL,
        workers: int = 2) -> dict:
    plan_path = private / "candidate-plan.private.json"
    manifest = json.loads(plan_path.read_text())
    if manifest.get("schema") != "ppt-wdi-original-candidates-v1":
        raise ValueError("Unexpected private plan")
    builder = prepare_builder(private, modules)
    rows = [row for split in ("train", "selection", "final_candidate")
            for row in manifest["sets"][split]]
    if limit is not None:
        rows = rows[:limit]
    finalizer = HERE / "finalize_deck.mjs"
    receipt_path = private / "build-receipt.private.json"
    if receipt_path.exists():
        prior = json.loads(receipt_path.read_bytes())
        if prior.get("builder_sha256") != sha(builder.read_bytes()):
            raise ValueError("Builder changed after source freeze; use a new private output root")
        if (prior.get("finalizer_sha256") is not None
                and prior["finalizer_sha256"] != sha(finalizer.read_bytes())):
            raise ValueError("Finalizer changed after source freeze; use a new private output root")
    final_env = {**os.environ, "NODE_OPTIONS": "--max-old-space-size=4096",
                 "PRESENTATIONS_SKILL_DIR": str(skill_dir),
                 "RUNTIME_PYTHON": str(runtime_python),
                 "RUNTIME_NODE": str(node),
                 "RUNTIME_NODE_MODULES": str(modules)}

    def materialize(row: dict) -> dict:
        package = private / "packages" / row["split"] / row["task_id"]
        package.mkdir(parents=True, exist_ok=True)
        spec_path = package / "task.private.json"
        spec = canonical(row)
        if spec_path.exists() and spec_path.read_bytes() != spec:
            raise ValueError("Existing task spec differs: " + row["task_id"])
        if not spec_path.exists():
            spec_path.write_bytes(spec)
            spec_path.chmod(0o600)
        draft = package / "draft.pptx"
        deck = package / "source.pptx"
        validation = private / "packages" / row["split"] / "validation" / (row["task_id"] + "-source.pptx.json")
        if not deck.exists():
            subprocess.run([str(node), str(builder), str(spec_path), str(draft)],
                           check=True, capture_output=True, env=final_env)
            draft.chmod(0o600)
            subprocess.run([str(node), str(finalizer), str(draft), str(deck)],
                           check=True, capture_output=True, env=final_env)
            deck.chmod(0o600)
        if not validation.is_file():
            raise ValueError("Finalizer validation receipt missing: " + row["task_id"])
        if not deck.is_file() or deck.stat().st_size < 5000:
            raise ValueError("Candidate deck missing or implausibly small: " + row["task_id"])
        return {"task_id": row["task_id"], "split": row["split"],
                "task_sha256": sha(spec), "draft_sha256": sha(draft.read_bytes()),
                "deck_sha256": sha(deck.read_bytes()), "deck_bytes": deck.stat().st_size,
                "finalizer_receipt_sha256": sha(validation.read_bytes())}

    output = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for index, result in enumerate(pool.map(materialize, rows), 1):
            output.append(result)
            if index % 10 == 0 or index == len(rows):
                print(json.dumps({"built_or_found": index, "requested": len(rows),
                                  "official_final_credit": 0}), flush=True)
    data = canonical({"schema": "ppt-wdi-original-build-receipt-v1",
                      "plan_sha256": sha(plan_path.read_bytes()),
                      "builder_sha256": sha(builder.read_bytes()),
                      "finalizer_sha256": sha(finalizer.read_bytes()),
                      "runtime_bundle_version": "26.905.11957", "rows": output,
                      "official_final_credit": 0})
    if receipt_path.exists() and receipt_path.read_bytes() != data:
        # A partial pilot may be superseded by a complete immutable inventory.
        prior = json.loads(receipt_path.read_bytes())
        prefix = output[:len(prior["rows"])]
        if len(prefix) != len(prior["rows"]) or any(
            any(new.get(key) != value for key, value in old.items())
            for old, new in zip(prior["rows"], prefix)
        ):
            raise ValueError("Prior build receipt conflicts with new output")
    receipt_path.write_bytes(data)
    receipt_path.chmod(0o600)
    return {"built_or_found": len(output), "build_receipt_sha256": sha(data),
            "official_final_credit": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-root", type=Path, required=True)
    parser.add_argument("--node", type=Path, default=DEFAULT_NODE)
    parser.add_argument("--node-modules", type=Path, default=DEFAULT_MODULES)
    parser.add_argument("--runtime-python", type=Path, default=DEFAULT_PYTHON)
    parser.add_argument("--presentations-skill-dir", type=Path, default=DEFAULT_SKILL)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    if args.limit is not None and not 1 <= args.limit <= 140:
        raise ValueError("Limit must be 1..140")
    if not 1 <= args.workers <= 8:
        raise ValueError("Workers must be 1..8")
    print(json.dumps(run(args.private_root.resolve(), args.node, args.node_modules,
                         limit=args.limit, runtime_python=args.runtime_python,
                         skill_dir=args.presentations_skill_dir, workers=args.workers)))


if __name__ == "__main__":
    main()
