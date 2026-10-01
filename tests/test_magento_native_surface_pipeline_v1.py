"""Production actor/guard/scorer/original clone-reset with synthetic native SDK."""
import asyncio
from contextlib import asynccontextmanager,ExitStack
import copy
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from cursibench import full_study_final_dispatch_v1 as final
from cursibench import native_surface_guard_policy_v1 as policy
from magento_catalog_factory import native_surface_actor_v1 as actor
from magento_catalog_factory import native_surface_workers_v1 as workers
from magento_catalog_factory import native_surface_budget_performance_v1 as audit
from tests.test_magento_catalog_saved_state import CASE
from tests.test_magento_native_surface_guard_v1 import Page
from tests.test_magento_dedicated_train_lane_v066 import FakeDocker
from tools import magento_dedicated_train_lane_v066 as original


class Runtime:
    """Original manager and reset method; fake process/native page only."""
    def __init__(self,positive=True,missing_reset=False,missing_saved=False,uncertain=False):
        self.page=Page();self.positive=positive;self.missing_reset=missing_reset;self.missing_saved=missing_saved;self.uncertain=uncertain
        self.events=[]
        old=self.page.mouse.click
        async def click(*args):
            if uncertain:raise TimeoutError('synthetic native IO unknown')
            await old(*args);self.events.append('real_fixture_click_returned')
        self.page.mouse.click=click
    @asynccontextmanager
    async def open_case(self,case,output):
        process=FakeDocker();journal=original.CommandJournal(output,runner=process)
        manager=original.DedicatedCloneManager(journal,seeder=lambda case,*_: {'task_id':case['task_id'],
            'package_sha256':case['package_sha256'],'page_id':8,'status':'trusted_fixture_seeded_not_gui_admitted'})
        from tests.test_magento_catalog_saved_state import baseline as fixture_baseline
        fixture_state=fixture_baseline();fixture_state['database']['quote']['identifier']='envloop-quote-'+case['task_id'].removeprefix('magento-catalog-')
        with patch.object(manager,'_ports_free'),patch('tests.test_magento_dedicated_train_lane_v066.baseline',return_value=fixture_state):
            prepared=manager.prepare(original.pair(0),source_search_sha256=process.source_sha)
            manager.seed_case(original.pair(0),case)
            baseline=original.read_snapshot_scoped(case,original.pair(0),8,manager)
            self.prepared_for_current_episode=prepared
            async def saved():
                self.events.append('saved_after_actor_end')
                state=copy.deepcopy(baseline)
                if self.positive and self.page.calls:
                    for target in case['target_variants']:state['database']['prices'][str(target['entity_id'])]['price']=target['target_price']
                return {'snapshot':state,'native_save_observed':not self.missing_saved}
            session=SimpleNamespace(page=self.page,baseline_state=baseline,spec=original.pair(0),manager=manager,
                saved_state=saved,reset_proof=None)
            try:yield session
            finally:
                reset=original.DedicatedMagentoTrainRuntime({'source_search_sha256':process.source_sha},Path(output)/'synthetic-lane',runner=process,seeder=manager.seeder)
                session.reset_proof=await reset._prove_fresh_reset(manager,case,process.source_sha,prepared,baseline)
                self.events.append('actual_original_fresh_clone_reset')
                if self.missing_reset:session.reset_proof=None
                self.assert_removed=not process.containers and not process.network


class Sampler:
    def __init__(self,actions=None,**kwargs):
        self.attempt_id=kwargs.get('attempt_id','synthetic-sample');self.actions=actions or ['{"type":"click","target":{"x":50,"y":50}}','{"type":"finish"}'];self.index=0;self.close_calls=0
    def sample(self,observation,**kwargs):
        self.actor_clock.check('before_actual_synthetic_model_call')
        text=self.actions[self.index];self.index+=1
        return {'status':'completed','new_dispatch':True,'reused':False,'text':text,
            'request_id':'odoo-sel-'+sha256(self.attempt_id.encode()).hexdigest()[:10]+f'-00-{observation.step:03d}',
            'usage':{'input_tokens':10,'image_tokens':5,'output_tokens':5}}
    def __enter__(self):return self
    def __exit__(self,*args):
        self.close_calls+=1
        if not hasattr(self,'actor_clock'):return
        self.provider_close_reference=self.actor_clock.store.json('actor-clock/provider-close.private.json',
            {'status':'acknowledged','real_close_call_returned':True,'synthetic_provider_close_call_count':self.close_calls},'dispatch_receipt')


class ProductionPipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.root.chmod(0o700)
        self.case={**copy.deepcopy(CASE),'instruction':'Repair the native synthetic supplier prices','split':'selection'}
        self.task={k:self.case[k] for k in ('task_id','package_sha256')}
    def run_episode(self,**kwargs):
        runtime=Runtime(**kwargs);sampler=Sampler();output=self.root/('episode-'+str(len(list(self.root.iterdir()))));output.mkdir(mode=0o700)
        with patch('time.monotonic',lambda:runtime.page.tick):
            row=asyncio.run(actor.run_task(case=self.case,task=self.task,output=output,runtime=runtime,sampler=sampler,
                username=runtime.page.uid,attempt_id='synthetic-owned',paid_attempt_id='synthetic-paid'))
            sampler.__exit__(None,None,None)
        row.update(provider_close_ref=sampler.provider_close_reference,complete_lifecycle_wall_time_ms=row['lifecycle_wall_time_ms'])
        workers.write(output,'native-row.private.json',row)
        return output,row,runtime,sampler
    def test_original_score_guard_real_io_and_real_distinct_clone_reset_reopen(self):
        output,row,runtime,sampler=self.run_episode()
        reopened=audit.audit_episode(output,row)
        self.assertEqual(row['score'],1);self.assertEqual(row['action_count'],1)
        self.assertEqual(row['turn_count'],2);self.assertTrue(runtime.assert_removed);self.assertEqual(sampler.close_calls,1)
        self.assertEqual(runtime.events,['real_fixture_click_returned','saved_after_actor_end','actual_original_fresh_clone_reset'])
        self.assertEqual(len(reopened['clock']['native_io']),1)
    def test_safe_wrong_action_scores_zero_after_saved_reset(self):
        output,row,runtime,_=self.run_episode(positive=False)
        audit.audit_episode(output,row);self.assertEqual(row['score'],0);self.assertTrue(runtime.assert_removed)
    def test_missing_saved_and_reset_fail_without_outcome(self):
        for key in ('missing_saved','missing_reset'):
            with self.subTest(key=key),self.assertRaises(policy.GuardError):self.run_episode(**{key:True})
        self.assertFalse(any(self.root.glob('*/native-row.private.json')))
    def test_uncertain_native_io_is_preserved_and_reset_without_score_or_replay(self):
        with self.assertRaises(TimeoutError):self.run_episode(uncertain=True)
        files=list(self.root.glob('*/guard/turn-000/uncertain.private.json'));self.assertEqual(len(files),1)
        self.assertFalse(json.loads(files[0].read_bytes())['applied_inferred'])
        self.assertFalse(any(self.root.glob('*/saved-state.private.json')))
    def test_tampered_principal_target_reset_clock_or_driver_ref_refuses(self):
        output,row,_,_=self.run_episode()
        for name in ['saved-state.private.json','reset.private.json','actor-clock/end.private.json','guard/turn-000/observation-native.private.json','guard/turn-000/driver.private.json']:
            with self.subTest(name=name):
                path=output/name;raw=path.read_bytes();value=json.loads(raw)
                if name=='saved-state.private.json':value['snapshot']['database']['prices']['111']['price']='1.00'
                elif name=='reset.private.json':value['different_app_container_ids']=False
                elif name=='actor-clock/end.private.json':value['native_actions_after_deadline']=1
                elif 'observation-native' in name:value['native_username']='wrong-account'
                else:value['returned']=False
                path.write_bytes(final.canonical(value))
                with self.assertRaises((ValueError,KeyError)):audit.audit_episode(output,row)
                path.write_bytes(raw)
    def test_final_projection_unknown_invoice_keeps_actual_tokens_and_clock(self):
        output,row,_,_=self.run_episode()
        outer=self.root/'final';outer.mkdir(mode=0o700)
        # Move the whole retained episode only within this synthetic fixture.
        episode=outer/'native-episode';output.rename(episode)
        command={**self.task,'attempt_id':'synthetic-owned','expected_initial_state_sha256':actor.verify.canonical_sha(row['baseline']),
            'owner_slot':'shared-base','checkpoint_sha256':'a'*64}
        row.update(started_at=100,finished_at=101)
        value=workers.final_outcome(command,outer,episode,row)
        self.assertIsNone(value['cost_usd']);self.assertEqual(value['wall_time_ms'],row['actor_wall_time_ms'])
        usage=json.loads((outer/value['usage']['path']).read_bytes())
        self.assertEqual(usage['output_tokens'],10);self.assertEqual(len(usage['paid_calls']),2)
        self.assertTrue(all(r['paid_attempt_id']=='synthetic-paid' for r in usage['paid_calls']))
    def test_source_closure_covers_all_slots_and_constructors_do_not_launch(self):
        binding=workers.public_binding();self.assertTrue(binding['all_teacher_control_base_and_four_checkpoint_slots_same_source'])
        self.assertEqual(binding['old_control_credit'],0)
        with self.assertRaisesRegex(policy.GuardError,'real_v22_final_gate_required'):workers.FinalWorker(gate=object(),inputs=object())
        with self.assertRaisesRegex(policy.GuardError,'real_v22_frozen_study_required'):workers.SelectionWorker(study=object(),inputs=object())

if __name__=='__main__':unittest.main()
