"""Principal metadata epoch is uniform across every actor and saved decoder."""
import asyncio,json,tempfile,types,unittest
from hashlib import sha256
from pathlib import Path
from unittest.mock import AsyncMock,patch
from magento_catalog_factory import native_surface_workers_v9 as old,native_surface_workers_v10 as workers
from magento_catalog_factory import native_queue_runtime_v10 as runtime,native_surface_budget_performance_v10 as budget
from magento_catalog_factory import native_surface_teacher_v8 as teacher,native_surface_shared_base_v8 as shared
from magento_catalog_factory import native_surface_facade_v10 as controls,native_surface_actor_v6 as actor
from magento_catalog_factory import native_surface_adapter_v4 as adapter,native_surface_lease_v2 as lease
from magento_catalog_factory import native_surface_lease_v1 as old_lease,native_principal_header_v2 as principal
from magento_catalog_factory import native_reference_bulk_price_v6 as reference

def names(code):
    yield from code.co_names
    for value in code.co_consts:
        if isinstance(value,types.CodeType):yield from names(value)

class EpochTests(unittest.TestCase):
    def test_all_roles_and_original_saved_reader_use_current_source(self):
        self.assertIs(workers.Inputs.__init__.__globals__['Runtime'],runtime.Runtime)
        self.assertIs(workers.execute_owned.__globals__['run_task'],runtime.run_task)
        self.assertIs(teacher._impl.run_task,runtime.run_task)
        self.assertIs(shared._impl.audit_episode,budget.audit_episode)
        self.assertIs(teacher._impl.audit_episode,budget.audit_episode)
        self.assertIs(controls.run_controls.__globals__['audit_episode'],budget.audit_episode)
        self.assertIs(controls.run_controls.__globals__['ReferenceSampler'],reference.sampler)
        self.assertIs(actor.run_task.__globals__['NativeAdapter'],adapter.NativeAdapter)
        self.assertIs(actor.run_task.__globals__['LeaseBoundary'],lease.LeaseBoundary)
        self.assertIs(actor.run_task.__globals__['NATIVE_JS'],principal.NATIVE_JS)
        self.assertIs(workers._impl.verifier_sha256,budget.verifier_sha256)
        self.assertIn('native_surface_workers_v10',budget._impl.original_audit.__code__.co_names)
        for value in vars(workers._impl).values():
            methods=[value] if isinstance(value,types.FunctionType) else [v for v in vars(value).values() if isinstance(v,types.FunctionType)] if isinstance(value,type) else []
            for method in methods:
                self.assertNotIn('native_surface_budget_performance_v2',list(names(method.__code__)))
        with self.assertRaises(AttributeError):getattr(controls,'complete_saved_baseline_trio')

    def test_unchanged_actual_lease_pid_exe_and_budget_conditions(self):
        self.assertIs(lease.LeaseBoundary.check,old_lease.LeaseBoundary.check)
        self.assertIs(lease.LeaseBoundary.__init__,old_lease.LeaseBoundary.__init__)
        new=workers.public_binding();before=old.public_binding()
        for key in ['policy_sha256','profile','max_actions','actor_seconds','owned_lifecycle_seconds']:
            self.assertEqual(new[key],before[key])
        self.assertEqual(old.public_binding()['binding_sha256'],'8d432928d5ecabfa726f621054186412c53096e71199a73e17ebc07369e5ce72')
        self.assertEqual(new['old_principal_epoch_qualification_credit'],0)
        self.assertTrue(new['native_principal_source_changed'])
        for name in ['native_principal_header_v2.py','native_surface_adapter_v4.py','native_surface_lease_v2.py']:
            self.assertIn('magento_catalog_factory/'+name,new['source_sha256s'])

    def test_passive_queue_observes_new_principal_read_without_modifying_metadata(self):
        async def run():
            metadata={'schema':'synthetic-browser-test'};page=types.SimpleNamespace(evaluate=AsyncMock(return_value=metadata))
            queue=types.SimpleNamespace(observe=AsyncMock());proxy=runtime._impl.PassivePage(page,queue)
            result=await proxy.evaluate(principal.NATIVE_JS,[])
            self.assertIs(result,metadata);queue.observe.assert_awaited_once_with(metadata)
        asyncio.run(run())

    def test_saved_decoder_reopens_observation_and_predispatch_principal_witnesses(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'guard').mkdir()
            (root/'guard/held-lease.private.json').write_text(json.dumps({'native_username_sha256':sha256(b'admin').hexdigest()}))
            native={'native_username':'admin','account_witness':{'schema':'magento-current-document-rendered-principal-v2',
                'selector':principal.SELECTOR,'visible_count':1,'rendered_count':1,'total_match_count':1,
                'username':'admin','connected_current_document':True,'rendered_css_visible':True,
                'header_bounds':[20,-300,60,20],'in_viewport':False,'viewport_excluded_from_principal_predicate':True}}
            def ref(name,value):
                (root/name).write_text(json.dumps(value));return {'path':name}
            raw=ref('raw.json',native);envelope={'raw_envelope':raw}
            stored=ref('envelope.json',envelope);capsule=ref('capsule.json',{'observed':envelope,'current':envelope})
            audited={'frames':[{'native_envelope':stored}],'actions':[{'contract':{'native_surface_guard':capsule}}]}
            with patch.object(budget,'_original_queue_audit',return_value=audited),patch.object(budget._impl.policy,'verify_artifact') as verify:
                self.assertIs(budget.audit_episode(root,{},provider_close_required=False),audited)
                self.assertEqual(verify.call_count,5)
                native['account_witness']['total_match_count']=2;ref('raw.json',native)
                with self.assertRaises(Exception):budget.audit_episode(root,{},provider_close_required=False)

if __name__=='__main__':unittest.main()
