"""Local frame/action adapter tests without browser or provider execution."""
from __future__ import annotations
import copy
import hashlib
import json
import unittest
from cursibench.scale_action_contract import ContractError
from tests.test_office_web_ppt_teacher_worker_v1 import png
from tools.office_local_browser_train_action_adapter_v1 import normalize_local_action


class LocalActionAdapterTests(unittest.TestCase):
    def setUp(self):
        self.image=png()
        self.frame={'schema':'office-local-browser-frame-v1','frame_id':'a'*32,
            'task_id':'ppt-wdi-transfer-'+'b'*16,'task_binding_sha256':'c'*64,
            'step':0,'width':64,'height':48,'expires_at_ms':110000,
            'screenshot_sha256':hashlib.sha256(self.image).hexdigest(),
            'screenshot_ref':{'path':'private.png','sha256':hashlib.sha256(self.image).hexdigest()},
            'local_profile':{'action_types':['click','double_click','type','key','scroll','finish'],
                'type_mode':'insert','editor_focus_required':True,'keys':['Home','End','Shift+End','Escape'],
                'actor_navigation_and_exports':False,'scroll_units':'cropped_screenshot_pixels',
                'safe_regions':[{'x':10,'y':10,'width':40,'height':30}]}}

    def call(self,payload,frame=None,image=None):
        return normalize_local_action(json.dumps(payload),frame or self.frame,image or self.image,
            'Repair the flagged fictional text through the document GUI.',current_frame_id='a'*32,now_ms=100000)

    def test_double_click_and_focused_insert_reuse_v066(self):
        action=self.call({'type':'double_click','target':{'x':20,'y':20}})
        self.assertEqual(action['frame_id'],self.frame['frame_id'])
        self.assertEqual(action['version'],'scale-computer-use-v0.6')
        self.assertEqual(self.call({'type':'type','mode':'insert','text':'fictional repair'})['type'],'type')

    def test_unsafe_region_and_whole_editor_or_navigation_chords_fail(self):
        for payload in ({'type':'click','target':{'x':0,'y':0}},
                        {'type':'key','key':'Control+A'}, {'type':'key','key':'Control+F'},
                        {'type':'type','target':{'x':20,'y':20},'mode':'fill','text':'x'},
                        {'type':'type','mode':'insert','text':'https://unapproved.example/'}):
            with self.subTest(payload=payload),self.assertRaises(ContractError):
                self.call(payload)

    def test_task_frame_hash_expiry_and_crop_must_match(self):
        for changed in ({'task_id':'final'}, {'frame_id':'d'*32}, {'expires_at_ms':99999},
                        {'screenshot_sha256':'e'*64}, {'width':63}, {'raw_url':'private'}):
            with self.subTest(changed=changed),self.assertRaises(ContractError):
                self.call({'type':'finish'},frame={**self.frame,**changed})

    def test_actual_image_bytes_are_validated_not_only_header_dimensions(self):
        broken=b'not a valid image';frame={**self.frame,'screenshot_sha256':hashlib.sha256(broken).hexdigest()}
        with self.assertRaises(ContractError):
            self.call({'type':'finish'},frame=frame,image=broken)

    def test_profile_cannot_expand_to_navigation_or_unbounded_regions(self):
        for profile in ({'keys':['Control+A']}, {'actor_navigation_and_exports':True},
                        {'safe_regions':[{'x':0,'y':0,'width':1000,'height':1000}]}):
            frame=copy.deepcopy(self.frame);frame['local_profile'].update(profile)
            with self.subTest(profile=profile),self.assertRaises(ContractError):
                self.call({'type':'finish'},frame=frame)


if __name__=='__main__':
    unittest.main()
