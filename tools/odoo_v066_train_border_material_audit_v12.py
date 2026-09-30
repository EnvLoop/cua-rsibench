"""Independent raw-image reader for finite v12 form-border material states."""
from __future__ import annotations
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit
from PIL import Image
from tools.audit_odoo_v066_train_attachment_calibration_v10 import require,_ref
from tools import odoo_v066_scale_protocol_v1 as protocol

PROFILE="train-calibrated-two-corner-material-price-frame-2026-09-30-v12"
TOP_POINTS=((16,155),(16,157),(17,157))
BOTTOM_POINTS=((16,861),(17,861),(16,863),(17,863))
TOP_STATES=(((246,247,248),(226,230,234),(249,250,250)),((246,247,249),(226,229,234),(250,250,251)))
BOTTOM_STATES=(((226,230,234),(249,250,250),(246,247,248),(229,233,236)),((226,229,234),(250,250,251),(246,247,249),(230,233,236)))


def independent_material(raw:bytes)->dict:
    with Image.open(BytesIO(raw)) as source:
        require(source.format=="PNG" and source.mode=="RGB" and source.size==(1440,1000),"v12_independent_png_format_or_viewport_invalid")
        image=source.copy()
    top=tuple(image.getpixel(xy) for xy in TOP_POINTS)
    bottom=tuple(image.getpixel(xy) for xy in BOTTOM_POINTS)
    require(top in TOP_STATES and bottom in BOTTOM_STATES,"v12_unknown_or_franken_corner_vector")
    state={"top":TOP_STATES.index(top),"bottom":BOTTOM_STATES.index(bottom)}
    for xy,rgb in zip(TOP_POINTS,TOP_STATES[0]):image.putpixel(xy,rgb)
    for xy,rgb in zip(BOTTOM_POINTS,BOTTOM_STATES[0]):image.putpixel(xy,rgb)
    return {"state_class":state,"canonical_material_sha256":sha256(b"RGB-1440x1000-two-form-corners-v12\0"+image.tobytes()).hexdigest()}


