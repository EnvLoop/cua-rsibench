"""Finite geometry guard adversaries, including optional preserved raw PNGs.

The historical failure has no DOM witness. Its supplied geometry is explicitly
reconstructed for this offline regression and cannot qualify a native run.
"""
from __future__ import annotations

import copy
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from PIL import Image

from cursibench.scale_action_contract import ContractError
from enterprise_fallback.odoo18 import native_material_workers_v1 as old_workers
from enterprise_fallback.odoo18 import native_material_workers_v2 as workers
from enterprise_fallback.odoo18.odoo_native_geometry_material_v2 import (
    border_material, near_border, projected_points)
from enterprise_fallback.odoo18.odoo_v066_native_material_adapter_v2 import (
    NATIVE_CONTEXT_JS, audit_guard)
from tests.test_odoo_v066_native_material_adapter_v2 import geometry, identity, png, setup
from tests.test_odoo_native_material_workers_v2 import fake_train_proof
from tools import odoo_v066_native_material_qualification_v2 as qualification
from tests.test_odoo_native_material_qualification_v2 import roster


def edit_pixel(raw, point, color):
    with Image.open(BytesIO(raw)) as source:
        image = source.copy()
    image.putpixel(point, color)
    stream = BytesIO()
    image.save(stream, 'PNG')
    return stream.getvalue()


