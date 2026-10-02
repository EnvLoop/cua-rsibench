"""Offline native coordinate facts never grant actor-action permission."""
from types import ModuleType, SimpleNamespace
import sys
import unittest
from unittest.mock import patch

from native_desktop_factory import native_coordinate_probe as probe


FLAGS = ("VISIBLE", "SHOWING", "ENABLED", "SENSITIVE", "EDITABLE", "FOCUSED", "DEFUNCT", "STALE", "MANAGES_DESCENDANTS")
API = SimpleNamespace(
    CoordType=SimpleNamespace(SCREEN="screen-coordinate", WINDOW="window-coordinate"),
    StateType=SimpleNamespace(**{name: name for name in FLAGS}),
)


class Node:
    def __init__(self, label, *, pid=100, flags=None):
        self.label = label
        self.pid = pid
        self.flags = set(flags if flags is not None else ["VISIBLE", "SHOWING", "ENABLED", "SENSITIVE"])
        self.parent = None
        self.children = []
        self.hit = None
        self.point_queries = []
        self.extent_queries = []

    def add(self, node):
        self.children.append(node)
        node.parent = self
        return node

    def get_process_id(self):
        return self.pid

    def get_state_set(self):
        return SimpleNamespace(contains=lambda name: name in self.flags)

    def get_role_name(self):
        return "frame" if self.parent is None else "text"

    def get_child_count(self):
        return len(self.children)

    def get_component_iface(self):
        def extents(mode):
            self.extent_queries.append(mode)
            if mode == API.CoordType.SCREEN:
                return SimpleNamespace(x=20, y=40, width=1280, height=800)
            if mode == API.CoordType.WINDOW:
                return SimpleNamespace(x=0, y=0, width=1280, height=800)
            raise AssertionError("Unknown coordinate mode")

        def point(x, y, mode):
            self.point_queries.append((x, y, mode))
            return self.hit

        return SimpleNamespace(get_extents=extents, get_accessible_at_point=point)

    def get_child_at_index(self, index):
        raise AssertionError("Coordinate diagnostic must not enumerate child subtrees")

    def get_collection_iface(self):
        raise AssertionError("Coordinate diagnostic must not call recursive Collection")

    def get_name(self):
        raise AssertionError("Point chains must not query document values")


def identity(node):
    return {"available": True, "identity_sha256": node.label} if node is not None else {"available": False, "identity_sha256": None}


def ancestry(node, window):
    chain = []
    while node is not None and len(chain) < 32:
        chain.append(node)
        if node is window:
            return chain
        node = node.parent
    raise ValueError("Synthetic native ancestry unavailable")


def chain(window, point=(52, 170), mode=API.CoordType.SCREEN):
    return probe.point_chain(API, window, point, mode, pid=100, identity=identity, ancestry=ancestry)


