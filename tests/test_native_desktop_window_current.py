"""Offline WINDOW/client projection with preserved strict native predicates."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest

from native_desktop_factory import native_window_current_reader as window_reader
from native_desktop_factory import native_visible_surface_probe_v31 as original
from native_desktop_factory import native_terminal_hit_diagnostic_v38 as frozen
from native_desktop_factory import native_current_inventory as inventory
from native_desktop_factory import native_business_reader as business_reader
from native_desktop_factory import business_native_runtime as business_runtime
from native_desktop_factory import current_inventory_runtime as inventory_runtime
from native_desktop_factory import terminal_owned_runtime as terminal_runtime
from native_desktop_factory import native_window_current_runtime as runtime
from native_desktop_factory import native_atspi_warning_policy_v32 as warning


FLAG_NAMES = ("VISIBLE", "SHOWING", "ENABLED", "SENSITIVE", "EDITABLE", "FOCUSED", "DEFUNCT", "STALE", "MANAGES_DESCENDANTS")
API = SimpleNamespace(CoordType=SimpleNamespace(SCREEN="SCREEN", WINDOW="WINDOW"), StateType=SimpleNamespace(**{name: name for name in FLAG_NAMES}))
CLIENT = {"WINDOW": 123, "X": 0, "Y": 51, "WIDTH": 400, "HEIGHT": 249}


class Node:
    def __init__(self, role="panel", *, box=(0, 0, 400, 249), pid=100, flags=None):
        self.role, self.box, self.pid = role, box, pid
        self.flags = set(flags if flags is not None else ["VISIBLE", "SHOWING", "ENABLED", "SENSITIVE"])
        self.parent = None
        self.index = 0
        self.children = []
        self.hit = None
        self.point_queries = []
        self.extent_queries = []
        self.screen_override = None

    def add(self, node):
        node.parent = self
        node.index = len(self.children)
        self.children.append(node)
        return node

    def get_process_id(self):
        return self.pid

    def get_state_set(self):
        return SimpleNamespace(contains=lambda flag: flag in self.flags)

    def get_role_name(self):
        return self.role

    def get_child_count(self):
        return len(self.children)

    def get_index_in_parent(self):
        return self.index

    def get_parent(self):
        return self.parent

    def get_name(self):
        raise AssertionError("Document/cell values must not be queried")

    def get_collection_iface(self):
        raise AssertionError("Recursive Collection must not be queried")

    def get_component_iface(self):
        def extents(mode):
            self.extent_queries.append(mode)
            x, y, width, height = self.box
            if mode == API.CoordType.SCREEN:
                result = self.screen_override or (x + CLIENT["X"], y + CLIENT["Y"], width, height)
            elif mode == API.CoordType.WINDOW:
                result = self.box
            else:
                raise AssertionError("Unexpected native coordinate mode")
            return SimpleNamespace(**dict(zip(("x", "y", "width", "height"), result)))

        def point(x, y, mode):
            self.point_queries.append((x, y, mode))
            return self.hit

        return SimpleNamespace(get_extents=extents, get_accessible_at_point=point)


def ancestry(node, window):
    chain = []
    for _ in range(32):
        if node is None:
            raise ValueError("Synthetic foreign ancestry")
        chain.append(node)
        if node is window:
            return chain
        node = node.parent
    raise ValueError("Synthetic ancestry depth cap")


def scoped():
    reader = SimpleNamespace(**{**vars(original), "namespace": dict(original.namespace)})
    return window_reader.install_coordinate_scope(reader, {"client": dict(CLIENT)})


def physical(reader, window, point=(52, 170)):
    return reader.physical_hit(API, window, point, pid=100, viewport=[400, 300], ancestry=ancestry)


def editable(reader, node, window):
    return window_reader.editable_record(reader, API, node, window, pid=100, uid=1000, viewport=[400, 300], ancestry=ancestry)


class WindowCurrentTests(unittest.TestCase):
    def leaf(self):
        window = Node("frame")
        leaf = window.add(Node("text", box=(0, 100, 100, 38), flags=["VISIBLE", "SHOWING", "ENABLED", "SENSITIVE", "EDITABLE", "FOCUSED"]))
        window.hit = leaf
        leaf.hit = leaf
        return window, leaf

    def test_original_screen_pixels_use_explicit_window_query_with_client_origin(self):
        reader = scoped()
        window, leaf = self.leaf()
        source_point = [52, 170]
        hit, depth = physical(reader, window, source_point)
        self.assertIs(hit, leaf)
        self.assertEqual(depth, 2)
        self.assertEqual(source_point, [52, 170])
        self.assertEqual(window.point_queries, [(52, 119, API.CoordType.WINDOW)])
        self.assertEqual(leaf.point_queries, [(52, 119, API.CoordType.WINDOW)])
        self.assertTrue(all(mode == API.CoordType.WINDOW for mode in window.extent_queries + leaf.extent_queries))
        self.assertEqual(reader.geometry(API, leaf, [400, 300]), [0, 151, 100, 38])

    def test_foreign_stale_managed_and_nonzero_child_terminals_remain_refused(self):
        for defect in ("foreign", "stale", "managed", "children"):
            with self.subTest(defect=defect):
                reader = scoped()
                window, leaf = self.leaf()
                if defect == "foreign":
                    leaf.pid = 200
                    error = "ownership changed"
                elif defect == "stale":
                    leaf.flags.add("STALE")
                    error = "state unavailable or unsafe"
                elif defect == "managed":
                    leaf.flags.add("MANAGES_DESCENDANTS")
                    error = "deferred point hit unavailable"
                else:
                    leaf.add(Node("text"))
                    error = "not a proved leaf"
                with self.assertRaisesRegex(ValueError, error):
                    physical(reader, window)
                if defect in ("foreign", "stale"):
                    self.assertEqual(leaf.point_queries, [])
        window = Node("frame")
        with self.assertRaisesRegex(ValueError, "root point hit unavailable"):
            physical(scoped(), window)

    def test_actual_focused_editable_container_needs_owned_center_leaf_for_keyboard(self):
        reader = scoped()
        window = Node("frame")
        container = window.add(Node("text", box=(20, 80, 100, 60), flags=["VISIBLE", "SHOWING", "ENABLED", "SENSITIVE", "EDITABLE", "FOCUSED"]))
        leaf = container.add(Node("text", box=(20, 80, 100, 60)))
        window.hit = container
        container.hit = leaf
        leaf.hit = leaf
        record, fact = editable(reader, container, window)
        self.assertTrue(record["enabled"])
        self.assertTrue(record["keyboard"])
        self.assertFalse(record["obscured"])
        self.assertIn("key", record["actions"])
        self.assertTrue(fact["native_flags"]["FOCUSED"])
        self.assertTrue(fact["point_hit_ownership_checked"])
        self.assertEqual(window.point_queries, [(70, 110, API.CoordType.WINDOW)])
        self.assertEqual(container.point_queries, window.point_queries)
        self.assertEqual(leaf.point_queries, window.point_queries)

    def test_failed_nonleaf_center_is_disabled_inventory_without_actor_hit_waiver(self):
        reader = scoped()
        window = Node("frame")
        container = window.add(Node("text", box=(20, 80, 100, 60), flags=["VISIBLE", "SHOWING", "ENABLED", "SENSITIVE", "EDITABLE", "FOCUSED"]))
        container.add(Node("text"))
        window.hit = container
        container.hit = container
        record, fact = editable(reader, container, window)
        self.assertFalse(record["enabled"])
        self.assertFalse(record["keyboard"])
        self.assertTrue(record["obscured"])
        self.assertEqual(record["actions"], [])
        self.assertTrue(fact["structural_inventory_only"])
        self.assertFalse(fact["native_actions_authorized"])
        with self.assertRaisesRegex(ValueError, "not a proved leaf"):
            physical(reader, window, [70, 161])

    def test_foreign_center_hit_cannot_fall_back_to_an_admitted_editable_target(self):
        reader = scoped()
        window, leaf = self.leaf()
        foreign = Node("text", box=(0, 100, 100, 38), pid=200)
        leaf.hit = foreign
        with self.assertRaisesRegex(ValueError, "ownership changed"):
            editable(reader, leaf, window)

    def test_noneditable_structural_container_stays_nonactionable(self):
        reader = scoped()
        window = Node("frame")
        container = window.add(Node("panel"))
        container.add(Node("text"))
        record, fact = editable(reader, container, window)
        self.assertEqual(record["actions"], [])
        self.assertFalse(record["enabled"])
        self.assertFalse(record["keyboard"])
        self.assertTrue(fact["structural_inventory_only"])
        self.assertEqual(window.point_queries, [])

    def test_root_projection_requires_exact_native_screen_window_matrix(self):
        window = Node("frame")
        proof = window_reader.root_projection(original, API, window, dict(CLIENT))
        self.assertEqual(proof["coordinate_api"], "WINDOW")
        self.assertFalse(proof["physical_pixels_retargeted"])
        self.assertTrue(proof["native_root_projection_equal"])
        self.assertEqual(proof["native_root_screen_extents"], [0, 51, 400, 249])
        self.assertEqual(proof["native_root_window_extents"], [0, 0, 400, 249])
        for screen in ((0, 0, 400, 249), (0, 51, 401, 249), (1, 51, 400, 249)):
            with self.subTest(screen=screen):
                window.screen_override = screen
                with self.assertRaisesRegex(ValueError, "mapping differs"):
                    window_reader.root_projection(original, API, window, dict(CLIENT))
        window.screen_override = None
        with self.assertRaisesRegex(ValueError, "mapping differs"):
            window_reader.root_projection(original, API, window, CLIENT | {"HEIGHT": 0})

    def test_xwininfo_absolute_client_origin_is_bound_to_exact_owned_window(self):
        raw = "xwininfo: Window id: 0x7b\n  Absolute upper-left X: 0\n  Absolute upper-left Y: 51\n  Width: 400\n  Height: 249\n"
        calls = []
        frozen_api = SimpleNamespace(command=lambda command: calls.append(command) or raw)
        client = window_reader.absolute_client_geometry(frozen_api, {"window_id": "123"})
        self.assertEqual(calls, [["xwininfo", "-id", "123"]])
        self.assertEqual({key: client[key] for key in CLIENT}, CLIENT)
        self.assertEqual(client["source"], "xwininfo_absolute_client_origin")
        self.assertEqual(client["actual_raw_metadata_sha256"], hashlib.sha256(raw.encode()).hexdigest())
        with self.assertRaisesRegex(ValueError, "queried client window differs"):
            window_reader.absolute_client_geometry(frozen_api, {"window_id": "124"})

    def test_scoped_construction_keeps_old_reader_bytes_globals_and_namespace_methods(self):
        modules = (original, frozen, inventory, business_reader, business_runtime, inventory_runtime, terminal_runtime)
        snapshots = {module: (Path(module.__file__).read_bytes(), dict(vars(module))) for module in modules}
        old_namespace = dict(original.namespace)
        reader = scoped()
        self.assertIsNot(reader.physical_hit, original.physical_hit)
        self.assertIsNot(reader.native_record, original.native_record)
        self.assertIsNot(reader.namespace, original.namespace)
        run, main = window_reader.scoped_reader()
        self.assertTrue(callable(run))
        self.assertTrue(callable(main))
        for module, (raw, values) in snapshots.items():
            self.assertEqual(Path(module.__file__).read_bytes(), raw)
            self.assertEqual(dict(vars(module)), values)
        self.assertEqual(original.namespace, old_namespace)
        self.assertEqual(hashlib.sha256(Path(business_reader.__file__).read_bytes()).hexdigest(), window_reader.BASE_SHA)
        self.assertEqual(hashlib.sha256(Path(frozen.__file__).read_bytes()).hexdigest(), inventory.V38_SHA)

    def test_runtime_constructor_uses_one_fresh_class_for_all_apps_without_provider_calls(self):
        manifest = runtime.source_manifest()
        old = business_runtime.source_manifest()
        old_factory = business_runtime.factory(manifest=old)
        old_probe = old_factory.actor_class.native_probe
        old_warning_files = warning.FILES
        factory = runtime.factory(manifest=manifest)
        actors = []
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for index, filename in enumerate(("fixture.xlsx", "fixture.docx", "fixture.pptx")):
                out = root / f"fixture-{index}" / "actor"
                out.mkdir(parents=True)
                # No methods capable of remote commands, files, or GUI input.
                sandbox = SimpleNamespace(sandbox_id=f"offline-window-{index}", commands=SimpleNamespace(), files=SimpleNamespace())
                actor = factory.wrap_owned_guest(sandbox, root=root, out=out, filename=filename, lease_started_monotonic=time.monotonic())
                actors.append(actor)
                self.assertIs(actor.__class__, factory.actor_class)
                self.assertEqual(actor.native_manifest, manifest)
                self.assertFalse(actor.bootstrap_completed)
                self.assertEqual(actor.native_probe.__globals__["PROBE_SCHEMA"], window_reader.SCHEMA)
                self.assertEqual(actor.native_probe.__globals__["PROBE_SOURCE"], Path(window_reader.__file__))
                self.assertIn("native_window_current_reader.py", actor._bootstrap.__globals__["PEERS"])
                self.assertIn("native_client_coordinate_probe.py", actor._bootstrap.__globals__["PEERS"])
        self.assertTrue(all(type(actor) is type(actors[0]) for actor in actors))
        self.assertIsNot(factory.actor_class, old_factory.actor_class)
        self.assertIs(old_factory.actor_class.native_probe, old_probe)
        self.assertIs(warning.FILES, old_warning_files)
        self.assertNotIn("native_window_current_reader.py", warning.FILES)
        with self.assertRaisesRegex(ValueError, "Fresh common native qualification"):
            factory.require_activation()

    def test_manifest_and_public_binding_keep_old_sources_and_no_qualification_credit(self):
        manifest = runtime.source_manifest()
        old = business_runtime.source_manifest()
        for name, source_hash in old["source_sha256s"].items():
            self.assertEqual(manifest["source_sha256s"][name], source_hash)
        self.assertEqual(set(manifest["source_sha256s"]) - set(old["source_sha256s"]), set(runtime.EXTRA) - set(old["source_sha256s"]))
        self.assertEqual(manifest["native_reader_schema"], window_reader.SCHEMA)
        self.assertEqual(manifest["native_coordinate_api"], "WINDOW_plus_verified_absolute_X11_client_origin")
        self.assertTrue(manifest["editable_container_requires_original_native_record"])
        self.assertFalse(manifest["physical_pixels_retargeted"])
        self.assertFalse(manifest["old_results_reclassified"])
        self.assertFalse(manifest["native_qualification_passed"])
        binding = runtime.public_binding()
        self.assertEqual(binding["source_manifest_sha256"], runtime.base.current.base.parent.digest(runtime.base.current.base.parent.canonical(manifest)))
        self.assertEqual(binding["actor_paths"], manifest["actor_paths"])
        self.assertEqual(binding["app_kinds"], ["calc", "writer", "impress"])
        self.assertFalse(binding["native_qualification_passed"])
        self.assertFalse(binding["old_results_reclassified"])
        self.assertFalse(binding["provider_dispatch_performed"])
        self.assertEqual((binding["model_calls"], binding["tinker_calls"]), (0, 0))

    def test_source_and_public_binding_cli_return_only_offline_json(self):
        root = Path(runtime.__file__).resolve().parents[1]
        for mode, expected in (("source", runtime.source_manifest(root)), ("public-binding", runtime.public_binding(root))):
            with self.subTest(mode=mode):
                result = subprocess.run(
                    [sys.executable, "-m", "native_desktop_factory.native_window_current_runtime", mode, "--root", str(root)],
                    cwd=root, capture_output=True, text=True, timeout=15,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, "")
                self.assertEqual(json.loads(result.stdout), expected)


if __name__ == "__main__":
    unittest.main()
