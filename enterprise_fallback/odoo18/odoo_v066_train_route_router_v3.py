"""Bounded passive price-frame stabilization before a TRAIN action intent.

This uses only the already-frozen v5 four-pixel pair. A successful parse still
requires three identical full screenshots and unchanged RFQ/editor identity.
Dispatch uses v5 unchanged; instability after the intent is never retried.
"""
from __future__ import annotations

from cursibench.scale_action_contract import ContractError
from .odoo_native_adapter import _digest
from .odoo_v066_train_attachment_route_adapter_v5 import (
    _decorative_corner_alternate, _price_identity,
)
from .odoo_v066_train_route_router_v2 import OdooV066TrainRouteRouterV2

PROFILE = "train-only-price-pre-intent-passive-stability-2026-09-30-v11"
MAX_PARSE_STABILITY_ROUNDS = 6
PARSE_STABILITY_WAIT_MS = 40


class OdooV066TrainRouteRouterV3(OdooV066TrainRouteRouterV2):
    def _frame_current(self, observation, *, stage: str) -> bool:
        if self._pending_price_edit is None or stage != "parse":
            return super()._frame_current(observation, stage=stage)
        if self.frame_guard_sink is None or not self._is_price_edit(
                observation, self._pending_price_edit):
            return False
        observed = _price_identity(self.observed_price_editor)
        if observed is None:
            return False
        rounds = []
        for index in range(MAX_PARSE_STABILITY_ROUNDS):
            # Every round is passive. Any changed identity, URL, latest
            # observation or material PNG invalidates the entire action.
            frames, refs, members = [], [], []
            for sample in range(3):
                if not self._is_price_edit(observation, self._pending_price_edit):
                    return False
                raw = self.page.screenshot(type="png")
                member = ("observed" if raw == observation.screenshot_bytes else
                          "corner_alternate" if _decorative_corner_alternate(
                              observation.screenshot_bytes, raw) else None)
                ref = self._save_price_frame(
                    observation, "parse_price_stability", index * 3 + sample,
                    raw, ("passive_" + member) if member else "third_or_material_rejected")
                frames.append(raw)
                refs.append(ref)
                members.append(member)
                if member is None or not self._is_price_edit(
                        observation, self._pending_price_edit):
                    return False
            rounds.append({"round": index, "frame_refs": refs,
                           "members": members, "all_three_exact":
                           frames[0] == frames[1] == frames[2]})
            if frames[0] == frames[1] == frames[2]:
                member = members[0]
                self._price_parse_guard = {
                    "profile": PROFILE, "stage": "parse",
                    "price_phase": self.current_price_target["phase"],
                    "classification": "two_frame_" + member + "_confirmed",
                    "observed_frame_sha256": observation.screenshot["sha256"],
                    "observed_frame_id_sha256": _digest(observation.frame_id.encode()),
                    "physical_frame_sha256": _digest(frames[0]),
                    "physical_url": self.page.url, "observed_url": self.latest_url,
                    "rfq_id_sha256": _digest(self.current_price_target["rfq_id"].encode()),
                    "sku_sha256": _digest(self.current_price_target["sku"].encode()),
                    "initial_price_sha256": _digest(self.current_price_target["initial_price"].encode()),
                    "target_point": self._pending_price_edit["target"],
                    "target_identity": observed, "base_sample_count": 1,
                    "base_frame_ref": refs[0], "first_final_frame_ref": refs[1],
                    "second_final_frame_ref": refs[2],
                    "passive_pre_intent_rounds": rounds,
                    "max_passive_rounds": MAX_PARSE_STABILITY_ROUNDS,
                    "passive_wait_ms": PARSE_STABILITY_WAIT_MS,
                }
                return True
            if index + 1 < MAX_PARSE_STABILITY_ROUNDS:
                self.page.wait_for_timeout(PARSE_STABILITY_WAIT_MS)
        return False


__all__ = ["OdooV066TrainRouteRouterV3", "PROFILE",
           "MAX_PARSE_STABILITY_ROUNDS", "PARSE_STABILITY_WAIT_MS"]