class CoordinateProbeTests(unittest.TestCase):
    def leaf(self):
        window = Node("owned-window")
        leaf = window.add(Node("owned-leaf", flags=["VISIBLE", "SHOWING", "ENABLED", "SENSITIVE", "EDITABLE", "FOCUSED"]))
        window.hit = leaf
        leaf.hit = leaf
        return window, leaf

    def test_each_explicit_coordinate_mode_preserves_exact_point_and_both_extents(self):
        for mode, coordinates in ((API.CoordType.SCREEN, [52, 170]), (API.CoordType.WINDOW, [32, 130])):
            with self.subTest(mode=mode):
                window, leaf = self.leaf()
                value = chain(window, coordinates, mode)
                self.assertEqual(window.point_queries, [(*coordinates, mode)])
                self.assertEqual(leaf.point_queries, [(*coordinates, mode)])
                self.assertEqual(window.extent_queries, [API.CoordType.SCREEN, API.CoordType.WINDOW])
                self.assertEqual(leaf.extent_queries, [API.CoordType.SCREEN, API.CoordType.WINDOW])
                self.assertEqual(value["rows"][1]["extents"], {"SCREEN": [20, 40, 1280, 800], "WINDOW": [0, 0, 1280, 800]})
                self.assertEqual(value["terminal_kind"], "same_native_identity")
                self.assertTrue(value["strict_leaf_shape_observed"])
                self.assertFalse(value["native_actions_authorized"])
                self.assertFalse(value["original_point_verdict_changed"])

    def test_foreign_and_stale_root_or_descendant_refuse_before_that_objects_point_query(self):
        for target in ("root", "descendant"):
            for defect in ("foreign", "stale", "hidden", "defunct"):
                with self.subTest(target=target, defect=defect):
                    window, leaf = self.leaf()
                    unsafe = window if target == "root" else leaf
                    if defect == "foreign":
                        unsafe.pid = 200
                    elif defect == "hidden":
                        unsafe.flags.remove("SHOWING")
                    else:
                        unsafe.flags.add(defect.upper())
                    with self.assertRaisesRegex(ValueError, "ownership changed|state unsafe"):
                        chain(window)
                    self.assertEqual(unsafe.point_queries, [])
                    self.assertEqual(unsafe.extent_queries, [])
                    self.assertEqual(len(window.point_queries), 0 if target == "root" else 1)

    def test_nonleaf_root_miss_and_managed_terminal_cannot_authorize_an_action(self):
        for defect in ("nonleaf", "root-miss", "managed"):
            with self.subTest(defect=defect):
                window, leaf = self.leaf()
                if defect == "nonleaf":
                    leaf.add(Node("unqueried-child"))
                elif defect == "managed":
                    leaf.flags.add("MANAGES_DESCENDANTS")
                else:
                    window.hit = None
                value = chain(window)
                self.assertFalse(value["strict_leaf_shape_observed"])
                self.assertFalse(value["native_actions_authorized"])
                self.assertFalse(value["original_point_verdict_changed"])
                if defect == "nonleaf":
                    self.assertEqual(value["rows"][-1]["actual_child_count"], 1)
                    self.assertEqual(value["terminal_kind"], "same_native_identity")

    def test_32_node_cap_retains_raw_chain_and_never_promotes_unknown_terminal(self):
        window = Node("node-0")
        nodes = [window]
        for index in range(1, 36):
            child = nodes[-1].add(Node(f"node-{index}"))
            nodes[-1].hit = child
            nodes.append(child)
        value = chain(window)
        self.assertEqual(value["terminal_kind"], "native_depth_cap")
        self.assertEqual(len(value["rows"]), 32)
        self.assertEqual([row["depth"] for row in value["rows"]], list(range(32)))
        self.assertTrue(all(len(node.point_queries) == 1 for node in nodes[:32]))
        self.assertTrue(all(node.point_queries == [] for node in nodes[32:]))
        self.assertFalse(value["strict_leaf_shape_observed"])
        self.assertFalse(value["native_actions_authorized"])

    def test_identity_cycle_is_refused_before_a_repeated_point_query(self):
        window, leaf = self.leaf()
        leaf.hit = window
        with self.assertRaisesRegex(ValueError, "identity unavailable or cycle"):
            chain(window)
        self.assertEqual(len(window.point_queries), 1)
        self.assertEqual(len(leaf.point_queries), 1)

    def test_actual_x11_client_geometry_is_checked_without_default_origin(self):
        calls = []
        good = "WINDOW=123\nX=20\nY=40\nWIDTH=1280\nHEIGHT=800\nSCREEN=0"
        frozen = SimpleNamespace(command=lambda command: calls.append(command) or good)
        self.assertEqual(probe.x11_geometry(frozen, {"window_id": "123"}), {"WINDOW": 123, "X": 20, "Y": 40, "WIDTH": 1280, "HEIGHT": 800, "SCREEN": 0})
        self.assertEqual(calls, [["xdotool", "getwindowgeometry", "--shell", "123"]])
        for raw in (good.replace("WINDOW=123", "WINDOW=456"), good.replace("X=20\n", ""), good.replace("WIDTH=1280", "WIDTH=0")):
            with self.subTest(raw=raw), self.assertRaisesRegex(ValueError, "geometry unavailable"):
                probe.x11_geometry(SimpleNamespace(command=lambda command, raw=raw: raw), {"window_id": "123"})

    def test_run_reports_both_explicit_modes_from_actual_client_origin_without_action_credit(self):
        window, leaf = self.leaf()
        x11 = {"window_id": "123", "pid": 100, "uid": 1000, "probe_uid": 1000, "title": "fixture.xlsx - LibreOffice Calc", "wm_class": 'WM_CLASS(STRING) = "libreoffice", "libreoffice-calc"'}
        geometry_queries, owned_calls, cache_calls = [], [], []
        geometry = "WINDOW=123\nX=20\nY=40\nWIDTH=1280\nHEIGHT=800\nSCREEN=0"
        frozen = SimpleNamespace(command=lambda command: geometry_queries.append(command) or geometry, x11=lambda: dict(x11))
        original_owner = SimpleNamespace(load=lambda: frozen)

        def owned_window(owner, filename):
            owned_calls.append(filename)
            self.assertIs(owner.load, original_owner.load)
            self.assertIs(owner.ownership, probe.business.ownership)
            self.assertTrue(owner.ownership(x11, filename, executable_reader=lambda pid: (probe.business.EXE_PATH, probe.business.EXE_SHA)))
            return frozen, dict(x11), SimpleNamespace(value=window)

        old = SimpleNamespace(owner_module=lambda: original_owner, owned_window=owned_window)
        reader = SimpleNamespace(namespace={"peer": lambda: old})

        def load(name, expected):
            if name == "native_visible_surface_probe_v31.py":
                self.assertEqual(expected, "pinned-v31")
                return reader
            self.assertEqual((name, expected), ("native_hit_identity_diagnostic_v33.py", "pinned-v33"))
            return SimpleNamespace(identity=identity)

        peer = SimpleNamespace(load=load, V31_SHA="pinned-v31", V33_SHA="pinned-v33")

        class Resolver:
            def __init__(self, actual_window, pid, actual_identity):
                self.proofs = []
                self.assertions = (actual_window is window, pid == 100, actual_identity is identity)
                if not all(self.assertions):
                    raise AssertionError("Synthetic owned resolver binding changed")

            def ancestors(self, node, owned):
                return ancestry(node, owned)

        base = SimpleNamespace(load=lambda: peer, forward_owned_paths=lambda actual_peer, writer: Resolver)
        current = SimpleNamespace(
            load_base=lambda: base,
            cache_owned_application=lambda *args, **kwargs: cache_calls.append((args, kwargs)) or {"native_mutations": 0},
        )
        gi = ModuleType("gi")
        repository = ModuleType("gi.repository")
        repository.Atspi = API
        gi.repository = repository
        with patch.object(probe.business, "load_current", return_value=current), patch.dict(sys.modules, {"gi": gi, "gi.repository": repository}):
            value = probe.run(filename="fixture.xlsx", points=[[52, 170]])
        self.assertEqual(owned_calls, ["fixture.xlsx"])
        self.assertEqual(len(cache_calls), 1)
        self.assertEqual(len(geometry_queries), 2)
        self.assertEqual(window.point_queries, [(52, 170, API.CoordType.SCREEN), (32, 130, API.CoordType.WINDOW)])
        self.assertEqual(leaf.point_queries, window.point_queries)
        self.assertEqual(value["facts"][0]["original_screen_point"], [52, 170])
        self.assertEqual(value["facts"][0]["x11_client_relative_point"], [32, 130])
        self.assertEqual(set(value["facts"][0]), {"original_screen_point", "x11_client_relative_point", "SCREEN", "WINDOW"})
        self.assertFalse(value["native_actions_authorized"])
        self.assertFalse(value["native_qualification_passed"])
        self.assertEqual((value["native_mutations"], value["actor_actions"], value["model_calls"]), (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
