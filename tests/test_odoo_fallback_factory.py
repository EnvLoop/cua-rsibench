"""Offline invariants for the original Odoo Community fallback prototypes."""

from __future__ import annotations

import copy
import importlib.util
import json
import math
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock

ODDO_DIR = Path(__file__).resolve().parents[1] / "enterprise_fallback/odoo18"
sys.path.insert(0, str(ODDO_DIR))
from factory import (  # noqa: E402
    SOURCE, candidates, catalog, confirmation, replenishment_candidates,
    proposed_clustered_split, sha256_bytes, split_audit, train_world_candidates,
)
from multifamily import crm_candidates, crm_pdf, sales_candidates, sales_pdf  # noqa: E402
from partition_factory import (candidate_world, scale_final_task_sets,
                               split_audit as partition_split_audit)  # noqa: E402
from hidden_factory import (hidden_candidate_world, hidden_split_audit,
                            hidden_source_asset, hidden_task_sets)  # noqa: E402
from worker_lease import WorkerBusyError, exclusive_worker_operation  # noqa: E402
from gui_controls import browser_login  # noqa: E402
SPLIT_VALIDATOR = Path(__file__).resolve().parents[1] / "src/cursibench/scale_final_v06.py"
SPEC = importlib.util.spec_from_file_location("odoo_scale_final_v06", SPLIT_VALIDATOR)
assert SPEC is not None and SPEC.loader is not None
SCALE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCALE)
validate_splits = SCALE.validate_splits
import bootstrap as bootstrap_module  # noqa: E402
from verify import (  # noqa: E402
    evaluate, evaluate_replenishment, evaluate_sales, evaluate_crm,
    protected_source_file_differences, protected_source_store_path_differences,
)


