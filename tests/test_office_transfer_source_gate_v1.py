"""Only synthetic IDs and public WDI fixture values enter these source-gate tests."""

import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from native_desktop_factory import source as wdi
from ppt_wdi_factory import plan as ppt
from tools import office_transfer_source_gate_v1 as gate
from tools import build_ppt_wdi_train_calibration_80_v1 as calibration


class PowerPointTransferTests(unittest.TestCase):
    def _fixture(self, root: Path):
        seed = b"a" * 32
        original = ppt.build(seed)
        original_path = root / "original.private.json"
        original_path.write_bytes(ppt.canonical(original))
        queue = {"schema": "envloop-ppt-future-reserve-queue-private-v1",
                 "current_plan_sha256": gate.digest(original_path.read_bytes()),
                 "ordered_future_country_iso": []}
        queue_path = root / "queue.private.json"
        queue_path.write_bytes(ppt.canonical(queue))
        original_five = sorted({r["source_group"] for r in original["sets"]["train"]})
        unused = [a+b+c for a in "ABCDEFGHJKLMNOPQRSTUVWXYZ"
                  for b in "ABCDEFGHJKLMNOPQRSTUVWXYZ"
                  for c in "ABCDEFGHJKLMNOPQRSTUVWXYZ"
                  if a+b+c not in wdi.COUNTRIES]
        calibration_sources = original_five + unused[:3]
        calibration = {"schema": "envloop-ppt-wdi-train-calibration-80-private-v1",
                       "rows": [{"source_group": calibration_sources[i % 8],
                                 "calibration_role":
                                 "nonfinal_train_only_four_target_analogue"}
                                for i in range(80)]}
        cal_path = root / "calibration.private.json"
        cal_path.write_bytes(ppt.canonical(calibration))
        source_root = root / "official_csv"
        source_root.mkdir()
        history = root / "history"
        history.mkdir()
        for i in range(12):
            revision = history / f"ppt-revised-{i:02d}"
            revision.mkdir()
            (revision / "candidate-plan.private.json").write_bytes(
                original_path.read_bytes())
        for iso in unused[3:11]:
            directory = source_root / iso
            directory.mkdir()
            zip_raw, snapshot_raw = ("zip-" + iso).encode(), iso.encode()
            (source_root / f"{iso}-country.private.zip").write_bytes(zip_raw)
            (directory / "source-snapshot.private.json").write_bytes(snapshot_raw)
            provenance = {"schema":
                          "envloop-wdi-official-country-csv-extract-private-v1",
                          "country_iso": iso, "country_name": "Test " + iso,
                          "catalog_license": "CC BY 4.0",
                          "zip_sha256": gate.digest(zip_raw),
                          "snapshot_sha256": gate.digest(snapshot_raw),
                          "download_date": "2026-09-29",
                          "data_last_updated": "2026-09-01"}
            (directory / "source-provenance.private.json").write_bytes(
                ppt.canonical(provenance))
        return original_path, queue_path, cal_path, source_root, history, unused

    def test_new_ppt_pool_is_eighty_four_target_disjoint_specs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original, queue, cal, sources, history, unused = self._fixture(root)
            old = wdi.country_facts(wdi.load(), sorted(wdi.COUNTRIES)[0])

            def fake_facts(raw):
                iso = raw.decode()
                return {"iso3": iso, "name": "Test " + iso,
                        "years": old["years"]}

            with patch.object(gate, "PLAN_SHA", gate.digest(original.read_bytes())), \
                 patch.object(gate, "QUEUE_SHA", gate.digest(queue.read_bytes())), \
                 patch.object(calibration, "PLAN_SHA", gate.digest(original.read_bytes())), \
                 patch.object(calibration, "QUEUE_SHA", gate.digest(queue.read_bytes())), \
                 patch.object(gate, "extract",
                              side_effect=lambda _raw, iso: (iso.encode(),
                                                              {"numeric_observation_count": 30})), \
                 patch.object(gate, "facts_from_official_response", side_effect=fake_facts):
                pilot_sources = root / "pilot_sources"
                pilot_sources.mkdir()
                for directory in sorted(path for path in sources.iterdir() if path.is_dir())[:2]:
                    shutil.copytree(directory, pilot_sources / directory.name)
                    shutil.copyfile(sources / f"{directory.name}-country.private.zip",
                                    pilot_sources / f"{directory.name}-country.private.zip")
                pilot = gate.ppt_transfer_plan(b"b" * 32, pilot_sources,
                                               original, original, queue, cal,
                                               history, stage="pilot")
                result = gate.ppt_transfer_plan(b"b" * 32, sources, original,
                                                original, queue, cal, history,
                                                stage="expansion", pilot_plan=pilot)
            rows = result["rows"]
            self.assertEqual(len(rows), 80)
            self.assertEqual(len({r["task_id"] for r in rows}), 80)
            self.assertEqual({r["source_group"] for r in rows}, set(unused[3:11]))
            self.assertEqual(set(r["workflow"] for r in rows), set(ppt.WORKFLOWS))
            self.assertTrue(all(len(r["target_keys"]) == 4 and
                                r["split"] == "train_policy_development" and
                                r["rights_tier"] == gate.RIGHTS_WDI and
                                r["official_final_credit"] == 0 for r in rows))
            receipt = gate.ppt_public_receipt(result)
            self.assertEqual(receipt["analogue_specs"], 80)
            self.assertEqual(receipt["full_expansion_target_specs"], 80)
            self.assertEqual(receipt["offline_control_passed"], 0)
            self.assertNotIn("Test ", json.dumps(receipt))
            self.assertNotIn(rows[0]["task_id"], json.dumps(receipt))
            builder = Path("ppt_wdi_factory/build_train_transfer_deck.mjs")
            self.assertTrue(builder.is_file())
            self.assertNotEqual(gate.digest(builder.read_bytes()),
                                gate.digest(Path("ppt_wdi_factory/build_deck.mjs").read_bytes()))

    def test_missing_or_reused_source_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original, queue, cal, sources, history, _unused = self._fixture(root)
            for directory in sorted(path for path in sources.iterdir() if path.is_dir())[2:]:
                (sources / f"{directory.name}-country.private.zip").unlink()
                shutil.rmtree(directory)
            (sources / sorted(path.name for path in sources.iterdir() if path.is_dir())[0] /
             "source-provenance.private.json").unlink()
            with patch.object(gate, "PLAN_SHA", gate.digest(original.read_bytes())), \
                 patch.object(gate, "extract",
                              side_effect=lambda _raw, iso: (iso.encode(),
                                                              {"numeric_observation_count": 30})), \
                 self.assertRaises(FileNotFoundError):
                gate.ppt_transfer_plan(b"b" * 32, sources, original,
                                       original, queue, cal, history,
                                       stage="pilot")

    def test_two_source_pilot_covers_all_ten_workflows(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original, queue, cal, sources, history, _unused = self._fixture(root)
            for directory in sorted(path for path in sources.iterdir() if path.is_dir())[2:]:
                (sources / f"{directory.name}-country.private.zip").unlink()
                shutil.rmtree(directory)
            old = wdi.country_facts(wdi.load(), sorted(wdi.COUNTRIES)[0])

            def fake_facts(raw):
                iso = raw.decode()
                return {"iso3": iso, "name": "Test " + iso,
                        "years": old["years"]}

            with patch.object(gate, "PLAN_SHA", gate.digest(original.read_bytes())), \
                 patch.object(gate, "QUEUE_SHA", gate.digest(queue.read_bytes())), \
                 patch.object(calibration, "PLAN_SHA", gate.digest(original.read_bytes())), \
                 patch.object(calibration, "QUEUE_SHA", gate.digest(queue.read_bytes())), \
                 patch.object(gate, "extract",
                              side_effect=lambda _raw, iso: (iso.encode(),
                                                              {"numeric_observation_count": 30})), \
                 patch.object(gate, "facts_from_official_response", side_effect=fake_facts):
                result = gate.ppt_transfer_plan(b"b" * 32, sources, original,
                                                original, queue, cal, history,
                                                stage="pilot")
            self.assertEqual(len(result["rows"]), 20)
            self.assertEqual({r["workflow"] for r in result["rows"]},
                             set(ppt.WORKFLOWS))
            self.assertTrue(all(len(r["target_keys"]) == 4 for r in result["rows"]))
            receipt = gate.ppt_public_receipt(result)
            self.assertEqual(receipt["cases_per_workflow"], 2)
            self.assertEqual(receipt["analogue_specs"], 20)

    def test_ppt_preflight_reports_missing_inputs_without_source_names(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original, _queue, _cal, _sources, _history, _unused = self._fixture(root)
            with patch.object(gate, "PLAN_SHA", gate.digest(original.read_bytes())):
                receipt = gate.ppt_source_preflight(original, None, None)
            self.assertEqual(receipt["status"], "blocked")
            self.assertTrue(receipt["active_v13_plan_sha256_matches"])
            self.assertEqual(receipt["additional_train_specs_built"], 0)
            self.assertEqual(receipt["office_web_gui_admitted"], 0)
            self.assertNotIn("source_group", json.dumps(receipt))


class ExcelTransferTests(unittest.TestCase):
    def _fixture(self):
        graphs = [f"sealed-graph-{i:02d}" for i in range(13)]
        slots = []
        for split, count in (("train", 20), ("selection", 20), ("final", 100)):
            for i in range(count):
                slots.append({"split": split, "issuer_cik": i +
                              {"train": 1000, "selection": 2000,
                               "final": 3000}[split],
                              "original_filing_accession": f"{i+1:010d}-24-000001",
                              "semantic_template_reservation": graphs[i % 13]
                              if split == "final" else f"{split}-graph"})
        registry = {"slots": slots}
        edges = [["select", "reconcile"]]
        signatures = [gate.digest(ppt.canonical({
            "causal_skill_atoms": ["select filed fact", f"reconcile graph {i}"],
            "dependency_edges": edges})) for i in range(13)]
        cards = {"schema": gate.EXCEL_SCHEMA,
                 "cards": [{"final_graph_reservation": graph,
                            "causal_skill_atoms": ["select filed fact", f"reconcile graph {i}"],
                            "dependency_edges": edges,
                            "skill_signature_sha256": signatures[i],
                            "final_template_sha256": f"{i+1000:064x}",
                            "minimum_target_edits": 9,
                            "independent_skill_review": True}
                           for i, graph in enumerate(graphs)]}
        cases = []
        for graph_index, graph in enumerate(graphs):
            for j in range(8):
                case = {"final_graph_reservation": graph,
                        "analogue_id": f"train-{graph_index}-{j}",
                        "issuer_cik": 5000 + graph_index * 2 + j // 4,
                        "original_filing_accession":
                        f"{graph_index*8+j+1:010d}-25-000001",
                        "train_template_family": f"train-graph-{graph_index}",
                        "skill_signature_sha256": signatures[graph_index],
                        "target_formula_edits": 9,
                        "near_miss_edit_count": 8,
                        "rights_tier": gate.RIGHTS_SEC,
                        "source_provenance_tier": "independently_verified_exact_facts",
                        "independent_verifier_review": True}
                for field in ("positive_reference_pass", "near_miss_rejected",
                              "hardcode_rejected", "collateral_source_rejected",
                              "source_counterfactual_pass", "scenario_counterfactual_pass",
                              "fresh_reset_exact"):
                    case[field] = True
                case["source_excerpt_sha256"] = f"{graph_index*8+j+10000:064x}"
                case["train_template_sha256"] = f"{graph_index+2000:064x}"
                case["actor_sha256"] = f"{graph_index*8+j+30000:064x}"
                case["reference_sha256"] = f"{graph_index*8+j+40000:064x}"
                case["verifier_sha256"] = f"{graph_index+5000:064x}"
                cases.append(case)
        return registry, cards, {"schema": gate.EXCEL_CASE_SCHEMA, "cases": cases}

    def test_thirteen_graphs_need_reviewed_mapping_and_104_cases(self):
        registry, cards, pool = self._fixture()
        pilot = {"schema": gate.EXCEL_CASE_SCHEMA,
                 "cases": [case for case in pool["cases"]
                           if case["analogue_id"].rsplit("-", 1)[1] in ("0", "4")]}
        good = gate.excel_transfer_screen(registry, cards, pool,
                                          split_sha256=gate.EXCEL_SPLIT_SHA,
                                          stage="expansion", pilot_pool=pilot)
        self.assertEqual(good["status"],
                         "source_contract_complete_artifact_replay_pending")
        self.assertEqual(good["graph_to_skill_contract_coverage"], 13)
        self.assertEqual(good["train_only_analogues_submitted"], 104)
        self.assertEqual(good["cases_required_per_graph_for_stage"], 8)
        self.assertEqual(good["independently_replayed_saved_ooxml_controls"], 0)
        self.assertEqual(good["official_final_admitted"], 0)
        self.assertNotIn("sealed-graph", json.dumps(good))
        absent = gate.excel_transfer_screen(registry, None, None,
                                            split_sha256=gate.EXCEL_SPLIT_SHA)
        self.assertEqual(absent["status"], "blocked")
        self.assertIn("missing_private_graph_to_skill_mapping", absent["errors"])

    def test_two_per_graph_pilot_does_not_require_full_104(self):
        registry, cards, pool = self._fixture()
        pilot = {"schema": gate.EXCEL_CASE_SCHEMA,
                 "cases": [case for case in pool["cases"]
                           if case["analogue_id"].rsplit("-", 1)[1] in ("0", "4")]}
        result = gate.excel_transfer_screen(registry, cards, pilot,
                                            split_sha256=gate.EXCEL_SPLIT_SHA,
                                            stage="pilot")
        self.assertEqual(result["status"],
                         "source_contract_complete_artifact_replay_pending")
        self.assertEqual(result["train_only_analogues_submitted"], 26)
        self.assertEqual(result["cases_required_per_graph_for_stage"], 2)
        full = gate.excel_transfer_screen(registry, cards, pilot,
                                          split_sha256=gate.EXCEL_SPLIT_SHA,
                                          stage="expansion")
        self.assertEqual(full["status"], "blocked")
        self.assertIn("8_train_analogues_per_final_graph_required", full["errors"])

    def test_overlap_depth_negative_rights_and_registry_change_fail(self):
        registry, cards, pool = self._fixture()
        broken = pool["cases"][0]
        broken["issuer_cik"] = registry["slots"][0]["issuer_cik"]
        broken["target_formula_edits"] = 8
        broken["near_miss_rejected"] = False
        broken["rights_tier"] = "unknown"
        result = gate.excel_transfer_screen(registry, cards, pool,
                                            split_sha256=gate.EXCEL_SPLIT_SHA)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("train_source_or_template_overlaps_original_split", result["errors"])
        self.assertIn("analogue_skill_or_target_depth_unverified", result["errors"])
        self.assertIn("near_miss_no_regression_or_reset_control_missing", result["errors"])
        self.assertIn("rights_source_or_independent_review_missing", result["errors"])
        changed = gate.excel_transfer_screen(registry, cards, pool,
                                             split_sha256="0" * 64)
        self.assertEqual(changed["status"], "blocked")
        self.assertIn("missing_or_changed_private_140_slot_registry", changed["errors"])


if __name__ == "__main__":
    unittest.main()
