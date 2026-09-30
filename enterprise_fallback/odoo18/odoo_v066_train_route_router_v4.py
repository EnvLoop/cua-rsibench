"""Finite TRAIN-calibrated form-border equivalence for price frames.

Each corner must be exactly one of two complete RGB state vectors. Every
other full-image RGB pixel and every RFQ/editor identity check stays exact.
There is no wait loop, input retry or task/model-dependent pixel allowance.
"""
from __future__ import annotations
from hashlib import sha256
from io import BytesIO
from PIL import Image
from .odoo_native_adapter import _digest
from .odoo_v066_train_attachment_route_adapter_v5 import _price_identity
from .odoo_v066_train_route_router_v2 import OdooV066TrainRouteRouterV2

PROFILE="train-calibrated-two-corner-material-price-frame-2026-09-30-v12"
TOP_POINTS=((16,155),(16,157),(17,157))
BOTTOM_POINTS=((16,861),(17,861),(16,863),(17,863))
TOP_STATES=(((246,247,248),(226,230,234),(249,250,250)),
            ((246,247,249),(226,229,234),(250,250,251)))
BOTTOM_STATES=(((226,230,234),(249,250,250),(246,247,248),(229,233,236)),
               ((226,229,234),(250,250,251),(246,247,249),(230,233,236)))


def border_material(raw:bytes)->dict|None:
    """Return an approved complete state and the exact remaining RGB identity."""
    try:
        with Image.open(BytesIO(raw)) as source:
            if source.format!="PNG" or source.mode!="RGB" or source.size!=(1440,1000):return None
            image=source.copy()
        top=tuple(image.getpixel(xy) for xy in TOP_POINTS)
        bottom=tuple(image.getpixel(xy) for xy in BOTTOM_POINTS)
        if top not in TOP_STATES or bottom not in BOTTOM_STATES:return None
        state={"top":TOP_STATES.index(top),"bottom":BOTTOM_STATES.index(bottom)}
        # Normalize only approved whole-corner vectors, never arbitrary pixel
        # differences. An edited pixel elsewhere changes this fingerprint.
        for xy,rgb in zip(TOP_POINTS,TOP_STATES[0]):image.putpixel(xy,rgb)
        for xy,rgb in zip(BOTTOM_POINTS,BOTTOM_STATES[0]):image.putpixel(xy,rgb)
        return {"state_class":state,"canonical_material_sha256":sha256(
            b"RGB-1440x1000-two-form-corners-v12\0"+image.tobytes()).hexdigest()}
    except (OSError,ValueError):return None


class OdooV066TrainRouteRouterV4(OdooV066TrainRouteRouterV2):
    def _frame_current(self,observation,*,stage:str)->bool:
        if self._pending_price_edit is None:
            return super()._frame_current(observation,stage=stage)
        if self.frame_guard_sink is None or stage not in ("parse","dispatch") or not self._is_price_edit(
                observation,self._pending_price_edit):return False
        observed=border_material(observation.screenshot_bytes)
        identity=_price_identity(self.observed_price_editor)
        if observed is None or identity is None:return False
        records=[]
        for sample in range(3):
            if not self._is_price_edit(observation,self._pending_price_edit):return False
            raw=self.page.screenshot(type="png");material=border_material(raw)
            accepted=material is not None and material["canonical_material_sha256"]==observed["canonical_material_sha256"]
            classification=("material_base_confirmed" if sample==0 else
                            "material_first_final_confirmed" if sample==1 else
                            "two_final_material_frames_confirmed") if accepted else "unknown_border_or_material_rejected"
            ref=self._save_price_frame(observation,stage+"_border_material",sample,raw,classification)
            record=self.frame_guard_samples[-1]
            record["border_state_class"]=None if material is None else material["state_class"]
            record["canonical_material_sha256"]=None if material is None else material["canonical_material_sha256"]
            records.append({"frame_ref":ref,"raw_frame_sha256":_digest(raw),"material":material})
            if not accepted or not self._is_price_edit(observation,self._pending_price_edit):return False
        # Independently captured final frames must have the same full-image
        # canonical material identity; their raw RGB state vectors are retained.
        if records[1]["material"]["canonical_material_sha256"]!=records[2]["material"]["canonical_material_sha256"]:
            return False
        receipt={"profile":PROFILE,"stage":stage,"price_phase":self.current_price_target["phase"],
                 "classification":"two_final_material_frames_confirmed","base_sample_count":1,
                 "observed_frame_sha256":observation.screenshot["sha256"],
                 "observed_frame_id_sha256":_digest(observation.frame_id.encode()),
                 "observed_material":observed,"physical_url":self.page.url,"observed_url":self.latest_url,
                 "rfq_id_sha256":_digest(self.current_price_target["rfq_id"].encode()),
                 "sku_sha256":_digest(self.current_price_target["sku"].encode()),
                 "initial_price_sha256":_digest(self.current_price_target["initial_price"].encode()),
                 "target_point":self._pending_price_edit["target"],"target_identity":identity,
                 "sampled_material_frames":records,"canonical_material_sha256":observed["canonical_material_sha256"]}
        if stage=="parse":self._price_parse_guard=receipt
        else:self._price_dispatch_guard=receipt
        return True


__all__=["OdooV066TrainRouteRouterV4","border_material","PROFILE",
         "TOP_POINTS","BOTTOM_POINTS","TOP_STATES","BOTTOM_STATES"]
