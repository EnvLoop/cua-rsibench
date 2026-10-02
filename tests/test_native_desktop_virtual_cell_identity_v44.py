"""Offline exact Table-position joins for distinct native cell instances."""
import copy
import hashlib
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest

from native_desktop_factory import native_virtual_cell_identity_v44 as virtual
from native_desktop_factory import native_window_current_reader as reader41
from native_desktop_factory import native_window_current_runtime as runtime41
from native_desktop_factory import native_editor_capability_v42 as capability
from native_desktop_factory import native_editor_reader_v42 as reader42
from native_desktop_factory import native_editor_runtime_v42 as runtime42
from native_desktop_factory import native_editor_reader_v43 as reader43
from native_desktop_factory import native_editor_runtime_v43 as runtime43
from native_desktop_factory import native_editor_evidence_v44 as evidence44
from native_desktop_factory import native_editor_reader_v44 as reader44
from native_desktop_factory import native_editor_runtime_v44 as runtime44
from native_desktop_factory import common_native_guest_v31 as common
from tests.test_native_desktop_window_current import API, Node, ancestry, scoped


class NativeNode(Node):
    def __init__(self, label, role, **kwargs):
        super().__init__(role, **kwargs)
        self.path = "/org/a11y/atspi/accessible/" + label
        self.app = SimpleNamespace(bus_name=":1.100")

    def get_name(self):
        raise AssertionError("A virtual cell name must never prove identity")

    def get_text_iface(self):
        raise AssertionError("Virtual identity must not query cell contents")

    def get_value_iface(self):
        raise AssertionError("Virtual identity must not query cell values")

    def get_child_at_index(self, index):
        raise AssertionError("Virtual identity must not enumerate a huge native Table")


class TableInterface:
    def __init__(self):
        self.rows, self.columns = 1048576, 1024
        self.calls = []
        self.row_override = None
        self.column_override = None
        self.roundtrip_override = None

    def get_n_rows(self):
        self.calls.append(("rows",))
        return self.rows

    def get_n_columns(self):
        self.calls.append(("columns",))
        return self.columns

    def get_row_at_index(self, index):
        self.calls.append(("row", index))
        return index // self.columns if self.row_override is None else self.row_override

    def get_column_at_index(self, index):
        self.calls.append(("column", index))
        return index % self.columns if self.column_override is None else self.column_override

    def get_index_at(self, row, column):
        self.calls.append(("index", row, column))
        return row * self.columns + column if self.roundtrip_override is None else self.roundtrip_override


class TableNode(NativeNode):
    def __init__(self, label):
        super().__init__(label, "table", flags=["VISIBLE", "SHOWING", "ENABLED", "EDITABLE", "FOCUSED", "MANAGES_DESCENDANTS"])
        self.interface = TableInterface()

    def get_table_iface(self):
        return self.interface

    def get_child_count(self):
        raise AssertionError("No virtual Table child count or full tree scan")


