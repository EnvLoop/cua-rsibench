"""Independently read every v11 passive PNG; retain the v10 final-pair check."""
from __future__ import annotations

import copy

from enterprise_fallback.odoo18.odoo_v066_train_attachment_route_adapter_v5 import PROFILE as OLD_PROFILE
from enterprise_fallback.odoo18.odoo_v066_train_route_router_v3 import (
    PROFILE, MAX_PARSE_STABILITY_ROUNDS, PARSE_STABILITY_WAIT_MS,
)
from tools import audit_odoo_v066_train_attachment_calibration_v10 as prior
from tools import odoo_v066_scale_protocol_v1 as protocol


def price_guard(out, action, intent, result, case, wrong, baseline, samples):
    receipt = action["contract_receipt"]
    parse = receipt.get("price_parse_guard")
    if parse is None:
        return prior._price_guard(out, action, intent, result, case, wrong, baseline, samples)
    prior.require(result.get("contract_receipt") == receipt,
                  "audit_v11_original_dispatch_receipt_changed")
    rounds = parse.get("passive_pre_intent_rounds")
    prior.require(parse.get("profile") == PROFILE and parse.get("stage") == "parse" and
                  type(rounds) is list and 1 <= len(rounds) <= MAX_PARSE_STABILITY_ROUNDS and
                  parse.get("max_passive_rounds") == MAX_PARSE_STABILITY_ROUNDS and
                  parse.get("passive_wait_ms") == PARSE_STABILITY_WAIT_MS,
                  "audit_v11_passive_policy_invalid")
    observed = prior._ref(out, action["frame"], image=True)[1]
    passive = [row for row in samples if row.get("step") == action["step"] and
               row.get("stage") == "parse_price_stability"]
    prior.require(len(passive) == 3 * len(rounds), "audit_v11_passive_samples_missing")
    paths = set()
    for index, item in enumerate(rounds):
        prior.require(type(item) is dict and set(item) ==
                      {"round", "frame_refs", "members", "all_three_exact"} and
                      item.get("round") == index and type(item.get("frame_refs")) is list and
                      len(item["frame_refs"]) == 3 and type(item.get("members")) is list and
                      len(item["members"]) == 3, "audit_v11_passive_round_invalid")
        frames = []
        for n, ref in enumerate(item["frame_refs"]):
            path, raw = prior._ref(out, ref, image=True)
            paths.add(str(path))
            frames.append(raw)
            member = ("observed" if raw == observed else "corner_alternate" if
                      prior._corner_matches(observed, raw) else None)
            sample = passive[3 * index + n]
            prior.require(member is not None and item["members"][n] == member and
                          sample.get("sample") == 3 * index + n and
                          sample.get("classification") == "passive_" + member and
                          sample.get("sampled_frame_ref") == ref and
                          sample.get("observed_frame_sha256") == protocol.digest(observed) and
                          sample.get("observed_frame_id_sha256") == parse["observed_frame_id_sha256"],
                          "audit_v11_passive_material_or_frame_mismatch")
        equal = frames[0] == frames[1] == frames[2]
        prior.require(item.get("all_three_exact") is equal and
                      equal is (index == len(rounds) - 1),
                      "audit_v11_passive_success_round_invalid")
    final = rounds[-1]
    prior.require(final["frame_refs"] == [parse.get("base_frame_ref"),
                                          parse.get("first_final_frame_ref"),
                                          parse.get("second_final_frame_ref")],
                  "audit_v11_success_refs_not_last_round")
    # The old independent checker validates all exact final PNGs and RFQ,
    # price, bounds, task, frame, URL and dispatch identity checks. Adapt only
    # the newly recorded passive chronology into its original sample schema.
    canonical = copy.deepcopy(action)
    canonical_result = copy.deepcopy(result)
    old = canonical["contract_receipt"]["price_parse_guard"]
    old["profile"] = OLD_PROFILE
    for key in ("passive_pre_intent_rounds", "max_passive_rounds", "passive_wait_ms"):
        old.pop(key)
    canonical_result["contract_receipt"] = canonical["contract_receipt"]
    retained = [row for row in samples if not
                (row.get("step") == action["step"] and row.get("stage") == "parse_price_stability")]
    member = final["members"][0]
    for n, ref in enumerate(final["frame_refs"]):
        retained.append({"step": action["step"],
                         "stage": "parse" if n == 0 else "parse_price_final", "sample": n,
                         "classification": ("one_" + member if n == 0 else
                                            "candidate_" + member if n == 1 else
                                            "two_frame_" + member + "_confirmed"),
                         "sampled_frame_ref": ref,
                         "observed_frame_sha256": parse["observed_frame_sha256"],
                         "observed_frame_id_sha256": parse["observed_frame_id_sha256"]})
    refs, count = prior._price_guard(out, canonical, intent, canonical_result,
                                     case, wrong, baseline, retained)
    return refs | paths, count
