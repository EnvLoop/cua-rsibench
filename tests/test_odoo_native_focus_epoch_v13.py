"""Additive factory/epoch checks; no native service, provider or hidden body."""
from hashlib import sha256
import copy
import dis
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from enterprise_fallback.odoo18 import native_surface_workers_v13 as workers
from enterprise_fallback.odoo18 import native_surface_workers_v12 as old
from enterprise_fallback.odoo18 import native_reference_facet_v2 as ref
from enterprise_fallback.odoo18 import native_surface_final_worker_v1 as final
from enterprise_fallback.odoo18 import native_surface_budget_performance_v13 as budget
from tools import odoo_v066_native_reference_qualification_v2 as qualification
from cursibench import full_study_native_counterparts_v22 as counterparts
from cursibench import full_study_runtime_v2 as runtime

FROZEN={'enterprise_fallback/odoo18/native_surface_workers_v12.py': 'bccc510bfc0b93d313759fb4046360c692950cb5c65779b1923203b80037ad61', 'enterprise_fallback/odoo18/odoo_native_surface_evidence_v12.py': '273ec7fb129481d4c41f1a4e70354e36fb78c24ed7c97b1082b1690fb86fb6c3', 'enterprise_fallback/odoo18/odoo_v066_native_surface_adapter_v12.py': 'cc079311e5998de607156b69769e57c1345117e3c5818159cc76375f4ad6c5aa', 'enterprise_fallback/odoo18/native_surface_budget_performance_v12.py': 'c29a2069be86bec62d71b3aa9c8b9bf90b3ca9ecee3c9e1ffb30770ebb7405fd', 'enterprise_fallback/odoo18/native_reference_facet_v1.py': 'dc9b3c9457d2f109896d958c9af11b42263dc29f463ad380228a4cf0c3da8d50', 'enterprise_fallback/odoo18/native_reference_split_finalizer_v1.py': '3b44b84abe20e6beb2dbc8c830341ec0264f6f045bf9ee343bc1cb6aeab3826d', 'tools/odoo_v066_native_surface_qualification_v12.py': '549056c79cdf85e93da146758b8a5b8f7c10afd700c4ea16fcc35d2265f7b819', 'tools/odoo_v066_native_reference_qualification_v1.py': '1498a0056f71953e49acdc100c635f860bce92d43e8426d97386f55f3bbb4fa8', 'tools/odoo_v066_scale_recipes_v3.py': 'cda4562b196068ec0f96a9adc861abab6e8557b1e56ae9a7a7295ead75cfab06', 'enterprise_fallback/odoo18/odoo_actor_model_modules_v1.py': 'ef91ab34d4d8fce69368140941bd3c3e02ea3f53e013ade2b8c9363490d0186c'}

