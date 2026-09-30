"""Typed resources, bounded getter behavior and retained original-worker DOM."""
import copy
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from enterprise_fallback.odoo18 import odoo_native_principal_witness_v7 as witness
from enterprise_fallback.odoo18 import odoo_v066_native_surface_adapter_v7 as native


def record(resource='res.partner',identity='17'):
    url=f'http://127.0.0.1:8092/web/image/{resource}/{identity}/avatar_128?unique=cache-key'
    return {'selector':witness.SELECTOR,'total':1,'visible_count':1,'nodes':[
        {'src':url,'current_src':url,'visible':True,'complete':True,'natural_width':28}]}


class PrincipalWitnessTests(unittest.TestCase):
    def test_native_partner_and_user_resources_are_typed_never_interchanged(self):
        for model in ('res.partner','res.users'):
            self.assertEqual(witness.principal_from_witness(record(model),'http://127.0.0.1:8092'),model+':17')
            self.assertEqual(witness.parse_resource(f'http://127.0.0.1:8092/web/image?model={model}&id=17&field=avatar_128','http://127.0.0.1:8092'),model+':17')
        self.assertNotEqual(witness.principal_from_witness(record(),'http://127.0.0.1:8092'),'res.users:17')

    def test_foreign_origin_unsupported_model_field_ids_and_duplicate_query_refused(self):
        for url in ('https://foreign.invalid/web/image/res.partner/17/avatar_128',
            'http://127.0.0.1:8092/web/image/res.company/17/avatar_128',
            'http://127.0.0.1:8092/web/image/res.partner/0/avatar_128',
            'http://127.0.0.1:8092/web/image/res.partner/17/image_1920',
            'http://127.0.0.1:8092/web/image?model=res.partner&id=17&id=18&field=avatar_128',
            'http://user:secret@127.0.0.1:8092/web/image/res.partner/17/avatar_128',
            'data:image/png;base64,fixture'):
            self.assertIsNone(witness.parse_resource(url,'http://127.0.0.1:8092'))

    def test_absent_multiple_invisible_loading_or_mismatched_current_resource_fail_closed(self):
        for change in ('absent','multiple','invisible','loading','empty','mismatch','bool_count'):
            item=record()
            if change=='absent':item.update(total=0,visible_count=0,nodes=[])
            elif change=='multiple':item.update(total=2,visible_count=2,nodes=item['nodes']*2)
            elif change=='invisible':item['nodes'][0]['visible']=False
            elif change=='loading':item['nodes'][0]['complete']=False
            elif change=='empty':item['nodes'][0]['natural_width']=0
            elif change=='mismatch':item['nodes'][0]['current_src']=item['nodes'][0]['src'].replace('/17/','/18/')
            else:item['visible_count']=True
            self.assertIsNone(witness.principal_from_witness(item,'http://127.0.0.1:8092'))

    def test_bounded_passive_getter_retains_missing_metadata_before_constructor(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);root.chmod(0o700)
            actor=object.__new__(native.OdooV066NativeSurfaceAdapter)
            actor.store=None;actor.latest=None;actor.started=0;actor.clock=lambda:1;waits=[]
            actor.page=SimpleNamespace(url='http://127.0.0.1:8092/odoo/purchase',wait_for_timeout=waits.append)
            absent={'app_shell':False,'visible':True,'top_window':True,'account_principal':'',
                    'principal_witness':{'selector':witness.SELECTOR,'total':0,'visible_count':0,'nodes':[]}}
            ready={'app_shell':True,'visible':True,'top_window':True,'account_principal':'res.partner:17','principal_witness':record()}
            snapshots=iter([absent,ready]);actor._meta=lambda:copy.deepcopy(next(snapshots))
            made=[]
            def constructor(**kwargs):
                made.append(kwargs)
                return SimpleNamespace(owns=lambda page,meta:True)
            with patch.object(native._impl,'OdooLeaseEvidence',side_effect=constructor):actor.bind_guard(root,root)
            self.assertEqual(len(made),1);self.assertEqual(made[0]['account_principal'],'res.partner:17')
            self.assertEqual(waits,[120])
            self.assertEqual(len(list(root.glob('surface-guard/principal-readiness-*.private.json'))),2)
            self.assertEqual(json.loads((root/'surface-guard/principal-readiness-00.private.json').read_bytes())['principal_witness']['total'],0)

    def test_missing_native_principal_is_not_inferred_from_credentials_and_exhaustion_is_saved(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);root.chmod(0o700);actor=object.__new__(native.OdooV066NativeSurfaceAdapter)
            actor.store=None;actor.latest=None;actor.started=0;actor.clock=lambda:1;waits=[]
            actor.page=SimpleNamespace(url='http://127.0.0.1:8092/odoo/purchase',wait_for_timeout=waits.append)
            actor._meta=lambda:{'app_shell':True,'visible':True,'top_window':True,'account_principal':'',
                'principal_witness':{'selector':witness.SELECTOR,'total':0,'visible_count':0,'nodes':[]}}
            with patch.object(native._impl,'OdooLeaseEvidence') as constructor:
                with self.assertRaisesRegex(ValueError,'guard_native_account_binding_missing'):actor.bind_guard(root,root)
                constructor.assert_not_called()
            self.assertEqual(len(waits),7);self.assertEqual(sum(waits),sum(witness.READINESS_DELAYS_MS))
            self.assertEqual(len(list(root.glob('surface-guard/principal-readiness-*.private.json'))),8)

    @unittest.skipUnless(os.environ.get('ODOO_V7_NATIVE_GETTER_DIR'),'Actual read-only native getter samples not supplied')
    def test_actual_original_train_native_getter_snapshots_all_parse_without_api_queries(self):
        root=Path(os.environ['ODOO_V7_NATIVE_GETTER_DIR']);files=sorted(root.glob('sample-*.private.json'))
        self.assertEqual(len(files),8)
        for file in files:
            sample=json.loads(file.read_bytes());meta=sample['new_v7_metadata']
            self.assertEqual(meta['account_principal'],'res.partner:17')
            self.assertEqual(witness.principal_from_witness(meta['principal_witness'],'http://127.0.0.1:8092'),'res.partner:17')
        terminal=json.loads((root/'terminal.private.json').read_bytes())
        self.assertTrue(terminal['services_restored']);self.assertEqual(terminal['task_edits'],0)
        self.assertEqual(terminal['provider_calls'],0)


if __name__=='__main__':unittest.main()
