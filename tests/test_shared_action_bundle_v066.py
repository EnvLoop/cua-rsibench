"""The proposed bundle rejects changed shared bytes and never authorizes work."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from cursibench import shared_action_bundle_v066 as bundle
from cursibench.full_study_matrix_v1 import CELLS as STUDY_CELLS


ROOT = Path(__file__).resolve().parents[1]


class ProposedBundleTests(unittest.TestCase):
    def test_exact_shared_source_bytes_and_unratified_state(self):
        with tempfile.TemporaryDirectory() as scratch:
            clone = Path(scratch)
            for relative in bundle.SOURCE_PATHS:
                path = clone / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes((ROOT / relative).read_bytes())
            proposed = bundle.build(clone)
            bundle.verify(clone, proposed)
            self.assertEqual(proposed["cell_ids"], list(bundle.CELLS))
            self.assertEqual(bundle.CELLS, STUDY_CELLS)
            self.assertFalse(proposed["base_and_selected_profile_uniformity_verified"])
            self.assertFalse(proposed["six_cell_adapter_live_v066_verified"])
            self.assertEqual(proposed["official_final_attempts"], 0)
            self.assertEqual(proposed["researcher_campaigns"], 0)
            changed = clone / bundle.SOURCE_PATHS[1]
            changed.write_bytes(changed.read_bytes() + b"\n# changed source\n")
            with self.assertRaisesRegex(ValueError, "source_or_field_mismatch"):
                bundle.verify(clone, proposed)

    def test_missing_or_symlink_source_fails(self):
        with tempfile.TemporaryDirectory() as scratch:
            clone = Path(scratch)
            for relative in bundle.SOURCE_PATHS:
                path = clone / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes((ROOT / relative).read_bytes())
            target = clone / bundle.SOURCE_PATHS[0]
            target.unlink()
            target.symlink_to(ROOT / bundle.SOURCE_PATHS[0])
            with self.assertRaisesRegex(ValueError, "missing_or_symlink"):
                bundle.build(clone)


if __name__ == "__main__":
    unittest.main()
