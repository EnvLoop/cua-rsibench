import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "plan_osworld_native_office_admission.py"
SPEC = importlib.util.spec_from_file_location("osworld_native_office_admission", SCRIPT)
assert SPEC and SPEC.loader
planner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(planner)


class NativeOfficeAdmissionTests(unittest.TestCase):
    def test_result_channels_do_not_consider_non_file_checks_saved_artifacts(self):
        self.assertEqual(planner.result_types({"type": "vm_command_line"}), {"vm_command_line"})
        self.assertEqual(
            planner.result_types([{"type": "vm_command_line"}, {"type": "vm_file"}]),
            {"vm_command_line", "vm_file"},
        )
        self.assertEqual(planner.result_types(None), set())
        self.assertEqual(planner.expected_types([{"type": "cloud_file"},
                                                 {"type": "rule"}]), {"cloud_file", "rule"})
        self.assertFalse(planner.postconfig_saves({"postconfig": []}))
        self.assertTrue(planner.postconfig_saves({"postconfig": [{
            "type": "execute", "parameters": {"command": ["python", "-c",
                "import pyautogui; pyautogui.hotkey('ctrl', 's')"]}}]}))

    def test_split_is_complete_stable_and_source_and_asset_name_disjoint(self):
        rows = []
        counts = {"libreoffice_calc": 46, "libreoffice_impress": 45, "libreoffice_writer": 22}
        for domain, count in counts.items():
            rows.extend(
                {
                    "id": f"{domain}-{i:03d}",
                    "domain": domain,
                    "source_group_sha256": f"source-{domain}-{i:03d}",
                    "input_asset_name_sha256s": [f"asset-{domain}-{i:03d}"],
                    "related_apps": [domain],
                }
                for i in range(count)
            )
        rows.extend(
            {
                "id": f"multi-{i:03d}",
                "domain": "multi_apps",
                "source_group_sha256": f"source-multi-{i:03d}",
                "input_asset_name_sha256s": [f"asset-multi-{i:03d}"],
                "related_apps": ["libreoffice_calc"] + (["os"] if i >= 4 else []),
            }
            for i in range(15)
        )
        # Source labels can be broad; repeated ones may appear in final but not selection.
        rows[0]["source_group_sha256"] = "broad-paper"
        rows[1]["source_group_sha256"] = "broad-paper"
        selection, final, reserve = planner.split_rows(rows)
        self.assertEqual((len(selection), len(final), len(reserve)), (20, 100, 8))
        self.assertEqual(
            {row["source_group_sha256"] for row in selection}
            & {row["source_group_sha256"] for row in final},
            set(),
        )
        self.assertEqual(
            {key for row in selection for key in row["input_asset_name_sha256s"]}
            & {key for row in final for key in row["input_asset_name_sha256s"]},
            set(),
        )
        self.assertEqual(len({row["id"] for row in selection + final + reserve}), 128)
        self.assertEqual(sum(row["domain"] == "multi_apps" for row in final), 7)
        self.assertEqual(
            [row["id"] for row in planner.split_rows(list(reversed(rows)))[1]],
            [row["id"] for row in final],
        )

    def test_shared_asset_name_excludes_task_from_selection(self):
        rows = []
        for domain, count in (("libreoffice_calc", 46), ("libreoffice_impress", 45),
                              ("libreoffice_writer", 22), ("multi_apps", 15)):
            for index in range(count):
                rows.append({"id": f"{domain}-{index:03d}", "domain": domain,
                             "source_group_sha256": f"source-{domain}-{index:03d}",
                             "input_asset_name_sha256s": [f"asset-{domain}-{index:03d}"],
                             "related_apps": [domain]})
        original, _, _ = planner.split_rows(rows)
        picked = next(row for row in original if row["domain"] == "libreoffice_calc")
        another = next(row for row in rows if row["domain"] == "libreoffice_calc"
                       and row["id"] != picked["id"])
        another["input_asset_name_sha256s"] = list(picked["input_asset_name_sha256s"])
        selection, final, _ = planner.split_rows(rows)
        self.assertNotIn(picked["id"], {row["id"] for row in selection})
        self.assertNotIn(another["id"], {row["id"] for row in selection})
        self.assertEqual(len(final), 100)

    def test_asset_family_assignment_is_transitive_and_order_independent(self):
        rows = [
            {"id": "a", "input_asset_name_sha256s": ["x"]},
            {"id": "b", "input_asset_name_sha256s": ["x", "y"]},
            {"id": "c", "input_asset_name_sha256s": ["y"]},
            {"id": "d", "input_asset_name_sha256s": ["z"]},
        ]
        planner.assign_input_asset_families(rows)
        first = {row["id"]: row["input_asset_basename_family_sha256"] for row in rows}
        self.assertEqual(len({first[key] for key in ("a", "b", "c")}), 1)
        self.assertNotEqual(first["a"], first["d"])
        self.assertEqual([row["input_asset_basename_family_size"] for row in rows],
                         [3, 3, 3, 1])
        planner.assign_input_asset_families(list(reversed(rows)))
        self.assertEqual(first, {row["id"]: row["input_asset_basename_family_sha256"]
                                 for row in rows})

    def test_pinned_index_hash_is_enforced(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evaluation_examples"
            path.mkdir()
            (path / "test_all.json").write_text('{"libreoffice_calc": []}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Unexpected OSWorld task index SHA-256"):
                planner.eligible_rows(Path(directory))

    def test_source_revision_rejects_dirty_or_different_checkout(self):
        with patch.object(planner.subprocess, "check_output",
                          side_effect=[planner.SOURCE_COMMIT + "\n", " M task.json\n"]):
            with self.assertRaisesRegex(ValueError, "modified tracked files"):
                planner.verify_source_revision(Path("/synthetic/source"))
        with patch.object(planner.subprocess, "check_output",
                          return_value="another-commit\n"):
            with self.assertRaisesRegex(ValueError, "source commit changed"):
                planner.verify_source_revision(Path("/synthetic/source"))


if __name__ == "__main__":
    unittest.main()
