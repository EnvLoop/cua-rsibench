"""Portable refusal checks; actual primary artifacts are audited separately."""
from __future__ import annotations
import inspect
from pathlib import Path
import tempfile
import unittest

from tools import office_ppt_native_save_collection_control_v1 as control
from tools import office_single_account_train_pilot_v1 as manual


class NativeSaveControlTests(unittest.TestCase):
    def test_corrected_proposal_and_strict_core_source_remain_pinned(self):
        hashes=control.source_hashes()
        self.assertEqual(hashes['tools/ppt_native_train_collection_proposal_v1.py'],
                         control.CORRECTED_PROPOSAL_SOURCE_SHA)
        self.assertEqual(hashes['ppt_wdi_factory/verify.py'],control.proposal.CORE_VERIFIER_SHA)
        self.assertNotIn('scorer_factory',inspect.signature(control.audit).parameters)

    def test_fabricated_adversarial_evidence_cannot_activate_manual_control(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/'audit.json';path.write_bytes(b'{}');path.chmod(0o600)
            with self.assertRaisesRegex(manual.SingleAccountPilotError,'corrected_adversarial_evidence_required'):
                control.reviewed_policy(path,work_root=root)

    def test_baseline_and_reset_must_use_exact_unsolved_native_seed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'invented.pptx';path.write_bytes(b'not the native seed')
            scorer=control.NativeSaveScorer.__new__(control.NativeSaveScorer)
            for method in (lambda:scorer.baseline(path),lambda:scorer.reset(path,path)):
                with self.assertRaises(manual.SingleAccountPilotError):method()

    def test_saved_control_cannot_be_reused_for_another_student_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'student.pptx';path.write_bytes(b'a different student save')
            scorer=control.NativeSaveScorer.__new__(control.NativeSaveScorer)
            with self.assertRaisesRegex(manual.SingleAccountPilotError,'exact_historical_saved_required'):
                scorer.saved(path,path)


if __name__=='__main__':unittest.main()
