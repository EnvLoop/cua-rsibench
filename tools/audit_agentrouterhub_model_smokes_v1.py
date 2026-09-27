"""Verify three researcher smoke rows against private raw response bytes.

This is offline and never reads a credential or calls a provider. The fourth
model, gpt-6-sol, is bound by the separate live route-preflight receipt. HTTP
status is an observed client field; raw JSON proves its body, not the status.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.preflight_agentrouterhub_researchers_v1 import digest, encoded


MODELS = ("gpt-6-astra", "gpt-5.6-sol", "gpt-6-luna")
SCHEMA = "envloop-researcher-model-live-smokes-v1"


def rows_from_private(private_dir: Path) -> list[dict]:
    rows = []
    for model in MODELS:
        name = "tiny-" + model.replace(".", "-") + ".private.json"
        raw = (private_dir / name).read_bytes()
        response = json.loads(raw)
        usage = response.get("usage") if isinstance(response, dict) else None
        if (not isinstance(response, dict)
                or response.get("status") != "completed"
                or response.get("model") != model
                or not isinstance(usage, dict)
                or any(type(usage.get(key)) is not int or usage[key] < 0
                       for key in ("input_tokens", "output_tokens", "total_tokens"))
                or usage["total_tokens"] != usage["input_tokens"] + usage["output_tokens"]):
            raise ValueError("private model response is incomplete or inconsistent")
        request = {"model": model, "input": "Reply with OK.",
                   "max_output_tokens": 8}
        rows.append({"model": model,
                     "request_sha256": digest(encoded(request)),
                     "response_sha256": digest(raw),
                     "response_status": "completed", "response_model": model,
                     "input_tokens": usage["input_tokens"],
                     "output_tokens": usage["output_tokens"],
                     "total_tokens": usage["total_tokens"],
                     "benchmark_task_sent": False})
    return rows


def audit(private_dir: Path, public_path: Path) -> dict:
    public = json.loads(public_path.read_bytes())
    rows = public.get("models") if isinstance(public, dict) else None
    observed_statuses = (isinstance(rows, list) and len(rows) == len(MODELS)
                         and all(isinstance(row, dict) and
                                 row.get("http_status") == 200 for row in rows))
    body_fields = ([{key: value for key, value in row.items()
                     if key != "http_status"} for row in rows]
                   if observed_statuses else None)
    if (not isinstance(public, dict) or public.get("schema") != SCHEMA
            or not observed_statuses
            or body_fields != rows_from_private(private_dir)
            or public.get("researcher_campaigns_started") != 0
            or public.get("official_final_tasks_observed") != 0
            or public.get("prior_sol_receipt") !=
            "full-study-researcher-route-live-preflight-2026-09-27.json"):
        raise ValueError("public smoke receipt differs from private response bytes")
    return {"schema": SCHEMA, "model_count": len(MODELS),
            "all_completed": True, "public_sha256": digest(public_path.read_bytes())}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--public-receipt", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.private_dir, args.public_receipt), sort_keys=True))


if __name__ == "__main__":
    main()
