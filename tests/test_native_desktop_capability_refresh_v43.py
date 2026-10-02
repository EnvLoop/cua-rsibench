"""Offline refresh of current mode/medium proof before V43 admission."""
import copy
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from native_desktop_factory import native_editor_capability_v42 as capability
from native_desktop_factory import native_editor_evidence_v42 as evidence42
from native_desktop_factory import native_editor_reader_v42 as reader42
from native_desktop_factory import native_editor_runtime_v42 as runtime42
from native_desktop_factory import native_window_current_reader as reader41
from native_desktop_factory import native_window_current_runtime as runtime41
from native_desktop_factory import native_editor_evidence_v43 as evidence
from native_desktop_factory import native_editor_reader_v43 as reader
from native_desktop_factory import native_editor_runtime_v43 as runtime
from native_desktop_factory import common_native_guest_v31 as common
from tests import test_native_desktop_capability_v42 as fixtures
from tests.test_native_desktop_window_current import API, ancestry


MODE_API = SimpleNamespace(StateType=SimpleNamespace(**{
    key: key for key in ("CHECKED", "ENABLED", "SENSITIVE", "STALE", "DEFUNCT")
}))


class ModeNode:
    def __init__(self, events):
        self.events = events
        self.flags = {"CHECKED", "ENABLED", "SENSITIVE"}
        self.clears = 0

    def clear_cache(self):
        self.clears += 1
        self.events.append("clear_cache")

    def get_state_set(self):
        self.events.append("current_native_state")
        return SimpleNamespace(contains=lambda flag: flag in self.flags)


def current_medium(*, readonly=False):
    return {
        "application_is_readonly": readonly,
        "original_medium_writable": not readonly,
        "original_file_writable": True,
        "document_content_read": False,
        "application_store_called": False,
        "evaluator_pipe_owned_by_current_native_pid": True,
        "current_soffice_pid": 100,
    }


