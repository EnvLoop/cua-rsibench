"""Real FinalGate/guard/loop/scorer; synthetic provider/native services only."""
from contextlib import contextmanager, ExitStack
import copy
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import factory
import gui_controls
import reset
import verify
import worker_lease
import partition_factory
from cursibench import full_study_final_dispatch_v1 as final, full_study_matrix_v1 as matrix
from enterprise_fallback.odoo18 import native_surface_final_worker_v22 as source, native_surface_workers_v13 as workers
from enterprise_fallback.odoo18 import native_service_readiness_v2 as readiness
from tests import test_full_study_final_dispatch_v1 as gate_fixture
from tests.test_odoo_native_surface_real_lease_v13 import NativePageFixture, native as fixture_native
from tests import test_odoo_fallback_factory as original_fixture


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    raw=final.canonical(value);final.private_write_new(path,raw)
    return sha256(raw).hexdigest()


class ProductionV22Tests(unittest.TestCase):
    def setUp(self):
        self.protocol=gate_fixture.FullStudyFinalDispatchTests();self.protocol.setUp();self.addCleanup(self.protocol.tearDown)
        from tests import v22_policy_runtime_fixture
        self.gate,_,_=v22_policy_runtime_fixture.final_gate(self.protocol);self.cell=next(row for row in self.gate.plan['cells'] if row['cell_id']==source.CELL)
        self.binding=workers.public_binding();self.binding_path=self.protocol.work/'odoo-v8-binding.private.json'
        self.binding_sha=save(self.binding_path,self.binding)
        self.source_path=self.protocol.work/'odoo-v8-final-source.private.json';self.source_sha=save(self.source_path,source.source_binding(workers.__name__))
        values={'runtime':self.binding['binding_sha256'],'verifier':self.binding['source_sha256s']['enterprise_fallback/odoo18/verify.py'],
            'source_snapshot':source.digest(final.canonical(source.study_source_snapshot(workers.__name__)))}
        for key,value in values.items():
            self.cell['matched_bindings'][key]=value
            for slot in [self.cell['base'],*self.cell['researcher_plans'].values()]:slot['bindings'][key]=value
        for slot in [self.cell['base'],*self.cell['researcher_plans'].values()]:
            slot['execution']['max_actions_per_task']=90;slot['execution']['max_wall_seconds_per_task']=720
        self.gate.frozen.ratification['cell_profiles'][source.CELL]['adapter_sha256']=self.binding['source_sha256s'][workers.ADAPTER_FILE]
        self.output=self.protocol.work/'odoo-final-output';self.output.mkdir(mode=0o700)
        self.worker_dir=self.protocol.work/'official_hidden';self.worker_dir.mkdir(mode=0o700)
        self.private=self.worker_dir/'private';self.private.mkdir(mode=0o700)
        (self.worker_dir/'.env').write_bytes(b'SYNTHETIC_SOURCE_FIXTURE=1');(self.worker_dir/'.env').chmod(0o600)
        (self.worker_dir/'compose.yaml').write_bytes((source.ROOT/'enterprise_fallback/odoo18/compose.yaml').read_bytes())
        self.cost_path=self.protocol.work/'odoo-local-cost.private.json'
        _,self.selection=workers._model_modules(self.binding)
        self.cost_sha=save(self.cost_path,{'schema':self.selection.LOCAL_COST_SCHEMA,'cell_id':source.CELL,
            'basis':'nominal_local_opportunity_cost_upper','hourly_usd_upper':'1','provider_invoice_usd':None,'lease_seconds':self.selection.LOCAL_LEASE_SECONDS})

    def factory(self,enabled=False):
        return source.final_worker_factory(gate=self.gate,native_binding_path=self.binding_path,native_binding_file_sha256=self.binding_sha,
            source_binding_path=self.source_path,source_binding_file_sha256=self.source_sha,worker_dir=self.worker_dir,
            final_output_root=self.output,local_cost_authority_path=self.cost_path,local_cost_authority_sha256=self.cost_sha,enable_live=enabled)

    def command(self,owner='shared-base'):
        task=next(row for chunk in self.cell['base']['chunks'] for row in chunk['tasks'])
        slot=self.cell['base'] if owner=='shared-base' else self.cell['researcher_plans'][owner]
        sampler=None if owner=='shared-base' else 'tinker://synthetic/sampler_weights/source-only-v8'
        if owner!='shared-base':
            self.cell['execution_evidence_owner_by_slot'][owner]=owner
            slot['bindings']['checkpoint']=source.digest(sampler.encode())
        attempt=f'final-{matrix.CELLS.index(source.CELL):02d}-{owner}-000-0'
        command={'schema':final.COMMAND_SCHEMA,'study_id':self.gate.plan['study_id'],'cell_id':source.CELL,'owner_slot':owner,
            'task_id':task['task_id'],'package_sha256':task['package_sha256'],'checkpoint_sha256':slot['bindings']['checkpoint'],
            'sampler_path':sampler,'expected_initial_state_sha256':self.gate.initial_state_by_task[source.CELL][task['task_id']],
            'attempt_id':attempt,'retry_index':0,'retry_rule_sha256':None,'action_profile':'scale-action-profile-v0.6.6',
            'sampling':slot['sampling'],'max_actions':90,'max_wall_seconds':720,'matched_bindings':self.cell['matched_bindings'],'reserve_usd':'1'}
        out=self.output/attempt;out.mkdir(mode=0o700);return command,out

    def reserve(self,command):
        category='shared_base_final' if command['owner_slot']=='shared-base' else 'selected_final'
        self.gate.budget.reserve(command['attempt_id'],source.CELL+':'+command['owner_slot'],category,command['reserve_usd'],source.digest(final.canonical(command)))
        self.gate.budget.mark_dispatched(command['attempt_id'],source.digest(final.canonical(command)))

    def test_metadata_only_constructor_and_mandatory_gate_source_snapshot(self):
        with patch.object(source,'_modules',side_effect=AssertionError('hidden lookup')),patch.object(partition_factory,'source_asset',side_effect=AssertionError('case body')):
            worker=self.factory();self.assertEqual(worker.identity['runtime_sha256'],self.binding['binding_sha256'])
        command,out=self.command()
        with self.assertRaisesRegex(source.OdooFinalWorkerError,'explicit_live'):worker.run_once(command,out)
        self.cell['matched_bindings']['source_snapshot']='0'*64
        with self.assertRaisesRegex(source.OdooFinalWorkerError,'supplemental_source_not_frozen'):self.factory()
        with self.assertRaisesRegex(source.OdooFinalWorkerError,'v22_final_gate'):
            source.final_worker_factory(gate=object(),native_binding_path=self.binding_path,native_binding_file_sha256=self.binding_sha,
                source_binding_path=self.source_path,source_binding_file_sha256=self.source_sha,worker_dir=self.worker_dir,
                final_output_root=self.output,local_cost_authority_path=self.cost_path,local_cost_authority_sha256=self.cost_sha)

    def test_explicit_epoch_cannot_override_hashed_native_profile(self):
        self.assertEqual(source.module_from_binding(self.binding),workers.__name__)
        with self.assertRaisesRegex(source.OdooFinalWorkerError,'explicit_native_module_mismatched'):
            source.module_from_binding(self.binding,'enterprise_fallback.odoo18.native_surface_workers_v9')
        with self.assertRaisesRegex(source.OdooFinalWorkerError,'unregistered'):
            source.module_from_binding({**self.binding,'profile':'native-owned-surface-safety-envelope-v7'})
        with self.assertRaisesRegex(source.OdooFinalWorkerError,'unregistered'):
            source._worker_module('another_package.provider')

    def test_wrong_task_checkpoint_nonce_policy_and_missing_reservation_stop_before_body(self):
        worker=self.factory(True);command,out=self.command()
        with self.assertRaisesRegex(source.OdooFinalWorkerError,'dispatched_reservation'):worker._command(command,out)
        self.reserve(command)
        worker._command(command,out)
        for field,value in [('task_id','outside-workspace'),('package_sha256','0'*64),('checkpoint_sha256','0'*64),('max_actions',91),('sampling',{}),('sampler_path','tinker://fake/sampler_weights/unbound'),('owner_slot','wrong'),('cell_id','gitlab')]:
            with self.subTest(field=field),patch.object(source,'_modules',side_effect=AssertionError('hidden lookup')):
                with self.assertRaises(source.OdooFinalWorkerError):worker.run_once({**command,field:value},out)
        with self.assertRaises(source.OdooFinalWorkerError):worker.run_once({**command,'unknown_field':True},out)
        with patch.object(worker,'_episode',side_effect=TimeoutError('synthetic unknown provider IO')) as episode:
            with self.assertRaises(TimeoutError):worker.run_once(command,out)
            with self.assertRaisesRegex(ValueError,'private_output_exists'):worker.run_once(command,out)
            self.assertEqual(episode.call_count,1)

    @contextmanager
    def production_fixture(self,command,*,positive=True,missing_reset=False,uncertain=False,missing_saved=False,budget_unknown=False):
        check=original_fixture.IndependentEvaluatorTests();check.setUp();baseline=copy.deepcopy(check.baseline)
        baseline['orders'][0]['name']=command['task_id']
        target={'lines':[{'line_id':1,'product_id':10,'expected':{'qty':2,'price':10.0,'date':'2025-01-01'}}]}
        cases=[]
        identities=[row for chunk in self.cell['base']['chunks'] for row in chunk['tasks']]
        for i,row in enumerate(identities):
            family=('purchase','inventory','sales','crm')[i//25]
            cases.append({'id':row['task_id'],'family':family,'prompt':'Repair the visible synthetic request.',
                'order_date':'2025-01-01','vendor':'Synthetic supplier','lines':[{'sku':'EL-SYNTHETIC','name':'Synthetic item','expected':{'qty':2,'price':10.0,'date':'2025-01-01'}}]})
        asset=b'synthetic source-only package asset'
        case=cases[0]
        package=source.digest(json.dumps(case,sort_keys=True).encode()+b'\n'+asset)
        identities[0]['package_sha256']=package;command['package_sha256']=package
        command['expected_initial_state_sha256']=source.digest(self.selection._canonical(baseline))
        self.gate.initial_state_by_task[source.CELL][command['task_id']]=command['expected_initial_state_sha256']
        save(self.private/'task_set_manifest.json',{'official':identities,'train':[],'selection':[]})
        save(self.private/'partition_cases.json',{'cases':{family:[c for c in cases if c['family']==family] for family in ('purchase','inventory','sales','crm')}})
        save(self.private/'development_gold.json',{command['task_id']:target})
        save(self.private/'baseline_snapshot.json',baseline)
        checksum=baseline['attachments'][0]['checksum'];files={'filestore/bench/'+checksum[:2]+'/'+checksum:'a'*64}
        save(self.private/'baseline-filestore-manifest.json',files)
        save(self.private/'checkpoint_receipt.json',{'db_sha256':'a'*64,'filestore_sha256':'b'*64})
        save(self.private/'actor_credentials.json',{'login':'synthetic actor','password':'synthetic fixture only'})
        events=[];business=copy.deepcopy(baseline);page=NativePageFixture();page.when_wait=lambda _n:None
        oldclick=page.click
        def click(x,y):
            oldclick(x,y);events.append('native_click_returned')
            if positive:business['lines'][0]['price']='10.00'
        page.mouse.click=click
        restore_count=[0]
        def restore():
            restore_count[0]+=1
            events.append('cold_reset');business.clear();business.update(copy.deepcopy(baseline))
            bad=missing_reset and restore_count[0]>=2
            return {'business_snapshot_equal':not bad,'physical_filestore_equal_before_web_restart':not bad}
        class Browser:
            def new_page(self,**_):return page
            def close(self):events.append('native_browser_closed')
        class Playwright:
            def __enter__(self):self.chromium=SimpleNamespace(launch=lambda **_:Browser());return self
            def __exit__(self,*_):return False
        current_native=workers.common_adapter_class().__module__
        import importlib
        native_module=importlib.import_module(current_native)
        old_evaluate=page.evaluate
        def evaluate(script,args=None):
            if script==native_module.BUSY_JS:
                value=old_evaluate(fixture_native.BUSY_JS,args)
                value['schema']='odoo-generic-native-loading-v13';return value
            if script==native_module.VISIBLE_CONTROLS_JS:return old_evaluate(fixture_native.VISIBLE_CONTROLS_JS,args)
            if script==native_module.NATIVE_CONTEXT_JS:
                value=old_evaluate(fixture_native.NATIVE_CONTEXT_JS,args)
                value['schema']='odoo-current-native-surface-v13';return value
            return old_evaluate(script,args)
        page.evaluate=evaluate
        page.goto=lambda url:setattr(page,'url',url)
        page.locator=lambda _:SimpleNamespace(wait_for=lambda:None)
        page.reload=lambda **_:events.append('native_reload')
        class Sampler:
            def __init__(self,**kwargs):self.kwargs=kwargs;self.count=0;self.attempt_id=kwargs["attempt_id"]
            def __enter__(self):events.append(('sampler_open',self.kwargs['checkpoint_path'],self.kwargs['base_mode']));return self
            def __exit__(self,*_):
                events.append('provider_close_ack')
                if not hasattr(self,'actor_clock'):return
                self.provider_close_reference=self.actor_clock.store.json('actor-clock/provider-close.private.json',{'status':'acknowledged','real_close_call_returned':True,'automatic_model_retries':0,'new_model_requests':0},'dispatch_receipt')
                if missing_saved:
                    (self.kwargs['output_root']/'saved-state.private.json').unlink()
            def sample(self,observation,**kwargs):
                self.count+=1;events.append('provider_sample');page.tick+=0.02
                if uncertain:raise TimeoutError('synthetic uncertain provider completion')
                self.assert_no_hidden(observation)
                journal=kwargs['task_dir']/'sampling-journal'/'requests.sqlite3'
                journal.parent.mkdir(exist_ok=True,mode=0o700);journal.write_bytes(b'synthetic durable provider request');journal.chmod(0o600)
                return {'status':'completed','text':'{"type":"click","target":{"x":350,"y":50}}' if self.count==1 else '{"type":"finish"}',
                    'new_dispatch':True,'reused':False,'request_id':'odoo-sel-'+source.digest(self.attempt_id.encode())[:10]+f'-00-{observation.step:03d}','error_subtype':None,
                    'usage':{'input_tokens':100,'image_tokens':30,'output_tokens':10}}
            @staticmethod
            def assert_no_hidden(observation):
                assert observation.instruction=='Repair the visible synthetic request.'
                assert 'development_gold' not in observation.instruction
        if budget_unknown:
            from enterprise_fallback.odoo18.odoo_actor_transport_v1 import sampler_class
            from tests.test_scale_vision_proxy import FakeBackend
            clock_sampler=sampler_class(self.selection)
            class Sampler(clock_sampler):
                def __enter__(self):
                    self.lifecycle_started_monotonic=page.tick
                    self.backend=FakeBackend();self.backend.text='{"type":"finish"}'
                    class Service:
                        def close(self,_status):
                            return SimpleNamespace(result=lambda **_:events.append('provider_close_ack'))
                    self.service=Service()
                    return self
                def sample(self,observation,**kwargs):
                    events.append('provider_sample')
                    page.tick=self.actor_clock.deadline-.25
                    backend=self.backend
                    def submit(*_args):
                        class Future:
                            def result(self,timeout=None):
                                page.tick+=timeout
                                raise TimeoutError('synthetic clipped request still unknown')
                        return Future()
                    backend.submit=submit
                    result=super().sample(observation,**kwargs)
                    return result
        config={'ODOO_PORT':'8069','ODOO_PROJECT':'source_fixture','ODOO_PARTITION':'official_hidden'}
        training={'model':'Qwen/Qwen3.8-27B','seed':0,'action_profile':'scale-action-profile-v0.6.6','sample_max_tokens':256,
            'prefill_usd_per_million_tokens':'1','sample_usd_per_million_tokens':'2','billing_multiplier_upper':'1'}
        def ready(**kwargs):
            events.append('native_generic_service_ready');kwargs['receipt_sink']({'schema':'synthetic-readiness-fixture','worker':str(self.worker_dir)})
        with ExitStack() as stack:
            for module,attr,value in [(factory,'HERE',self.worker_dir),(factory,'PRIVATE',self.private),(reset,'HERE',self.worker_dir),
                (reset,'PRIVATE',self.private),(verify,'PRIVATE',self.private),(gui_controls,'PRIVATE',self.private),(worker_lease,'PRIVATE',self.private)]:
                stack.enter_context(patch.object(module,attr,value.resolve()))
            stack.enter_context(patch.object(factory,'local_config',return_value=config))
            stack.enter_context(patch.object(reset,'restore',side_effect=restore))
            stack.enter_context(patch.object(reset,'filestore_manifest',return_value=files))
            stack.enter_context(patch.object(verify,'snapshot',side_effect=lambda:copy.deepcopy(business)))
            stack.enter_context(patch.object(verify,'attachment_store_paths',return_value={'1':checksum[:2]+'/'+checksum}))
            stack.enter_context(patch.object(gui_controls,'browser_login',side_effect=lambda *args:events.append('native_login')))
            stack.enter_context(patch.object(partition_factory,'source_asset',return_value=asset))
            stack.enter_context(patch.object(self.selection.RealOdooSelectionEnvironment,'_running',return_value={'db','web'}))
            stack.enter_context(patch.object(self.selection.RealOdooSelectionEnvironment,'_compose',side_effect=AssertionError('unexpected native compose in fixture')))
            stack.enter_context(patch.object(readiness,'ensure_ready',side_effect=ready))
            stack.enter_context(patch.object(self.selection,'RealTinkerSelectionSampler',Sampler))
            stack.enter_context(patch.object(self.gate.frozen,'student_training_configuration',return_value=(training,'c'*64)))
            stack.enter_context(patch.object(source.runtime_gate,'pre_dispatch',return_value=None))
            stack.enter_context(patch.object(workers,'audit_readiness_receipt',side_effect=lambda path,*_:json.loads(path.read_bytes())))
            stack.enter_context(patch('playwright.sync_api.sync_playwright',return_value=Playwright()))
            stack.enter_context(patch.dict('os.environ',{'TINKER_API_KEY':'synthetic source fixture'}))
            stack.enter_context(patch('time.monotonic',lambda:page.tick))
            yield events,business


    def validate_controller(self,worker,outcome,command,out):
        from cursibench import full_study_final_performance_v2 as current
        peers={cell_id:gate_fixture.FakeTrustedWorker(next(r for r in self.gate.plan['cells'] if r['cell_id']==cell_id)) for cell_id in matrix.CELLS}
        peers[source.CELL]=worker
        sampler=json.loads(self.protocol.sampler_path.read_bytes());sampler['matrix_plan_sha256']=self.gate.plan_sha256
        path=self.protocol.work/'actual-v22-samplers.private.json';save(path,sampler)
        controller=current.FinalController(self.gate,workers=peers,sampler_bindings_path=path,output_dir=self.protocol.work/'checked-v22-output')
        checked,_=controller._validate_outcome(outcome,command,out,outcome['lifecycle_wall_time_ms'])
        self.assertIsNone(checked['cost']);self.assertEqual(checked['value']['score'],outcome['score'])
        return controller

    def test_real_v22_native_actor_saved_reset_unknown_invoice_and_current_gate_projection(self):
        command,out=self.command()
        with self.production_fixture(command) as (events,business):
            worker=self.factory(True);self.reserve(command);outcome=worker.run_once(command,out)
        self.assertEqual(outcome['score'],1);self.assertIsNone(outcome['cost_usd'])
        self.assertEqual(outcome['action_count'],1);self.assertEqual(outcome['turn_count'],2)
        self.assertEqual(events[-1],'provider_close_ack')
        actor=json.loads((out/'native-episode/actor-clock/end.private.json').read_bytes())
        life=json.loads((out/'native-episode/actor-clock/complete-lifecycle.private.json').read_bytes())
        self.assertEqual(actor['actor_deadline_monotonic']-actor['actor_started_monotonic'],720)
        self.assertTrue(life['saved_readback_reset_and_provider_close_complete'])
        self.assertEqual(actor['native_actions_after_deadline'],0)
        usage=json.loads((out/'usage.private.json').read_bytes());self.assertIsNone(usage['cost_usd'])
        self.assertEqual(len(usage['paid_calls']),2);self.assertTrue(all(r['paid_attempt_id']==command['attempt_id'] for r in usage['paid_calls']))
        self.assertEqual(outcome['wall_time_ms'],round(actor['actor_elapsed_seconds']*1000))
        self.assertIsNone(outcome['budget_performance'])
        self.validate_controller(worker,outcome,command,out)

    def test_actual_unknown_deadline_saved_scored_reset_and_provider_close(self):
        command,out=self.command()
        with self.production_fixture(command,budget_unknown=True) as (events,business):
            worker=self.factory(True);self.reserve(command);outcome=worker.run_once(command,out)
        self.assertEqual(outcome['score'],0);self.assertIsNone(outcome['cost_usd'])
        self.assertEqual(outcome['wall_time_ms'],720000);self.assertEqual(outcome['action_count'],0)
        self.assertIsNotNone(outcome['budget_performance'])
        proof=json.loads((out/outcome['budget_performance']['path']).read_bytes())
        self.assertFalse(proof['receipt']['inference']['unknown_response_is_completed'])
        self.assertTrue(proof['receipt']['provider_close_acknowledged'])
        self.assertEqual(proof['receipt']['sample_paid_attempt_id'],command['attempt_id'])
        controller=self.validate_controller(worker,outcome,command,out)
        self.assertEqual(controller._last_inference['model_completion_unknown_count'],1)

    def test_real_loop_missing_reset_saved_and_uncertain_io_never_emit_final_outcome(self):
        for mode in ('missing_reset','missing_saved','uncertain'):
            with self.subTest(mode=mode):
                # Each consumed failure is isolated; no paid/native request is replayed.
                test=ProductionV22Tests('test_actual_unknown_deadline_saved_scored_reset_and_provider_close')
                test.setUp()
                try:
                    command,out=test.command()
                    with test.production_fixture(command,**{mode:True}) as (events,_):
                        worker=test.factory(True);test.reserve(command)
                        with self.assertRaises(Exception):worker.run_once(command,out)
                        with self.assertRaises(ValueError):worker.run_once(command,out)
                    self.assertIn('provider_close_ack',events)
                    self.assertFalse((out/'independent-verifier.private.json').exists())
                finally:test.doCleanups()


if __name__=='__main__':unittest.main()
