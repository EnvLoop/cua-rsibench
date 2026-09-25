import importlib.util
import tempfile
import unittest
from pathlib import Path


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

    def test_split_is_complete_stable_and_exact_source_string_disjoint(self):
        rows = []
        counts = {"libreoffice_calc": 46, "libreoffice_impress": 45, "libreoffice_writer": 22}
        for domain, count in counts.items():
            rows.extend(
                {
                    "id": f"{domain}-{i:03d}",
                    "domain": domain,
                    "source_group_sha256": f"source-{domain}-{i:03d}",
                    "related_apps": [domain],
                }
                for i in range(count)
            )
        rows.extend(
            {
                "id": f"multi-{i:03d}",
                "domain": "multi_apps",
                "source_group_sha256": f"source-multi-{i:03d}",
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
        self.assertEqual(len({row["id"] for row in selection + final + reserve}), 128)
        self.assertEqual(sum(row["domain"] == "multi_apps" for row in final), 7)
        self.assertEqual(
            [row["id"] for row in planner.split_rows(list(reversed(rows)))[1]],
            [row["id"] for row in final],
        )

    def test_pinned_index_hash_is_enforced(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evaluation_examples"
            path.mkdir()
            (path / "test_all.json").write_text('{"libreoffice_calc": []}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Unexpected OSWorld task index SHA-256"):
                planner.eligible_rows(Path(directory))


if __name__ == "__main__":
    unittest.main()
