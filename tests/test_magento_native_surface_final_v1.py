"""Actual v22 FinalGate and Magento command interface; synthetic native SDK."""
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from cursibench import full_study_final_dispatch_v1 as final
from cursibench import full_study_runtime_v2 as v22
from cursibench import native_surface_guard_policy_v1 as policy
from magento_catalog_factory import native_surface_workers_v1 as source
from tests import test_full_study_final_dispatch_v1 as gates
from tests import v22_policy_runtime_fixture as fixture
from tests.test_magento_native_surface_pipeline_v1 import Runtime,Sampler
from tests.test_magento_catalog_saved_state import CASE


class MagentoFinalTests(unittest.TestCase):
    def setUp(self):
        self.protocol=gates.FullStudyFinalDispatchTests();self.protocol.setUp();self.addCleanup(self.protocol.tearDown)
        self.gate,_,_=fixture.final_gate(self.protocol);self.cell=next(r for r in self.gate.plan['cells'] if r['cell_id']==source.CELL)
        self.binding=source.public_binding()
        for key,value in [('source_snapshot',source.digest(final.canonical(source.study_source_snapshot()))),('runtime',self.binding['binding_sha256']),('verifier',self.binding['source_sha256s']['magento_catalog_factory/verify.py'])]:
            self.cell['matched_bindings'][key]=value
            for slot in [self.cell['base'],*self.cell['researcher_plans'].values()]:slot['bindings'][key]=value
        self.gate.frozen.ratification['cell_profiles'][source.CELL]['adapter_sha256']=self.binding['source_sha256s']['magento_catalog_factory/native_surface_guard_v1.py']
        self.identities=[row for chunk in self.cell['base']['chunks'] for row in chunk['tasks']]
        self.out=(self.protocol.work/'magento-synthetic-final').resolve();self.out.mkdir(mode=0o700)
        self.inputs=SimpleNamespace(control_preparation_only=False,binding=self.binding,
            roster={'splits':{'official_candidate':self.identities}},output=self.out,validate_train_admission=lambda:None)
        self.worker=source.FinalWorker(gate=self.gate,inputs=self.inputs,enable_live=True)
    def command(self,owner='shared-base'):
        row=self.identities[0];slot=self.cell['base'] if owner=='shared-base' else self.cell['researcher_plans'][owner]
        sampler=None if owner=='shared-base' else 'tinker://synthetic/sampler_weights/source-only-magento'
        if owner!='shared-base':
            self.cell['execution_evidence_owner_by_slot'][owner]=owner;slot['bindings']['checkpoint']=source.digest(sampler.encode())
        command={'schema':final.COMMAND_SCHEMA,'study_id':self.gate.plan['study_id'],'cell_id':source.CELL,'owner_slot':owner,
            **row,'checkpoint_sha256':slot['bindings']['checkpoint'],'sampler_path':sampler,
            'expected_initial_state_sha256':self.gate.initial_state_by_task[source.CELL][row['task_id']],
            'attempt_id':f'final-{source.matrix.CELLS.index(source.CELL):02d}-{owner}-000-0','retry_index':0,'retry_rule_sha256':None,
            'action_profile':'scale-action-profile-v0.6.6','sampling':slot['sampling'],'max_actions':90,'max_wall_seconds':720,
            'matched_bindings':self.cell['matched_bindings'],'reserve_usd':'1'}
        output=self.out/command['attempt_id'];output.mkdir(mode=0o700);return command,output
    def reserve(self,command):
        owner=source.CELL+':'+command['owner_slot'];kind='shared_base_final' if command['owner_slot']=='shared-base' else 'selected_final'
        self.gate.budget.reserve(command['attempt_id'],owner,kind,'1',source.digest(final.canonical(command)))
        self.gate.budget.mark_dispatched(command['attempt_id'],source.digest(final.canonical(command)))
    def test_actual_gate_constructor_and_commands_are_metadata_only(self):
        command,output=self.command()
        with patch.object(source,'execute_owned',side_effect=AssertionError('hidden task opened')):
            with self.assertRaisesRegex(policy.GuardError,'paid_reservation'):self.worker.run_once(command,output)
            self.reserve(command)
            for field,value in [('cell_id','gitlab'),('task_id','wrong-task'),('checkpoint_sha256','0'*64),('sampling',{}),
                ('max_wall_seconds',1200),('max_actions',89),('retry_index',2),('owner_slot','unknown')]:
                with self.subTest(field=field),self.assertRaises(policy.GuardError):self.worker.run_once({**command,field:value},output)
            with self.assertRaises(policy.GuardError):self.worker.run_once({**command,'unknown_field':True},output)
        self.assertEqual(list(output.iterdir()),[])
        self.gate.study.amendment=copy.deepcopy(self.gate.study.amendment)
        self.gate.study.amendment['native_environment_by_cell'][source.CELL]='owned_e2b_native_desktop'
        with self.assertRaisesRegex(policy.GuardError,'environment_not_ratified'):source.FinalWorker(gate=self.gate,inputs=self.inputs)
    def test_real_factory_actor_original_scorer_reset_and_provider_close_all_slot_transport(self):
        for owner in ['shared-base',*source.matrix.RESEARCHERS]:
            with self.subTest(owner=owner):
                command,output=self.command(owner);runtime=Runtime();row=command
                case={**copy.deepcopy(CASE),'task_id':row['task_id'],'package_sha256':row['package_sha256'],
                    'instruction':'Synthetic qualified native task','split':'official_candidate'}
                # Reopened initial state is derived by the original trusted
                # snapshot method; this fixture fixes that known source state.
                from tools import magento_dedicated_train_lane_v066 as original
                from tests.test_magento_dedicated_train_lane_v066 import FakeDocker
                from tests.test_magento_catalog_saved_state import baseline
                before=baseline();before['task_id']=case['task_id'];before['database']['quote']['identifier']='envloop-quote-'+case['task_id'].removeprefix('magento-catalog-')
                # search snapshot produced by the fake original process:
                process=FakeDocker();documents=process.documents;parent=str(case['parent_id'])
                before['search']={'document_count':181,'full_sha256':source.verify.canonical_sha(documents),
                    'other_documents_sha256':source.verify.canonical_sha({k:v for k,v in documents.items() if k!=parent}),
                    'parent_document_sha256':source.verify.canonical_sha(documents[parent])}
                command['expected_initial_state_sha256']=source.verify.canonical_sha(before)
                self.gate.initial_state_by_task[source.CELL][case['task_id']]=command['expected_initial_state_sha256']
                self.reserve(command)
                self.inputs.load=lambda identity,split:case
                self.inputs.runtime=lambda:runtime;self.inputs.username=lambda:runtime.page.uid
                with patch.object(source,'sampler_class',return_value=Sampler),patch.object(self.gate.study,'student_training_configuration',return_value=({'model':'Qwen/Qwen3.8-27B','seed':0,'sample_max_tokens':128},'a'*64)),patch('time.monotonic',lambda:runtime.page.tick):
                    outcome=self.worker.run_once(command,output)
                self.assertEqual(outcome['score'],1);self.assertIsNone(outcome['cost_usd']);self.assertEqual(outcome['action_count'],1)
                self.assertTrue(runtime.assert_removed)
                with self.assertRaises(ValueError):self.worker.run_once(command,output)

if __name__=='__main__':unittest.main()
