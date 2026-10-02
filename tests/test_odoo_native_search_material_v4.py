"""Raw finite vectors and common native dispatch; no browser/provider calls."""
import copy
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import unittest
from PIL import Image,ImageChops
from cursibench.scale_action_contract import ContractError
from enterprise_fallback.odoo18 import odoo_native_search_material_v4 as material
from enterprise_fallback.odoo18 import odoo_v066_native_material_adapter_v4 as adapter
from enterprise_fallback.odoo18 import native_material_workers_v3 as old_workers
from enterprise_fallback.odoo18 import native_material_workers_v4 as workers_facade
from tools import odoo_v066_native_material_qualification_v4 as qualification_facade
from tests.test_odoo_native_projection_v3 import test_module

fixture=test_module('tests/test_odoo_v066_native_material_adapter_v2.py','_v4_adapter_fixture',[
    ('odoo_v066_native_material_adapter_v2','odoo_v066_native_material_adapter_v4')])
_fixture_evaluate=fixture.FakePage.evaluate
def _current_context_fixture(page,script,args=None):
    value=_fixture_evaluate(page,script,args)
    if script==adapter.NATIVE_CONTEXT_JS:value['native_search_geometry']={'count':0,'element':None}
    return value
fixture.FakePage.evaluate=_current_context_fixture
workers=workers_facade._impl
qualification=qualification_facade._impl
worker_tests=test_module('tests/test_odoo_native_material_workers_v2.py','_v4_worker_tests',[
    ('native_material_workers_v2 as workers','native_material_workers_v4 as workers')])
worker_tests.workers=workers;worker_tests.fixture=lambda:fixture
qualification_tests=test_module('tests/test_odoo_native_material_qualification_v2.py','_v4_qualification_tests',[
    ('native_material_workers_v2 as workers','native_material_workers_v4 as workers'),
    ('odoo_v066_native_material_qualification_v2 as qualification','odoo_v066_native_material_qualification_v4 as qualification'),
    ('"v066_native_material_controls_v2"','"v066_native_material_controls_v4"')])
qualification_tests.workers=workers;qualification_tests.qualification=qualification
qualification_tests.fake_train_proof=worker_tests.fake_train_proof


def search_geometry():
    style=copy.deepcopy(fixture.geometry()['sheet']['style'])
    style['borderTopLeftRadius']=style['borderBottomLeftRadius']='0px'
    return {'count':1,'element':{'tag':'button','class_name':'o_searchview_dropdown_toggler btn rounded-start-0',
        'role':'','aria_selected':'','ref':'','bounds':[922,54,952,89],'style':style}}


def repaint(raw,state=0,bad=None):
    with Image.open(BytesIO(raw)) as source:image=source.copy()
    points=((948,87),(949,87),(950,88))
    for xy,rgb in zip(points,material.SEARCH_STATES[state]):image.putpixel(xy,rgb)
    if bad=='partial':image.putpixel(points[0],material.SEARCH_STATES[1-state][0])
    if bad=='outside':image.putpixel((951,88),(1,2,3))
    if bad=='unknown':image.putpixel(points[0],(255,255,255))
    output=BytesIO();image.save(output,'PNG');return output.getvalue()


def setup(family='inventory'):
    page,a,raw=fixture.setup(family);native_evaluate=page.evaluate
    def evaluate(script,args=None):
        value=native_evaluate(script,args)
        if script==adapter.NATIVE_CONTEXT_JS:value['native_search_geometry']=copy.deepcopy(page.search_geometry)
        return value
    native_screenshot=page.screenshot
    def screenshot(**kwargs):
        raw=native_screenshot(**kwargs)
        return repaint(raw,page.capture%2 if page.search_alt and page.capture>2 else 0,page.search_bad)
    page.search_geometry=search_geometry();page.search_alt=False;page.search_bad=None
    page.evaluate=evaluate;page.screenshot=screenshot
    return page,a,raw