class VirtualCellTests(unittest.TestCase):
    def fixture(self):
        reader = scoped()
        window = NativeNode("window", "frame")
        table = window.add(TableNode("table"))
        flags = ["VISIBLE", "SHOWING", "ENABLED", "EDITABLE"]
        requested = NativeNode("requested_cell", "table cell", box=(100, 100, 80, 20), flags=flags)
        hit = NativeNode("physical_cell", "table cell", box=(100, 100, 80, 20), flags=flags)
        requested.parent = hit.parent = table
        requested.index = hit.index = 3 * 1024 + 1
        window.hit = table
        table.hit = hit
        hit.hit = hit
        calls = []
        original_physical = reader.physical_hit

        def physical(*args, **kwargs):
            calls.append((args[2], kwargs))
            return original_physical(*args, **kwargs)

        reader.physical_hit = physical
        return reader, window, table, requested, hit, calls

    def prove(self, reader, window, node, *, ancestry_fn=ancestry, build=None, pid=100):
        return virtual.checked_virtual_cell(reader, API, node, window, pid=pid, viewport=[400, 300], ancestry=ancestry_fn,
            build=copy.deepcopy(capability.BUILD) if build is None else build)

    def test_distinct_bus_path_instances_join_only_by_exact_native_table_position_and_bounds(self):
        reader, window, table, requested, hit, calls = self.fixture()
        before = [set(node.flags) for node in (window, table, requested, hit)]
        proof = self.prove(reader, window, requested)
        self.assertFalse(proof["native_bus_object_ids_equal"])
        self.assertNotEqual(proof["node_identity"]["identity_sha256"], proof["physical_leaf_identity"]["identity_sha256"])
        self.assertEqual(proof["virtual_descriptor"], {
            "table_identity_sha256": virtual.native_identity(table)["identity_sha256"],
            "native_index": 3073, "row": 3, "column": 1,
        })
        self.assertTrue(proof["native_table_position_equality_checked"])
        self.assertTrue(proof["original_strict_physical_leaf_checks_used"])
        self.assertTrue(proof["raw_native_flags_preserved"])
        self.assertIs(proof["node_raw_flags"]["SENSITIVE"], False)
        self.assertIs(proof["physical_leaf_raw_flags"]["SENSITIVE"], False)
        self.assertFalse(proof["cell_name_or_value_used"])
        self.assertFalse(proof["same_pid_or_bounds_shortcut_used"])
        self.assertEqual(proof["physical_hit_depth"], 3)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], [140, 161])
        self.assertEqual(hit.point_queries, [(140, 110, API.CoordType.WINDOW)])
        self.assertEqual(table.interface.calls, [
            ("rows",), ("columns",), ("row", 3073), ("column", 3073), ("index", 3, 1),
            ("rows",), ("columns",), ("row", 3073), ("column", 3073), ("index", 3, 1),
        ])
        self.assertEqual([set(node.flags) for node in (window, table, requested, hit)], before)
        self.assertNotIn("effective_input_eligible", proof)

    def test_same_literal_cell_still_runs_original_fresh_physical_proof(self):
        reader, window, table, requested, hit, calls = self.fixture()
        table.hit = requested
        requested.hit = requested
        proof = self.prove(reader, window, requested)
        self.assertTrue(proof["native_bus_object_ids_equal"])
        self.assertEqual(len(calls), 1)

    def test_every_unsupported_build_pin_and_unknown_pid_is_refused(self):
        for field in capability.BUILD:
            with self.subTest(field=field):
                reader, window, table, requested, hit, calls = self.fixture()
                build = copy.deepcopy(capability.BUILD)
                build[field] = "unsupported"
                with self.assertRaisesRegex(ValueError, "Unsupported virtual-cell application build"):
                    self.prove(reader, window, requested, build=build)
                self.assertEqual(calls, [])
        for pid in (None, True, 0, "100"):
            with self.subTest(pid=pid), self.assertRaisesRegex(ValueError, "process unknown"):
                reader, window, table, requested, hit, calls = self.fixture()
                self.prove(reader, window, requested, pid=pid)

    def test_same_pid_and_bounds_cannot_join_cells_from_different_owned_tables(self):
        reader, window, table, requested, hit, calls = self.fixture()
        other = window.add(TableNode("other_table"))
        hit.parent = other
        window.hit = other
        other.hit = hit
        with self.assertRaisesRegex(ValueError, "another native Table position"):
            self.prove(reader, window, requested)

    def test_foreign_pid_on_either_literal_cell_or_any_owned_ancestor_is_refused(self):
        for target in ("requested", "physical", "table", "window"):
            with self.subTest(target=target):
                reader, window, table, requested, hit, calls = self.fixture()
                {"requested": requested, "physical": hit, "table": table, "window": window}[target].pid = 200
                with self.assertRaisesRegex(ValueError, "ownership"):
                    self.prove(reader, window, requested)

    def test_both_literal_leaf_states_refuse_disabled_protected_hidden_stale_defunct_managed_or_sensitive(self):
        for target in ("requested", "physical"):
            for defect in ("ENABLED", "EDITABLE", "VISIBLE", "SHOWING", "STALE", "DEFUNCT", "MANAGES_DESCENDANTS", "SENSITIVE"):
                with self.subTest(target=target, defect=defect):
                    reader, window, table, requested, hit, calls = self.fixture()
                    node = requested if target == "requested" else hit
                    if defect in ("ENABLED", "EDITABLE", "VISIBLE", "SHOWING"):
                        node.flags.remove(defect)
                    else:
                        node.flags.add(defect)
                    with self.assertRaises(ValueError):
                        self.prove(reader, window, requested)

    def test_unfocused_or_noneditable_table_and_unsafe_intermediary_cannot_prove_virtual_identity(self):
        for defect in ("FOCUSED", "EDITABLE", "ENABLED", "STALE", "DEFUNCT"):
            with self.subTest(table_defect=defect):
                reader, window, table, requested, hit, calls = self.fixture()
                if defect in ("FOCUSED", "EDITABLE", "ENABLED"):
                    table.flags.remove(defect)
                else:
                    table.flags.add(defect)
                with self.assertRaises(ValueError):
                    self.prove(reader, window, requested)
        for defect in ("ENABLED", "VISIBLE", "SHOWING", "STALE", "DEFUNCT", "SENSITIVE"):
            with self.subTest(intermediary_defect=defect):
                reader, window, table, requested, hit, calls = self.fixture()
                intermediary = NativeNode("intermediary", "panel")
                intermediary.parent = table
                requested.parent = intermediary
                if defect in ("ENABLED", "VISIBLE", "SHOWING", "SENSITIVE"):
                    intermediary.flags.remove(defect)
                else:
                    intermediary.flags.add(defect)
                with self.assertRaisesRegex(ValueError, "ancestor unsafe|insensitive native ancestor"):
                    self.prove(reader, window, requested)

    def test_nonleaf_missing_table_interface_and_missing_or_ambiguous_table_reference_are_refused(self):
        for target in ("requested", "physical"):
            with self.subTest(nonleaf=target):
                reader, window, table, requested, hit, calls = self.fixture()
                (requested if target == "requested" else hit).add(NativeNode("child", "text"))
                with self.assertRaisesRegex(ValueError, "leaf"):
                    self.prove(reader, window, requested)
        reader, window, table, requested, hit, calls = self.fixture()
        table.interface = None
        with self.assertRaisesRegex(ValueError, "position interface unavailable"):
            self.prove(reader, window, requested)
        reader, window, table, requested, hit, calls = self.fixture()
        requested.parent = window
        with self.assertRaisesRegex(ValueError, "Table missing/ambiguous"):
            self.prove(reader, window, requested)
        reader, window, table, requested, hit, calls = self.fixture()
        other = TableNode("outer_table")
        other.parent = window
        table.parent = other
        with self.assertRaisesRegex(ValueError, "Table missing/ambiguous"):
            self.prove(reader, window, requested)

    def test_invalid_dimensions_index_and_native_position_roundtrip_are_refused(self):
        for field, invalid in (("rows", 0), ("rows", 1048577), ("rows", True), ("columns", 0), ("columns", 1025), ("columns", "1024")):
            with self.subTest(field=field, invalid=invalid):
                reader, window, table, requested, hit, calls = self.fixture()
                setattr(table.interface, field, invalid)
                with self.assertRaisesRegex(ValueError, "dimensions unsupported"):
                    self.prove(reader, window, requested)
        for index in (-1, None, True, 1048576 * 1024):
            with self.subTest(index=index):
                reader, window, table, requested, hit, calls = self.fixture()
                requested.index = index
                with self.assertRaisesRegex(ValueError, "index unknown/outside"):
                    self.prove(reader, window, requested)
        for field, invalid in (("row_override", -1), ("column_override", 1024), ("row_override", True), ("roundtrip_override", 3074), ("roundtrip_override", True)):
            with self.subTest(field=field, invalid=invalid):
                reader, window, table, requested, hit, calls = self.fixture()
                setattr(table.interface, field, invalid)
                with self.assertRaisesRegex(ValueError, "does not round trip"):
                    self.prove(reader, window, requested)

    def test_changed_native_index_or_projected_geometry_refuses_even_with_same_pid_and_table(self):
        reader, window, table, requested, hit, calls = self.fixture()
        hit.index = 3074
        with self.assertRaisesRegex(ValueError, "another native Table position"):
            self.prove(reader, window, requested)
        reader, window, table, requested, hit, calls = self.fixture()
        hit.box = (101, 100, 80, 20)
        with self.assertRaisesRegex(ValueError, "geometry changed"):
            self.prove(reader, window, requested)
        reader, window, table, requested, hit, calls = self.fixture()
        requested.box = (-500, 100, 80, 20)
        with self.assertRaisesRegex(ValueError, "outside actual viewport"):
            self.prove(reader, window, requested)
        self.assertEqual(calls, [])

    def test_changed_position_mapping_refuses_even_when_each_mapping_roundtrips_to_same_index(self):
        reader, window, table, requested, hit, calls = self.fixture()
        row_reads = []

        def row_at(index):
            row_reads.append(index)
            return 3 if len(row_reads) == 1 else 4

        table.interface.get_row_at_index = row_at
        table.interface.roundtrip_override = 3073
        with self.assertRaisesRegex(ValueError, "another native Table position"):
            self.prove(reader, window, requested)
        self.assertEqual(row_reads, [3073, 3073])

    def test_unsupported_role_unavailable_identity_and_wrong_chain_roots_are_refused(self):
        reader, window, table, requested, hit, calls = self.fixture()
        requested.role = "entry"
        with self.assertRaisesRegex(ValueError, "Unsupported virtual-cell role"):
            self.prove(reader, window, requested)
        reader, window, table, requested, hit, calls = self.fixture()
        requested.path = "invalid native path"
        with self.assertRaisesRegex(ValueError, "identity unknown"):
            self.prove(reader, window, requested)
        for defect in ("wrong-first", "wrong-root", "empty"):
            with self.subTest(defect=defect):
                reader, window, table, requested, hit, calls = self.fixture()
                foreign_root = NativeNode("foreign_root", "frame")

                def wrong(node, owned):
                    if defect == "empty":
                        return []
                    return [hit, table, window] if defect == "wrong-first" else [node, table, foreign_root]

                with self.assertRaisesRegex(ValueError, "another native ownership root"):
                    self.prove(reader, window, requested, ancestry_fn=wrong)

    def test_virtual_proof_does_not_mutate_frozen_41_through_43_sources_or_globals(self):
        modules = (reader41, runtime41, capability, reader42, runtime42, reader43, runtime43)
        snapshots = {module: (Path(module.__file__).read_bytes(), dict(vars(module))) for module in modules}
        old_build = copy.deepcopy(capability.BUILD)
        reader, window, table, requested, hit, calls = self.fixture()
        self.prove(reader, window, requested)
        for module, (raw, attributes) in snapshots.items():
            self.assertEqual(Path(module.__file__).read_bytes(), raw)
            self.assertEqual(dict(vars(module)), attributes)
        self.assertEqual(capability.BUILD, old_build)
        self.assertEqual(hashlib.sha256(Path(runtime43.__file__).read_bytes()).hexdigest(), "d5117086477e9ff0a1d449dc9d6886cb9bc6230d37114b5d57329c0e794b4663")

    def listener(self, inode="11"):
        return {"inode": inode, "flags": "00010000", "type": "0001", "state": "01"}

    def connection(self, inode="22"):
        return {"inode": inode, "flags": "00000000", "type": "0001", "state": "03"}

    def test_unique_owned_listener_and_owned_accepted_connections_pass_without_mutation(self):
        rows = [self.listener(), self.connection()]
        before = copy.deepcopy(rows)
        proof = evidence44.checked_listener_rows(rows, {"11", "22"})
        self.assertTrue(proof["unique_current_owned_listener_checked"])
        self.assertEqual(proof["listener"], rows[0])
        self.assertEqual(proof["owned_accepted_connections"], [rows[1]])
        proof["listener"]["inode"] = "99"
        proof["owned_accepted_connections"][0]["state"] = "04"
        self.assertEqual(rows, before)
        self.assertEqual(evidence44.checked_listener_rows([self.listener()], {"11"})["owned_accepted_connections"], [])

    def test_duplicate_or_missing_listener_foreign_inode_type_state_and_duplicate_rows_refuse(self):
        cases = [
            ([self.listener(), self.listener("33")], {"11", "33"}),
            ([self.connection()], {"22"}),
            ([self.listener()], {"22"}),
            ([self.listener(), self.connection()], {"11"}),
            ([self.listener() | {"type": "0002"}], {"11"}),
            ([self.listener() | {"state": "03"}], {"11"}),
            ([self.listener(), self.connection() | {"state": "02"}], {"11", "22"}),
            ([self.listener(), self.connection() | {"flags": "00010000"}], {"11", "22"}),
            ([self.listener(), self.connection("11")], {"11"}),
            ([self.listener() | {"inode": "invalid"}], {"invalid"}),
            ([], {"11"}),
            ([self.listener(str(index)) for index in range(65)], {str(index) for index in range(65)}),
        ]
        for rows, owned in cases:
            with self.subTest(rows=rows):
                with self.assertRaises(ValueError):
                    evidence44.checked_listener_rows(rows, owned)

    def test_v44_factory_shares_one_new_class_across_seven_roles_three_apps_and_preserves_old_sources(self):
        modules = (reader41, runtime41, capability, reader42, runtime42, reader43, runtime43)
        snapshots = {module: (Path(module.__file__).read_bytes(), dict(vars(module))) for module in modules}
        old_manifest = runtime43.source_manifest()
        old_factory = runtime43.factory(manifest=old_manifest)
        old_methods = {name: getattr(old_factory.actor_class, name) for name in ("prepare", "native_probe", "dispatch_model")}
        manifest = runtime44.source_manifest()
        factory = runtime44.factory(manifest=manifest)
        actors = []
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for role in common.ACTOR_PATHS:
                for filename in ("fixture.xlsx", "fixture.docx", "fixture.pptx"):
                    out = root / role / Path(filename).suffix[1:]
                    out.mkdir(parents=True)
                    sandbox = SimpleNamespace(sandbox_id=f"offline44-{role}-{filename}", commands=SimpleNamespace(), files=SimpleNamespace())
                    actor = factory.wrap_owned_guest(sandbox, root=root, out=out, filename=filename, lease_started_monotonic=time.monotonic())
                    actors.append(actor)
                    self.assertIs(type(actor), factory.actor_class)
                    self.assertFalse(actor.bootstrap_completed)
                    self.assertFalse(hasattr(actor, "editor_pipe"))
                    self.assertEqual(actor.native_probe.__globals__["PROBE_SCHEMA"], reader44.SCHEMA)
                    self.assertEqual(actor.native_probe.__globals__["PROBE_SOURCE"], Path(reader44.__file__))
                    self.assertTrue({"native_editor_reader_v44.py", "native_editor_evidence_v44.py", "native_virtual_cell_identity_v44.py"} <= set(actor._bootstrap.__globals__["PEERS"]))
        self.assertEqual(len(actors), 21)
        self.assertTrue(all(type(actor) is type(actors[0]) for actor in actors))
        self.assertIsNot(factory.actor_class, old_factory.actor_class)
        for name, method in old_methods.items():
            self.assertIs(getattr(old_factory.actor_class, name), method)
        for module, (raw, attributes) in snapshots.items():
            self.assertEqual(Path(module.__file__).read_bytes(), raw)
            self.assertEqual(dict(vars(module)), attributes)
        self.assertEqual(runtime43.source_manifest(), old_manifest)
        for name, source_hash in old_manifest["source_sha256s"].items():
            self.assertEqual(manifest["source_sha256s"][name], source_hash)
        self.assertIn("tests/test_native_desktop_virtual_cell_identity_v44.py", manifest["source_sha256s"])
        self.assertTrue(manifest["raw_native_flags_preserved"])
        self.assertFalse(manifest["native_qualification_passed"])
        self.assertFalse(manifest["old_results_reclassified"])
        binding = runtime44.public_binding()
        self.assertEqual(binding["source_manifest_sha256"], runtime44.parent.digest(runtime44.parent.canonical(manifest)))
        self.assertEqual(binding["actor_paths"], list(common.ACTOR_PATHS))
        self.assertFalse(binding["native_qualification_passed"])
        with self.assertRaisesRegex(ValueError, "Fresh common native qualification"):
            factory.require_activation()


if __name__ == "__main__":
    unittest.main()
