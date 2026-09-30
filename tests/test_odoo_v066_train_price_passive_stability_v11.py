"""Passive waits retain material rejection and the no-replay intent boundary."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

from cursibench.scale_action_contract import ContractError
from enterprise_fallback.odoo18.odoo_v066_train_route_router_v3 import (
    OdooV066TrainRouteRouterV3, MAX_PARSE_STABILITY_ROUNDS,
)
from tests.test_odoo_v066_train_price_corner_route_v5 import ALTERNATE, OBSERVED, THIRD, TARGETS
from tests.test_odoo_v066_train_route_owning_row_adapter_v1 import OwningPricePage
from tests.test_odoo_v066_train_route_router_v1 import PriceLocator
from tools import record_odoo_v066_train_gui_v1 as recorder
from tools.audit_odoo_v066_train_attachment_calibration_v10 import CalibrationAuditError
from tools.odoo_v066_train_price_stability_audit_v11 import price_guard
from tools.odoo_v066_train_route_journal_v1 import RouteAwareHoldoutJournal


class PassivePricePage(OwningPricePage):
    def __init__(self, phase="positive"):
        super().__init__(phase)
        self.waits = []
        self.mutate_on_wait = False

    def wait_for_timeout(self, duration):
        self.waits.append(duration)
        if self.mutate_on_wait and duration == 40:
            self.strict_identity = False


class PassiveStabilityTests(unittest.TestCase):
    def setup_attempt(self, frames, phase="positive"):
        temp = tempfile.TemporaryDirectory()
        out = Path(temp.name) / "attempt"
        out.mkdir(mode=0o700)
        page = PassivePricePage(phase)
        page.frames = list(frames)
        page.attempt_dir = out
        adapter = OdooV066TrainRouteRouterV3(
            page, task_id="ELPO-TRN-0001", task_binding_sha256="a" * 64,
            instruction="train-only", expected_attachment_label="ELPO-TRN-0001-source.pdf",
            expected_price_targets=TARGETS)
        journal = RouteAwareHoldoutJournal(adapter, page, out)
        routes = out / "routes"
        routes.mkdir(mode=0o700)

        def sink(prefix):
            def save(serial, value):
                ref = recorder._artifact(routes, f"{prefix}-{serial:04d}.json", value)
                ref["path"] = "routes/" + ref["path"]
                return ref
            return save

        adapter.route_probe_sink = sink("probe")
        adapter.route_decision_sink = sink("decision")

        def guard(index, raw):
            ref = recorder._artifact(out / "frames", f"guard-{index:04d}.png", raw)
            ref["path"] = "frames/" + ref["path"]
            return ref

        adapter.frame_guard_sink = guard
        return temp, out, page, adapter, journal

    def audit_action(self, out, adapter, journal):
        ai = json.loads((out / "actions/step-000-intent.private.json").read_bytes())
        result = json.loads((out / "actions/step-000-result.private.json").read_bytes())
        case = {"id": TARGETS[0]["rfq_id"], "lines": [{"sku": TARGETS[0]["sku"],
                "initial": {"price": float(TARGETS[0]["initial_price"])}, "expected": {"price": 100.0}}]}
        wrong = {"id": TARGETS[1]["rfq_id"], "lines": [{"sku": TARGETS[1]["sku"],
                 "initial": {"price": float(TARGETS[1]["initial_price"])}}]}
        baseline = {"orders": [{"name": row["rfq_id"], "id": int(row["route_path"].rsplit("/", 1)[1])} for row in TARGETS]}
        return ai, result, case, wrong, baseline

    def test_one_unstable_round_then_exact_parse_and_unchanged_dispatch(self):
        for phase in ("positive", "negative"):
            with self.subTest(phase=phase):
                # Two observation reads, one unstable passive triple, then
                # an exact triple and the original exact v5 dispatch triple.
                temp, out, page, adapter, journal = self.setup_attempt(
                    [OBSERVED, OBSERVED, OBSERVED, ALTERNATE, OBSERVED] + [ALTERNATE] * 6, phase)
                with temp:
                    journal.act("double_click", phase=phase, locator=PriceLocator())
                    self.assertEqual(page.clicks, [(809, 479)])
                    self.assertTrue(page.intent_existed_at_click)
                    self.assertEqual(page.waits, [120, 40])
                    parse = journal.trace[0]["contract_receipt"]["price_parse_guard"]
                    self.assertEqual(len(parse["passive_pre_intent_rounds"]), 2)
                    self.assertEqual([r["all_three_exact"] for r in parse["passive_pre_intent_rounds"]], [False, True])
                    ai, result, case, wrong, baseline = self.audit_action(out, adapter, journal)
                    refs, count = price_guard(out, journal.trace[0], ai, result, case, wrong,
                                               baseline, adapter.frame_guard_samples)
                    self.assertEqual(count, 1)
                    self.assertEqual(len(refs), 9)

    def test_material_frame_rejected_without_wait_or_intent(self):
        temp, out, page, adapter, _journal = self.setup_attempt([OBSERVED, OBSERVED, THIRD])
        with temp:
            adapter.observe_for_model()
            with self.assertRaises(ContractError):
                adapter.parse_current_action(json.dumps({"type": "double_click", "target": {"x": 809, "y": 479}}))
            self.assertEqual(page.clicks, [])
            self.assertFalse(any((out / "actions").glob("*-intent.private.json")))
            self.assertNotIn(40, page.waits)

    def test_material_pixel_after_known_pair_still_rejected(self):
        temp, out, page, adapter, _journal = self.setup_attempt([OBSERVED, OBSERVED, OBSERVED, ALTERNATE, THIRD])
        with temp:
            adapter.observe_for_model()
            with self.assertRaises(ContractError):
                adapter.parse_current_action(json.dumps({"type": "double_click", "target": {"x": 809, "y": 479}}))
            self.assertEqual(page.clicks, [])
            self.assertEqual(page.waits, [120])

    def test_permanent_alternation_exhausts_six_rounds_before_intent(self):
        temp, out, page, adapter, _journal = self.setup_attempt(
            [OBSERVED, OBSERVED] + [OBSERVED, ALTERNATE, OBSERVED] * MAX_PARSE_STABILITY_ROUNDS)
        with temp:
            adapter.observe_for_model()
            with self.assertRaises(ContractError):
                adapter.parse_current_action(json.dumps({"type": "double_click", "target": {"x": 809, "y": 479}}))
            self.assertEqual(len(adapter.frame_guard_samples), 18)
            self.assertEqual(page.waits, [120] + [40] * 5)
            self.assertEqual(page.clicks, [])

    def test_identity_change_during_passive_wait_rejected(self):
        temp, out, page, adapter, _journal = self.setup_attempt(
            [OBSERVED, OBSERVED, OBSERVED, ALTERNATE, OBSERVED] + [ALTERNATE] * 3)
        with temp:
            page.mutate_on_wait = True
            adapter.observe_for_model()
            with self.assertRaises(ContractError):
                adapter.parse_current_action(json.dumps({"type": "double_click", "target": {"x": 809, "y": 479}}))
            self.assertEqual(len(adapter.frame_guard_samples), 3)
            self.assertEqual(page.clicks, [])

    def test_unstable_dispatch_after_intent_is_terminal_without_retry(self):
        temp, out, page, _adapter, journal = self.setup_attempt(
            [OBSERVED, OBSERVED] + [ALTERNATE] * 4 + [OBSERVED])
        with temp:
            with self.assertRaises(ContractError):
                journal.act("double_click", phase="positive", locator=PriceLocator())
            self.assertTrue((out / "actions/step-000-intent.private.json").exists())
            self.assertEqual(page.clicks, [])
            self.assertEqual(page.waits, [120])
            self.assertEqual(journal.pre_intent_rejections, [])
            self.assertFalse((out / "actions/step-000-result.private.json").exists())

    def test_auditor_rejects_forged_round_or_missing_sample(self):
        temp, out, _page, adapter, journal = self.setup_attempt([OBSERVED, OBSERVED] + [ALTERNATE] * 6)
        with temp:
            journal.act("double_click", phase="positive", locator=PriceLocator())
            ai, result, case, wrong, baseline = self.audit_action(out, adapter, journal)
            changed = copy.deepcopy(journal.trace[0])
            changed["contract_receipt"]["price_parse_guard"]["passive_pre_intent_rounds"][0]["all_three_exact"] = False
            with self.assertRaises(CalibrationAuditError):
                price_guard(out, changed, ai, result, case, wrong, baseline, adapter.frame_guard_samples)
            with self.assertRaises(CalibrationAuditError):
                price_guard(out, journal.trace[0], ai, result, case, wrong, baseline, adapter.frame_guard_samples[1:])


if __name__ == "__main__":
    unittest.main()
