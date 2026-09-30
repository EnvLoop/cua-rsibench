"""Whole RGB vectors separate legitimate border states from edits and Franken states."""
from __future__ import annotations
import copy
from io import BytesIO
import json
from itertools import product
from pathlib import Path
import tempfile
import unittest
from PIL import Image
from cursibench.scale_action_contract import ContractError
from enterprise_fallback.odoo18.odoo_v066_train_route_router_v4 import (
    OdooV066TrainRouteRouterV4,border_material,TOP_POINTS,BOTTOM_POINTS,TOP_STATES,BOTTOM_STATES)
from tests.test_odoo_v066_train_price_passive_stability_v11 import PassivePricePage
from tests.test_odoo_v066_train_route_router_v1 import PriceLocator,TARGETS
from tools.odoo_v066_train_border_material_audit_v12 import independent_material,price_guard
from tools.audit_odoo_v066_train_attachment_calibration_v10 import CalibrationAuditError
from tools.audit_odoo_v066_train_attachment_calibration_v12 import _route_binding
from tools.odoo_v066_train_route_journal_v1 import RouteAwareHoldoutJournal
from tools import record_odoo_v066_train_gui_v1 as recorder


def png(top=0,bottom=0,*,extra=None,franken=False,mode="RGB"):
    image=Image.new("RGB",(1440,1000),"white")
    for xy,rgb in zip(TOP_POINTS,TOP_STATES[top]):image.putpixel(xy,rgb)
    for xy,rgb in zip(BOTTOM_POINTS,BOTTOM_STATES[bottom]):image.putpixel(xy,rgb)
    if extra:image.putpixel(extra,(0,0,0))
    if franken:image.putpixel(TOP_POINTS[0],TOP_STATES[1-top][0])
    if mode!="RGB":image=image.convert(mode)
    out=BytesIO();image.save(out,"PNG");return out.getvalue()


STATES=[png(t,b) for t in (0,1) for b in (0,1)]