class EpochTests(unittest.TestCase):
    def test_every_retained_v12_reference_and_clock_source_is_byte_identical(self):
        for name,expected in FROZEN.items():
            with self.subTest(name=name):self.assertEqual(sha256((workers._ROOT/name).read_bytes()).hexdigest(),expected)

    def test_binding_closes_new_native_reference_reader_and_original_dependencies(self):
        binding=workers.public_binding();workers.validate_binding(binding)
        required={'enterprise_fallback/odoo18/native_surface_workers_v13.py',
            'enterprise_fallback/odoo18/odoo_v066_native_surface_adapter_v13.py',
            'enterprise_fallback/odoo18/odoo_native_surface_evidence_v13.py',
            'enterprise_fallback/odoo18/native_surface_budget_performance_v13.py',
            'enterprise_fallback/odoo18/native_reference_facet_v2.py',
            'enterprise_fallback/odoo18/native_reference_split_finalizer_v2.py',
            'tools/odoo_v066_native_surface_qualification_v13.py',
            'tools/odoo_v066_native_reference_qualification_v2.py','tools/odoo_v066_scale_recipes_v4.py',
            'enterprise_fallback/odoo18/odoo_actor_clock_v1.py',
            'enterprise_fallback/odoo18/odoo_actor_transport_v1.py',
            'enterprise_fallback/odoo18/odoo_actor_model_modules_v1.py',
            'enterprise_fallback/odoo18/verify.py','enterprise_fallback/odoo18/reset.py',
            'enterprise_fallback/odoo18/worker_lease.py'}
        self.assertLessEqual(required,set(binding['source_sha256s']))
        epoch=binding['source_epoch'];self.assertEqual(epoch['native'],'v13');self.assertEqual(epoch['reference'],'v2')
        self.assertEqual(epoch['historical_control_credit'],0);self.assertEqual(epoch['prior_full20_and_full100_prefix_credit'],0)
        self.assertTrue(epoch['fresh_train_full20_full100_required'])
        self.assertEqual(epoch['owned_lifecycle_schema'],'odoo-owned-complete-lifecycle-v12')
        self.assertEqual(binding['old_positive_credit'],0);self.assertEqual(binding['official_final_tasks_admitted'],0)
        for key,value in [('historical_control_credit',20),('prior_full20_and_full100_prefix_credit',33)]:
            changed=copy.deepcopy(binding);changed['source_epoch'][key]=value
            with self.assertRaisesRegex(ValueError,'whole_binding_changed'):workers.validate_binding(changed)

    def test_registration_is_source_only_and_does_not_activate_or_reclassify_old_epoch(self):
        registration=workers.policy_source_registration()
        self.assertFalse(registration['qualified_native_epoch']);self.assertFalse(registration['old_epoch_reclassified'])
        self.assertFalse(registration['all_seven_actor_paths_qualified']);self.assertEqual(registration['provider_calls'],0)
        self.assertEqual(registration['task_policy'],{'max_actions':90,'actor_seconds':720,'lease_seconds':1200})
        with self.assertRaisesRegex(ValueError,'fresh_native_actor_clock'):counterparts.require_activation(registration)

    def test_teacher_shared_base_four_checkpoints_and_controls_select_exact_current_adapter(self):
        binding=workers.public_binding();old_binding=old.public_binding()
        teacher,selection=workers._model_modules(binding);adapter=workers.common_adapter_class()
        self.assertIs(teacher.OdooV066TrainAdapter,adapter);self.assertIs(selection.OdooV066TrainAdapter,adapter)
        core=workers.evaluator_module(binding);reference=ref.candidate_module(binding,ref.reference_binding())
        for native_control in (core,reference):
            imports=[item.argval for item in dis.get_instructions(native_control.execute_case) if item.opname=='IMPORT_NAME']
            self.assertIn(workers.ADAPTER_MODULE,imports)
            self.assertNotIn(old.ADAPTER_MODULE,imports)
        self.assertEqual(final.module_from_binding(binding,workers.__name__),workers.__name__)
        snapshot=final.study_source_snapshot(workers.__name__)
        self.assertEqual(snapshot['native_worker_binding_sha256'],binding['binding_sha256'])
        for slot in ('shared-base','researcher-0','researcher-1','researcher-2','researcher-3'):
            with self.subTest(slot=slot):self.assertEqual(final.source_binding(workers.__name__)['native_worker_module'],workers.__name__)
        self.assertEqual(old.public_binding(),old_binding)
        self.assertIsNot(old.common_adapter_class(),adapter)
        with self.assertRaises(ValueError):workers.validate_binding(old_binding)
        with self.assertRaisesRegex(ValueError,'explicit_native_module_mismatched'):final.module_from_binding(binding,old.__name__)

    def test_fresh_reference_preparation_does_not_read_any_task_body_and_rejects_v1_plan(self):
        from tests.test_odoo_native_material_qualification_v2 import roster
        with patch('enterprise_fallback.odoo18.partition_factory.source_asset',side_effect=AssertionError('hidden body read')):
            plans=[]
            for split,count in [('train',20),('selection',20),('official_hidden',100)]:
                metadata=roster(split);metadata['schema']=qualification.core.ROSTER_SCHEMA
                plan,public=qualification.prepare(metadata);qualification.validate_plan(plan);plans.append(plan)
                self.assertEqual(public['task_count'],count);self.assertEqual(plan['historical_reference_credit'],0)
                self.assertEqual(plan['native_core_plan']['tasks'],metadata['tasks'])
                self.assertTrue(plan['native_core_plan']['fresh_run_directory_name'].startswith('native-v13-'))
                self.assertFalse(plan['formal_registration_performed'])
        self.assertEqual(len({plan['native_core_plan']['run_nonce_sha256'] for plan in plans}),3)
        wrong=copy.deepcopy(plans[0]);wrong['schema']='odoo-native-reference-qualification-plan-v1'
        with self.assertRaisesRegex(ValueError,'epoch_plan_invalid'):qualification.validate_plan(wrong)

    def test_v13_reader_is_registered_by_current_v22_source_hash_and_rejects_old_descriptor(self):
        relative='enterprise_fallback/odoo18/native_surface_budget_performance_v13.py'
        sources=runtime.source_manifest(workers._ROOT)['source_sha256s']
        self.assertEqual(sources[relative],sha256((workers._ROOT/relative).read_bytes()).hexdigest())
        descriptor={'adapter':{'module':budget.__name__,'function':'verify_budget_performance','source_sha256':sources[relative]},
            'arguments':{name:None for name in budget.FIELDS}}
        descriptor['arguments'].update(schema='odoo-budget-performance-input-v12',cell_id='odoo-community')
        with self.assertRaisesRegex(ValueError,'descriptor_changed'):
            runtime._portable_budget_verification(SimpleNamespace(repo_root=workers._ROOT),'shared-base',descriptor)
        descriptor['adapter']['source_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'not_in_frozen_source_closure'):
            runtime._portable_budget_verification(SimpleNamespace(repo_root=workers._ROOT),'shared-base',descriptor)

if __name__=='__main__':unittest.main()
