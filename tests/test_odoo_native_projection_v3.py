"""Native-witness regression plus reused v2 seams, with no native/model calls."""
from __future__ import annotations
import copy
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
from types import ModuleType
import unittest
from unittest.mock import patch
from PIL import Image

from cursibench.scale_action_contract import ContractError
from enterprise_fallback.odoo18 import odoo_native_geometry_material_v2 as old_geometry
from enterprise_fallback.odoo18 import odoo_native_geometry_material_v3 as geometry
from enterprise_fallback.odoo18 import odoo_v066_native_material_adapter_v3 as adapter
from enterprise_fallback.odoo18 import native_material_workers_v2 as old_workers
from enterprise_fallback.odoo18 import native_material_workers_v3 as workers_facade
from tools import odoo_v066_native_material_qualification_v3 as qualification_facade

ROOT=Path(__file__).resolve().parents[1]
workers=workers_facade._impl
qualification=qualification_facade._impl


def test_module(relative, name, replacements):
    source=(ROOT/relative).read_text()
    for before,after in replacements:source=source.replace(before,after)
    module=ModuleType(name);module.__file__=str(ROOT/relative)
    exec(compile(source,module.__file__,'exec'),module.__dict__)
    return module


fixture=test_module('tests/test_odoo_v066_native_material_adapter_v2.py','_v3_adapter_fixture',[
    ('odoo_v066_native_material_adapter_v2','odoo_v066_native_material_adapter_v3'),
    ('odoo_native_geometry_material_v2','odoo_native_geometry_material_v3')])
worker_tests=test_module('tests/test_odoo_native_material_workers_v2.py','_v3_worker_tests',[
    ('native_material_workers_v2 as workers','native_material_workers_v3 as workers')])
worker_tests.workers=workers
worker_tests.fixture=lambda:fixture
qualification_tests=test_module('tests/test_odoo_native_material_qualification_v2.py','_v3_qualification_tests',[
    ('native_material_workers_v2 as workers','native_material_workers_v3 as workers'),
    ('odoo_v066_native_material_qualification_v2 as qualification','odoo_v066_native_material_qualification_v3 as qualification'),
    ('"v066_native_material_controls_v2"','"v066_native_material_controls_v3"')])
qualification_tests.workers=workers;qualification_tests.qualification=qualification
qualification_tests.fake_train_proof=worker_tests.fake_train_proof


def native_geometry(bottom=865.03125):
    value=fixture.geometry()
    value['form_bounds']=[0,46,1440,1000]
    value['sheet']['bounds']=[16,153.75,1424,bottom]
    value['selected_tab']['bounds']=[41,380.9375,133.109375,419.9375]
    return value


def changed_pixel(raw,point,color):
    with Image.open(BytesIO(raw)) as source:image=source.copy()
    image.putpixel(point,color);output=BytesIO();image.save(output,'PNG')
    return output.getvalue()