class SearchV4Tests(unittest.TestCase):
    def test_only_current_unique_unambiguous_native_geometry_projects(self):
        page,a,_=setup();a.observe_for_model();ctx=a._observed_context
        self.assertEqual(material.search_points(ctx),[[948,87],[949,87],[950,88]])
        for key,value in [('count',2),('count',0)]:
            other=copy.deepcopy(ctx);other['native_search_geometry'][key]=value
            other['native_search_geometry']['element']=None
            self.assertIsNone(material.search_points(other))
        for field,value in [('tag','canvas'),('class_name','unrelated')]:
            other=copy.deepcopy(ctx);other['native_search_geometry']['element'][field]=value
            self.assertIsNone(material.search_points(other))
        for field,value in [('opacity','0.9'),('transform','matrix(1,0,0,1,1,0)'),
                            ('boxShadow','black 0px 0px 1px'),('borderBottomRightRadius','5px')]:
            other=copy.deepcopy(ctx);other['native_search_geometry']['element']['style'][field]=value
            self.assertIsNone(material.search_points(other))
        other=copy.deepcopy(ctx);other['native_search_geometry']['element']['bounds'][2]+=.5
        self.assertIsNone(material.search_points(other))
        other=copy.deepcopy(ctx);other['native_search_geometry']['element']['bounds'][2]-=.390625
        self.assertEqual(material.search_points(other),[[948,87],[949,87],[950,88]])
        other=copy.deepcopy(ctx);other['native_search_geometry']['element']['bounds'][2]-=.01
        self.assertIsNone(material.search_points(other))
        self.assertTrue(material.near_border({'x':948,'y':87},ctx))
        self.assertFalse(material.near_border({'x':800,'y':166},ctx))

    def test_complete_vectors_share_identity_outside_pixels_and_partial_states_do_not(self):
        page,a,_=setup();obs,_=a.observe_for_model();ctx=a._observed_context
        base=material.border_material(repaint(obs.screenshot_bytes,0),ctx)
        other=material.border_material(repaint(obs.screenshot_bytes,1),ctx)
        self.assertEqual(base['canonical_material_sha256'],other['canonical_material_sha256'])
        for bad in ('partial','unknown'):
            self.assertIsNone(material.border_material(repaint(obs.screenshot_bytes,1,bad),ctx))
        outside=material.border_material(repaint(obs.screenshot_bytes,1,'outside'),ctx)
        self.assertNotEqual(base['canonical_material_sha256'],outside['canonical_material_sha256'])

    def test_uniform_all_four_families_with_six_saved_raw_guards_and_auditor(self):
        for family in ('purchase','inventory','sales','crm'):
            page,a,raw=setup(family);obs,_=a.observe_for_model();page.search_alt=True
            action=a.parse_current_action('{"type":"key","key":"Control+A"}')
            result=a.dispatch(action);receipt=result['public_contract_receipt']
            self.assertEqual(page.actions,[('key','Control+A')])
            for stage in ('parse','dispatch'):
                guard=receipt['native_material_'+stage+'_guard']
                self.assertEqual(guard['mode'],'finite_native_decorative_material')
                self.assertEqual(adapter.audit_guard(guard,obs.screenshot_bytes,
                    lambda ref:raw[ref['path']],action=action)['raw_guard_pngs_reopened'],3)
            bad=copy.deepcopy(receipt['native_material_dispatch_guard'])
            bad['native_context']['native_search_geometry']['element']['bounds'][2]+=1
            with self.assertRaises(ValueError):adapter.audit_guard(bad,obs.screenshot_bytes,
                lambda ref:raw[ref['path']],action=action)

    def test_material_context_action_change_and_near_corner_target_refused(self):
        for change in ('pixel','focus','bounds','style','modal','viewer'):
            page,a,_=setup();a.observe_for_model()
            action=a.parse_current_action('{"type":"key","key":"Control+A"}')
            if change=='pixel':page.search_bad='outside'
            elif change=='focus':page.bad_context='focus'
            elif change=='bounds':page.search_geometry['element']['bounds'][2]+=1
            elif change=='style':page.search_geometry['element']['style']['borderBottomColor']='red'
            elif change=='modal':page.bad_context='modal'
            else:page.canvas=True
            with self.assertRaises(ContractError):a.dispatch(action)
            self.assertEqual(page.actions,[])
        page,a,_=setup();a.observe_for_model()
        with self.assertRaises(ContractError):a.parse_current_action('{"type":"click","target":{"x":948,"y":87}}')
        self.assertEqual(page.actions,[])

    def test_unknown_search_geometry_keeps_exact_png_in_other_families(self):
        for family in ('inventory','sales','crm'):
            page,a,_=setup(family);page.search_geometry={'count':0,'element':None}
            a.observe_for_model();page.search_alt=True
            with self.assertRaises(ContractError):a.parse_current_action('{"type":"key","key":"Control+A"}')
            self.assertEqual(page.actions,[])

    def test_same_common_adapter_and_fresh_source_proof_required_for_all_paths(self):
        binding=workers.public_binding();workers.validate_binding(binding)
        self.assertIs(workers.common_adapter_class(),adapter.OdooV066NativeMaterialAdapter)
        teacher,selection=workers._model_modules(binding)
        self.assertIs(teacher.OdooV066TrainAdapter,adapter.OdooV066NativeMaterialAdapter)
        self.assertIs(selection.OdooV066TrainAdapter,adapter.OdooV066NativeMaterialAdapter)
        from tests.test_odoo_native_material_workers_v2 import fake_train_proof
        proof=fake_train_proof(old_workers.public_binding())
        with self.assertRaises(workers.NativeMaterialWorkerError):workers.validate_train_control(proof,binding)

    def test_teacher_sampling_freshness_uses_the_same_native_material_for_each_family(self):
        for family in ('purchase','inventory','sales','crm'):
            page,a,_=setup(family);observation,_=a.observe_for_model();page.search_alt=True
            self.assertEqual(workers._native_current_frame_id(a,page),observation.frame_id)
            page.search_bad='outside'
            self.assertEqual(workers._native_current_frame_id(a,page),'stale')
            page.search_bad=None;page.search_geometry['element']['bounds'][2]+=1
            self.assertEqual(workers._native_current_frame_id(a,page),'stale')
            self.assertEqual(page.actions,[])

    @unittest.skipUnless(os.environ.get('ODOO_NATIVE_V4_ACTUAL_FAILURE_DIR'),'Retained native witness not supplied')
    def test_retained_native_pixels_prove_only_rgb_delta_not_new_dom_witness(self):
        root=Path(os.environ['ODOO_NATIVE_V4_ACTUAL_FAILURE_DIR'])
        before=(root/'frames/step-009.png').read_bytes();after=(root/'frames/guard-0057.png').read_bytes()
        self.assertEqual(sha256(before).hexdigest(),'4968d5e427e4b86efd960e4f4edadccabd51eafeadb4a0706ad2bafd0221266e')
        self.assertEqual(sha256(after).hexdigest(),'b620fbb75c6663d86a2a69f1f4fd9180455f4e392da551dd4884a350a3be5302')
        with Image.open(BytesIO(before)) as a,Image.open(BytesIO(after)) as b:
            self.assertEqual(ImageChops.difference(a,b).getbbox(),(948,87,951,89))
            for i,xy in enumerate(((948,87),(949,87),(950,88))):
                self.assertEqual(a.getpixel(xy),material.SEARCH_STATES[0][i])
                self.assertEqual(b.getpixel(xy),material.SEARCH_STATES[1][i])
        trace=json.loads((root/'gui_trace.json').read_bytes())
        last=trace['exact_return_guard_samples'][-4:]
        self.assertEqual([row['stage'] for row in last],['parse','parse','parse','dispatch'])
        self.assertEqual(len({json.dumps(row['sample_native_context'],sort_keys=True) for row in last}),1)
        self.assertNotIn('native_search_geometry',last[0]['sample_native_context'])


def load_tests(_loader,_tests,_pattern):
    suite=unittest.TestSuite()
    for module in (worker_tests,qualification_tests):
        suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(SearchV4Tests))
    return suite


if __name__=='__main__':unittest.main()
