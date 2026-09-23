import copy,json,unittest
from pathlib import Path
from cursibench.factory_cases import SourceRegistry,compile_case,digest
from cursibench.factory_corpus import VerifiedCorpus
from cursibench.gui_contract import prompt

class CorpusTests(unittest.TestCase):
    def fixture(self):
        raw=json.loads((Path(__file__).resolve().parents[1]/'datasets/public/kanboard_issues.json').read_text())
        number=raw['records'][0]['number'];registry=SourceRegistry(raw,[number],[])
        case=compile_case({'id':'corpus-test','mode':'direct','source_numbers':[number],'select_numbers':[number],'changes':{'owner':'Chen','priority':3,'score':8}},registry)
        baseline={'tasks':[{'id':1,'owner_id':0,'priority':0,'score':0}]}
        final={'tasks':[{'id':1,'owner_id':2,'priority':3,'score':8}]}
        observation={'text':'Saved native task','controls':[]}
        response=json.dumps({'action':{'type':'done'},'memory':'Saved and checked'})
        result={'case_hash':digest(case),'baseline':baseline,'final':final,'mapping':{'users':{'Chen':2},'tasks':{f'GH-{number}':1}},'infrastructure_error':None,
                'trace':[{'step':0,'prompt':prompt(case['instruction'],observation),'observation':observation,'response':response,'outcome':{'done':True}}]}
        return case,result

    def test_forged_success_is_rejected_by_saved_state(self):
        case,result=self.fixture();result['verification']={'success':True};result['final']=result['baseline']
        with self.assertRaisesRegex(ValueError,'saved-state'):VerifiedCorpus().add(case,result,'e0')

    def test_contract_and_observation_tampering_rejected(self):
        case,result=self.fixture();result['trace'][0]['prompt']='a different instruction header'
        with self.assertRaisesRegex(ValueError,'contract'):VerifiedCorpus().add(case,result,'e0')

    def test_generated_jsonl_must_match_registered_execution(self):
        case,result=self.fixture();corpus=VerifiedCorpus();rows=corpus.add(case,result,'e0')
        selected=[rows[0],rows[0]]
        accepted=corpus.validate_submission('\n'.join(json.dumps(x) for x in selected));self.assertEqual(accepted,selected)
        altered=copy.deepcopy(rows[0]);altered['messages'][-1]['content']='invented successful behavior'
        with self.assertRaisesRegex(ValueError,'provenance'):corpus.validate_submission(json.dumps(altered))
        altered=copy.deepcopy(rows[0]);altered['source_split']='test'
        with self.assertRaises(ValueError):corpus.validate_submission(json.dumps(altered))

    def test_evaluation_case_cannot_register_positive_demonstrations(self):
        case,result=self.fixture();case['provenance']['source_split']='selection';result['case_hash']=digest(case)
        with self.assertRaisesRegex(ValueError,'evaluation evidence'):VerifiedCorpus().add(case,result,'e0')
