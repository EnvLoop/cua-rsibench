"""Synthetic API and tree tests for the additive current inventory adapter."""
import hashlib
from pathlib import Path
from types import FunctionType, SimpleNamespace
import unittest

from native_desktop_factory import native_current_inventory as current
from native_desktop_factory import native_terminal_hit_diagnostic_v38 as frozen
from native_desktop_factory import native_visible_surface_probe_v30 as traversal
from native_desktop_factory import native_visible_surface_probe_v31 as reader
from tests.test_native_desktop_visible_surface_probe_v30 import API, Node, ancestry


class CacheObject:
    def __init__(self, calls, name, *, pid=100, bus="owned-bus", available=True):
        self.calls = calls
        self.name = name
        self.pid = pid
        self.bus = bus
        self.available = available
        self.application = None
        self.active = True

    def get_process_id(self):
        self.calls.append((self.name, "pid"))
        return self.pid

    def get_application(self):
        self.calls.append((self.name, "application"))
        return self.application

    def set_cache_mask(self, mask):
        self.calls.append((self.name, "set_cache_mask", mask))

    def clear_cache(self):
        self.calls.append((self.name, "clear_cache"))

    def get_state_set(self):
        self.calls.append((self.name, "fresh_state"))
        return SimpleNamespace(contains=lambda flag: self.active and flag == "ACTIVE")

    def get_name(self):
        raise AssertionError("Cache control must not query document names or values")


def cache_identity(node):
    if node is None:
        return {"available": False}
    node.calls.append((node.name, "identity"))
    return {
        "available": node.available,
        "bus_name_sha256": node.bus,
        "identity_sha256": "identity-" + node.name,
    }


class InventoryNode(Node):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.child_indices = []

    def get_child_at_index(self, index):
        self.child_indices.append(index)
        return super().get_child_at_index(index)


def inventory_function(*, breadth_first, maximum):
    namespace = {
        **vars(traversal),
        "MAX_NODES": maximum,
        "native_record": lambda *args, **kwargs: frozen.structural_record(reader, *args, **kwargs),
    }
    if breadth_first:
        source = current.breadth_first_source(traversal.bounded_surface)
        exec(compile(source, current.__file__, "exec"), namespace)
        return namespace["bounded_surface"]
    return FunctionType(traversal.bounded_surface.__code__, namespace)


def surface(function, window):
    return function(API, window, pid=100, uid=1000, viewport=[400, 300], ancestry=ancestry)