def price_guard(out: Path, action: dict, intent: dict, result: dict,
                 case: dict, wrong: dict, baseline: dict,
                 samples: list[dict]) -> tuple[set[str], int]:
    receipt = action["contract_receipt"]
    parse = receipt.get("price_parse_guard")
    dispatch = receipt.get("price_dispatch_guard")
    if parse is None and dispatch is None:
        return set(), 0
    phase = action.get("phase")
    require(phase in ("positive", "negative"),
            "audit_price_guard_phase_invalid")
    if phase == "positive":
        relevant = case
        changed = [line for line in case["lines"]
                   if line["initial"]["price"] !=
                   line["expected"]["price"]]
        require(len(changed) == 1, "audit_price_train_line_not_unique")
        line = changed[0]
    else:
        relevant, line = wrong, wrong["lines"][0]
    sku, initial = line["sku"], f"{line['initial']['price']:.2f}"
    orders = [row for row in baseline["orders"]
              if row.get("name") == relevant["id"]]
    require(len(orders) == 1 and type(orders[0].get("id")) is int,
            "audit_price_rfq_route_not_unique")
    expected_route = f"/odoo/purchase/{orders[0]['id']}"
    target = intent.get("normalized_action", {}).get("target")
    frame_sha = action["frame"]["sha256"]
    frame_id_sha = protocol.digest(intent["frame_id"].encode())
    require(type(parse) is dict and type(dispatch) is dict and
            parse.get("price_phase") ==
            dispatch.get("price_phase") == phase and
            receipt.get("action_type") == "double_click" and
            intent.get("normalized_action", {}).get("type") ==
                "double_click" and
            type(target) is dict and set(target) == {"x", "y"} and
            parse.get("stage") == "parse" and
            dispatch.get("stage") == "dispatch" and
            parse.get("profile") == dispatch.get("profile") ==
                PROFILE and
            parse.get("rfq_id_sha256") ==
            dispatch.get("rfq_id_sha256") ==
                protocol.digest(relevant["id"].encode()) and
            parse.get("sku_sha256") == dispatch.get("sku_sha256") ==
                protocol.digest(sku.encode()) and
            parse.get("initial_price_sha256") ==
            dispatch.get("initial_price_sha256") ==
                protocol.digest(initial.encode()) and
            parse.get("observed_frame_sha256") ==
            dispatch.get("observed_frame_sha256") == frame_sha and
            parse.get("observed_frame_id_sha256") ==
            dispatch.get("observed_frame_id_sha256") == frame_id_sha and
            parse.get("target_point") ==
            dispatch.get("target_point") == target and
            parse.get("observed_url") ==
            dispatch.get("observed_url") ==
            parse.get("physical_url") ==
            dispatch.get("physical_url") == intent.get("observed_url") and
            urlsplit(intent["observed_url"]).path == expected_route,
            "audit_price_guard_binding_invalid")
    identity = parse.get("target_identity")
    require(type(identity) is dict and identity ==
            dispatch.get("target_identity") and
            identity.get("rfq_id") == relevant["id"] and
            identity.get("route_path") == expected_route and
            identity.get("sku") == sku and
            identity.get("initial_price") == initial and
            identity.get("editor_tag") == "input" and
            identity.get("editor_type") in ("text", "number", "search") and
            identity.get("focused") is True and
            identity.get("modal_absent") is True and
            identity.get("product_cell_sku_seen") is True and
            identity.get("editor_readonly") is False and
            type(identity.get("product_cell_bounds")) is list and
            len(identity["product_cell_bounds"]) == 4 and
            type(identity.get("editor_bounds")) is list and
            len(identity["editor_bounds"]) == 4 and
            identity["editor_bounds"][0] <= target["x"] <=
                identity["editor_bounds"][2] and
            identity["editor_bounds"][1] <= target["y"] <=
                identity["editor_bounds"][3] and
            not (16 <= target["x"] < 18 and 861 <= target["y"] < 864),
            "audit_price_target_identity_invalid")
    require(result.get("contract_receipt")==receipt,"v12_original_dispatch_receipt_changed")
    require((target["x"],target["y"]) not in set(TOP_POINTS)|set(BOTTOM_POINTS),"v12_target_inside_corner")
    observed=_ref(out,action["frame"],image=True)[1]
    expected=independent_material(observed)
    refs=set()
    for item in (parse,dispatch):
        stage=item["stage"]
        records=item.get("sampled_material_frames")
        require(item.get("classification")=="two_final_material_frames_confirmed" and item.get("base_sample_count")==1 and
                item.get("observed_material")==expected and item.get("canonical_material_sha256")==expected["canonical_material_sha256"] and
                type(records) is list and len(records)==3,"v12_material_guard_or_observed_fingerprint_invalid")
        phase_samples=[s for s in samples if s.get("step")==action["step"] and s.get("stage")==stage+"_border_material"]
        require(len(phase_samples)==3 and [s.get("sample") for s in phase_samples]==[0,1,2],"v12_material_sample_order_or_count_invalid")
        canonical=[]
        for n,(record,sample) in enumerate(zip(records,phase_samples)):
            require(type(record) is dict and set(record)=={"frame_ref","raw_frame_sha256","material"},"v12_raw_material_ref_invalid")
            path,raw=_ref(out,record["frame_ref"],image=True);refs.add(str(path))
            material=independent_material(raw)
            require(record.get("raw_frame_sha256")==protocol.digest(raw) and record.get("material")==material and
                    sample.get("sampled_frame_ref")==record["frame_ref"] and
                    sample.get("observed_frame_sha256")==frame_sha and sample.get("observed_frame_id_sha256")==frame_id_sha and
                    sample.get("border_state_class")==material["state_class"] and
                    sample.get("canonical_material_sha256")==material["canonical_material_sha256"] and
                    sample.get("classification")==("material_base_confirmed","material_first_final_confirmed","two_final_material_frames_confirmed")[n],
                    "v12_raw_material_membership_or_sample_changed")
            canonical.append(material["canonical_material_sha256"])
        require(canonical==[expected["canonical_material_sha256"]]*3 and canonical[1]==canonical[2],
                "v12_remaining_full_rgb_pixels_or_final_material_changed")
    return refs,1