class ProjectionV3Tests(unittest.TestCase):
    def test_only_finite_proven_phases_and_v2_integer_profile_project(self):
        for bottom in (844.03125,865.03125,907.03125):
            points=geometry.projected_points(native_geometry(bottom))
            self.assertEqual(points['top'],[[16,155],[16,157],[17,157]])
            self.assertEqual(points['bottom'][0],[16,int(bottom)-4])
            self.assertEqual(points['selected_tab'],[[41,419],[132,419]])
        self.assertEqual(geometry.projected_points(fixture.geometry()),old_geometry.projected_points(fixture.geometry()))
        for element,index,phase in (('sheet',0,.5),('sheet',1,.5),('sheet',3,.5),
                                    ('selected_tab',0,.5),('selected_tab',2,.5),('selected_tab',3,.5),
                                    ('sheet',1,.25),('selected_tab',2,.125)):
            value=native_geometry();value[element]['bounds'][index]=int(value[element]['bounds'][index])+phase
            self.assertIsNone(geometry.projected_points(value))
        value=native_geometry();value['sheet']['style']['backgroundColor']='rgb(254, 255, 255)'
        self.assertIsNone(geometry.projected_points(value))

    def test_all_existing_whole_rgb_vectors_still_exact_and_business_pixel_protected(self):
        geo=native_geometry()
        identities=set()
        for top in range(2):
            for bottom in range(2):
                for tab in range(2):
                    raw=fixture.png(top,bottom,geo=geo,tab=tab)
                    result=geometry.border_material(raw,geo);self.assertIsNotNone(result)
                    identities.add(result['canonical_material_sha256'])
                    other=geometry.border_material(changed_pixel(raw,(810,480),(1,2,3)),geo)
                    self.assertNotEqual(other['canonical_material_sha256'],result['canonical_material_sha256'])
        self.assertEqual(len(identities),1)
        raw=fixture.png(geo=geo)
        self.assertIsNone(geometry.border_material(changed_pixel(raw,(41,419),(235,237,239)),geo))
        self.assertIsNone(geometry.border_material(changed_pixel(raw,(16,155),(246,247,249)),geo))

    def test_v2_credit_and_source_drift_refused_with_uniform_all_worker_paths(self):
        binding=workers.public_binding();workers.validate_binding(binding)
        self.assertEqual(binding['profile'],adapter.PROFILE)
        self.assertIs(workers.common_adapter_class(),adapter.OdooV066NativeMaterialAdapter)
        teacher,selection=workers._model_modules(binding)
        self.assertIs(teacher.OdooV066TrainAdapter,adapter.OdooV066NativeMaterialAdapter)
        self.assertIs(selection.OdooV066TrainAdapter,adapter.OdooV066NativeMaterialAdapter)
        proof=worker_tests.fake_train_proof(old_workers.public_binding())
        proof['schema']=old_workers.TRAIN_CONTROL_SCHEMA
        with self.assertRaises(workers.NativeMaterialWorkerError):workers.validate_train_control(proof,binding)
        bad=copy.deepcopy(binding);bad['source_sha256s']['enterprise_fallback/odoo18/odoo_native_geometry_material_v3.py']='0'*64
        with self.assertRaises(workers.NativeMaterialWorkerError):workers.validate_binding(bad)
        plan,_=qualification.prepare(qualification_tests.roster('train'))
        self.assertEqual(plan['tasks'],qualification_tests.roster('train')['tasks'])
        self.assertTrue(plan['fresh_run_directory_name'].startswith('native-v3-'))
        self.assertEqual(plan['old_positive_credit'],0)
        self.assertEqual(plan['native_worker_binding']['profile'],adapter.PROFILE)

    def test_cached_compatibility_cannot_freeze_or_audit_changed_v2_source(self):
        original=Path.read_bytes
        target=ROOT/'enterprise_fallback/odoo18/odoo_native_geometry_material_v2.py'
        def changed(path):return b'changed_source = True\n' if path==target else original(path)
        with patch.object(Path,'read_bytes',changed):
            with self.assertRaisesRegex(ValueError,'frozen_v2_source_changed'):workers.public_binding()
            with self.assertRaisesRegex(ValueError,'frozen_v2_source_changed'):
                geometry.border_material(fixture.png(),fixture.geometry())

    @unittest.skipUnless(os.environ.get('ODOO_NATIVE_V3_ACTUAL_FAILURE_DIR'),'Retained native witness path not supplied')
    def test_actual_native_witness_raw_pairs_and_three_stage_guard_reopening(self):
        root=Path(os.environ['ODOO_NATIVE_V3_ACTUAL_FAILURE_DIR'])
        trace=json.loads((root/'gui_trace.json').read_bytes())
        rows=[row for row in trace['exact_return_guard_samples'] if row['step']==8]
        self.assertEqual(len(rows),2)
        context=rows[0]['sample_native_context'];self.assertEqual(context,rows[1]['sample_native_context'])
        geo=context['native_geometry'];self.assertEqual(geo['sheet']['bounds'],[16,153.75,1424,865.03125])
        observed=(root/'frames'/'step-008.png').read_bytes()
        alternate=(root/'frames'/'guard-0049.png').read_bytes()
        rejected=(root/'frames'/'step-008-rejected-current.png').read_bytes()
        self.assertEqual(sha256(observed).hexdigest(),'c4153f543872da0a92d19dd7e5fe15d241c2eeb8379006a6a120760b41c91981')
        self.assertEqual(sha256(alternate).hexdigest(),'12867e3c62f8b5865ff5801d416989123de33bcc5fbbf538889557d37436de5b')
        self.assertEqual(sha256(rejected).hexdigest(),'5980f2ac9762cd6dafd4aba8aa330ea77aa70b47c54e9e78e7a88229e0d455e5')
        self.assertIsNone(old_geometry.border_material(observed,geo))
        material=[geometry.border_material(raw,geo) for raw in (observed,alternate,rejected)]
        self.assertEqual(len({row['canonical_material_sha256'] for row in material}),1)
        self.assertEqual([row['whole_state_index'] for row in material],[4,0,6])
        counts={'no_projection':0,'finite':0,'strict_invalid':0}
        for row in trace['exact_return_guard_samples']:
            g=row['sample_native_context']['native_geometry'];raw=(root/row['sampled_frame_ref']['path']).read_bytes()
            key='no_projection' if geometry.projected_points(g) is None else 'finite' if geometry.border_material(raw,g) is not None else 'strict_invalid'
            counts[key]+=1
        self.assertEqual(counts,{'no_projection':18,'finite':20,'strict_invalid':12})
        page,a,raws=fixture.setup();original=page.evaluate;capture=[0]
        def evaluate(script,args=None):
            if script==adapter.NATIVE_CONTEXT_JS:return copy.deepcopy(context)
            return original(script,args)
        def screenshot(**_kwargs):
            index=capture[0];capture[0]+=1
            return (observed,alternate,rejected)[0 if index<2 else (index-2)%3]
        page.evaluate=evaluate;page.screenshot=screenshot
        page.url='http://127.0.0.1:8069'+context['route_path']
        obs,_=a.observe_for_model();action=a.parse_current_action('{"type":"key","key":"Control+A"}')
        receipt=a.dispatch(action)['public_contract_receipt']
        for stage in ('parse','dispatch'):
            guard=receipt['native_material_'+stage+'_guard']
            self.assertEqual(guard['mode'],'finite_rfq_material')
            self.assertEqual(adapter.audit_guard(guard,obs.screenshot_bytes,lambda ref:raws[ref['path']],action=action)['raw_guard_pngs_reopened'],3)
        protected=geometry.border_material(changed_pixel(alternate,(810,480),(1,2,3)),geo)
        self.assertNotEqual(protected['canonical_material_sha256'],material[0]['canonical_material_sha256'])
        page,a,_=fixture.setup();page.geometry=native_geometry();a.observe_for_model()
        action=a.parse_current_action('{"type":"key","key":"Control+A"}')
        page.geometry['sheet']['bounds'][3]+=1
        with self.assertRaises(ContractError):a.dispatch(action)


def load_tests(_loader, _tests, _pattern):
    suite=unittest.TestSuite()
    for module in (fixture,worker_tests,qualification_tests):suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(ProjectionV3Tests))
    return suite
