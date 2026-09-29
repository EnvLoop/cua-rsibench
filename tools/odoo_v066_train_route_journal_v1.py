"""Train-only action journal with a durable route token before GUI dispatch.

This copies the frozen v0.6.6 action evidence path and adds a route claim
reference/token to the intent. It never writes SFT examples or retries after a
pre-dispatch intent exists.
"""

from __future__ import annotations

import json
from pathlib import Path
import time

from cursibench.scale_action_contract import ContractError

from tools import record_odoo_v066_train_gui_v1 as recorder


class RouteAwareHoldoutJournal(recorder.ActionJournal):
    def act(self, kind: str, *, phase: str, locator=None,
            ref: str | None = None, memory: str = "", **fields) -> dict:
        recorder.require(phase in ("positive", "negative") and
                         len(self.trace) < recorder.MAX_ACTIONS and
                         time.monotonic() - self.started < recorder.WALL_SECONDS,
                         "train_gui_action_or_wall_budget_exceeded")
        index = len(self.trace)
        for attempt in range(recorder.MAX_PRE_INTENT_STALE_OBSERVATIONS):
            recorder.require(time.monotonic() - self.started <
                             recorder.WALL_SECONDS,
                             "train_gui_wall_budget_exceeded_before_dispatch")
            observation, rendered = self.adapter.observe_for_model(memory=memory)
            recorder.require(
                observation.step == index and
                type(rendered.get("instruction")) is str and
                type(rendered.get("image_bytes")) is bytes and
                rendered["image_bytes"] == observation.screenshot_bytes,
                "current_gui_observation_or_renderer_invalid")
            prefix = (f"step-{index:03d}" if attempt == 0 else
                      f"step-{index:03d}-resample-{attempt:02d}")
            frame = recorder._write(
                self.out / "frames" / (prefix + ".png"),
                observation.screenshot_bytes)
            frame["path"] = "frames/" + frame["path"]
            instruction = recorder._write(
                self.out / "actions" / (prefix + "-instruction.txt"),
                rendered["instruction"].encode())
            instruction["path"] = "actions/" + instruction["path"]
            visible = recorder._write(
                self.out / "actions" / (prefix + "-visible.txt"),
                rendered["visible_text"].encode())
            visible["path"] = "actions/" + visible["path"]
            payload = {"type": kind, **fields}
            if ref is not None:
                recorder.require(
                    len([item for item in observation.controls
                         if item.ref == ref and item.visible and
                         item.enabled]) == 1,
                    "visible_control_ref_not_unique")
                payload["target"] = {"ref": ref}
            elif locator is not None:
                box = locator.bounding_box()
                recorder.require(box is not None and box["width"] > 0 and
                                 box["height"] > 0,
                                 "gui_locator_not_visible")
                payload["target"] = {
                    "x": int(box["x"] + box["width"] / 2),
                    "y": int(box["y"] + box["height"] / 2),
                }
            raw_action = json.dumps(payload, ensure_ascii=False,
                                    sort_keys=True, separators=(",", ":"))
            action_ref = recorder._write(
                self.out / "actions" / (prefix + "-assistant.json"),
                raw_action.encode())
            action_ref["path"] = "actions/" + action_ref["path"]
            try:
                normalized = self.adapter.parse_current_action(raw_action)
                claim = self.adapter.parsed_route_claim
                claim_ref = self.adapter.parsed_route_claim_ref
                probe_ref = self.adapter.latest_route_probe_ref
                if (type(claim) is not dict or
                        claim.get("status") != "claimed" or
                        type(claim.get("route_token")) is not str or
                        type(claim_ref) is not dict or
                        type(probe_ref) is not dict or
                        claim.get("frame_sha256") != frame["sha256"] or
                        claim.get("step") != index or
                        claim.get("probe_ref") != probe_ref):
                    raise ContractError("stale_frame")
            except ContractError as exc:
                current_ref = None
                try:
                    current_ref = recorder._write(
                        self.out / "frames" /
                        (prefix + "-rejected-current.png"),
                        self.page.screenshot(type="png"))
                    current_ref["path"] = "frames/" + current_ref["path"]
                except Exception:
                    pass
                rejection = {
                    "schema": "envloop-odoo-v066-route-pre-intent-rejection-v1",
                    "phase": phase, "step": index,
                    "observation_attempt": attempt,
                    "error_code": exc.code,
                    "frame_id_sha256": recorder.sha(
                        observation.frame_id.encode()),
                    "observed_frame_ref": frame,
                    "assistant_action_ref": action_ref,
                    "current_frame_ref": current_ref,
                    "route_probe_ref":
                        self.adapter.latest_route_probe_ref,
                    "route_decision_ref":
                        self.adapter.latest_route_decision_ref,
                    "pre_dispatch_intent_created": False,
                    "gui_action_dispatched": False,
                }
                rejection_ref = recorder._write(
                    self.out / "actions" /
                    (prefix + "-rejection.private.json"),
                    recorder.canonical(rejection))
                rejection_ref["path"] = "actions/" + rejection_ref["path"]
                self.pre_intent_rejections.append(rejection_ref)
                recorder.require(not (self.out / "actions" /
                                     (prefix + "-intent.private.json")).exists(),
                                 "pre_intent_rejection_has_intent")
                if (exc.code != "stale_frame" or
                        attempt + 1 >=
                        recorder.MAX_PRE_INTENT_STALE_OBSERVATIONS):
                    raise
                self.page.wait_for_timeout(recorder.STALE_RESAMPLE_WAIT_MS)
                continue
            token = claim["route_token"]
            intent = {
                "schema": "envloop-odoo-v066-route-action-intent-v1",
                "phase": phase, "step": index,
                "task_id": observation.task_id,
                "task_binding_sha256": observation.task_binding_sha256,
                "frame_id": observation.frame_id,
                "frame_sha256": frame["sha256"],
                "frame_ref": frame,
                "instruction_ref": instruction,
                "visible_text_ref": visible,
                "assistant_action_ref": action_ref,
                "normalized_action": normalized,
                "observed_url": getattr(self.adapter, "latest_url", None),
                "observation_controls": [
                    {"ref": control.ref, "role": control.role,
                     "label": control.label, "visible": control.visible,
                     "enabled": control.enabled}
                    for control in observation.controls],
                "observed_target_control": getattr(
                    self.adapter, "observed_target_control", None),
                "route_probe_ref": probe_ref,
                "route_claim_ref": claim_ref,
                "route_kind": claim["route_kind"],
                "route_token": token,
                "dispatch_state": "intent_durable_before_gui_action",
                "pre_intent_stale_resamples": attempt,
            }
            intent_ref = recorder._write(
                self.out / "actions" /
                (prefix + "-intent.private.json"),
                recorder.canonical(intent))
            intent_ref["path"] = "actions/" + intent_ref["path"]
            applied = self.adapter.dispatch(normalized, route_token=token)
            receipt = applied.get("public_contract_receipt", {})
            recorder.require(
                applied.get("action") == normalized and
                receipt.get("screenshot", {}).get("sha256") ==
                    frame["sha256"] and
                receipt.get("route_kind") == claim["route_kind"] and
                receipt.get("route_token_sha256") ==
                    recorder.sha(token.encode()) and
                receipt.get("route_claim_ref_sha256") ==
                    claim_ref["sha256"],
                "gui_dispatch_route_or_frame_receipt_invalid")
            result = {
                "schema": "envloop-odoo-v066-route-dispatch-result-v1",
                "phase": phase, "step": index,
                "intent_sha256": intent_ref["sha256"],
                "applied_action": applied["action"],
                "route_kind": claim["route_kind"],
                "route_token_sha256": recorder.sha(token.encode()),
                "route_claim_ref": claim_ref,
                "contract_receipt": receipt,
            }
            result_ref = recorder._write(
                self.out / "actions" /
                (prefix + "-result.private.json"),
                recorder.canonical(result))
            result_ref["path"] = "actions/" + result_ref["path"]
            self.trace.append({
                "phase": phase, "step": index,
                "frame": frame, "route_claim_ref": claim_ref,
                "route_kind": claim["route_kind"],
                "contract_receipt": receipt,
            })
            self.sft.clear()
            return frame
        raise recorder.RecorderError("pre_intent_resample_exhausted")


__all__ = ["RouteAwareHoldoutJournal"]
