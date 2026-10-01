"""Actual request journal/typed future deadline and read-only saved verification."""
import asyncio
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import time
import unittest
from unittest.mock import patch
from magento_catalog_factory import native_surface_actor_v1 as actor
from magento_catalog_factory import native_surface_workers_v1 as workers
from magento_catalog_factory import native_surface_budget_performance_v1 as audit
from enterprise_fallback.odoo18.odoo_actor_transport_v1 import sampler_class
from tests.test_magento_native_surface_pipeline_v1 import Runtime
from tests.test_magento_catalog_saved_state import CASE
from tests.test_scale_vision_proxy import FakeBackend


class BudgetTests(unittest.TestCase):
    def test_actual_unknown_request_saved_zero_reset_close_and_precise_portable_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            repo=Path(directory).resolve();work=repo/'work';work.mkdir(mode=0o700);output=work/'owned';output.mkdir(mode=0o700)
            episode=output/'native-episode';episode.mkdir(mode=0o700)
            runtime=Runtime(positive=False);case={**copy.deepcopy(CASE),'instruction':'Synthetic native supplier task','split':'selection'}
            identity={k:case[k] for k in ('task_id','package_sha256')};cls=sampler_class(workers.qwen);closed=[]
            class ActualSampler(cls):
                def __enter__(self):
                    self.backend=FakeBackend()
                    class Service:
                        def close(self,status):return SimpleNamespace(result=lambda **_:closed.append(status))
                    self.service=Service();return self
                def sample(self,observation,**kwargs):
                    runtime.page.tick=self.actor_clock.deadline-.25
                    backend=self.backend
                    def submit(*_args):
                        backend.submissions.append('single_actual_submission')
                        class Future:
                            def result(self,timeout=None):runtime.page.tick+=timeout;raise TimeoutError('synthetic unknown response')
                        return Future()
                    backend.submit=submit
                    return super().sample(observation,**kwargs)
            sampler=ActualSampler(checkpoint_path='Qwen/Qwen3.8-27B',config={'seed':0,'sample_max_tokens':128},output_root=episode,
                attempt_id='actual-parent-paid',base_mode=True,expected_base_checkpoint_sha256='a'*64)
            with patch('time.monotonic',lambda:runtime.page.tick):
                with sampler as active:
                    row=asyncio.run(actor.run_task(case=case,task=identity,output=episode,runtime=runtime,sampler=active,
                        username=runtime.page.uid,attempt_id='actual-parent-paid',paid_attempt_id='actual-parent-paid'))
            row.update(provider_close_ref=sampler.provider_close_reference,complete_lifecycle_wall_time_ms=row['lifecycle_wall_time_ms'])
            workers.write(episode,'native-row.private.json',row);audit.audit_episode(episode,row)
            self.assertEqual(row['score'],0);self.assertEqual(row['actor_wall_time_ms'],720000)
            self.assertEqual(runtime.page.calls,[]);self.assertEqual(closed,['success']);self.assertTrue(runtime.assert_removed)
            self.assertEqual(len(sampler.backend.submissions),1);self.assertIsNone(row['samples'][0]['raw_result']['usage']['output_tokens'])
            command={**identity,'attempt_id':'actual-parent-paid','owner_slot':'shared-base','checkpoint_sha256':'a'*64}
            spec=audit.prepare_budget_performance(command=command,output=output,episode=episode,row=row)
            study=SimpleNamespace(repo_root=repo,amendment_sha256='b'*64)
            receipt=audit.verify_budget_performance(study=study,owner_slot='shared-base',verification=spec['verification']['arguments'])
            self.assertEqual(receipt['inference']['status'],'completion_unknown_after_actor_deadline')
            self.assertEqual(receipt['inference']['completed_model_response_count'],0)
            self.assertFalse(receipt['inference']['unknown_response_is_completed']);self.assertIsNone(receipt['billing']['actual_usd'])
            self.assertEqual(set(receipt['evidence_sha256']),{'saved-state.private.json','verifier.private.json','reset.private.json',
                'actor-clock.private.json','actor-budget-stop.private.json','task.private.json'})
            with self.assertRaises(ValueError):audit.verify_budget_performance(study=study,owner_slot='astra',verification=spec['verification']['arguments'])
            changed={**spec['verification']['arguments'],'sample_paid_attempt_id':'invented-paid-call'}
            with self.assertRaises(ValueError):audit.verify_budget_performance(study=study,owner_slot='shared-base',verification=changed)
            stop=episode/'actor-clock/budget-stop.private.json';value=json.loads(stop.read_bytes());value['gui_applied']=True;stop.write_bytes(workers.final.canonical(value))
            with self.assertRaises(ValueError):audit.verify_budget_performance(study=study,owner_slot='shared-base',verification=spec['verification']['arguments'])

if __name__=='__main__':unittest.main()
