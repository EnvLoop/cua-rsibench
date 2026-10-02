"""Offline bounded reopening of the exact current native Edit Mode path."""
import copy
import hashlib
from pathlib import Path
import unittest

from native_desktop_factory import native_editor_evidence_v45 as evidence
from native_desktop_factory import native_editor_evidence_v44 as old_evidence
from native_desktop_factory import native_editor_reader_v44 as old_reader
from native_desktop_factory import native_editor_runtime_v44 as old_runtime
from native_desktop_factory import native_editor_capability_v42 as capability
from tests.test_native_desktop_capability_v42 import fixture as capability_fixture


class Node:
    def __init__(self, label, pid=100):
        self.label, self.pid = label, pid
        self.children = []
        self.slot_reads = []
        self.count_reads = 0
        self.count_override = None

    def add(self, child):
        self.children.append(child)
        return child

    def get_process_id(self):
        return self.pid

    def get_child_count(self):
        self.count_reads += 1
        return len(self.children) if self.count_override is None else self.count_override

    def get_child_at_index(self, index):
        self.slot_reads.append(index)
        return self.children[index]

    def get_state_set(self):
        raise AssertionError("Path reopening must not query or mutate native state")

    def get_name(self):
        raise AssertionError("Native labels must not substitute for exact path identity")

    def clear_cache(self):
        raise AssertionError("The pure path checker must not mutate client cache")


def identity(node):
    if node is None or node.label is None:
        return {"available": False, "identity_sha256": None}
    return {"available": True, "identity_sha256": hashlib.sha256(node.label.encode()).hexdigest()}


def edge(parent, child, index=0):
    return {"parent_identity_sha256": identity(parent)["identity_sha256"],
            "child_index": index, "child_identity_sha256": identity(child)["identity_sha256"]}


