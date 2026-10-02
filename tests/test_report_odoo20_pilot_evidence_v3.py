"""Synthetic operation receipts and exact statistics; never render fake results."""
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from tools import report_odoo20_pilot_v3 as report
from tests.test_report_odoo20_pilot_public_safety_v3 import complete_publication


class ReportEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inputs = SimpleNamespace(identity='synthetic-dataset', plan={'models':{'student':'Qwen/Qwen3.8-27B'}},
            training={'optimizer_steps':2,'lora_rank':8,'seed':0,'learning_rate':'0.0001','sample_max_tokens':512},
            indices=[[0,1],[1,0]], datums=[None,None], scheduled_tokens=100)
        self.result = {'optimizer_steps_completed':2,'scheduled_tokens':100,'checkpoint_path':'tinker://synthetic/sampler_weights/x',
                       'sample_token_count':2}
        self.request = {'datum_count':2}
        from tinker import types
        params = types.AdamParams(learning_rate=0.0001).model_dump(mode='json')
        operations = [
            ('session-create',{'model':'Qwen/Qwen3.8-27B','max_retries':0,'holder_retries':False},{'session_id':'SYNTHETIC'}),
            ('lora-create',{'model':'Qwen/Qwen3.8-27B','rank':8,'seed':0,'optimizer':'adamw'},{'model_id':'SYNTHETIC'})]
        for step, indices in enumerate(self.inputs.indices):
            operations.extend([(f'step-{step:04d}-forward-backward',{'datum_indices':indices,'loss_fn':'cross_entropy'},
                {'metrics':{},'loss_fn_output_type':'tensor','loss_fn_outputs':[{},{}]}),
                (f'step-{step:04d}-optim',params,{'metrics':{}})])
        operations.extend([
            ('sampler-weights-save',{'name':'odoo20-synthetic-dataset'},{'path':self.result['checkpoint_path']}),
            ('sampler-create',{'model_path':self.result['checkpoint_path'],'retry_logic':False},{'response_type':'SyntheticSampler'}),
            ('sampler-base-read',{},'Qwen/Qwen3.8-27B'),
            ('checkpoint-sample',{'prompt_index':0,'max_tokens':512,'temperature':0,'seed':0},{'sequences':[{'tokens':[1,2]}]}),
            ('service-close',{'status':'success'},None)])
        for name, request, response in operations:
            self.save(name+'-intent.private.json',{'schema':'envloop-odoo20-tinker-operation-intent-v1',
                'operation':name,'dataset_identity':self.inputs.identity,'request':request,
                'before_provider_call':True,'automatic_replay_authorized':False})
            self.save(name+'-result.private.json',{'status':'completed','formal_large_study_credit':0,'result':response})

    def save(self, name, value):
        path = self.root/name; path.write_text(json.dumps(value)); path.chmod(0o600)

    def check(self, result=None):
        report.audit_training_operations(self.root, self.inputs, self.result if result is None else result, self.request)

    def test_each_operation_and_frozen_schedule_reopened(self):
        self.check()
        partial = {**self.result,'optimizer_steps_completed':1}
        with self.assertRaisesRegex(ValueError,'complete_frozen_training_schedule'): self.check(partial)
        (self.root/'step-0001-optim-result.private.json').unlink()
        with self.assertRaises(ValueError): self.check()

    def test_uncertain_operation_or_changed_training_batch_is_not_publishable(self):
        self.save('step-0001-optim-error.private.json',{'status':'uncertain_no_replay'})
        with self.assertRaisesRegex(ValueError,'uncertain_training_operation'): self.check()
        (self.root/'step-0001-optim-error.private.json').unlink()
        path = self.root/'step-0000-forward-backward-intent.private.json'
        intent = json.loads(path.read_bytes()); intent['request']['datum_indices']=[1,1]
        self.save(path.name,intent)
        with self.assertRaisesRegex(ValueError,'intent_or_completion_changed'): self.check()

    def test_exact_paired_transitions_and_small_sample_intervals(self):
        data = complete_publication()
        stats = report.uncertainty(data)
        self.assertEqual(stats['transitions'],{'both_pass':0,'base_only':0,'checkpoint_only':20,'both_fail':0})
        self.assertAlmostEqual(stats['exact_paired_mcnemar_two_sided_p'],2/(2**20))
        self.assertAlmostEqual(stats['baseline_wilson95'][1],0.1611251581,places=8)
        self.assertAlmostEqual(stats['selected_checkpoint_wilson95'][0],0.8388748419,places=8)
        self.assertTrue(all(row['task_count']==5 for row in stats['family_counts'].values()))
        for row in data['outcomes']: row['score']=0
        self.assertEqual(report.uncertainty(data)['exact_paired_mcnemar_two_sided_p'],1.0)

    def test_v4_continuation_preserves_original_prefix_and_unscored_exclusion(self):
        tasks = [{'task':{'task_id':f'SYNTHETIC-{i}','package_sha256':'a'*64}} for i in range(20)]
        scores = [{'task':row['task'],'score':0} for row in tasks]
        exclusion = {'classification':'provider_infrastructure_uncertain_no_model_score','model_score':None,
            'original_request_replay_authorized':False,'original_attempt_resume_authorized':False,
            'completed_sample_calls':44,'uncertain_request_ids':['SYNTHETIC-UNCERTAIN']}
        origin = {'binding_sha256':'b'*64}
        candidate = {'selection_tasks':tasks[:3],'scores':scores[:3],'infrastructure_exclusion':exclusion,
            'source_binding':{'original_selection_source_binding':origin}}
        baseline = {'orchestration_epoch':'v4','continuation_authority_ref':{'path':'/SYNTHETIC','sha256':'c'*64},
            'selection_tasks':tasks,'scores':scores,'infrastructure_exclusion':exclusion,'imported_row_source_binding':origin}
        selected = {'orchestration_epoch':'v4','continuation_authority_ref':None,'infrastructure_exclusion':None,
            'imported_row_source_binding':None}
        with patch.object(report.selection,'_authority',return_value=({'actor_sampler_scorer_reset_changed':False},candidate)):
            result = report.audit_v4_selection_lineage(baseline,selected,'d'*64)
            self.assertIsNone(result['model_score']); self.assertEqual(result['imported_original_v3_cases'],3)
            bad = copy.deepcopy(baseline); bad['scores'][0]['score']=1
            with self.assertRaisesRegex(ValueError,'prefix_or_exclusion_changed'):
                report.audit_v4_selection_lineage(bad,selected,'d'*64)
            bad = {**selected,'imported_row_source_binding':origin}
            with self.assertRaisesRegex(ValueError,'fresh_checkpoint_pair'):
                report.audit_v4_selection_lineage(baseline,bad,'d'*64)

    def test_late_local_error_can_settle_without_rewriting_false_close_snapshot(self):
        root = self.root/'prior-failed'; root.mkdir()
        def saved(name,value):
            path=root/name; path.write_text(json.dumps(value)); path.chmod(0o600); return path
        for name in ('step-0019-forward-backward','service-close'):
            saved(name+'-intent.private.json',{'schema':'envloop-odoo20-tinker-operation-intent-v1',
                'operation':name,'dataset_identity':'SYNTHETIC','before_provider_call':True,'automatic_replay_authorized':False})
        error=saved('step-0019-forward-backward-error.private.json',{'status':'uncertain_no_replay','automatic_replay_authorized':False})
        saved('step-0019-forward-backward-deadline.private.json',{'status':'uncertain_owned_future_retained','automatic_replay_authorized':False})
        saved('service-close-result.private.json',{'status':'completed'})
        close=saved('owned-provider-close.private.json',{'real_close_call_returned':True,'owned_client_cleanup_proved':False,
            'lifecycle':{'all_owned_calls_settled':False,'pending_owned_calls':1}})
        original=close.read_bytes()
        terminal={'pid':999999,'exit_code':1,'automatic_restarts':0,'ended_at':max(path.stat().st_mtime for path in root.iterdir())+1}
        with patch.object(report.os,'kill',side_effect=ProcessLookupError):
            result=report.audit_prior_local_settlement(root,terminal,'SYNTHETIC')
            self.assertEqual(result['settled_operations'],2)
            self.assertEqual(result['remote_uncertain_operation_completion'],'unknown')
            self.assertEqual(close.read_bytes(),original)
            with self.assertRaisesRegex(ValueError,'must_follow_last_local_settlement'):
                report.audit_prior_local_settlement(root,{**terminal,'ended_at':0},'SYNTHETIC')
            error.unlink()
            with self.assertRaisesRegex(ValueError,'not_terminal_or_ambiguous'):
                report.audit_prior_local_settlement(root,terminal,'SYNTHETIC')


if __name__=='__main__': unittest.main()
