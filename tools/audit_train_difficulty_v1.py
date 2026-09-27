"""Aggregate private train-only difficulty receipts without publishing task IDs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cursibench.train_difficulty_gate_v1 import evaluate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    result = evaluate(args.input)
    if args.out.exists():
        raise SystemExit("Refusing to overwrite an existing aggregate")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n",
                        encoding="utf-8")
    print(json.dumps({"cell_id": result["cell_id"],
                      "train_task_count": result["train_task_count"],
                      "all_observed_train_workflows_discriminative":
                      result["all_observed_train_workflows_discriminative"]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
