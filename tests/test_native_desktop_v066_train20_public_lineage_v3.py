"""A later public v1 edit cannot silently leave the v2 lineage pointer stale."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from native_desktop_factory import v066_train20_public_lineage_v3 as lineage


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n")


class PublicLineageTests(unittest.TestCase):
    def test_correction_binds_reachable_v1_published_v2_and_full100_bytes(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            public = root / "docs/evidence"
            v1 = root / lineage.V1
            v2 = root / lineage.V2
            plan = root / lineage.PLAN
            freeze = root / lineage.FULL100
            corrected = public / "correction-v3.json"
            prior = {"schema":
                     "cua-native-wdi-v066-train20-battery-preflight-amendment-public-v1",
                     "assignment_unchanged": True,
                     "sft_candidate_count": 15, "holdout_candidate_count": 5,
                     "e2b_train_guest_creates": 0, "tinker_calls": 0,
                     "official_final_admissions": 0,
                     "official_model_results": 0}
            write(v1, prior)
            stale_sha = lineage.digest(v1.read_bytes())
            write(plan, {"schema":
                         "cua-native-wdi-v066-train20-source-plan-public-v1",
                         "sft_candidate_count": 15,
                         "holdout_candidate_count": 5,
                         "official_final_admissions": 0,
                         "official_model_results": 0})
            write(v2, {"schema":
                       "cua-native-wdi-v066-train20-battery-preflight-amendment-public-v2",
                       "prior_offline_amendment_sha256": stale_sha,
                       "new_plan_public_sha256": lineage.digest(plan.read_bytes()),
                       "assignment_unchanged": True,
                       "sft_candidate_count": 15,
                       "holdout_candidate_count": 5,
                       "paid_train_e2b_creates": 0, "tinker_calls": 0,
                       "official_final_admissions": 0,
                       "official_model_results": 0})
            prior["renamed_public_key"] = True
            write(v1, prior)
            files = {}
            for index in range(35):
                name = f"frozen/file-{index:02d}.txt"
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"source-{index}")
                files[name] = lineage.digest(path.read_bytes())
            write(freeze, {"schema":
                           "cua-native-wdi-v066-day-rollover-runtime-freeze-public-v1",
                           "source_sha256s": files,
                           "official_final_admissions": 0,
                           "official_model_results": 0})
            kwargs = dict(source_root=root, v1_path=v1, v2_path=v2,
                          plan_path=plan, full100_freeze_path=freeze)
            expected = lineage.build(**kwargs)
            self.assertNotEqual(expected["public_v1_actual_sha256"], stale_sha)
            write(corrected, expected)
            self.assertEqual(lineage.validate(
                correction_path=corrected, **kwargs), expected)
            prior["another_edit"] = True
            write(v1, prior)
            with self.assertRaisesRegex(ValueError, "drifted"):
                lineage.validate(correction_path=corrected, **kwargs)
            prior.pop("another_edit")
            write(v1, prior)
            (root / "frozen/file-00.txt").write_text("changed")
            with self.assertRaisesRegex(ValueError, "full100 source"):
                lineage.validate(correction_path=corrected, **kwargs)


if __name__ == "__main__":
    unittest.main()
