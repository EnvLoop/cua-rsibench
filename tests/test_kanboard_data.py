import unittest
from cursibench.kanboard_cases import build_case,public_issue_case
from cursibench.tinker_backend import validate_records

class RealDataTests(unittest.TestCase):
    def test_provenance_and_target_selection(self):
        case=public_issue_case()
        self.assertEqual(len(case['targets']),3)
        self.assertIn('snapshot_sha256',case['provenance'])
        for task in case['tasks'][1:]:
            self.assertIn('https://github.com/kanboard/kanboard/issues/',task['description'])
            self.assertIn('SOURCE SNAPSHOT',task['description'])
    def test_training_rejects_eval_rows(self):
        for split in ('test','acceptance',None):
            with self.assertRaises(ValueError):
                validate_records([{'source_split':split,'messages':[{'role':'user','content':'hi'},{'role':'assistant','content':'hello'}]}])
    def test_allocations_feasible_and_not_all(self):
        c=build_case('allocation')
        self.assertGreater(len(c['targets']),0)
        self.assertLess(len(c['targets']),12)
    def test_verifier_accepts_only_known_gui_normalization(self):
        import copy
        from cursibench.kanboard_cases import verify
        baseline={'tasks':[{'id':1,'owner_id':0,'priority':0,'score':0,'description':'original','time_spent':None,'time_estimated':None,'date_modification':1}, {'id':2,'owner_id':0,'priority':0,'score':0,'description':'archive'}], 'comments':[]}
        mapping={'tasks':{'A':1},'users':{'Chen':2}};targets={'A':{'owner':'Chen','priority':3,'score':8}}
        final=copy.deepcopy(baseline);final['tasks'][0].update(owner_id=2,priority=3,score=8,time_spent=0,time_estimated=0,date_modification=2)
        self.assertTrue(verify(baseline,final,mapping,targets)['success'])
        final['tasks'][1]['description']='tampered'
        self.assertFalse(verify(baseline,final,mapping,targets)['success'])
    def test_verifier_rejects_task_deletion_and_comment_tampering(self):
        from cursibench.kanboard_cases import verify
        base={'tasks':[{'id':1,'description':'keep'}],'comments':[{'id':1,'comment':'source'}]}
        self.assertFalse(verify(base,{'tasks':[],'comments':base['comments']},{'tasks':{},'users':{}},{})['success'])
        self.assertFalse(verify(base,{'tasks':base['tasks'],'comments':[]},{'tasks':{},'users':{}},{})['success'])
