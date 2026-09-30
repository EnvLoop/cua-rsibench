"""Explicit folder-scope evidence remains manual TRAIN and fake-test scoped."""
from __future__ import annotations
import json
import unittest
from tests import test_office_single_account_train_pilot_v1 as fixtures
from tools import office_single_account_train_pilot_v1 as pilot


FakeScorer=fixtures.FakeScorer
ref=fixtures.ref
write_private=fixtures.write_private


class FolderScopeTests(unittest.TestCase):
    setUp=fixtures.SingleAccountTests.setUp
    fixture=fixtures.SingleAccountTests.fixture
    def folder_fixture(self):
        spec,path,out,source,evidence=self.fixture('powerpoint-web')
        evidence['schema']=pilot.FOLDER_EVIDENCE_SCHEMA
        evidence['manual_gui']['signed_in_dedicated_test_account']=False
        evidence['manual_gui']['account_scope']=pilot.EXISTING_FOLDER_SCOPE
        write_private(path,pilot._canonical(evidence))
        return spec,path,out,source,evidence

    def test_explicit_false_account_assertion_passes_only_fake_folder_control(self):
        spec,path,out,_,_=self.folder_fixture()
        result=pilot.audit(spec,path,out,work_root=self.work_root,
                           scorer_factory=FakeScorer,account_scope=pilot.EXISTING_FOLDER_SCOPE)
        self.assertEqual(result['status'],'fake_test_control_only')
        self.assertFalse(result['dedicated_test_account_operator_asserted'])
        self.assertFalse(result['automated_model_scope_qualified'])
        self.assertFalse(result['selection_or_final_admitted'])
        self.assertEqual(result['official_final_credit'],0)

    def test_default_dedicated_account_gate_stays_strict(self):
        spec,path,out,_,_=self.folder_fixture()
        with self.assertRaises(pilot.SingleAccountPilotError):
            pilot.audit(spec,path,out,work_root=self.work_root,scorer_factory=FakeScorer)
        self.assertFalse(out.exists())

    def test_folder_mode_cannot_claim_dedicated_account(self):
        spec,path,out,_,evidence=self.folder_fixture()
        evidence['manual_gui']['signed_in_dedicated_test_account']=True
        write_private(path,pilot._canonical(evidence))
        with self.assertRaisesRegex(pilot.SingleAccountPilotError,'manual_original_gui'):
            pilot.audit(spec,path,out,work_root=self.work_root,scorer_factory=FakeScorer,
                        account_scope=pilot.EXISTING_FOLDER_SCOPE)

    def test_folder_mode_still_rejects_extra_item_and_failed_saved_state(self):
        for condition in ('extra_item','neutral_saved'):
            spec,path,out,_,evidence=self.folder_fixture()
            if condition=='extra_item':
                inv_path,_=pilot._ref(evidence['phases']['saved']['inventory_ref'],self.work_root)
                inv=json.loads(inv_path.read_bytes());inv['items'].append(inv['items'][0])
                write_private(inv_path,pilot._canonical(inv));evidence['phases']['saved']['inventory_ref']=ref(inv_path,self.work_root)
            else:
                before_path,raw=pilot._ref(evidence['phases']['before']['downloads'][0],self.work_root)
                for n in range(2):
                    saved_path,_=pilot._ref(evidence['phases']['saved']['downloads'][n],self.work_root)
                    write_private(saved_path,raw);evidence['phases']['saved']['downloads'][n]=ref(saved_path,self.work_root)
            write_private(path,pilot._canonical(evidence))
            with self.assertRaises(pilot.SingleAccountPilotError):
                pilot.audit(spec,path,out,work_root=self.work_root,scorer_factory=FakeScorer,
                            account_scope=pilot.EXISTING_FOLDER_SCOPE)
            self.assertFalse(out.exists())
if __name__=='__main__':
    unittest.main()
