import copy
import json
import unittest
from pathlib import Path
from cursibench.factory_cases import SourceRegistry, compile_case

SNAPSHOT=Path(__file__).resolve().parents[1]/'datasets/public/kanboard_issues.json'

class FactoryCaseTests(unittest.TestCase):
    def setUp(self):
        self.data=json.loads(SNAPSHOT.read_text())
        self.train=[r['number'] for r in self.data['records'][:12]]
        self.protected=[r['number'] for r in self.data['records'][12:36]]
        self.registry=SourceRegistry(self.data,self.train,self.protected)
        self.base={'id':'generated-edit','source_numbers':self.train[:4],'mode':'direct',
                   'select_numbers':self.train[:1],'changes':{'owner':'Chen','priority':3,'score':8}}

    def test_train_export_never_exposes_protected_records(self):
        exported=self.registry.training_input()
        self.assertEqual({r['number'] for r in exported['records']},set(self.train))
        self.assertNotIn('protected',exported)
        bad=dict(self.base,source_numbers=[self.protected[0]])
        with self.assertRaisesRegex(ValueError,'training sources'):compile_case(bad,self.registry)
        with self.assertRaises(ValueError):SourceRegistry(self.data,self.train,self.train[:1])

    def test_real_facts_and_explicit_goals(self):
        case=compile_case(self.base,self.registry)
        self.assertEqual(case['targets'],{f'GH-{self.train[0]}':self.base['changes']})
        self.assertEqual(case['provenance']['source_split'],'train')
        self.assertEqual(case['source_numbers'],self.train[:4])
        source=self.data['records'][0]
        row=next(x for x in case['tasks'] if x['reference']==f'GH-{source["number"]}')
        self.assertIn(source['updated_at'],row['description'])
        self.assertIn(source['source_url'],row['description'])
        bad=copy.deepcopy(self.base);bad['source_facts']={'state':'fabricated'}
        with self.assertRaisesRegex(ValueError,'unknown'):compile_case(bad,self.registry)

    def test_rank_uses_source_state_and_stable_ties(self):
        spec={k:v for k,v in self.base.items() if k!='select_numbers'}
        spec.update(mode='rank',source_numbers=self.train,where={'field':'state','op':'eq','value':'open'},order_by=[{'field':'updated_at','direction':'asc'}],limit=2)
        case=compile_case(spec,self.registry)
        expected=sorted([r for r in self.data['records'][:12] if r['state']=='open'],key=lambda r:(r['updated_at'],r['number']))[:2]
        self.assertEqual(set(case['targets']),{f'GH-{r["number"]}' for r in expected})
        self.assertIn('source state',case['tasks'][0]['description'])

    def test_planning_targets_are_derived_not_submitted(self):
        spec={k:v for k,v in self.base.items() if k!='select_numbers'}
        ids=self.train[:3]
        spec.update(mode='allocation',source_numbers=ids,cost_limit=7,hour_limit=3,
                    planning=[{'number':ids[0],'cost':3,'hours':1,'value':5},
                              {'number':ids[1],'cost':4,'hours':2,'value':8},
                              {'number':ids[2],'cost':7,'hours':3,'value':12}])
        case=compile_case(spec,self.registry)
        self.assertEqual(set(case['targets']),{f'GH-{ids[0]}',f'GH-{ids[1]}'})
        self.assertIn('SYNTHETIC PLANNING INPUTS',case['tasks'][1]['description'])

    def test_invalid_empty_and_duplicate_states_rejected(self):
        for patch in ({'select_numbers':[]},{'source_numbers':[self.train[0]]*2},{'targets':{}},
                      {'changes':{'owner':'admin','priority':3,'score':8}},{'id':'../../tests'}):
            with self.subTest(patch=patch),self.assertRaises(ValueError):compile_case(dict(self.base,**patch),self.registry)

    def test_evaluation_registry_cannot_be_exposed_as_training_input(self):
        registry=SourceRegistry(self.data,self.protected,self.train,partition='selection')
        with self.assertRaisesRegex(ValueError,'cannot be exported'):registry.training_input()
        spec=dict(self.base,source_numbers=self.protected[:2],select_numbers=self.protected[:1])
        case=compile_case(spec,registry)
        self.assertEqual(case['provenance']['source_split'],'selection')

    def test_generated_markup_is_inert(self):
        case=compile_case(dict(self.base,notes='```\n<script>alert(1)</script>'),self.registry)
        text=case['tasks'][0]['description']
        self.assertNotIn('<script>',text)
        self.assertIn('\\u003cscript\\u003e',text)
