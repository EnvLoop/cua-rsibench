"""The historical source ratifier must reject the later Desktop amendment."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import ratify_v066_action_source_for_controls_v1 as ratify
class CodeOnlyRatificationTests(unittest.TestCase):
    def test_historical_ratifier_refuses_amended_desktop_bytes(self):
        with self.assertRaisesRegex(ValueError,
                                    "six_cell_adapter_source_changed"):
            ratify.build()

    def test_changed_adapter_source_refuses_before_output(self):
        raw = ratify.LEDGER.read_bytes()
        changed = json.loads(raw)
        changed["cells"][0]["adapter_source_sha256s"][
            changed["cells"][0]["v066_adapter_source"]] = "0" * 64
        with tempfile.TemporaryDirectory() as scratch:
            ledger = Path(scratch) / "changed-ledger.json"
            ledger.write_text(json.dumps(changed))
            # Exercise the source check without editing tracked files.
            with patch.object(ratify, "LEDGER", ledger):
                with self.assertRaisesRegex(ValueError,
                                            "six_cell_adapter_source_changed"):
                    ratify.build()

    def test_historical_ratifier_cannot_write_new_source_authority(self):
        with tempfile.TemporaryDirectory(dir=ratify.ROOT / "work") as scratch:
            private = Path(scratch) / "freeze.private.json"
            public = ratify.ROOT / "docs/evidence" / (
                "_temporary-v066-code-freeze-test.json")
            try:
                with self.assertRaisesRegex(
                        ValueError, "six_cell_adapter_source_changed"):
                    ratify.write(private, public)
                self.assertFalse(private.exists())
                self.assertFalse(public.exists())
            finally:
                public.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
