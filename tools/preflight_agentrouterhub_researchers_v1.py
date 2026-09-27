"""Record a bounded researcher-route preflight without benchmark task content.

The private output contains the provider's raw model catalog and one optional
tiny Sol response. The public receipt contains only allowlisted status, model
presence, token totals and hashes. This is not a campaign or a model score.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import time

import httpx


BASE = "https://sub2api.agentrouterhub.com/v1"
ROOT = Path(__file__).resolve().parents[1]
MODELS = ("gpt-6-astra", "gpt-5.6-sol", "gpt-6-sol", "gpt-6-luna")
TINY_REQUEST = {"model": "gpt-6-sol", "input": "Reply with OK.",
                "max_output_tokens": 8}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def encoded(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def private_write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def public_summary(catalog_raw: bytes, response_raw: bytes | None) -> dict:
    catalog = json.loads(catalog_raw)
    if not isinstance(catalog, dict) or not isinstance(catalog.get("data"), list):
        raise ValueError("provider model catalog shape changed")
    identifiers = {row.get("id") for row in catalog["data"]
                   if isinstance(row, dict) and isinstance(row.get("id"), str)}
    if not all(name in identifiers for name in MODELS):
        raise ValueError("required researcher model ID absent from catalog")
    sample = None
    if response_raw is not None:
        response = json.loads(response_raw)
        usage = response.get("usage") if isinstance(response, dict) else None
        if (not isinstance(response, dict) or response.get("status") != "completed"
                or response.get("model") != TINY_REQUEST["model"]
                or not isinstance(usage, dict)
                or any(type(usage.get(k)) is not int or usage[k] < 0
                       for k in ("input_tokens", "output_tokens", "total_tokens"))):
            raise ValueError("tiny response or usage not complete")
        sample = {"model": response["model"], "status": response["status"],
                  "request_sha256": digest(encoded(TINY_REQUEST)),
                  "response_sha256": digest(response_raw),
                  "input_tokens": usage["input_tokens"],
                  "output_tokens": usage["output_tokens"],
                  "total_tokens": usage["total_tokens"],
                  "benchmark_task_sent": False}
    return {"schema": "envloop-researcher-route-preflight-v1",
            "base_host": "sub2api.agentrouterhub.com",
            "catalog_sha256": digest(catalog_raw),
            "catalog_model_count": len(identifiers),
            "requested_model_ids_present": {name: name in identifiers for name in MODELS},
            "tiny_sol_sample": sample,
            "researcher_campaigns_started": 0,
            "official_final_tasks_observed": 0}


def run(private_dir: Path, public_path: Path, *, tiny_sol: bool) -> dict:
    private_dir = private_dir.resolve()
    public_path = public_path.resolve()
    if (not private_dir.is_relative_to((ROOT / "work").resolve())
            or not public_path.is_relative_to((ROOT / "docs/evidence").resolve())):
        raise ValueError("private work/ and public docs/evidence/ paths required")
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise ValueError("OPENAI_API_KEY is absent")
    if private_dir.exists() or public_path.exists():
        raise FileExistsError("preflight output already exists")
    with httpx.Client(timeout=60) as client:
        headers = {"Authorization": "Bearer " + key, "Accept": "application/json"}
        roster = client.get(BASE + "/models", headers=headers)
        roster.raise_for_status()
        catalog_raw = roster.content
        response_raw = None
        if tiny_sol:
            sample = client.post(BASE + "/responses", headers=headers,
                                 json=TINY_REQUEST)
            sample.raise_for_status()
            response_raw = sample.content
    summary = public_summary(catalog_raw, response_raw)
    summary["verified_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    private_write(private_dir / "model-catalog.private.json", catalog_raw)
    if response_raw is not None:
        private_write(private_dir / "tiny-sol-response.private.json", response_raw)
    private_write(private_dir / "summary.private.json", encoded(summary))
    public_path.parent.mkdir(parents=True, exist_ok=True)
    public_path.write_bytes(json.dumps(summary, sort_keys=True, indent=2).encode() + b"\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    parser.add_argument("--tiny-sol", action="store_true")
    args = parser.parse_args()
    summary = run(args.private_dir, args.public_out, tiny_sol=args.tiny_sol)
    print(json.dumps({"catalog_model_count": summary["catalog_model_count"],
                      "requested_model_ids_present": summary["requested_model_ids_present"],
                      "tiny_sol_sample_status": (summary["tiny_sol_sample"] or {}).get("status"),
                      "researcher_campaigns_started": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
