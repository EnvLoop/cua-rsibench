"""The Magento GUI sweep retains a failed process without retry or scoring."""

from __future__ import annotations

import json
import stat
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch
import unittest

from tools import sweep_magento_original_gui_controls_v1 as sweep


class MagentoSweepJournalTests(unittest.TestCase):
    def test_failed_prepare_keeps_private_diagnostics_and_stops(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            journal = root / 'events.private.jsonl'
            outcome = subprocess.CompletedProcess(['prep'], 1,
                                                  b'partial output', b'traceback')
            with patch.object(sweep.subprocess, 'run', return_value=outcome) as run:
                with self.assertRaisesRegex(ValueError, 'command failed'):
                    sweep.run_step(root, journal, 7, 'positive-prepare',
                                   ['prep'], timeout=3)
            run.assert_called_once()
            self.assertEqual((root / 'positive-prepare-stderr.private.bin').read_bytes(),
                             b'traceback')
            self.assertEqual((root / 'positive-prepare-stdout.private.bin').read_bytes(),
                             b'partial output')
            self.assertEqual(stat.S_IMODE((root / 'positive-prepare-stderr.private.bin').stat().st_mode),
                             0o600)
            process = json.loads((root / 'positive-prepare-process.private.json').read_bytes())
            self.assertEqual(process['exit_code'], 1)
            events = [json.loads(line) for line in journal.read_text().splitlines()]
            self.assertEqual([row['event'] for row in events],
                             ['step_intent', 'step_finished'])
            self.assertEqual(events[-1]['exit_code'], 1)


if __name__ == '__main__':
    unittest.main()
