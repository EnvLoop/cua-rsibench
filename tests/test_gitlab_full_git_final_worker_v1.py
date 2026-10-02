"""Synthetic FinalGate metadata and fake original actor loop; no actual final admission."""
from __future__ import annotations
import copy
from contextlib import nullcontext
import json
from pathlib import Path
import time
import unittest
from unittest.mock import patch

from cursibench import full_study_final_dispatch_v1 as final, full_study_matrix_v1 as matrix
from gitlab_world import full_git_final_worker_v1 as worker_source
from gitlab_world import full_git_model_workers_v1 as common
from gitlab_world import verify
from tests import test_full_study_final_dispatch_v1 as gate_fixture
from tests import test_gitlab_selection_worker_v066 as actor_fixture
from tests.test_gitlab_full_git_model_proof_v1 import scenario, NativeFixture, BackendFixture, git_reader, binding_file
from tests import test_gitlab_saved_git_oracle_v1 as saved_fixture


class FullGitFinalWorkerTests(unittest.TestCase):
    def setUp(self):
        self.protocol=gate_fixture.FullStudyFinalDispatchTests()
        self.protocol.setUp();self.addCleanup(self.protocol.tearDown)
        self.gate=self.protocol.gate()
        self.cell=next(row for row in self.gate.plan['cells'] if row['cell_id']=='gitlab')
        # The existing gate is built with synthetic source identities. Bind the
        # worker fixture to its real local source bytes; this is no admission.
        for key,value in (('runtime',common.selection.runtime_sha256()),('verifier',common.selection.verifier_sha256())):
            self.cell['matched_bindings'][key]=value
            self.cell['base']['bindings'][key]=value
            for slot in self.cell['researcher_plans'].values():slot['bindings'][key]=value
        self.gate.frozen.ratification['cell_profiles']['gitlab']['adapter_sha256']=common.selection.adapter_sha256()
        self.binding,self.binding_path,self.binding_file_sha=binding_file(self.protocol.work)
        self.output=self.protocol.work/'full-git-final-output';self.output.mkdir(mode=0o700)
        self.cohort=self.protocol.work/'cohort-freeze.private.json'
        self.cohort.write_text('{}');self.cohort.chmod(0o600)

    def factory(self,enabled=False):
        return worker_source.final_worker_factory(gate=self.gate,full_git_binding_path=self.binding_path,
            full_git_binding_file_sha256=self.binding_file_sha,final_output_root=self.output,
            cohort_freeze_path=self.cohort,enable_live=enabled)

    def command(self,worker):
        task=next(row for chunk in self.cell['base']['chunks'] for row in chunk['tasks'])
        index=matrix.CELLS.index('gitlab');attempt=f'final-{index:02d}-shared-base-000-0'
        command={'schema':final.COMMAND_SCHEMA,'study_id':self.gate.plan['study_id'],'cell_id':'gitlab','owner_slot':'shared-base',
            'task_id':task['task_id'],'package_sha256':task['package_sha256'],
            'checkpoint_sha256':self.cell['base']['bindings']['checkpoint'],'sampler_path':None,
            'expected_initial_state_sha256':self.gate.initial_state_by_task['gitlab'][task['task_id']],
            'attempt_id':attempt,'retry_index':0,'retry_rule_sha256':None,'action_profile':'scale-action-profile-v0.6.6',
            'sampling':self.cell['base']['sampling'],'max_actions':self.cell['base']['execution']['max_actions_per_task'],
            'max_wall_seconds':self.cell['base']['execution']['max_wall_seconds_per_task'],
            'matched_bindings':self.cell['matched_bindings'],'reserve_usd':'0.5'}
        directory=self.output/attempt;directory.mkdir(mode=0o700)
        return command,directory

    def reserve(self,command):
        self.gate.budget.reserve(command['attempt_id'],'gitlab:shared-base','shared_base_final',command['reserve_usd'],final.sha(final.canonical(command)))
        self.gate.budget.mark_dispatched(command['attempt_id'],final.sha(final.canonical(command)))

    def test_factory_uses_existing_gate_100_metadata_five_uniform_slots_and_no_hidden_lookup(self):
        with patch.object(verify,'_context',side_effect=AssertionError('hidden lookup during construction')), \
             patch.object(worker_source.bootstrap,'world',side_effect=AssertionError('world during construction')):
            worker=self.factory()
        self.assertEqual(worker.identity['action_profile'],'scale-action-profile-v0.6.6')
        self.assertEqual(worker.full_git_model_binding_sha256,self.binding['binding_sha256'])
        self.assertEqual(sum(len(chunk['tasks']) for chunk in self.cell['base']['chunks']),100)
        self.assertEqual(set(self.cell['execution_evidence_owner_by_slot']),{'shared-base',*matrix.RESEARCHERS})
        # Equal selected checkpoints keep the existing shared execution owner.
        self.assertEqual(set(self.cell['execution_evidence_owner_by_slot'].values()),{'shared-base'})
        command,directory=self.command(worker)
        with self.assertRaisesRegex(ValueError,'explicit_live'):worker.run_once(command,directory)
        self.cell['researcher_plans'][next(iter(matrix.RESEARCHERS))]['bindings']['runtime']='0'*64
        with self.assertRaisesRegex(ValueError,'source_bindings_differ'):self.factory()
        with self.assertRaisesRegex(ValueError,'real_final_gate'):
            worker_source.final_worker_factory(gate=object(),full_git_binding_path=self.binding_path,
                full_git_binding_file_sha256=self.binding_file_sha,final_output_root=self.output,cohort_freeze_path=self.cohort)

    def test_gate_dispatched_reservation_policy_and_no_replay_required_before_application(self):
        worker=self.factory(True);command,directory=self.command(worker)
        with self.assertRaisesRegex(ValueError,'dispatched_reservation'):worker._command(command,directory)
        self.reserve(command)
        _,_,identities=worker._command(command,directory);self.assertEqual(len(identities),100)
        for field,value in (('max_actions',command['max_actions']+1),('checkpoint_sha256','0'*64),
                            ('package_sha256','0'*64),('sampler_path','tinker://fake/sampler_weights/forbidden')):
            with self.subTest(field=field),self.assertRaises(ValueError):worker._command({**command,field:value},directory)
        with patch.object(worker,'_run_episode',side_effect=TimeoutError('fixture uncertainty')) as episode:
            with self.assertRaises(TimeoutError):worker.run_once(command,directory)
            with self.assertRaisesRegex(ValueError,'private_output_exists'):worker.run_once(command,directory)
        self.assertEqual(episode.call_count,1)

    def test_full_concrete_final_episode_reuses_original_loop_and_formal_reader_before_reset(self):
        worker=self.factory(True);command,directory=self.command(worker)
        task,project,progress,before,after,sidecar,raws=scenario('final_candidate_unsealed',saved_fixture.FAMILIES[4])
        task['task_id']=command['task_id']
        identity={key:command[key] for key in ('task_id','package_sha256')}
        events,reset=[],[False];active=NativeFixture(identity,task,before)
        self.gate.initial_state_by_task['gitlab'][command['task_id']]=before['business_sha256']
        command['expected_initial_state_sha256']=before['business_sha256'];self.reserve(command)
        class FakeSampler:
            def __init__(self,**kw):self.kw=kw;self.closed=False
            def __call__(self,request,_prompt):
                return {'schema':'envloop-gitlab-v066-selection-sampler-result-v1','status':'completed','reported_model':common.selection.MODEL,
                    'checkpoint_path_sha256':self.kw['checkpoint_sha256'],'text':'{"type":"finish"}','stop_reason':'stop','elapsed_seconds':0.0,
                    'usage':{'input_tokens':request['input_tokens'],'image_tokens':request['image_tokens'],'output_tokens':5,
                        'prompt_cache_hit_tokens':None,'provider_billed_tokens':None,'basis':'rendered_input_and_returned_output_not_invoice'}}
            def close(self,**_kw):self.closed=True
        training={'model':common.selection.MODEL,'action_profile':'scale-action-profile-v0.6.6','max_supervised_tokens':32768,'prefill_usd_per_million_tokens':'1','sample_usd_per_million_tokens':'2','billing_multiplier_upper':'1'}
        with patch.object(self.gate.frozen,'student_training_configuration',return_value=(training,'c'*64)), \
             patch.object(worker_source,'_SealedFinalBackend',return_value=BackendFixture(active,events,reset)), \
             patch.object(common.cohort_source,'validate_source',return_value={}), \
             patch.object(common.cohort_scope,'cohort_context',side_effect=lambda _value:nullcontext()), \
             patch.object(verify,'state_snapshot',return_value=after),patch.object(verify,'_context',return_value=(project,progress)), \
             patch.object(verify,'_git',side_effect=git_reader(sidecar,raws,events,reset)), \
             patch.object(common.selection.GitLabSelectionWorker,'_load_vision',return_value=actor_fixture.FakeVision()), \
             patch.object(common.selection,'_RealTinkerSampler',FakeSampler),patch.dict('os.environ',{'TINKER_API_KEY':'fixture-only-key'}):
            outcome=worker.run_once(command,directory)
        self.assertEqual(events[-1],('cold_reset',))
        self.assertEqual(outcome['status'],'scored');self.assertEqual(outcome['score'],1)
        self.assertEqual(outcome['action_count'],1)
        saved=json.loads((directory/'native-episode'/'saved-state.private.json').read_bytes())
        self.assertTrue(saved['full_git_tree_verified'])
        self.assertEqual(saved['full_git_original_verdict']['score'],1.0)
        self.assertEqual(saved['independent_score']['reward'],1.0)
        self.assertTrue((directory/'native-episode'/'artifacts'/'full-git-post-reset-audit.private.json').is_file())
        intent=json.loads((directory/'worker-intent.private.json').read_bytes())
        self.assertEqual(intent['uniform_final_slot_model_source_binding_sha256'],self.binding['binding_sha256'])
        self.assertFalse(intent['automatic_action_or_provider_retry'])


if __name__=='__main__':unittest.main()