class CapabilityRefreshTests(unittest.TestCase):
    def fixture(self):
        native, window, table, cell = fixtures.CapabilityTests().reader_fixture()
        events = []
        node = ModeNode(events)
        source = evidence.CurrentEvidence(copy.deepcopy(native._v42_evidence))
        source.hooks = {"mode_node": node, "Atspi": MODE_API}
        source.pipe_name = "offline-owned-pipe"
        source.filename = "fixture.xlsx"
        source.x11 = {"window_id": "123", "pid": 100, "uid": 1000}
        native._v42_evidence = source
        return native, window, table, cell, source, node, events

    def medium_reader(self, source, events, result):
        def read(pipe_name, filename, x11):
            self.assertEqual((pipe_name, filename, x11), (source.pipe_name, source.filename, source.x11))
            events.append("current_medium")
            return copy.deepcopy(result)
        return read

    def record(self, module, native, window, cell):
        return module.compatible_record(native, API, cell, window, pid=100, uid=1000, viewport=[400, 300], ancestry=ancestry)

    def test_refresh_reopens_native_state_then_medium_before_timestamp_and_preserves_bindings(self):
        native, window, table, cell, source, node, events = self.fixture()
        binding = source["binding"]
        node_id = source["mode"]["node_identity_sha256"]

        def clock():
            events.append("refresh_clock")
            return 200.0

        with patch.object(evidence, "medium_metadata", side_effect=self.medium_reader(source, events, current_medium())), patch.object(evidence.time, "monotonic", side_effect=clock):
            self.assertIs(source.refresh(), source)
        self.assertEqual(events, ["clear_cache", "current_native_state", "current_medium", "refresh_clock"])
        self.assertEqual(node.clears, 1)
        self.assertEqual((source["mode"]["observed_at"], source["mode"]["expires_at"]), (200.0, 210.0))
        self.assertEqual(source["binding"], binding)
        self.assertEqual(source["mode"]["node_identity_sha256"], node_id)
        self.assertIs(source["medium"]["application_is_readonly"], False)
        self.assertFalse(source["medium"]["document_content_read"])
        self.assertFalse(source["medium"]["application_store_called"])

    def test_expired_v42_snapshot_refuses_then_v43_refreshes_once_immediately_before_capability(self):
        native, window, table, cell, source, node, events = self.fixture()
        before_flags = set(cell.flags)
        original_capability = capability.editor_capability

        def checked(**kwargs):
            events.append("capability")
            self.assertEqual(kwargs["edit_mode"]["observed_at"], 200.0)
            self.assertEqual(kwargs["edit_mode"]["expires_at"], 210.0)
            self.assertEqual(kwargs["now"], 200.0)
            return original_capability(**kwargs)

        with patch.object(evidence.time, "monotonic", return_value=200.0):
            old_record, old_fact = self.record(reader42, native, window, cell)
        self.assertFalse(old_record["enabled"])
        self.assertNotIn("sensitivity_capability_evidence", old_fact)
        self.assertEqual(node.clears, 0)
        with patch.object(evidence, "medium_metadata", side_effect=self.medium_reader(source, events, current_medium())), patch.object(evidence.time, "monotonic", return_value=200.0), patch.object(capability, "editor_capability", side_effect=checked):
            record, fact = self.record(reader, native, window, cell)
        self.assertEqual(events, ["clear_cache", "current_native_state", "current_medium", "capability"])
        self.assertEqual(node.clears, 1)
        self.assertTrue(record["enabled"])
        self.assertTrue(record["keyboard"])
        self.assertIs(fact["native_flags"]["SENSITIVE"], False)
        self.assertIs(fact["sensitivity_capability_evidence"]["raw_sensitive_value"], False)
        self.assertFalse(fact["sensitivity_capability_evidence"]["original_native_sensitive_asserted_true"])
        self.assertEqual(cell.flags, before_flags)

    def test_fresh_unchecked_disabled_insensitive_stale_defunct_and_readonly_rereads_refuse(self):
        for defect in ("unchecked", "disabled", "insensitive", "stale", "defunct", "readonly"):
            with self.subTest(defect=defect):
                native, window, table, cell, source, node, events = self.fixture()
                original_flags = set(cell.flags)
                if defect in ("unchecked", "disabled", "insensitive"):
                    node.flags.remove({"unchecked": "CHECKED", "disabled": "ENABLED", "insensitive": "SENSITIVE"}[defect])
                elif defect in ("stale", "defunct"):
                    node.flags.add(defect.upper())
                medium = current_medium(readonly=defect == "readonly")
                with patch.object(evidence, "medium_metadata", side_effect=self.medium_reader(source, events, medium)), patch.object(evidence.time, "monotonic", return_value=200.0):
                    record, fact = self.record(reader, native, window, cell)
                self.assertEqual(node.clears, 1)
                self.assertFalse(record["enabled"])
                self.assertFalse(record["keyboard"])
                self.assertNotIn("sensitivity_capability_evidence", fact)
                self.assertEqual(cell.flags, original_flags)
                self.assertEqual(source["mode"]["observed_at"], 200.0)
                if defect == "readonly":
                    self.assertIs(source["medium"]["application_is_readonly"], True)
                    self.assertIs(source["medium"]["original_medium_writable"], False)
                elif defect == "unchecked":
                    self.assertIs(source["mode"]["checked"], False)

    def test_foreign_missing_invalid_build_or_binding_does_not_gain_eligibility_after_refresh(self):
        for defect in ("foreign-principal", "foreign-document", "missing-document", "invalid-node", "unsupported-build", "ambiguous"):
            with self.subTest(defect=defect):
                native, window, table, cell, source, node, events = self.fixture()
                if defect == "foreign-principal":
                    source["native_pid"] = 200
                elif defect == "foreign-document":
                    source["binding"] = "c" * 64
                elif defect == "missing-document":
                    source["binding"] = None
                    source["mode"]["document_binding_sha256"] = None
                elif defect == "invalid-node":
                    source["mode"]["node_identity_sha256"] = "x" * 64
                elif defect == "unsupported-build":
                    source["build"]["executable_sha256"] = "0" * 64
                else:
                    source["mode"]["unique_current_command"] = False
                with patch.object(evidence, "medium_metadata", side_effect=self.medium_reader(source, events, current_medium())), patch.object(evidence.time, "monotonic", return_value=200.0):
                    record, fact = self.record(reader, native, window, cell)
                self.assertFalse(record["enabled"])
                self.assertFalse(record["keyboard"])
                self.assertNotIn("sensitivity_capability_evidence", fact)

    def test_failed_foreign_medium_reread_cannot_extend_expired_proof_or_admit(self):
        native, window, table, cell, source, node, events = self.fixture()
        with patch.object(evidence, "medium_metadata", side_effect=ValueError("Current original application medium differs")), patch.object(evidence.time, "monotonic", return_value=200.0):
            record, fact = self.record(reader, native, window, cell)
        self.assertFalse(record["enabled"])
        self.assertNotIn("sensitivity_capability_evidence", fact)
        self.assertEqual((source["mode"]["observed_at"], source["mode"]["expires_at"]), (100.0, 110.0))

    def test_unsupported_unfocused_or_unproved_native_node_skips_refresh_and_capability(self):
        for defect in ("unsupported-role", "unfocused-editor", "nonleaf"):
            with self.subTest(defect=defect):
                native, window, table, cell, source, node, events = self.fixture()
                if defect == "unsupported-role":
                    cell.role = "text"
                elif defect == "unfocused-editor":
                    table.flags.remove("FOCUSED")
                else:
                    cell.add(fixtures.Node("table cell"))
                with patch.object(evidence, "medium_metadata", side_effect=AssertionError("Unproved node must not query medium")), patch.object(evidence.time, "monotonic", return_value=200.0):
                    record, fact = self.record(reader, native, window, cell)
                self.assertFalse(record["enabled"])
                self.assertEqual(node.clears, 0)
                self.assertNotIn("sensitivity_capability_evidence", fact)

    def test_new_factory_has_one_class_for_seven_roles_and_three_apps_without_mutating_41_or_42(self):
        old_modules = (reader41, runtime41, capability, evidence42, reader42, runtime42)
        snapshots = {module: (Path(module.__file__).read_bytes(), dict(vars(module))) for module in old_modules}
        old_manifest = runtime42.source_manifest()
        old_factory = runtime42.factory(manifest=old_manifest)
        old_methods = {name: getattr(old_factory.actor_class, name) for name in ("prepare", "native_probe", "dispatch_model")}
        manifest = runtime.source_manifest()
        factory = runtime.factory(manifest=manifest)
        actors = []
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for role in common.ACTOR_PATHS:
                for filename in ("fixture.xlsx", "fixture.docx", "fixture.pptx"):
                    out = root / role / Path(filename).suffix[1:]
                    out.mkdir(parents=True)
                    sandbox = SimpleNamespace(sandbox_id=f"offline43-{role}-{filename}", commands=SimpleNamespace(), files=SimpleNamespace())
                    actor = factory.wrap_owned_guest(sandbox, root=root, out=out, filename=filename, lease_started_monotonic=time.monotonic())
                    actors.append(actor)
                    self.assertIs(type(actor), factory.actor_class)
                    self.assertFalse(actor.bootstrap_completed)
                    self.assertFalse(hasattr(actor, "editor_pipe"))
                    self.assertEqual(actor.native_probe.__globals__["PROBE_SCHEMA"], reader.SCHEMA)
                    self.assertEqual(actor.native_probe.__globals__["PROBE_SOURCE"], Path(reader.__file__))
                    self.assertTrue({"native_editor_reader_v43.py", "native_editor_evidence_v43.py", "native_editor_capability_v42.py"} <= set(actor._bootstrap.__globals__["PEERS"]))
        self.assertEqual(len(actors), 21)
        self.assertTrue(all(type(actor) is type(actors[0]) for actor in actors))
        self.assertIsNot(factory.actor_class, old_factory.actor_class)
        for name, method in old_methods.items():
            self.assertIs(getattr(old_factory.actor_class, name), method)
        for module, (raw, attributes) in snapshots.items():
            self.assertEqual(Path(module.__file__).read_bytes(), raw)
            self.assertEqual(dict(vars(module)), attributes)
        self.assertEqual(runtime42.source_manifest(), old_manifest)

    def test_new_source_closure_contains_refresh_test_and_retains_formal_qualification_gate(self):
        manifest = runtime.source_manifest()
        old = runtime42.source_manifest()
        for name, source_hash in old["source_sha256s"].items():
            self.assertEqual(manifest["source_sha256s"][name], source_hash)
        self.assertIn("tests/test_native_desktop_capability_refresh_v43.py", manifest["source_sha256s"])
        self.assertIs(manifest["raw_native_flags_preserved"], True)
        self.assertFalse(manifest["actor_office_api_available"])
        self.assertFalse(manifest["native_qualification_passed"])
        self.assertFalse(manifest["old_results_reclassified"])
        factory = runtime.factory(manifest=manifest)
        with self.assertRaisesRegex(ValueError, "Fresh common native qualification"):
            factory.require_activation()


if __name__ == "__main__":
    unittest.main()
