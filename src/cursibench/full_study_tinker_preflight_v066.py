"""Read-only Tinker preflight for the proposed six-cell v0.6.6 action bundle.

The historical v0.6.5 preflight remains byte-for-byte reproducible. This
successor checks the current source inventory and account capabilities; it
cannot train, sample, ratify a cell, or authorize a campaign.
"""

from __future__ import annotations

import importlib.metadata
from pathlib import Path

from . import full_study_tinker_preflight_v1 as historical
from . import shared_action_bundle_v066 as action_bundle


SCHEMA = "cua-full-study-tinker-v066-read-only-preflight-v1"


def run_read_only(repo_root: Path, output_dir: Path, *, fetcher=None,
                  service_factory=None) -> dict:
    root = Path(repo_root).resolve()
    catalog_raw, pricing = historical.official_catalog(fetcher)
    bundle = action_bundle.build(root)
    action_bundle.verify(root, bundle)
    historical.require(
        bundle["model"] == historical.MODEL and
        bundle["output_version"] == "scale-action-output-v0.6.6" and
        bundle["status"] == "proposed_unratified_no_dispatch_authority" and
        len(bundle["cell_ids"]) == 6,
        "v066_shared_action_bundle_mismatch")
    desktop = historical.desktop_boundary(root)
    output = historical.private_output_dir(root, Path(output_dir))
    provider = historical.provider_capabilities(service_factory)
    receipt = {
        "schema": SCHEMA,
        "scope": "read_only_current_action_and_model_capability_check",
        "model": historical.MODEL,
        "tinker_sdk_version": importlib.metadata.version("tinker"),
        "catalog": pricing,
        "action_bundle": bundle,
        "desktop_attestation_snapshot": desktop,
        "provider": provider,
        "six_cell_ratification_verified": False,
        "available_balance_usd": None,
        "provider_billed_usd": None,
        "campaign_dispatch_authorized": False,
        "training_or_sampling_provider_calls": 0,
        "official_final_results": 0,
    }
    historical.private_write_new(output / "published-models.private.json",
                                 catalog_raw)
    historical.private_write_new(output / "receipt.private.json",
                                 historical.canonical(receipt))
    return receipt


def public_summary(repo_root: Path, receipt: dict, *,
                   private_receipt_sha256: str) -> dict:
    historical.exact_hash(private_receipt_sha256, "private_receipt")
    historical.require(
        type(receipt) is dict and receipt.get("schema") == SCHEMA and
        receipt.get("scope") ==
        "read_only_current_action_and_model_capability_check" and
        receipt.get("training_or_sampling_provider_calls") == 0 and
        receipt.get("official_final_results") == 0 and
        receipt.get("campaign_dispatch_authorized") is False and
        receipt.get("six_cell_ratification_verified") is False and
        receipt.get("provider", {}).get("authenticated_capabilities") is True and
        receipt.get("provider", {}).get("exact_model_trainable") is True and
        receipt.get("provider", {}).get("exact_model_sampleable") is True,
        "v066_preflight_receipt_not_publishable")
    bundle = receipt["action_bundle"]
    action_bundle.verify(Path(repo_root), bundle)
    return {
        "schema": "cua-full-study-tinker-v066-public-preflight-v1",
        "status": "read_only_capabilities_verified_no_campaign_authority",
        "model": receipt["model"],
        "tinker_sdk_version": receipt["tinker_sdk_version"],
        "action_profile_version": bundle["action_profile_version"],
        "output_version": bundle["output_version"],
        "six_cell_action_bundle_sha256": bundle["bundle_sha256"],
        "published_model_catalog_sha256":
            receipt["catalog"]["published_models_json_sha256"],
        "private_receipt_sha256": private_receipt_sha256,
        "exact_model_trainable": True,
        "exact_model_sampleable": True,
        "six_cell_ratification_verified": False,
        "available_balance_usd": None,
        "training_or_sampling_provider_calls": 0,
        "official_final_results": 0,
    }
