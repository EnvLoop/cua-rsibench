"""Reference5 isolated source/binding and original Native14 guard proof."""
from hashlib import sha256
from pathlib import Path
from types import CodeType
import json
import tempfile
import unittest
from unittest.mock import patch

from enterprise_fallback.odoo18 import native_surface_workers_v14 as workers
from enterprise_fallback.odoo18 import native_reference_viewport_v4 as old
from enterprise_fallback.odoo18 import native_reference_viewport_v5 as current
from tools import odoo_v066_scale_recipes_v5 as old_recipes
from tools import odoo_v066_scale_recipes_v6 as recipes
from tools import odoo_v066_native_reference_qualification_v5 as qualification
from enterprise_fallback.odoo18 import native_reference_save_v5 as save
from enterprise_fallback.odoo18 import native_reference_split_finalizer_v5 as finalizer
from test_odoo_native_surface_qualification_v14 import metadata_fixture
from test_odoo_native_surface_expiry_v14 import held_fixture
from test_odoo_native_reference_viewport_v4 import Handle,Locator

def executable(code):
    return (code.co_code,code.co_names,code.co_varnames,
        tuple(executable(x) if isinstance(x,CodeType) else x for x in code.co_consts))

class ReferenceEpochTests(unittest.TestCase):
    def test_current_recipe_has_narrow_save_override_without_mutating_original_modules(self):
        modules=(old,old_recipes,workers)
        snapshots={m:(Path(m.__file__).read_bytes(),dict(vars(m))) for m in modules}
        prior=old.reference_binding();binding=current.reference_binding()
        evaluator=current.candidate_module(workers.public_binding(),binding)
        self.assertIs(evaluator.recipes,recipes)
        self.assertIs(recipes._grid_edit.__globals__['_save'],save.save_original_form)
        self.assertIsNot(old_recipes._grid_edit.__globals__['_save'],save.save_original_form)
        for name in ('apply_positive','apply_negative','_grid_edit'):
            self.assertEqual(executable(getattr(recipes,name).__code__),executable(getattr(old_recipes,name).__code__))
        for m,(raw,attributes) in snapshots.items():
            self.assertEqual(Path(m.__file__).read_bytes(),raw);self.assertEqual(dict(vars(m)),attributes)
        self.assertEqual(old.reference_binding(),prior)
        self.assertEqual(workers.public_binding()['binding_sha256'],'558f82222096b398898948a4de162c290e8af82b2d6c55fd8f6b5831a3c8390c')

    def test_metadata_keeps_original_20_20_100_and_new_reference_no_old_credit(self):
        for split,count in (('train',20),('selection',20),('official_hidden',100)):
            metadata=metadata_fixture(split);plan,public=qualification.prepare(metadata)
            qualification.validate_plan(plan)
            self.assertEqual(plan['schema'],'odoo-native-reference-qualification-plan-v5')
            self.assertEqual(plan['native_core_plan']['tasks'],metadata['tasks'])
            self.assertEqual(public['task_count'],count)
            self.assertEqual(plan['native_core_plan']['native_worker_binding'],workers.public_binding())
            self.assertFalse(plan['formal_registration_performed']);self.assertEqual(plan['historical_reference_credit'],0)
            binding=plan['reference_binding'];self.assertEqual(binding['prior_reference4_control_credit'],0)
            self.assertEqual((binding['max_actions'],binding['actor_seconds']),(90,720))
            self.assertTrue(binding['same_v14_adapter_actor_scorer_reset'])
            self.assertTrue(binding['manual_native_save_click_required'])
            for name in ('enterprise_fallback/odoo18/native_reference_save_v5.py','tools/odoo_v066_scale_recipes_v6.py',
                'tools/odoo_v066_native_reference_qualification_v5.py','enterprise_fallback/odoo18/native_reference_split_finalizer_v5.py',
                'tests/test_odoo_native_reference_save_v5.py','tests/test_odoo_native_reference_epoch_v5.py'):
                self.assertEqual(binding['source_sha256s'][name],sha256((workers.ROOT/name).read_bytes()).hexdigest())
            with self.assertRaises(Exception):current.validate_reference_binding(old.reference_binding())

    def test_save_locator_click_uses_original_native14_decision_and_disabled_hit_refuses(self):
        binding=workers.public_binding();ref=current.reference_binding()
        for disabled in (False,True):
            with held_fixture() as (adapter,page,_private,root):
                if disabled:page.disabled=True
                journal=current.recorder_module(binding,ref).ActionJournal(adapter,page,root)
                candidate=Locator([Handle({'x':320,'y':30,'width':100,'height':40})])
                if disabled:
                    with self.assertRaises(Exception):journal.act('click',phase='positive',locator=candidate)
                    self.assertFalse(any(call[0]=='click' for call in page.calls))
                else:
                    journal.act('click',phase='positive',locator=candidate)
                    self.assertTrue(any(call[0]=='click' for call in page.calls))

    def test_full_split_cannot_consume_intent_or_run_using_old_native14_train_alone(self):
        plan,_=qualification.prepare(metadata_fixture('official_hidden'))
        with patch.object(qualification._impl.workers,'private_json',return_value=plan), \
             patch.object(qualification,'_reference5_train',side_effect=ValueError('missing actual Reference5 TRAIN')), \
             patch.object(qualification,'_run') as run:
            with self.assertRaisesRegex(ValueError,'missing actual Reference5 TRAIN'):
                qualification.run(plan_path='fixture',worker_dir='fixture',run_dir='fresh-unused',execute=True,
                    train_control_path='old-native14-train',train_control_sha256='f'*64)
            run.assert_not_called()

    def test_saved_finalizer_requires_mandatory_current_save_proof_and_exact_input_span(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);root.chmod(0o700);(root/'actions').mkdir(mode=0o700)
            def write(name,value):
                p=root/name;p.write_text(json.dumps(value));p.chmod(0o600);return p
            read=finalizer.SavedReader();trace=write('trace.private.json',{'actions':[{},{}]})
            receipt={'refs':{'gui_trace':{'path':trace.name,'sha256':sha256(trace.read_bytes()).hexdigest()}}}
            with patch.object(finalizer,'_prior_provenance',return_value={'prior_guard_audit':True}):
                with self.assertRaisesRegex(ValueError,'lacks mandatory native save proof'):
                    finalizer._v5_action_provenance(read,root,receipt,{}, {})
                url='http://127.0.0.1:8069/odoo/purchase/fixture'
                write('reference-save-000-intent.private.json',{'schema':'odoo-reference-native-save-intent-v5',
                    'one_guarded_click_required':True,'same_action_replay_authorized':False,
                    'selected_name':'Save manually','phase':'positive','document_url_sha256':sha256(url.encode()).hexdigest()})
                native={'kind':'form','url':url,'connected_current_document':True,'mode':'saved',
                    'root_visible':True,'buttons_count':1,'invalid_visible':False,'invisible_class':True,'buttons_visible':False}
                write('reference-save-000-result.private.json',{'schema':'odoo-reference-native-save-result-v5',
                    'status':'saved_native_indicator','one_native_save_click':True,'original_native14_guard_used':True,
                    'skip_performed':False,'same_action_replay_performed':False,'selected_name':'Save manually',
                    'phase':'positive','save_action_start_step':0,'save_action_end_step':1,
                    'started_monotonic':100,'ended_monotonic':101,'maximum_wait_seconds':30,
                    'samples':[{'monotonic':100.5,'native':native}]})
                write('actions/step-000-intent.private.json',{'normalized_action':{'type':'scroll'},'phase':'positive'})
                write('actions/step-001-intent.private.json',{'normalized_action':{'type':'click'},'phase':'positive'})
                result=finalizer._v5_action_provenance(finalizer.SavedReader(),root,receipt,{}, {})
                self.assertTrue(result['v5_mandatory_native_save_provenance_verified'])
                write('actions/step-000-intent.private.json',{'normalized_action':{'type':'click'},'phase':'positive'})
                with self.assertRaisesRegex(ValueError,'unexpected input'):
                    finalizer._v5_action_provenance(finalizer.SavedReader(),root,receipt,{}, {})
        with patch.object(qualification,'_run') as run:
            with self.assertRaises(Exception):qualification.run(plan_path='fixture',worker_dir='fixture',run_dir='fresh-unused')
            run.assert_not_called()

if __name__=='__main__':unittest.main()
