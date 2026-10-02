"""Synthetic V42 capability refusals; never native qualification evidence."""
import copy
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from native_desktop_factory import native_editor_capability_v42 as capability
from native_desktop_factory import native_window_current_reader as frozen_reader
from native_desktop_factory import native_window_current_runtime as frozen_runtime
from native_desktop_factory import native_editor_reader_v42 as reader
from native_desktop_factory import native_editor_runtime_v42 as runtime
from native_desktop_factory import common_native_guest_v31 as common
from tests.test_native_desktop_window_current import API, Node, ancestry, scoped


def fixture():
    flags = {name: True for name in capability.FLAGS}
    flags.update(SENSITIVE=False, DEFUNCT=False, STALE=False)
    return {
        "build": copy.deepcopy(capability.BUILD), "role": "table cell", "raw_flags": flags,
        "editor": {
            "enabled": True, "editable": True, "focused": True, "visible": True,
            "showing": True, "stale": False, "defunct": False,
        },
        "context": {
            "owned_current_principal": True, "lease_active": True,
            "strict_current_leaf_hit_proved": True, "same_current_editor": True,
            "original_file_writable": True, "original_medium_writable": True,
            "document_binding_sha256": "a" * 64,
        },
        "edit_mode": {
            "schema": "owned-current-edit-mode-evidence-v42",
            "document_binding_sha256": "a" * 64,
            "observed_at": 100.0, "expires_at": 110.0,
            "visible_initial_native_proof": True, "same_native_node_reopened": True,
            "current_native_state_read": True, "unique_current_command": True,
            "command": ".uno:EditDoc", "name": "Edit Mode", "parent_menu": "Edit",
            "checked": True, "enabled": True, "sensitive": True,
            "stale": False, "defunct": False, "node_identity_sha256": "b" * 64,
        },
        "now": 105.0,
    }