class CurrentInventoryTests(unittest.TestCase):
    def cache_fixture(self):
        calls = []
        application = CacheObject(calls, "application")
        window = CacheObject(calls, "window")
        window.application = application
        api = SimpleNamespace(Cache=SimpleNamespace(NONE="CACHE_NONE"), StateType=SimpleNamespace(ACTIVE="ACTIVE"))
        return calls, application, window, api

    def test_owned_cache_none_follows_pid_and_bus_proof_then_rechecks_active(self):
        calls, application, window, api = self.cache_fixture()
        proof = current.cache_owned_application(reader, api, window, pid=100, identity=cache_identity)
        mask = calls.index(("application", "set_cache_mask", "CACHE_NONE"))
        self.assertLess(calls.index(("application", "identity")), mask)
        self.assertLess(calls.index(("window", "identity")), mask)
        self.assertLess(calls.index(("application", "pid")), mask)
        self.assertLess(calls.index(("window", "pid")), mask)
        self.assertEqual(calls[mask:], [
            ("application", "set_cache_mask", "CACHE_NONE"),
            ("window", "clear_cache"), ("window", "fresh_state"),
        ])
        self.assertTrue(proof["same_native_process_and_bus_checked"])
        self.assertTrue(proof["window_client_cache_cleared"])
        self.assertEqual(proof["cache_mask"], "NONE")
        self.assertEqual(proof["native_mutations"], 0)
        self.assertEqual(proof["application_identity_sha256"], "identity-application")
        self.assertEqual(proof["window_identity_sha256"], "identity-window")

    def test_foreign_process_bus_and_unavailable_identity_reject_before_cache_operation(self):
        for defect in ("window-pid", "application-pid", "foreign-bus", "application-identity", "window-identity", "missing-application"):
            with self.subTest(defect=defect):
                calls, application, window, api = self.cache_fixture()
                if defect == "window-pid":
                    window.pid = 200
                elif defect == "application-pid":
                    application.pid = 200
                elif defect == "foreign-bus":
                    application.bus = "foreign-bus"
                elif defect == "application-identity":
                    application.available = False
                elif defect == "window-identity":
                    window.available = False
                else:
                    window.application = None
                with self.assertRaisesRegex(ValueError, "process differs|bus differs"):
                    current.cache_owned_application(reader, api, window, pid=100, identity=cache_identity)
                self.assertFalse(any(row[1] in ("set_cache_mask", "clear_cache", "fresh_state") for row in calls))

    def test_cache_clear_cannot_admit_window_without_fresh_actual_active_state(self):
        calls, application, window, api = self.cache_fixture()
        window.active = False
        with self.assertRaisesRegex(ValueError, "no longer active"):
            current.cache_owned_application(reader, api, window, pid=100, identity=cache_identity)
        self.assertEqual(calls[-3:], [
            ("application", "set_cache_mask", "CACHE_NONE"),
            ("window", "clear_cache"), ("window", "fresh_state"),
        ])

    def test_late_owned_visible_editable_leaf_is_reached_before_dominant_subtree(self):
        def tree():
            window = InventoryNode("frame")
            branch = window.add(InventoryNode("panel"))
            for _ in range(12):
                branch = branch.add(InventoryNode("panel"))
            leaf = window.add(InventoryNode("text", flags=["VISIBLE", "SHOWING", "ENABLED", "SENSITIVE", "EDITABLE", "FOCUSED"]))
            window.hit = leaf
            return window, leaf

        old_window, old_leaf = tree()
        with self.assertRaisesRegex(ValueError, "node cap"):
            surface(inventory_function(breadth_first=False, maximum=6), old_window)
        self.assertEqual(old_leaf.child_reads, 0)
        window, leaf = tree()
        targets, facts, branches, focus = surface(inventory_function(breadth_first=True, maximum=6), window)
        pairs = list(zip(targets, facts))
        editable = [(target, fact) for target, fact in pairs if target["keyboard"]]
        self.assertEqual(len(editable), 1)
        self.assertEqual(editable[0][1]["role"], "text")
        self.assertTrue(editable[0][0]["enabled"])
        self.assertFalse(editable[0][0]["obscured"])
        self.assertTrue(editable[0][1]["point_hit_ownership_checked"])
        self.assertEqual(focus[0]["ref"], editable[0][0]["ref"])
        self.assertEqual([row["role"] for row in branches[:3]], ["frame", "panel", "text"])
        self.assertLessEqual(len(branches), 6)
        self.assertTrue(any(row.get("reason") == "native_frontier_budget_cap" for row in branches))
        self.assertGreater(leaf.child_reads, 0)
        for target, fact in pairs:
            if fact["role"] != "text":
                self.assertFalse(target["enabled"])
                self.assertFalse(target["keyboard"])
                self.assertEqual(target["actions"], [])

    def test_frontier_cap_defers_unread_children_without_promoting_structural_targets(self):
        window = InventoryNode("frame")
        for _ in range(8):
            window.add(InventoryNode("panel"))
        # A deferred branch's content/state cannot become an admitted target.
        window.children[-1].pid = 200
        window.children[-1].flags.add("STALE")
        window.children[-1].forbid_children = True
        targets, facts, branches, focus = surface(inventory_function(breadth_first=True, maximum=4), window)
        self.assertEqual(window.child_indices, [0, 1, 2])
        self.assertEqual(len(branches), 4)
        self.assertTrue(branches[0]["deferred"])
        self.assertEqual(branches[0]["reason"], "native_frontier_budget_cap")
        self.assertEqual(branches[0]["remaining_child_count"], 5)
        self.assertIsNone(focus)
        self.assertTrue(all(not target["enabled"] and not target["keyboard"] and target["actions"] == [] for target in targets))
        self.assertTrue(all(fact["native_pid"] == 100 for fact in facts))
        self.assertEqual(window.children[-1].child_reads, 0)

    def test_breadth_first_inventory_keeps_foreign_and_stale_branch_refusal(self):
        for defect in ("foreign", "stale"):
            with self.subTest(defect=defect):
                window = InventoryNode("frame")
                child = window.add(InventoryNode("panel"))
                if defect == "foreign":
                    child.pid = 200
                else:
                    child.flags.add("STALE")
                with self.assertRaisesRegex(ValueError, "ownership changed|stale or defunct"):
                    surface(inventory_function(breadth_first=True, maximum=4), window)

    def test_breadth_first_still_prunes_hidden_and_offscreen_before_child_reads(self):
        window = InventoryNode("frame")
        hidden = window.add(InventoryNode("panel", flags=["VISIBLE"]))
        offscreen = window.add(InventoryNode("panel", box=(-100, 0, 20, 20)))
        hidden.forbid_children = offscreen.forbid_children = True
        targets, facts, branches, focus = surface(inventory_function(breadth_first=True, maximum=4), window)
        self.assertEqual([row.get("pruned") for row in branches[1:]], ["native_hidden", "native_offscreen"])
        self.assertEqual(hidden.child_reads, 0)
        self.assertEqual(offscreen.child_reads, 0)
        self.assertIsNone(focus)

    def test_scoped_construction_preserves_frozen_v38_source_and_globals(self):
        source = Path(frozen.__file__)
        raw = source.read_bytes()
        globals_before = dict(vars(frozen))
        traversal_before = dict(vars(traversal))
        self.assertEqual(hashlib.sha256(raw).hexdigest(), current.V38_SHA)
        base = current.load_base()
        run, main = current.scoped_reader()
        self.assertTrue(callable(run))
        self.assertTrue(callable(main))
        self.assertIsNot(base, frozen)
        self.assertIsNot(base.guarded_run, frozen.guarded_run)
        self.assertEqual(source.read_bytes(), raw)
        self.assertEqual(dict(vars(frozen)), globals_before)
        self.assertEqual(dict(vars(traversal)), traversal_before)

    def test_unrecognized_traversal_source_is_rejected(self):
        def changed_traversal(*args, **kwargs):
            return [], [], [], None

        with self.assertRaisesRegex(ValueError, "traversal source changed"):
            current.breadth_first_source(changed_traversal)


if __name__ == "__main__":
    unittest.main()
