"""Twenty production selection episodes and real v22 paid/shared-base APIs."""
import copy
import json
import time
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from cursibench import full_study_runtime_v2 as v22
from cursibench import full_study_qwen_runtime_gate_v1 as runtime_gate
from magento_catalog_factory import native_surface_workers_v1 as source
from tests import test_full_study_final_dispatch_v1 as gates
from tests import v22_policy_runtime_fixture as fixture
from tests.test_magento_native_surface_pipeline_v1 import Runtime,Sampler
from tests.test_magento_catalog_saved_state import CASE


class SelectionTests(unittest.TestCase):
    def test_real_shared_paid_ledger_twenty_original_saved_reset_episodes_and_result_contract(self):
        f=gates.FullStudyFinalDispatchTests();f.setUp();self.addCleanup(f.tearDown)
        study=fixture.study(f.frozen);cell=next(r for r in study.plan['cells'] if r['cell_id']==source.CELL)
        binding=source.public_binding();cell['matched_bindings']['runtime']=binding['binding_sha256'];cell['matched_bindings']['source_snapshot']=source.digest(source.final.canonical(source.study_source_snapshot()))
        cell['matched_bindings']['verifier']=binding['verifier_sha256']
        identities=list(study.task_views(source.CELL)['selection'])
        inputs=SimpleNamespace(control_preparation_only=False,binding=binding,roster={'splits':{'selection':[{k:r[k] for k in ('task_id','package_sha256')} for r in identities]}},validate_train_admission=lambda:None,
            username=lambda:'synthetic-admin')
        def load(identity,split):
            self.assertEqual(split,'selection')
            return {**copy.deepcopy(CASE),**identity,'instruction':'Synthetic frozen supplier price task','split':'selection'}
        inputs.load=load;current=[None];monotonic=time.monotonic
        def runtime():current[0]=Runtime();return current[0]
        inputs.runtime=runtime
        config={'model':'Qwen/Qwen3.8-27B','seed':0,'sample_max_tokens':128};raw=source.final.canonical(config);config_sha=source.digest(raw)
        runtime_receipt={key:'a'*64 for key in ('runtime_spec_sha256','toy_public_receipt_sha256','runtime_gate_source_sha256')}
        with patch.object(study,'student_training_configuration',return_value=(config,config_sha)),patch.object(runtime_gate,'pre_dispatch',return_value=runtime_receipt),patch.object(source,'sampler_class',return_value=Sampler),patch('time.monotonic',lambda:monotonic() if current[0] is None else current[0].page.tick):
            session=v22.SharedBaseSession(study,source.CELL)
            worker=source.SelectionWorker(study=study,inputs=inputs,enable_live=True)
            output=session.directory/'native'
            result=worker.run_selection(started=session.started,checkpoint_path='Qwen/Qwen3.8-27B',student_config_raw=raw,
                student_config_sha256=config_sha,out_dir=output,dispatch_paid=session.dispatch_paid,base_mode=True)
        self.assertEqual(len(result['result']['tasks']),20);self.assertEqual(sum(r['score'] for r in result['result']['tasks']),20)
        self.assertEqual(len(result['paid_attempt_ids']),80)
        records=study.budget.owner_attempts(source.CELL+':shared-base')
        self.assertEqual(set(records),set(result['paid_attempt_ids']))
        self.assertEqual({r['category'] for r in records.values()},{'tinker','storage_application'})
        self.assertTrue(all(r['actual_usd'] is None for r in records.values()))
        campaign=object.__new__(v22.CampaignSession);campaign.intent={'cell_id':source.CELL};campaign.views={'selection':identities}
        checked=campaign._selection_result(result['result'],checkpoint_sha256=session.started['checkpoint_path_sha256'])
        self.assertEqual(sum(checked.values()),20)
        self.assertTrue(result['performance_coverage']['performance_coverage_complete'])
        self.assertEqual(result['performance_coverage']['completed_model_response_count'],40)
        bad={**session.started,'selection_tasks':identities[:19]}
        with self.assertRaises(ValueError):worker.run_selection(started=bad,checkpoint_path='Qwen/Qwen3.8-27B',student_config_raw=raw,
            student_config_sha256=config_sha,out_dir=session.directory/'wrong',dispatch_paid=session.dispatch_paid,base_mode=True)

if __name__=='__main__':unittest.main()