class CapabilityTests(unittest.TestCase):
    def test_supported_roles_have_separate_capability_with_raw_sensitive_still_false(self):
        original_build = copy.deepcopy(capability.BUILD)
        for role in capability.ROLES:
            with self.subTest(role=role):
                value = fixture()
                value["role"] = role
                before = copy.deepcopy(value)
                result = capability.editor_capability(**value)
                self.assertEqual(result["schema"], capability.SCHEMA)
                self.assertTrue(result["effective_input_eligible"])
                self.assertIs(result["raw_native_flags"]["SENSITIVE"], False)
                self.assertIs(result["raw_sensitive_value"], False)
                self.assertTrue(result["raw_native_flags_preserved"])
                self.assertFalse(result["original_native_sensitive_asserted_true"])
                self.assertFalse(result["native_policy_override_for_unsupported_nodes"])
                self.assertEqual(value, before)
                result["raw_native_flags"]["SENSITIVE"] = True
                result["edit_mode_evidence"]["checked"] = False
                result["build"]["executable_sha256"] = "0" * 64
                self.assertEqual(value, before)
        self.assertEqual(capability.BUILD, original_build)

    def test_every_build_pin_and_unsupported_role_fail_closed(self):
        for field in capability.BUILD:
            with self.subTest(build_field=field):
                value = fixture()
                value["build"][field] = "unsupported-" + value["build"][field]
                with self.assertRaisesRegex(ValueError, "Unsupported native application build"):
                    capability.editor_capability(**value)
        for role in ("entry", "push button", "panel", "document text", "unknown"):
            with self.subTest(role=role):
                value = fixture()
                value["role"] = role
                with self.assertRaisesRegex(ValueError, "Unsupported sensitivity capability role"):
                    capability.editor_capability(**value)

    def test_disabled_protected_hidden_stale_and_defunct_native_nodes_are_refused(self):
        for field, invalid in (
            ("ENABLED", False), ("EDITABLE", False), ("VISIBLE", False),
            ("SHOWING", False), ("STALE", True), ("DEFUNCT", True),
        ):
            with self.subTest(native_field=field):
                value = fixture()
                value["raw_flags"][field] = invalid
                with self.assertRaisesRegex(ValueError, "Disabled/protected/stale"):
                    capability.editor_capability(**value)

    def test_missing_nonboolean_or_true_sensitive_raw_state_is_never_reinterpreted(self):
        for field in capability.FLAGS:
            for invalid in ("missing", None, 1):
                with self.subTest(field=field, invalid=invalid):
                    value = fixture()
                    if invalid == "missing":
                        value["raw_flags"].pop(field)
                    else:
                        value["raw_flags"][field] = invalid
                    with self.assertRaisesRegex(ValueError, "flags missing/unknown"):
                        capability.editor_capability(**value)
        value = fixture()
        value["raw_flags"]["SENSITIVE"] = True
        with self.assertRaisesRegex(ValueError, "only for preserved false"):
            capability.editor_capability(**value)

    def test_foreign_inactive_unproved_leaf_and_different_editor_context_are_refused(self):
        for field in ("owned_current_principal", "lease_active", "strict_current_leaf_hit_proved", "same_current_editor"):
            for invalid in (False, None):
                with self.subTest(field=field, invalid=invalid):
                    value = fixture()
                    value["context"][field] = invalid
                    with self.assertRaisesRegex(ValueError, "ownership/leaf/editor evidence"):
                        capability.editor_capability(**value)

    def test_readonly_or_unknown_original_file_and_medium_are_refused(self):
        for field in ("original_file_writable", "original_medium_writable"):
            for invalid in (False, None):
                with self.subTest(field=field, invalid=invalid):
                    value = fixture()
                    value["context"][field] = invalid
                    with self.assertRaisesRegex(ValueError, "medium/file read-only or unknown"):
                        capability.editor_capability(**value)

    def test_current_editor_requires_positive_enabled_editable_focused_visible_states(self):
        for field in ("enabled", "editable", "focused", "visible", "showing", "stale", "defunct"):
            with self.subTest(field=field):
                value = fixture()
                value["editor"][field] = field in ("stale", "defunct")
                with self.assertRaisesRegex(ValueError, "focused editable editor missing"):
                    capability.editor_capability(**value)

    def test_missing_ambiguous_unreopened_or_wrong_command_edit_mode_is_refused(self):
        value = fixture()
        value["edit_mode"] = None
        with self.assertRaisesRegex(ValueError, "Edit Mode evidence missing"):
            capability.editor_capability(**value)
        for field in ("visible_initial_native_proof", "same_native_node_reopened", "current_native_state_read", "unique_current_command"):
            with self.subTest(field=field):
                value = fixture()
                value["edit_mode"][field] = False
                with self.assertRaisesRegex(ValueError, "missing/ambiguous"):
                    capability.editor_capability(**value)
        for field, invalid in (("schema", "old-proof"), ("command", ".uno:ReadOnlyDoc"), ("name", "Different Mode"), ("parent_menu", "File")):
            with self.subTest(field=field):
                value = fixture()
                value["edit_mode"][field] = invalid
                with self.assertRaisesRegex(ValueError, "unsupported"):
                    capability.editor_capability(**value)

    def test_unchecked_disabled_insensitive_stale_or_defunct_edit_mode_is_refused(self):
        for field in ("checked", "enabled", "sensitive", "stale", "defunct"):
            with self.subTest(field=field):
                value = fixture()
                value["edit_mode"][field] = field in ("stale", "defunct")
                with self.assertRaisesRegex(ValueError, "Document UI read-only/disabled"):
                    capability.editor_capability(**value)

    def test_stale_future_expired_overlong_and_unknown_proof_clocks_are_refused(self):
        for observed, expires, now in (
            (100.0, 110.0, 110.0), (100.0, 110.0, 99.0),
            (100.0, 111.0, 105.0), (None, 110.0, 105.0),
            (100.0, None, 105.0), (100.0, 110.0, None),
            (100.0, 110.0, float("nan")),
        ):
            with self.subTest(observed=observed, expires=expires, now=now):
                value = fixture()
                value["edit_mode"].update(observed_at=observed, expires_at=expires)
                value["now"] = now
                with self.assertRaisesRegex(ValueError, "stale/uncertain clock"):
                    capability.editor_capability(**value)

    def test_foreign_missing_and_invalid_document_or_native_node_bindings_are_refused(self):
        value = fixture()
        value["edit_mode"]["document_binding_sha256"] = "c" * 64
        with self.assertRaisesRegex(ValueError, "foreign document"):
            capability.editor_capability(**value)
        for invalid in (None, "", "x" * 64, "a" * 63):
            with self.subTest(invalid_document=invalid):
                value = fixture()
                value["context"]["document_binding_sha256"] = invalid
                value["edit_mode"]["document_binding_sha256"] = invalid
                with self.assertRaisesRegex(ValueError, "document binding missing"):
                    capability.editor_capability(**value)
            with self.subTest(invalid_native_node=invalid):
                value = fixture()
                value["edit_mode"]["node_identity_sha256"] = invalid
                with self.assertRaisesRegex(ValueError, "native node identity missing"):
                    capability.editor_capability(**value)

    def test_pure_capability_checks_do_not_modify_frozen_v41_bytes_or_globals(self):
        modules = (frozen_reader, frozen_runtime)
        snapshots = {module: (Path(module.__file__).read_bytes(), dict(vars(module))) for module in modules}
        capability.editor_capability(**fixture())
        for module, (raw, attributes) in snapshots.items():
            self.assertEqual(Path(module.__file__).read_bytes(), raw)
            self.assertEqual(dict(vars(module)), attributes)

    def reader_fixture(self):
        native = scoped()
        window = Node("frame")
        doc = window.add(Node("document spreadsheet", flags=["VISIBLE", "SHOWING", "ENABLED", "EDITABLE"]))
        table = doc.add(Node("table", flags=["VISIBLE", "SHOWING", "ENABLED", "EDITABLE", "FOCUSED"]))
        cell = table.add(Node("table cell", box=(100, 100, 80, 20), flags=["VISIBLE", "SHOWING", "ENABLED", "EDITABLE"]))
        window.hit = doc
        doc.hit = table
        table.hit = cell
        cell.hit = cell
        value = fixture()
        native._v42_evidence = {
            "build": value["build"], "mode": value["edit_mode"], "binding": "a" * 64,
            "native_pid": 100, "native_uid": 1000,
            "medium": {"original_file_writable": True, "original_medium_writable": True},
        }
        return native, window, table, cell

    def compatible(self, native, window, cell):
        with patch.object(reader.time, "monotonic", return_value=105.0):
            return reader.compatible_record(native, API, cell, window, pid=100, uid=1000, viewport=[400, 300], ancestry=ancestry)

    def test_actual_strict_leaf_record_gets_separate_capability_without_mutating_node_states(self):
        native, window, table, cell = self.reader_fixture()
        before = [set(node.flags) for node in (window, table, cell)]
        old_record, old_fact = frozen_reader.editable_record(native, API, cell, window, pid=100, uid=1000, viewport=[400, 300], ancestry=ancestry)
        self.assertFalse(old_record["enabled"])
        self.assertTrue(old_fact["point_hit_ownership_checked"])
        record, fact = self.compatible(native, window, cell)
        self.assertTrue(record["enabled"])
        self.assertTrue(record["keyboard"])
        self.assertFalse(record["obscured"])
        self.assertIs(fact["native_flags"]["SENSITIVE"], False)
        self.assertIs(fact["sensitivity_capability_evidence"]["raw_native_flags"]["SENSITIVE"], False)
        self.assertFalse(fact["sensitivity_capability_evidence"]["original_native_sensitive_asserted_true"])
        self.assertEqual([set(node.flags) for node in (window, table, cell)], before)

    def test_reader_does_not_project_capability_for_protected_readonly_foreign_or_missing_proof(self):
        for defect in ("protected-cell", "protected-sheet", "readonly", "foreign", "missing", "ambiguous", "unsupported-build", "nonleaf"):
            with self.subTest(defect=defect):
                native, window, table, cell = self.reader_fixture()
                if defect == "protected-cell":
                    cell.flags.remove("EDITABLE")
                elif defect == "protected-sheet":
                    table.flags.remove("EDITABLE")
                elif defect == "readonly":
                    native._v42_evidence["mode"]["checked"] = False
                elif defect == "foreign":
                    native._v42_evidence["native_pid"] = 200
                elif defect == "missing":
                    del native._v42_evidence
                elif defect == "ambiguous":
                    native._v42_evidence["mode"]["unique_current_command"] = False
                elif defect == "unsupported-build":
                    native._v42_evidence["build"]["gtk_plugin_sha256"] = "0" * 64
                else:
                    cell.add(Node("table cell"))
                record, fact = self.compatible(native, window, cell)
                self.assertFalse(record["enabled"])
                self.assertFalse(record["keyboard"])
                self.assertNotIn("sensitivity_capability_evidence", fact)

    def test_all_seven_roles_and_three_apps_share_exact_factory_class_without_prepare_or_provider_calls(self):
        old_sources = {module: (Path(module.__file__).read_bytes(), dict(vars(module))) for module in (frozen_reader, frozen_runtime)}
        old_manifest = frozen_runtime.source_manifest()
        old_factory = frozen_runtime.factory(manifest=old_manifest)
        old_prepare = old_factory.actor_class.prepare
        old_probe = old_factory.actor_class.native_probe
        manifest = runtime.source_manifest()
        factory = runtime.factory(manifest=manifest)
        actors = []
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for role in common.ACTOR_PATHS:
                for filename in ("fixture.xlsx", "fixture.docx", "fixture.pptx"):
                    with self.subTest(role=role, filename=filename):
                        out = root / role / Path(filename).suffix[1:]
                        out.mkdir(parents=True)
                        # Construction has no command, file IO, screenshot,
                        # GUI, SDK, or evaluator-listener implementation.
                        sandbox = SimpleNamespace(sandbox_id=f"offline-{role}-{filename}", commands=SimpleNamespace(), files=SimpleNamespace())
                        actor = factory.wrap_owned_guest(sandbox, root=root, out=out, filename=filename, lease_started_monotonic=time.monotonic())
                        actors.append(actor)
                        self.assertIs(type(actor), factory.actor_class)
                        self.assertEqual(actor.native_manifest, manifest)
                        self.assertFalse(actor.bootstrap_completed)
                        self.assertFalse(hasattr(actor, "editor_pipe"))
                        self.assertEqual(actor.native_probe.__globals__["PROBE_SCHEMA"], reader.SCHEMA)
                        self.assertEqual(actor.native_probe.__globals__["PROBE_SOURCE"], Path(reader.__file__))
                        peers = actor._bootstrap.__globals__["PEERS"]
                        self.assertTrue({"native_editor_reader_v42.py", "native_editor_capability_v42.py", "native_editor_evidence_v42.py"} <= set(peers))
                        self.assertTrue(callable(actor.refresh_editor_bootstrap))
        self.assertEqual(len(actors), 21)
        self.assertTrue(all(type(actor) is type(actors[0]) for actor in actors))
        self.assertIsNot(factory.actor_class, old_factory.actor_class)
        self.assertIs(old_factory.actor_class.prepare, old_prepare)
        self.assertIs(old_factory.actor_class.native_probe, old_probe)
        for module, (raw, attributes) in old_sources.items():
            self.assertEqual(Path(module.__file__).read_bytes(), raw)
            self.assertEqual(dict(vars(module)), attributes)
        self.assertEqual(frozen_runtime.source_manifest(), old_manifest)
        with self.assertRaisesRegex(ValueError, "Fresh common native qualification"):
            factory.require_activation()

    def test_source_manifest_and_public_binding_keep_old_sources_and_no_formal_credit(self):
        old = frozen_runtime.source_manifest()
        manifest = runtime.source_manifest()
        for name, source_hash in old["source_sha256s"].items():
            self.assertEqual(manifest["source_sha256s"][name], source_hash)
        self.assertEqual(set(manifest["source_sha256s"]) - set(old["source_sha256s"]), set(runtime.EXTRA) - set(old["source_sha256s"]))
        self.assertEqual(manifest["native_reader_schema"], reader.SCHEMA)
        self.assertEqual(manifest["capability_build"], capability.BUILD)
        self.assertTrue(manifest["raw_native_flags_preserved"])
        self.assertFalse(manifest["actor_office_api_available"])
        self.assertFalse(manifest["old_results_reclassified"])
        self.assertFalse(manifest["native_qualification_passed"])
        binding = runtime.public_binding()
        self.assertEqual(binding["source_manifest_sha256"], runtime.parent.digest(runtime.parent.canonical(manifest)))
        self.assertEqual(binding["actor_paths"], list(common.ACTOR_PATHS))
        self.assertFalse(binding["native_qualification_passed"])
        self.assertFalse(binding["old_results_reclassified"])
        self.assertEqual((binding["model_calls"], binding["tinker_calls"]), (0, 0))


if __name__ == "__main__":
    unittest.main()