class GeometryMaterialTests(unittest.TestCase):
    def test_variable_geometry_all_complete_vectors_and_protected_body_pixels(self):
        for bottom, tab_bounds in ((844, [41,381,133,420]), (865, [41,381,133,420]),
                                   (907, [80,401,222,440])):
            geo = geometry(bottom, tab_bounds)
            points = projected_points(geo)
            self.assertEqual(points['bottom'][0], [16,bottom-4])
            canonical = set()
            for top in range(2):
                for lower in range(2):
                    for tab in range(2):
                        raw = png(top, lower, geo=geo, tab=tab)
                        value = border_material(raw, geo)
                        self.assertIsNotNone(value)
                        self.assertEqual(value['state_class'], {'top':top,'bottom':lower,'selected_tab':tab})
                        canonical.add(value['canonical_material_sha256'])
                        changed = border_material(edit_pixel(raw, (810,420), (1,2,3)), geo)
                        self.assertNotEqual(changed['canonical_material_sha256'], value['canonical_material_sha256'])
            self.assertEqual(len(canonical), 1)

    def test_unknown_colour_and_mixed_whole_tab_or_sheet_vector_refused(self):
        geo = geometry(844)
        raw = png(geo=geo)
        for point, rgb in (((41,419),(235,237,239)), ((132,419),(235,237,238)),
                           ((16,155),(246,247,249)), ((16,840),(226,229,234))):
            with self.subTest(point=point,rgb=rgb):
                self.assertIsNone(border_material(edit_pixel(raw, point, rgb), geo))

    def test_unknown_style_ambiguous_clipped_fractional_and_payload_geometry_strict(self):
        for mutation in ('style','count','tab_count','outside','fraction','scale','payload','overlap'):
            geo = geometry()
            if mutation == 'style': geo['sheet']['style']['backgroundColor']='rgb(254, 255, 255)'
            elif mutation == 'count': geo.update(sheet_count=2,sheet=None)
            elif mutation == 'tab_count': geo.update(selected_tab_count=2,selected_tab=None)
            elif mutation == 'outside': geo['sheet']['bounds'][3]=1001
            elif mutation == 'fraction': geo['selected_tab']['bounds'][0]=41.00001
            elif mutation == 'scale': geo['viewport']['device_pixel_ratio']=2
            elif mutation == 'payload': geo['selected_tab']['gold']='unsupported'
            else: geo['selected_tab']['bounds']=[16,154,40,170]
            with self.subTest(mutation=mutation):
                self.assertIsNone(projected_points(geo))
                self.assertIsNone(border_material(png(), geo))

    def test_current_geometry_and_tab_class_change_block_dispatch(self):
        for mutation in ('bounds','tab','style','scale'):
            page, adapter, _ = setup()
            adapter.observe_for_model()
            action=adapter.parse_current_action(json.dumps({'type':'key','key':'Control+A'}))
            if mutation == 'bounds': page.geometry['sheet']['bounds'][3]+=1
            elif mutation == 'tab': page.geometry['selected_tab']['class_name']+=' changed'
            elif mutation == 'style': page.geometry['selected_tab']['style']['borderBottomColor']='rgb(1, 2, 3)'
            else: page.geometry['viewport']['visual_scale']=2
            with self.subTest(mutation=mutation),self.assertRaises(ContractError):
                adapter.dispatch(action)
            self.assertEqual(page.actions,[])

    def test_every_projected_pixel_and_nearby_action_point_refused(self):
        for values in projected_points(geometry()).values():
            for x,y in values:
                self.assertTrue(near_border({'x':x+8,'y':y+8},geometry()))
                page, adapter, _ = setup()
                evaluate=page.evaluate
                def hit(script,args=None):
                    context=evaluate(script,args)
                    if script==NATIVE_CONTEXT_JS and args:
                        target=identity('button','price');target['bounds']=[0,0,1440,1000]
                        context.update(target=target,row=None)
                    return context
                page.evaluate=hit
                adapter.observe_for_model()
                with self.assertRaises(ContractError):
                    adapter.parse_current_action(json.dumps({'type':'click','target':{'x':x,'y':y}}))
                self.assertEqual(page.actions,[])

    def test_auditor_reprojects_raw_vectors_sample_context_and_geometry(self):
        page,adapter,raw=setup();page.alt=True
        observed,_=adapter.observe_for_model()
        action=adapter.parse_current_action(json.dumps({'type':'key','key':'Control+A'}))
        guard=adapter.dispatch(action)['public_contract_receipt']['native_material_parse_guard']
        for mutation in ('bounds','points','vectors','state','sample_context'):
            bad=copy.deepcopy(guard)
            if mutation == 'bounds':
                for key in ('native_context','observed_native_context'):
                    bad[key]['native_geometry']['sheet']['bounds'][3]+=1
            elif mutation == 'points': bad['observed_material']['projected_points']['top'][0][1]+=1
            elif mutation == 'vectors': bad['observed_material']['rgb_vectors']['selected_tab'][0][2]=238
            elif mutation == 'state': bad['sampled_frames'][0]['material']['state_class']['selected_tab']=7
            else: bad['sampled_frames'][0]['sample_native_context']['native_geometry']['selected_tab']['bounds'][0]+=1
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                audit_guard(bad,observed.screenshot_bytes,lambda r:raw[r['path']],action=action)

    def test_teacher_freshness_uses_same_geometry_and_v1_proof_cannot_cross_v2(self):
        page,adapter,_=setup();page.geometry=geometry(844);page.alt=True
        observed,_=adapter.observe_for_model()
        self.assertEqual(workers._native_current_frame_id(adapter,page),observed.frame_id)
        page.geometry['selected_tab']['bounds'][2]+=1
        self.assertEqual(workers._native_current_frame_id(adapter,page),'stale')
        binding=workers.public_binding()
        self.assertIn('enterprise_fallback/odoo18/odoo_native_geometry_material_v2.py',binding['source_sha256s'])
        with self.assertRaises(workers.NativeMaterialWorkerError):
            workers.validate_train_control(fake_train_proof(old_workers.public_binding()),binding)
        changed=copy.deepcopy(binding)
        changed['source_sha256s']['enterprise_fallback/odoo18/odoo_native_geometry_material_v2.py']='0'*64
        with self.assertRaises(workers.NativeMaterialWorkerError): workers.validate_binding(changed)
        original=workers.ROOT
        class ChangedRoot:
            def __truediv__(self,name):
                if name=='enterprise_fallback/odoo18/odoo_native_geometry_material_v2.py':
                    class ChangedFile:
                        def read_bytes(self):return b'changed source bytes'
                    return ChangedFile()
                return original/name
        with patch.object(workers,'ROOT',ChangedRoot()),self.assertRaises(workers.NativeMaterialWorkerError):
            workers.validate_binding(binding)
        plan,_=qualification.prepare(roster())
        self.assertEqual(plan['tasks'],roster()['tasks'])
        self.assertTrue(plan['fresh_run_directory_name'].startswith('native-v2-'))
        self.assertEqual(plan['old_positive_credit'],0)

    @unittest.skipUnless(os.environ.get('ODOO_NATIVE_V2_ACTUAL_FAILURE_DIR'), 'Preserved raw fixture path not supplied')
    def test_actual_failure_pair_only_reconstructed_geometry_not_native_credit(self):
        frames=Path(os.environ['ODOO_NATIVE_V2_ACTUAL_FAILURE_DIR'])/'frames'
        observed=(frames/'step-003.png').read_bytes()
        physical=(frames/'guard-0019.png').read_bytes()
        self.assertEqual(sha256(observed).hexdigest(),'cd09ffdc190707351c739bdb31dd336a7748a61707d9bf180e3650ded439157f')
        self.assertEqual(sha256(physical).hexdigest(),'57266a84eb3439be32d85c8e81141eda67112486b4965ee3afafca92b4541743')
        self.assertEqual(observed,(frames/'guard-0018.png').read_bytes())
        self.assertEqual(physical,(frames/'step-003-rejected-current.png').read_bytes())
        # This reconstruction supplies no proof about the old DOM witness.
        reconstructed=geometry(844)
        a,b=border_material(observed,reconstructed),border_material(physical,reconstructed)
        self.assertEqual(a['canonical_material_sha256'],b['canonical_material_sha256'])
        self.assertEqual(a['state_class']['selected_tab'],0)
        self.assertEqual(b['state_class']['selected_tab'],1)
        changed=border_material(edit_pixel(physical,(810,480),(1,2,3)),reconstructed)
        self.assertNotEqual(changed['canonical_material_sha256'],a['canonical_material_sha256'])
        wrong_geometry=geometry(865)
        self.assertIsNone(border_material(physical,wrong_geometry))
        self.assertEqual(workers.public_binding()['old_positive_credit'],0)


if __name__=='__main__': unittest.main()