class OdooFixtureTests(unittest.TestCase):
    def test_worker_operation_lease_rejects_concurrent_process(self):
        child = (
            "import sys; from pathlib import Path; "
            "sys.path.insert(0,sys.argv[2]); "
            "from worker_lease import exclusive_worker_operation,WorkerBusyError; "
            "root=Path(sys.argv[1]); "
            "\ntry:\n"
            " with exclusive_worker_operation('child',root=root): pass\n"
            "except WorkerBusyError:\n sys.exit(23)\n"
        )
        with tempfile.TemporaryDirectory() as scratch:
            directory = Path(scratch)
            with exclusive_worker_operation("parent", root=directory):
                with exclusive_worker_operation("nested", root=directory):
                    blocked = subprocess.run(
                        [sys.executable, "-c", child, str(directory), str(ODDO_DIR)],
                        capture_output=True, text=True)
                    self.assertEqual(blocked.returncode, 23, blocked.stderr)
            accepted = subprocess.run(
                [sys.executable, "-c", child, str(directory), str(ODDO_DIR)],
                capture_output=True, text=True)
            self.assertEqual(accepted.returncode, 0, accepted.stderr)

    def test_native_gui_helper_requires_worker_lease(self):
        with self.assertRaises(WorkerBusyError):
            browser_login(object(), 8078, "unread")

    def test_bootstrap_password_cannot_begin_with_cli_option_prefix(self):
        with mock.patch.object(bootstrap_module.secrets, "token_urlsafe", return_value="-dash-start"):
            self.assertEqual(bootstrap_module.local_password(), "p-dash-start")

    def test_four_family_partition_worlds_are_entity_and_asset_disjoint(self):
        seed = "local-test-seed-only-0123456789abcdef"
        audit = partition_split_audit(seed)
        self.assertTrue(audit["entity_disjoint"])
        self.assertEqual(audit["template_generalization"],
                         "held_out_causal_templates_within_four_workflows")
        self.assertEqual(audit["family_counts"], {
            "train": {"purchase": 5, "inventory": 5, "sales": 5, "crm": 5},
            "selection": {"purchase": 5, "inventory": 5, "sales": 5, "crm": 5},
            "evaluation_candidate": {"purchase": 25, "inventory": 25,
                                     "sales": 25, "crm": 25},
        })
        self.assertTrue(all(value == 0 for pair in audit["overlaps"].values()
                            for value in pair.values()))
        for part in audit["family_counts"]:
            world = candidate_world(seed, part)
            self.assertEqual(world, candidate_world(seed, part))
            self.assertEqual(len({case["id"] for family in world["cases"].values()
                                  for case in family}), sum(audit["family_counts"][part].values()))
            self.assertTrue(all(case["initial"] != case["expected"]
                                for case in world["cases"]["inventory"]))
            self.assertTrue(all(any(line["initial"] != line["expected"]
                                    for line in case["lines"])
                                for case in world["cases"]["purchase"]
                                + world["cases"]["sales"]))
        self.assertNotEqual(candidate_world(seed, "train"),
                            candidate_world(seed + "-different", "train"))
        task_sets = scale_final_task_sets(seed)
        self.assertEqual({name: len(rows) for name, rows in task_sets.items()},
                         {"train": 20, "selection": 20, "official": 100})
        self.assertEqual(len(validate_splits(task_sets)), 100)

    def test_partition_causal_templates_change_actual_target_transformations(self):
        worlds = {split: candidate_world("causal-template-test-0123456789abcdef", split)
                  for split in ("train", "selection", "evaluation_candidate")}
        for split, world in worlds.items():
            for case in world["cases"]["purchase"]:
                faults = [(position, field) for position, line in enumerate(case["lines"])
                          for field in ("qty", "price")
                          if line["initial"][field] != line["expected"][field]]
                positions = {position for position, _ in faults}
                if split == "train":
                    self.assertEqual(len(faults), 1)
                    self.assertEqual(faults[0][1], "price")
                elif split == "selection":
                    self.assertEqual(len(faults), 2)
                    self.assertEqual(len(positions), 1)
                else:
                    self.assertGreaterEqual(len(positions), 2)
            for case in world["cases"]["sales"]:
                changed = [(position, field) for position, line in enumerate(case["lines"])
                           for field in ("qty", "price")
                           if line["initial"][field] != line["expected"][field]]
                if split == "train":
                    self.assertEqual(len(changed), 1)
                    self.assertEqual(changed[0][1], "price")
                elif split == "selection":
                    self.assertEqual(len(changed), 1)
                    self.assertEqual(changed[0][1], "qty")
                else:
                    self.assertGreaterEqual(len({pos for pos, _ in changed}), 2)
                    self.assertEqual({field for _, field in changed}, {"qty", "price"})
            for case in world["cases"]["crm"]:
                changed = {field for field in case["expected"]
                           if case["initial"][field] != case["expected"][field]}
                self.assertEqual(changed, {
                    "train": {"stage_name", "salesperson_index"},
                    "selection": {"revenue", "deadline", "priority"},
                    "evaluation_candidate": set(case["expected"]),
                }[split])
            for case in world["cases"]["inventory"]:
                params = case["formula_inputs"]
                weeks = params["weeks"]
                if split == "train":
                    basis = sum(weeks) / 4
                elif split == "selection":
                    basis = max(weeks)
                else:
                    basis = sum((index + 1) * value for index, value in enumerate(weeks)) / 10
                    basis *= (100 + params["seasonal_uplift_pct"]) / 100
                minimum = math.ceil(basis * params["lead_days"] / 7)
                minimum += params["safety_stock"]
                self.assertEqual(case["expected"], {
                    "minimum": minimum,
                    "maximum": minimum + 2 * params["case_pack"]})

    def test_hidden_final_changes_business_rules_and_isolates_exposed_development(self):
        train_seed = "train-hidden-audit-seed-0123456789abcdef"
        hidden_seed = "new-hidden-only-seed-9876543210zyxwvutsr"
        world = hidden_candidate_world(hidden_seed)
        self.assertEqual(world["split"], "official_hidden")
        self.assertEqual({key: len(rows) for key, rows in world["cases"].items()},
                         {"purchase": 25, "inventory": 25, "sales": 25, "crm": 25})
        audit = hidden_split_audit(train_seed, hidden_seed)
        self.assertTrue(audit["strict_identity_source_template_disjoint"])
        self.assertTrue(all(value == 0 for group in audit["overlap_with_hidden"].values()
                            for value in group.values()))
        task_sets = hidden_task_sets(train_seed, hidden_seed)
        self.assertEqual({key: len(rows) for key, rows in task_sets.items()},
                         {"train": 20, "selection": 20, "official": 100})
        self.assertEqual(len(validate_splits(task_sets)), 100)
        self.assertTrue(all(row["task_id"].split("-")[1] == "HID"
                            for row in task_sets["official"]))
        other_hidden = hidden_candidate_world("another-hidden-seed-abcdef0123456789")
        self.assertFalse({case["id"] for rows in world["cases"].values() for case in rows}
                         & {case["id"] for rows in other_hidden["cases"].values() for case in rows})
        for case in world["cases"]["purchase"]:
            self.assertNotEqual(case["vendor_reference"], case["initial_vendor_reference"])
            self.assertEqual(case["revision_rule"]["authoritative"], "B")
        for case in world["cases"]["inventory"]:
            p = case["formula_inputs"]
            weeks = p["weeks"]
            lead = p["lead_days"] / 7
            target = math.ceil(sum(weeks) / 4 * lead
                               + p["service_factor"] * (max(weeks) - min(weeks))
                               * math.sqrt(lead)) + p["safety_stock"]
            self.assertEqual(case["expected"], {
                "minimum": target, "maximum": target + 3 * p["case_pack"]})
            self.assertIn("service factor", case["source_note"])
        for case in world["cases"]["sales"]:
            self.assertNotEqual(case["expiration_date"], case["initial_expiration_date"])
        for case in world["cases"]["crm"]:
            self.assertNotEqual(case["expected"]["email_from"], case["initial"]["email_from"])
            self.assertNotEqual(case["expected"]["phone"], case["initial"]["phone"])

    @unittest.skipUnless(importlib.util.find_spec("reportlab") and importlib.util.find_spec("pypdf"),
                         "PDF report dependencies not installed")
    def test_hidden_source_pdfs_expose_revision_deadline_and_verified_contact(self):
        from io import BytesIO
        from pypdf import PdfReader

        world = hidden_candidate_world("hidden-pdf-test-seed-0123456789abcdef")
        for family, required in (("purchase", ("Revision A", "Revision B", "Vendor reference")),
                                 ("sales", ("Quotation must expire", "Customer PO reference")),
                                 ("crm", ("Verified contact channels", "Phone:", "Email:"))):
            case = world["cases"][family][0]
            document = PdfReader(BytesIO(hidden_source_asset(case, world)))
            self.assertEqual(len(document.pages), 1)
            text = document.pages[0].extract_text()
            self.assertIn(case["id"], text)
            for phrase in required:
                self.assertIn(phrase, text)

    def test_bootstrap_rejects_occupied_loopback_port_before_credentials(self):
        with socket.socket() as occupied, tempfile.TemporaryDirectory() as scratch:
            occupied.bind(("127.0.0.1", 0))
            occupied.listen(1)
            port = occupied.getsockname()[1]
            root = Path(scratch)
            with mock.patch.object(bootstrap_module, "HERE", root), \
                 mock.patch.object(bootstrap_module, "PRIVATE", root / "private"), \
                 mock.patch.dict(os.environ, {"ODOO_PORT": str(port),
                                             "ODOO_PROJECT": "envloop-odoo-test"}):
                with self.assertRaisesRegex(RuntimeError, "already occupied"):
                    bootstrap_module.bootstrap()
            self.assertFalse((root / ".env").exists())

    def test_seeded_candidate_shape_and_provenance(self):
        rfqs = candidates()
        rules = replenishment_candidates()
        self.assertEqual(len(rfqs), 120)
        self.assertEqual(len(rules), 20)
        self.assertEqual(len(catalog()), 48)
        self.assertEqual(len({r["id"] for r in rfqs}), 120)
        self.assertEqual(len({r["sku"] for r in rules}), 20)
        self.assertEqual(sum(r["partition"] == "selection_candidate" for r in rfqs), 20)
        self.assertEqual(sum(r["partition"] == "unsealed_scale_candidate" for r in rfqs), 100)
        self.assertEqual(set(Counter(r["pattern"] for r in rfqs).values()), {15})
        for case in rfqs:
            self.assertEqual(len(case["lines"]), 3)
            self.assertEqual(len({line["sku"] for line in case["lines"]}), 3)
            self.assertTrue(any(line["initial"] != line["expected"] for line in case["lines"]))
        for case in rules:
            self.assertNotEqual(case["initial"], case["expected"])
            self.assertIn("four-week demand", case["source_note"])
        source = SOURCE.read_bytes()
        self.assertEqual(len(json.loads(source)["records"]), 112)
        self.assertEqual(sha256_bytes(source), "df9f56387b2c30bc521d8a4eb13c6e437a065d3b921ed4ae3a5fab1e1f20f64a")

    def test_sales_and_crm_are_distinct_nontrivial_development_families(self):
        sales, crm = sales_candidates(), crm_candidates()
        self.assertEqual((len(sales), len(crm)), (20, 20))
        self.assertEqual(len({c["id"] for c in sales + crm}), 40)
        self.assertEqual(len({c["customer"] for c in sales + crm}), 20)
        for case in sales:
            self.assertEqual(len(case["lines"]), 3)
            self.assertTrue(any(line["initial"] != line["expected"] for line in case["lines"]))
            self.assertNotEqual(case["initial_customer_reference"], case["customer_reference"])
            self.assertTrue(all(line["initial"]["discount"] == line["expected"]["discount"]
                                for line in case["lines"]))
        self.assertEqual({sum(line["initial"] != line["expected"] for line in case["lines"])
                          for case in sales}, {1, 2, 3})
        for case in crm:
            self.assertEqual(set(case["expected"]), set(case["initial"]))
            self.assertTrue(all(case["expected"][key] != case["initial"][key]
                                for key in case["expected"]))

    def test_train_world_entities_are_disjoint_and_reproducible(self):
        first = train_world_candidates(20260925)
        self.assertEqual(first, train_world_candidates(20260925))
        self.assertNotEqual(first, train_world_candidates(20260926))
        self.assertEqual(len(first), 40)
        evaluated = candidates()
        self.assertFalse({c["id"] for c in first} & {c["id"] for c in evaluated})
        self.assertFalse({c["vendor"] for c in first} & {c["vendor"] for c in evaluated})
        self.assertFalse({l["sku"] for c in first for l in c["lines"]} &
                         {l["sku"] for c in evaluated for l in c["lines"]})
        audit = split_audit()
        self.assertEqual(audit["train_selection_overlap"]["vendors"], 0)
        self.assertEqual(audit["train_scale_overlap"]["skus"], 0)
        self.assertEqual(audit["selection_scale_overlap"],
                         {"ids": 0, "vendors": 20, "skus": 36, "patterns": 8})
        self.assertFalse(audit["official_entity_and_pattern_disjoint_gate"])

    def test_proposed_clustered_split_is_entity_disjoint_but_same_template(self):
        plan = proposed_clustered_split(20260925)
        self.assertEqual({part: len(rows) for part, rows in plan.items()},
                         {"train": 40, "selection": 20, "evaluation_candidate_unsealed": 100})
        self.assertEqual(plan, proposed_clustered_split(20260925))
        pools = {}
        for part, rows in plan.items():
            pools[part] = {
                "ids": {row["id"] for row in rows},
                "vendors": {row["vendor"] for row in rows},
                "skus": {line["sku"] for row in rows for line in row["lines"]},
                "patterns": {row["pattern"] for row in rows},
            }
            self.assertTrue(all(count == 5 for count in Counter(row["vendor"] for row in rows).values()))
        parts = list(pools)
        for index, left in enumerate(parts):
            for right in parts[index + 1:]:
                for field in ("ids", "vendors", "skus"):
                    self.assertFalse(pools[left][field] & pools[right][field])
                self.assertEqual(len(pools[left]["patterns"] & pools[right]["patterns"]), 8)

    @unittest.skipUnless(importlib.util.find_spec("reportlab") and importlib.util.find_spec("pypdf"),
                         "PDF report dependencies not installed")
    def test_confirmation_is_readable_single_page_pdf(self):
        from io import BytesIO
        from pypdf import PdfReader

        case = candidates()[4]
        data = confirmation(case)
        reader = PdfReader(BytesIO(data))
        self.assertEqual(len(reader.pages), 1)
        text = reader.pages[0].extract_text()
        self.assertIn(case["id"], text)
        self.assertIn("SYNTHETIC BENCHMARK DOCUMENT", text)
        for line in case["lines"]:
            self.assertIn(line["sku"], text)
            self.assertIn(f"{line['expected']['price']:.2f}", text)

    @unittest.skipUnless(importlib.util.find_spec("reportlab") and importlib.util.find_spec("pypdf"),
                         "PDF report dependencies not installed")
    def test_new_source_documents_are_readable_pdfs(self):
        from io import BytesIO
        from pypdf import PdfReader
        sales = sales_candidates()[3]
        crm = crm_candidates()[3]
        for document, case in ((sales_pdf(sales), sales),
                               (crm_pdf(crm, ["Avery Lane", "Morgan Ellis", "Riley Chen"]), crm)):
            reader = PdfReader(BytesIO(document))
            self.assertEqual(len(reader.pages), 1)
            text = reader.pages[0].extract_text()
            self.assertIn(case["id"], text)
            self.assertIn("SYNTHETIC BENCHMARK DOCUMENT", text)


class IndependentEvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.baseline = {
            "orders": [{"id": 1, "name": "ELPO-0001"}],
            "lines": [
                {"id": 1, "order_id": 1, "product_id": 10, "name": "target", "qty": "2", "price": "12.00", "date": "2025-01-01"},
                {"id": 2, "order_id": 2, "product_id": 20, "name": "other", "qty": "3", "price": "15.00", "date": "2025-01-02"},
            ],
            "attachments": [{"id": 1, "checksum": "abc"}],
            "vendors": [{"id": 1, "name": "Vendor"}],
            "products": [{"id": 10, "description_purchase": "source"}],
            "orderpoints": [
                {"id": 1, "product_id": 10, "location_id": 8, "warehouse_id": 1,
                 "company_id": 1, "minimum": "15", "maximum": "19", "multiple": "1", "trigger": "manual"},
                {"id": 2, "product_id": 20, "location_id": 8, "warehouse_id": 1,
                 "company_id": 1, "minimum": "8", "maximum": "12", "multiple": "1", "trigger": "manual"},
            ],
            "sales_orders": [
                {"id": 10, "name": "ELSQ-0001", "origin": "ENVLOOP-SALES-DEV",
                 "partner_id": 100, "state": "draft", "client_order_ref": "draft", "note": "terms"},
                {"id": 11, "name": "ELSQ-0002", "origin": "ENVLOOP-SALES-DEV",
                 "partner_id": 101, "state": "draft", "client_order_ref": "other", "note": "terms"},
            ],
            "sales_lines": [
                {"id": 10, "order_id": 10, "product_id": 10, "name": "sale target",
                 "qty": "5", "price": "20", "discount": "5"},
                {"id": 11, "order_id": 11, "product_id": 20, "name": "other sale",
                 "qty": "7", "price": "30", "discount": "0"},
            ],
            "crm_leads": [
                {"id": 20, "name": "ELCRM-0001", "type": "opportunity", "partner_id": 100,
                 "user_id": 1, "team_id": 1, "stage_id": 2, "revenue": "5000",
                 "deadline": "2025-10-01", "priority": "0", "description": "intake", "active": True},
                {"id": 21, "name": "ELCRM-0002", "type": "opportunity", "partner_id": 101,
                 "user_id": 2, "team_id": 1, "stage_id": 2, "revenue": "6000",
                 "deadline": "2025-10-08", "priority": "0", "description": "intake", "active": True},
            ],
            "customers": [{"id": 100}], "salespeople": [{"id": 1}],
            "crm_stages": [{"id": 2}],
        }

    def test_purchase_positive_and_wrong_object_negative(self):
        target = {"lines": [{"line_id": 1, "product_id": 10,
                             "expected": {"qty": 2, "price": 10.0, "date": "2025-01-01"}}]}
        observed = copy.deepcopy(self.baseline)
        observed["lines"][0]["price"] = "10.00"
        self.assertEqual(evaluate("ELPO-0001", target, self.baseline, observed)["reward"], 1.0)
        observed["lines"][1]["qty"] = "4"
        self.assertIn("unrelated_order_line_changed",
                      evaluate("ELPO-0001", target, self.baseline, observed)["difference_codes"])
        observed = copy.deepcopy(self.baseline)
        observed["attachments"][0]["checksum"] = "tampered"
        self.assertIn("attachments_changed_or_missing",
                      evaluate("ELPO-0001", target, self.baseline, observed)["difference_codes"])

    def test_hidden_purchase_vendor_reference_is_required_and_other_fields_preserved(self):
        self.baseline["orders"][0]["partner_ref"] = "old-revision"
        target = {"order_id": 1, "vendor_reference": "VR-CURRENT",
                  "lines": [{"line_id": 1, "product_id": 10,
                             "expected": {"qty": 2, "price": 10.0, "date": "2025-01-01"}}]}
        observed = copy.deepcopy(self.baseline)
        observed["lines"][0]["price"] = "10.00"
        observed["orders"][0]["partner_ref"] = "VR-CURRENT"
        self.assertEqual(evaluate("ELPO-HID-0001", target, self.baseline, observed)["reward"], 1.0)
        observed["orders"][0]["partner_ref"] = "old-revision"
        self.assertIn("target_vendor_reference_mismatch",
                      evaluate("ELPO-HID-0001", target, self.baseline, observed)["difference_codes"])

    def test_global_business_identity_guard_rejects_new_unscoped_document(self):
        self.baseline["global_business_identity"] = {
            "purchase_order": [1], "stock_move": [3], "account_move": []}
        target = {"rule_id": 1, "expected": {"minimum": 13, "maximum": 21}}
        observed = copy.deepcopy(self.baseline)
        observed["orderpoints"][0]["minimum"] = "13"
        observed["orderpoints"][0]["maximum"] = "21"
        self.assertEqual(evaluate_replenishment("ELRP-0001", target,
                                                self.baseline, observed)["reward"], 1.0)
        observed["global_business_identity"]["purchase_order"].append(2)
        result = evaluate_replenishment("ELRP-0001", target, self.baseline, observed)
        self.assertEqual(result["reward"], 0.0)
        self.assertIn("global_business_record_identity_changed", result["difference_codes"])

    def test_replenishment_positive_and_wrong_rule_negative(self):
        target = {"rule_id": 1, "expected": {"minimum": 13, "maximum": 21}}
        observed = copy.deepcopy(self.baseline)
        observed["orderpoints"][0]["minimum"] = "13"
        observed["orderpoints"][0]["maximum"] = "21"
        self.assertEqual(evaluate_replenishment("ELRP-0001", target, self.baseline, observed)["reward"], 1.0)
        observed["orderpoints"][1]["minimum"] = "9"
        self.assertIn("unrelated_replenishment_rule_changed",
                      evaluate_replenishment("ELRP-0001", target, self.baseline, observed)["difference_codes"])

    def test_sales_positive_and_wrong_quote_negative(self):
        target = {"order_id": 10, "customer_reference": "CPO-391",
                  "lines": [{"line_id": 10, "product_id": 10,
                             "expected": {"qty": 5, "price": 18.0, "discount": 5}}]}
        observed = copy.deepcopy(self.baseline)
        observed["sales_orders"][0]["client_order_ref"] = "CPO-391"
        observed["sales_lines"][0]["price"] = "18.0"
        self.assertEqual(evaluate_sales("ELSQ-0001", target, self.baseline, observed)["reward"], 1.0)
        observed["sales_orders"][1]["client_order_ref"] = "wrong-object"
        self.assertIn("unrelated_sales_order_changed",
                      evaluate_sales("ELSQ-0001", target, self.baseline, observed)["difference_codes"])

    def test_hidden_sales_expiration_is_required(self):
        self.baseline["sales_orders"][0]["validity_date"] = "2027-03-01"
        target = {"order_id": 10, "customer_reference": "CPO-391",
                  "expiration_date": "2027-02-15",
                  "lines": [{"line_id": 10, "product_id": 10,
                             "expected": {"qty": 5, "price": 18.0, "discount": 5}}]}
        observed = copy.deepcopy(self.baseline)
        observed["sales_orders"][0].update({"client_order_ref": "CPO-391",
                                             "validity_date": "2027-02-15"})
        observed["sales_lines"][0]["price"] = "18.0"
        self.assertEqual(evaluate_sales("ELSQ-HID-0001", target, self.baseline, observed)["reward"], 1.0)
        observed["sales_orders"][0]["validity_date"] = "2027-03-01"
        self.assertIn("target_quotation_expiration_mismatch",
                      evaluate_sales("ELSQ-HID-0001", target, self.baseline, observed)["difference_codes"])

    def test_crm_positive_and_wrong_opportunity_negative(self):
        target = {"lead_id": 20, "expected": {"stage_id": 3, "user_id": 2,
                  "revenue": 7000, "deadline": "2025-10-15", "priority": "2"}}
        observed = copy.deepcopy(self.baseline)
        observed["crm_leads"][0].update({"stage_id": 3, "user_id": 2,
                                         "revenue": "7000", "deadline": "2025-10-15", "priority": "2"})
        self.assertEqual(evaluate_crm("ELCRM-0001", target, self.baseline, observed)["reward"], 1.0)
        observed["crm_leads"][1]["stage_id"] = 3
        self.assertIn("unrelated_crm_opportunity_changed",
                      evaluate_crm("ELCRM-0001", target, self.baseline, observed)["difference_codes"])

    def test_hidden_crm_verified_contact_channels_are_required(self):
        self.baseline["crm_leads"][0].update({"email_from": "intake@example.invalid",
                                               "phone": "+1 555 0901"})
        target = {"lead_id": 20, "expected": {"stage_id": 3, "user_id": 2,
                  "revenue": 7000, "deadline": "2025-10-15", "priority": "2",
                  "email_from": "verified@example.invalid", "phone": "+1 555 0101"}}
        observed = copy.deepcopy(self.baseline)
        observed["crm_leads"][0].update({"stage_id": 3, "user_id": 2,
            "revenue": "7000", "deadline": "2025-10-15", "priority": "2",
            "email_from": "verified@example.invalid", "phone": "+1 555 0101"})
        self.assertEqual(evaluate_crm("ELCRM-HID-0001", target, self.baseline, observed)["reward"], 1.0)
        observed["crm_leads"][0]["phone"] = "+1 555 0901"
        self.assertIn("target_crm_verified_phone_mismatch",
                      evaluate_crm("ELCRM-HID-0001", target, self.baseline, observed)["difference_codes"])

    def test_physical_source_oracle_ignores_cache_but_rejects_tampering(self):
        checksum = "a" * 40
        path = "filestore/bench/aa/" + checksum
        baseline = {"attachments": [{"checksum": checksum}]}
        frozen = {path: "file-bytes-sha256"}
        self.assertEqual(protected_source_file_differences(
            baseline, frozen, {**frozen, "filestore/bench/web-assets": "new-cache"}), [])
        self.assertEqual(protected_source_file_differences(
            baseline, frozen, {path: "tampered"}),
            ["protected_source_filestore_changed_or_missing"])
        self.assertEqual(protected_source_file_differences(
            baseline, frozen, {}),
            ["protected_source_filestore_changed_or_missing"])
        self.assertEqual(protected_source_store_path_differences(
            {"attachments": [{"id": 1, "checksum": checksum}]}, {"1": "aa/" + checksum}), [])
        self.assertEqual(protected_source_store_path_differences(
            {"attachments": [{"id": 1, "checksum": checksum}]}, {"1": "other/path"}),
            ["protected_source_store_path_changed_or_missing"])


if __name__ == "__main__":
    unittest.main()
