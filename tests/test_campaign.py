import copy
import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from cursibench.workbench_data import suite,verify_case,digest
from cursibench.campaign import promotion
from cursibench.campaign_runtime import Ledger,verify_ledger,BudgetExhausted

class CampaignTests(unittest.TestCase):
    def test_visible_excludes_answers(self):
        for c in suite():
            self.assertNotIn('expected',c.visible());self.assertNotIn('split',c.visible())
    def test_every_oracle_and_noop(self):
        for c in suite():
            final={'records':c.expected,'source':c.source,'policy':c.policy}
            self.assertTrue(verify_case(c,final)['success'])
            self.assertFalse(verify_case(c,dict(final,records=c.records))['success'])
    def test_source_tamper_and_unrelated_edit(self):
        for c in suite():
            final={'records':copy.deepcopy(c.expected),'source':[],'policy':c.policy}
            self.assertFalse(verify_case(c,final)['success'])
            final['source']=c.source;final['records'][0]['id']='tampered'
            self.assertFalse(verify_case(c,final)['integrity'])
    def test_duplicate_fails(self):
        c=suite()[0];final={'records':c.expected+[c.expected[0]],'source':c.source,'policy':c.policy}
        self.assertFalse(verify_case(c,final)['success'])
    def test_gate_rejects_regression_and_infra(self):
        base={'infrastructure_errors':0,'by_task':{'a':1,'b':0},'success_rate':.5}
        for candidate in [base,dict(base,infrastructure_errors=1),dict(base,by_task={'a':0,'b':1},success_rate=.6)]:
            self.assertFalse(promotion(base,candidate)[0])
        self.assertTrue(promotion(base,dict(base,by_task={'a':1,'b':1},success_rate=1))[0])
    def test_ledger_tampering_and_budget(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'ledger.jsonl';l=Ledger(path,max_calls=1);l.reserve('one');l.append('one',{'x':1})
            with self.assertRaises(BudgetExhausted):l.reserve('two')
            self.assertTrue(verify_ledger(path));path.write_text(path.read_text().replace('"x": 1','"x": 2'))
            self.assertFalse(verify_ledger(path))
    def test_split_hashes_distinct(self):
        data=suite();hashes=[digest([asdict(c) for c in data if c.split==s]) for s in ['train','acceptance','test']]
        self.assertEqual(len(set(hashes)),3)
