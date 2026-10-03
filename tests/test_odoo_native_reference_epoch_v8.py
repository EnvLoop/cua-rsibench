"""Reference8 closure and saved-only autosave provenance; no world calls."""
from hashlib import sha256
from pathlib import Path
from types import CodeType
import json
import tempfile
import unittest
from unittest.mock import patch
from enterprise_fallback.odoo18 import native_surface_workers_v14 as workers
from enterprise_fallback.odoo18 import native_reference_viewport_v7 as prior
from enterprise_fallback.odoo18 import native_reference_viewport_v8 as current
from enterprise_fallback.odoo18 import native_reference_save_v7 as save
from enterprise_fallback.odoo18 import native_reference_autosave_v8 as autosave
from enterprise_fallback.odoo18 import native_reference_split_finalizer_v8 as finalizer
from tools import odoo_v066_scale_recipes_v8 as old_recipes
from tools import odoo_v066_scale_recipes_v9 as recipes
from tools import odoo_v066_native_reference_qualification_v8 as qualification
from test_odoo_native_surface_qualification_v14 import metadata_fixture


def executable(code):
    return (code.co_code,code.co_names,code.co_varnames,
        tuple(executable(x) if isinstance(x,CodeType) else x for x in code.co_consts))


class Reference8Tests(unittest.TestCase):
    def test_loaded_recipe_waits_after_both_priority_clicks_and_keeps_exact_old_save(self):
        snapshot={module:(Path(module.__file__).read_bytes(),dict(vars(module)))
            for module in (prior,old_recipes,save,workers)}
        old_binding=prior.reference_binding();binding=current.reference_binding()
        candidate=current.candidate_module(workers.public_binding(),binding)
        self.assertIs(candidate.recipes,recipes)
        self.assertIs(recipes._save,save.save_original_form)
        self.assertIs(recipes.wait_positive_priority_autosave,autosave.wait_positive_priority_autosave)
        for name in ('_grid_edit','open_case','_fill'):
            self.assertEqual(executable(getattr(recipes,name).__code__),executable(getattr(old_recipes,name).__code__))
        for name in ('apply_positive','apply_negative'):
            self.assertIn('wait_positive_priority_autosave',getattr(recipes,name).__code__.co_names)
        for module,(raw,globals_before) in snapshot.items():
            self.assertEqual(Path(module.__file__).read_bytes(),raw)
            self.assertEqual(dict(vars(module)),globals_before)
        self.assertEqual(prior.reference_binding(),old_binding)
        self.assertEqual(workers.public_binding()['binding_sha256'],
            '558f82222096b398898948a4de162c290e8af82b2d6c55fd8f6b5831a3c8390c')

    def test_original_allocations_and_complete_ancestor_source_closure(self):
        for split,count in (('train',20),('selection',20),('official_hidden',100)):
            metadata=metadata_fixture(split);plan,public=qualification.prepare(metadata)
            qualification.validate_plan(plan)
            self.assertEqual(plan['native_core_plan']['tasks'],metadata['tasks'])
            self.assertEqual(public['task_count'],count)
            binding=plan['reference_binding']
            self.assertTrue(binding['unchanged_reference7_save_helper_used'])
            self.assertEqual(binding['prior_reference7_control_credit'],0)
            self.assertEqual((binding['max_actions'],binding['actor_seconds']),(90,720))
            self.assertTrue(set(prior.reference_binding()['source_sha256s'])<=set(binding['source_sha256s']))
            for name in ('enterprise_fallback/odoo18/native_reference_autosave_v8.py',
                'enterprise_fallback/odoo18/native_reference_save_v7.py','tools/odoo_v066_scale_recipes_v9.py',
                'tools/odoo_v066_native_reference_qualification_v8.py',
                'tests/test_odoo_native_reference_autosave_v8.py','tests/test_odoo_native_reference_epoch_v8.py'):
                self.assertEqual(binding['source_sha256s'][name],sha256((workers.ROOT/name).read_bytes()).hexdigest())

    def test_purchase_or_implicit_train_refuses_before_any_run(self):
        plan,_=qualification.prepare(metadata_fixture('train'))
        purchase=next(row['task_id'] for row in plan['native_core_plan']['tasks'] if row['family']=='purchase')
        for task in (None,purchase):
            with patch.object(qualification._impl.workers,'private_json',return_value=plan), \
                 patch.object(qualification,'_run') as run:
                with self.assertRaisesRegex(Exception,'Explicit original first public CRM TRAIN'):
                    qualification.run(plan_path='fixture',worker_dir='original',run_dir='fresh',
                        train_task_id=task,execute=True)
                run.assert_not_called()

    def test_old_train_cannot_launch_split_or_consume_intent(self):
        plan,_=qualification.prepare(metadata_fixture('official_hidden'))
        with patch.object(qualification._impl.workers,'private_json',return_value=plan), \
             patch.object(qualification,'_reference8_train',side_effect=ValueError('missing current CRM widget proof')), \
             patch.object(qualification,'_run') as run:
            with self.assertRaisesRegex(ValueError,'missing current CRM widget proof'):
                qualification.run(plan_path='fixture',worker_dir='original',run_dir='fresh',execute=True,
                    train_control_path='old-train',train_control_sha256='a'*64)
            run.assert_not_called()

    def test_reviewed_boundary_is_only_original_failed_crm_without_roster_or_full100_credit(self):
        plan,_=qualification.prepare(metadata_fixture('official_hidden'))
        with patch.object(qualification._impl.workers,'private_json',return_value=plan), \
             patch.object(qualification,'_reference8_train',return_value={'actual_crm_widget':True}):
            contract=qualification.boundary_review_contract(plan_path=__file__,worker_dir='original',
                run_dir='fresh-boundary',train_control_path='current-crm-train',train_control_sha256='b'*64)
        self.assertEqual(contract['original_ordinal'],77)
        self.assertEqual(contract['original_case_identity'],plan['native_core_plan']['tasks'][77])
        self.assertEqual(contract['original_case_identity']['family'],'crm')
        for field in ('task_roster_mutation_authorized','original_full100_intent_consumption_authorized',
            'formal_or_full100_control_credit_authorized','negative_only_or_partial_skip_authorized'):
            self.assertFalse(contract[field])
        with patch.object(qualification._impl,'_facade') as facade:
            with self.assertRaises(Exception):qualification.run_boundary(plan_path='missing',worker_dir='original',
                run_dir='fresh',train_control_path='current',train_control_sha256='a'*64,
                root_review_path='missing',root_review_sha256='c'*64)
            facade.assert_not_called()

    def test_saved_finalizer_requires_original_click_zero_input_current_stable_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);root.chmod(0o700);(root/'actions').mkdir(mode=0o700)
            def write(name,value):
                path=root/name;path.write_text(json.dumps(value));path.chmod(0o600);return path
            url='http://127.0.0.1:8095/odoo/crm/local-fixture'
            intent={'schema':'odoo-reference-priority-autosave-intent-v8','policy':autosave.POLICY,
                'phase':'negative','trigger_action_step':0,'actor_action_count_before':1,
                'started_monotonic':100,
                'document_url_sha256':sha256(url.encode()).hexdigest(),'gui_input_authorized':False,
                'same_action_retry_authorized':False}
            native={'kind':'form','url':url,'connected_current_document':True,'mode':'saved',
                'root_visible':True,'buttons_count':1,'invalid_visible':False,
                'invisible_class':True,'buttons_visible':False}
            proof={'schema':'odoo-reference-priority-autosave-result-v8',
                'status':'positive_current_priority_autosave_verified','phase':'negative','trigger_action_step':0,
                'actor_action_count_before':1,'actor_action_count_after':1,'document_url_sha256':intent['document_url_sha256'],
                'gui_input_performed':False,'same_action_retry_performed':False,
                'unchanged_reference7_save_reload_and_independent_sql_readback_still_required':True,
                'started_monotonic':100,'ended_monotonic':101,'maximum_wait_seconds':30,'stable_saved_seconds':.25,
                'samples':[{'monotonic':100.1,'native':native},{'monotonic':100.5,'native':native}]}
            receipt={'family':'crm'}
            with patch.object(finalizer,'_save_provenance',return_value={'original_save_checked':True}):
                with self.assertRaisesRegex(ValueError,'lacks native priority autosave proof'):
                    finalizer._v8_action_provenance(finalizer.SavedReader(),root,receipt,{}, {})
                write('reference-priority-autosave-001-intent.private.json',intent)
                write('reference-priority-autosave-001-result.private.json',proof)
                action={'phase':'negative','normalized_action':{'type':'click'}}
                write('actions/step-000-intent.private.json',action)
                actual=finalizer._v8_action_provenance(finalizer.SavedReader(),root,receipt,{}, {})
                self.assertTrue(actual['v8_priority_autosave_zero_input_provenance_verified'])
                self.assertEqual(actual['reference_priority_autosave_wait_count'],1)
                for key,value in (('gui_input_performed',True),('actor_action_count_after',2),
                    ('same_action_retry_performed',True)):
                    write('reference-priority-autosave-001-result.private.json',{**proof,key:value})
                    with self.assertRaisesRegex(ValueError,'zero-input proof changed'):
                        finalizer._v8_action_provenance(finalizer.SavedReader(),root,receipt,{}, {})
                write('reference-priority-autosave-001-result.private.json',proof)
                write('actions/step-000-intent.private.json',{**action,'normalized_action':{'type':'type'}})
                with self.assertRaisesRegex(ValueError,'not original guarded click'):
                    finalizer._v8_action_provenance(finalizer.SavedReader(),root,receipt,{}, {})
                write('actions/step-000-intent.private.json',action)
                dirty={**native,'mode':'dirty','invisible_class':False,'buttons_visible':True}
                write('reference-priority-autosave-001-result.private.json',{**proof,
                    'samples':[{'monotonic':100.1,'native':native},{'monotonic':100.5,'native':dirty}]})
                with self.assertRaisesRegex(ValueError,'stable saved interval missing'):
                    finalizer._v8_action_provenance(finalizer.SavedReader(),root,receipt,{}, {})


if __name__=='__main__':unittest.main()