class BorderMaterialTests(unittest.TestCase):
    def setup_attempt(self,frames,phase="positive"):
        temp=tempfile.TemporaryDirectory();out=Path(temp.name)/"attempt";out.mkdir(mode=0o700)
        page=PassivePricePage(phase);page.frames=list(frames);page.attempt_dir=out
        adapter=OdooV066TrainRouteRouterV4(page,task_id="ELPO-TRN-0001",task_binding_sha256="a"*64,
            instruction="train-only",expected_attachment_label="ELPO-TRN-0001-source.pdf",expected_price_targets=TARGETS)
        journal=RouteAwareHoldoutJournal(adapter,page,out);routes=out/"routes";routes.mkdir(mode=0o700)
        def sink(prefix):
            def save(serial,value):
                ref=recorder._artifact(routes,f"{prefix}-{serial:04d}.json",value);ref["path"]="routes/"+ref["path"];return ref
            return save
        adapter.route_probe_sink=sink("probe");adapter.route_decision_sink=sink("decision")
        def guard(index,raw):
            ref=recorder._artifact(out/"frames",f"guard-{index:04d}.png",raw);ref["path"]="frames/"+ref["path"];return ref
        adapter.frame_guard_sink=guard
        return temp,out,page,adapter,journal

    def audit_arguments(self,out,adapter,journal):
        intent=json.loads((out/"actions/step-000-intent.private.json").read_bytes())
        result=json.loads((out/"actions/step-000-result.private.json").read_bytes())
        case={"id":TARGETS[0]["rfq_id"],"lines":[{"sku":TARGETS[0]["sku"],"initial":{"price":float(TARGETS[0]["initial_price"])},"expected":{"price":100.0}}]}
        wrong={"id":TARGETS[1]["rfq_id"],"lines":[{"sku":TARGETS[1]["sku"],"initial":{"price":float(TARGETS[1]["initial_price"])}}]}
        baseline={"orders":[{"name":r["rfq_id"],"id":int(r["route_path"].rsplit("/",1)[1])} for r in TARGETS]}
        return intent,result,case,wrong,baseline

    def test_exact_four_whole_states_have_one_material_fingerprint(self):
        hashes=set()
        for t in (0,1):
            for b in (0,1):
                raw=png(t,b);producer=border_material(raw);auditor=independent_material(raw)
                self.assertEqual(producer,auditor);self.assertEqual(producer["state_class"],{"top":t,"bottom":b})
                hashes.add(producer["canonical_material_sha256"])
        self.assertEqual(len(hashes),1)

    def test_franken_vectors_and_mode_or_unknown_rgb_are_rejected(self):
        for raw in (png(franken=True),png(mode="RGBA"),png(mode="L")):
            self.assertIsNone(border_material(raw))
            with self.assertRaises(CalibrationAuditError):independent_material(raw)

    def test_every_mixed_top_and_bottom_state_vector_is_rejected(self):
        for points,states in ((TOP_POINTS,TOP_STATES),(BOTTOM_POINTS,BOTTOM_STATES)):
            for bits in product((0,1),repeat=len(points)):
                if len(set(bits))==1:continue
                image=Image.open(BytesIO(png())).copy()
                for i,xy in enumerate(points):image.putpixel(xy,states[bits[i]][i])
                stream=BytesIO();image.save(stream,"PNG");raw=stream.getvalue()
                self.assertIsNone(border_material(raw))
                with self.assertRaises(CalibrationAuditError):independent_material(raw)

    def test_one_pixel_outside_the_seven_is_never_normalized(self):
        baseline=border_material(png())
        for point in ((18,155),(16,156),(800,800),(809,479)):
            self.assertNotEqual(border_material(png(extra=point))["canonical_material_sha256"],baseline["canonical_material_sha256"])

    def test_alternating_complete_states_parse_and_dispatch_without_wait(self):
        for phase in ("positive","negative"):
            with self.subTest(phase=phase):
                temp,out,page,adapter,journal=self.setup_attempt([STATES[0],STATES[0],*STATES,*STATES],phase)
                with temp:
                    journal.act("double_click",phase=phase,locator=PriceLocator())
                    self.assertEqual(page.clicks,[(809,479)]);self.assertTrue(page.intent_existed_at_click)
                    self.assertEqual(page.waits,[120]) # Unchanged observation wait only.
                    intent,result,case,wrong,baseline=self.audit_arguments(out,adapter,journal)
                    kind,_route_refs=_route_binding(out,journal.trace[0],intent,result)
                    self.assertEqual(kind,"price_editor")
                    refs,count=price_guard(out,journal.trace[0],intent,result,case,wrong,baseline,adapter.frame_guard_samples)
                    self.assertEqual(count,1);self.assertEqual(len(refs),6)

    def test_material_and_franken_parse_fail_without_action_or_intent(self):
        for bad in (png(extra=(800,800)),png(franken=True)):
            temp,out,page,adapter,_journal=self.setup_attempt([STATES[0],STATES[0],STATES[1],bad])
            with temp:
                adapter.observe_for_model()
                with self.assertRaises(ContractError):adapter.parse_current_action(json.dumps({"type":"double_click","target":{"x":809,"y":479}}))
                self.assertEqual(page.clicks,[]);self.assertFalse(any((out/"actions").glob("*-intent.private.json")))

    def test_material_change_after_intent_is_terminal_without_retry(self):
        temp,out,page,_adapter,journal=self.setup_attempt([STATES[0],STATES[0],STATES[0],STATES[1],STATES[2],png(extra=(800,800))])
        with temp:
            with self.assertRaises(ContractError):journal.act("double_click",phase="positive",locator=PriceLocator())
            self.assertTrue((out/"actions/step-000-intent.private.json").exists());self.assertEqual(page.clicks,[])
            self.assertEqual(journal.pre_intent_rejections,[]);self.assertFalse((out/"actions/step-000-result.private.json").exists())

    def test_identity_loss_at_parse_or_dispatch_refuses_mouse(self):
        for parse in (True,False):
            temp,out,page,adapter,_journal=self.setup_attempt([STATES[0]]*9)
            with temp:
                adapter.observe_for_model()
                if parse:
                    page.strict_identity=False
                    with self.assertRaises(ContractError):adapter.parse_current_action(json.dumps({"type":"double_click","target":{"x":809,"y":479}}))
                else:
                    action=adapter.parse_current_action(json.dumps({"type":"double_click","target":{"x":809,"y":479}}))
                    page.strict_identity=False
                    with self.assertRaises(ContractError):adapter.dispatch(action,route_token=adapter.parsed_route_claim["route_token"])
                self.assertEqual(page.clicks,[])

    def test_independent_reader_rejects_forged_fingerprint_or_missing_raw_sample(self):
        temp,out,page,adapter,journal=self.setup_attempt([STATES[0]]*9)
        with temp:
            journal.act("double_click",phase="positive",locator=PriceLocator())
            intent,result,case,wrong,baseline=self.audit_arguments(out,adapter,journal)
            changed=copy.deepcopy(journal.trace[0]);changed["contract_receipt"]["price_parse_guard"]["canonical_material_sha256"]="b"*64
            with self.assertRaises(CalibrationAuditError):price_guard(out,changed,intent,result,case,wrong,baseline,adapter.frame_guard_samples)
            with self.assertRaises(CalibrationAuditError):price_guard(out,journal.trace[0],intent,result,case,wrong,baseline,adapter.frame_guard_samples[:-1])


if __name__=="__main__":unittest.main()