class ModePathTests(unittest.TestCase):
    def tree(self):
        window = Node("owned-window")
        menu = window.add(Node("owned-menu"))
        mode = menu.add(Node("owned-edit-mode"))
        return window, menu, mode, [edge(window, menu), edge(menu, mode)]

    def test_each_exact_current_slot_is_reopened_twice_without_state_mutation(self):
        window, menu, mode, path = self.tree()
        before = copy.deepcopy(path)
        result, chain = evidence.reopen_mode_path(window, path, 100, identity)
        self.assertIs(result, mode)
        self.assertEqual(chain, [window, menu, mode])
        self.assertEqual(window.slot_reads, [0, 0])
        self.assertEqual(menu.slot_reads, [0, 0])
        self.assertEqual(window.count_reads, 2)
        self.assertEqual(menu.count_reads, 2)
        self.assertEqual(mode.slot_reads, [])
        self.assertEqual(path, before)

    def test_second_slot_identity_or_pid_change_is_refused(self):
        for defect in ("identity", "pid", "missing"):
            with self.subTest(defect=defect):
                window, menu, mode, path = self.tree()
                reads = []

                def read(index):
                    reads.append(index)
                    if len(reads) == 1:
                        return menu
                    if defect == "missing":
                        return None
                    return Node("replacement" if defect == "identity" else menu.label, pid=200 if defect == "pid" else 100)

                window.get_child_at_index = read
                with self.assertRaisesRegex(ValueError, "edge changed|process differs|identity missing"):
                    evidence.reopen_mode_path(window, path, 100, identity)
                self.assertEqual(reads, [0, 0])

    def test_parent_identity_or_pid_change_after_first_read_is_refused_before_second(self):
        for defect in ("identity", "pid"):
            with self.subTest(defect=defect):
                window, menu, mode, path = self.tree()
                reads = []

                def read(index):
                    reads.append(index)
                    if defect == "identity":
                        window.label = "changed-window"
                    else:
                        window.pid = 200
                    return menu

                window.get_child_at_index = read
                with self.assertRaisesRegex(ValueError, "edge changed|process differs"):
                    evidence.reopen_mode_path(window, path, 100, identity)
                self.assertEqual(reads, [0])

    def test_child_count_bounds_are_rechecked_before_second_slot_read(self):
        for changed_count in (0, 129, True, None):
            with self.subTest(changed_count=changed_count):
                window, menu, mode, path = self.tree()
                counts = iter([1, changed_count])
                window.get_child_count = lambda: next(counts)
                with self.assertRaisesRegex(ValueError, "second child set changed"):
                    evidence.reopen_mode_path(window, path, 100, identity)
                self.assertEqual(window.slot_reads, [0])

    def test_foreign_or_unknown_parent_and_child_identities_fail_without_label_shortcut(self):
        for target, defect in (("window", "pid"), ("menu", "pid"), ("window", "identity"), ("menu", "identity")):
            with self.subTest(target=target, defect=defect):
                window, menu, mode, path = self.tree()
                node = window if target == "window" else menu
                if defect == "pid":
                    node.pid = 200
                else:
                    node.label = None
                with self.assertRaisesRegex(ValueError, "process differs|identity missing"):
                    evidence.reopen_mode_path(window, path, 100, identity)
                if target == "window":
                    self.assertEqual(window.count_reads, 0)
                    self.assertEqual(window.slot_reads, [])
        window, menu, mode, path = self.tree()
        with self.assertRaisesRegex(ValueError, "identity missing"):
            evidence.reopen_mode_path(window, path, 100, lambda node: {"available": True, "identity_sha256": "x" * 64})

    def test_invalid_edge_shape_index_count_and_path_bound_are_refused(self):
        for index in (-1, 1, True, "0"):
            with self.subTest(index=index):
                window, menu, mode, path = self.tree()
                path[0]["child_index"] = index
                with self.assertRaisesRegex(ValueError, "parent/slot changed"):
                    evidence.reopen_mode_path(window, path, 100, identity)
                self.assertEqual(window.slot_reads, [])
        for count in (0, 129, True):
            with self.subTest(count=count):
                window, menu, mode, path = self.tree()
                window.count_override = count
                with self.assertRaisesRegex(ValueError, "parent/slot changed"):
                    evidence.reopen_mode_path(window, path, 100, identity)
        for invalid in ({"child_index": 0}, {"parent_identity_sha256": "a" * 64, "child_index": 0, "child_identity_sha256": "b" * 64, "extra": True}, None):
            with self.subTest(edge=invalid), self.assertRaisesRegex(ValueError, "edge shape invalid"):
                window, menu, mode, path = self.tree()
                evidence.reopen_mode_path(window, [invalid], 100, identity)
        for invalid_path in (None, [], "path", [{}] * 25):
            with self.subTest(path=invalid_path), self.assertRaisesRegex(ValueError, "invalid/unbounded"):
                window, menu, mode, path = self.tree()
                evidence.reopen_mode_path(window, invalid_path, 100, identity)
        for pid in (0, None, True, "100"):
            with self.subTest(pid=pid), self.assertRaisesRegex(ValueError, "invalid/unbounded"):
                window, menu, mode, path = self.tree()
                evidence.reopen_mode_path(window, path, pid, identity)

    def test_exact_24_edge_path_is_bounded_and_reopened_without_full_sibling_scan(self):
        window = Node("node-0")
        nodes = [window]
        path = []
        for index in range(1, 25):
            child = nodes[-1].add(Node(f"node-{index}"))
            path.append(edge(nodes[-1], child))
            nodes.append(child)
        result, chain = evidence.reopen_mode_path(window, path, 100, identity)
        self.assertIs(result, nodes[-1])
        self.assertEqual(chain, nodes)
        self.assertTrue(all(node.slot_reads == [0, 0] for node in nodes[:-1]))
        self.assertEqual(nodes[-1].slot_reads, [])

    def test_path_reopen_does_not_override_inherited_readonly_or_disabled_capability_checks(self):
        window, menu, mode, path = self.tree()
        evidence.reopen_mode_path(window, path, 100, identity)
        for field, where in (("checked", "edit_mode"), ("enabled", "edit_mode"), ("sensitive", "edit_mode"), ("original_medium_writable", "context")):
            with self.subTest(field=field):
                value = capability_fixture()
                value[where][field] = False
                with self.assertRaises(ValueError):
                    capability.editor_capability(**value)

    def test_path_check_preserves_old_v44_sources_globals_and_capability_build(self):
        modules = (old_evidence, old_reader, old_runtime, capability)
        snapshots = {module: (Path(module.__file__).read_bytes(), dict(vars(module))) for module in modules}
        old_build = copy.deepcopy(capability.BUILD)
        window, menu, mode, path = self.tree()
        evidence.reopen_mode_path(window, path, 100, identity)
        for module, (raw, attributes) in snapshots.items():
            self.assertEqual(Path(module.__file__).read_bytes(), raw)
            self.assertEqual(dict(vars(module)), attributes)
        self.assertEqual(capability.BUILD, old_build)


if __name__ == "__main__":
    unittest.main()
