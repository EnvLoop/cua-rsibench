from __future__ import annotations

from io import BytesIO
import json
from hashlib import sha256
import os
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from tools import audit_odoo_v066_selection_post_intent_stale_v1 as incident


ROOT = Path(__file__).resolve().parents[1]


def frame(path: Path, *, blue: int, third: bool = False) -> None:
    image = Image.new("RGB", (1440, 1000), "white")
    for x in (41, 132):
        image.putpixel((x, 419), (235, 237, blue))
    if third:
        image.putpixel((508, 479), (0, 0, 0))
    image.save(path)


class PinnedBorderTests(unittest.TestCase):
    def test_only_two_exact_border_pixels_are_eligible(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            observed, alternate, third = (root / n for n in
                                          ("observed.png", "alternate.png",
                                           "third.png"))
            frame(observed, blue=239)
            frame(alternate, blue=240)
            frame(third, blue=240, third=True)
            self.assertTrue(incident._two_pinned_pixels(observed, alternate))
            self.assertFalse(incident._two_pinned_pixels(observed, third))
            self.assertFalse(incident._two_pinned_pixels(alternate, observed))


class RetainedAttemptTests(unittest.TestCase):
    def test_real_attempt_is_bound_without_replay(self):
        external = os.environ.get("ODOO_POST_INTENT_EVIDENCE_ROOT")
        if not external:
            self.skipTest("private Odoo run root not supplied")
        external = Path(external)
        worker = external / "enterprise_fallback/odoo18/partition_workers/selection"
        self.worker = worker
        plan = external / "work/odoo-original/v066-scale-controls-20260928/selection/plan-exact-frame-return-blank-compose-20260929.private.json"
        report = incident.audit(
            repo=ROOT, worker=worker,
            run_dir=worker / "private/v066_scale_controls/controls-20260929-exact-return-01",
            old_run_dir=worker / "private/v066_scale_controls/controls-20260928-v1",
            private_plan_path=plan,
            public_plan_path=ROOT / "docs/evidence/odoo-v066-selection-control-plan-exact-frame-return-blank-compose-2026-09-29.json",
            source_freeze_path=ROOT / "docs/evidence/odoo-v066-scale-exact-frame-return-blank-compose-source-freeze-2026-09-29.json",
            incident_public_path=ROOT / "docs/evidence/odoo-v066-selection-first-exact-frame-flicker-incident-2026-09-28.json",
            verify_services=True)
        published = json.loads((ROOT / "docs/evidence/odoo-v066-selection-second-post-intent-stale-2026-09-29.json").read_text())
        lease_path = self.worker / "private/worker-lease-events.jsonl"
        prefix = b""
        historical_lease_hashes = set()
        for line in lease_path.read_bytes().splitlines(keepends=True):
            prefix += line
            historical_lease_hashes.add(sha256(prefix).hexdigest())
        self.assertIn(published["worker_lease_events_sha256"],
                      historical_lease_hashes)
        report["worker_lease_events_sha256"] = published[
            "worker_lease_events_sha256"]
        self.assertEqual(report, published)
        self.assertFalse(report["post_intent_mouse_action_dispatched"])
        self.assertTrue(report["journal_payload_sha_reused_across_distinct_runs"])


if __name__ == "__main__":
    unittest.main()
