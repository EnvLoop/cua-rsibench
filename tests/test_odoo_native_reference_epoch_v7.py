"""Reference7 isolated source/binding and original Native14 guard proof."""
from hashlib import sha256
from pathlib import Path
from types import CodeType
import json
import tempfile
import unittest
from unittest.mock import patch

from enterprise_fallback.odoo18 import native_surface_workers_v14 as workers
from enterprise_fallback.odoo18 import native_reference_viewport_v6 as old
from enterprise_fallback.odoo18 import native_reference_viewport_v7 as current
from tools import odoo_v066_scale_recipes_v7 as old_recipes
from tools import odoo_v066_scale_recipes_v8 as recipes
from tools import odoo_v066_native_reference_qualification_v7 as qualification
from enterprise_fallback.odoo18 import native_reference_save_v7 as save
from enterprise_fallback.odoo18 import native_reference_split_finalizer_v7 as finalizer
from test_odoo_native_surface_qualification_v14 import metadata_fixture
from test_odoo_native_surface_expiry_v14 import held_fixture
from test_odoo_native_reference_viewport_v4 import Handle,Locator

def executable(code):
    return (code.co_code,code.co_names,code.co_varnames,
        tuple(executable(x) if isinstance(x,CodeType) else x for x in code.co_consts))

class ReferenceEpochTests(unittest.TestCase):
    def test_url_changes_after_positive_dirty_read_before_delegate_refuses_without_input(self):
        from playwright.sync_api import sync_playwright
        from test_odoo_native_reference_save_v5 import LocalRecipeJournal,form_html
        with sync_playwright() as playwright, tempfile.TemporaryDirectory() as directory:
            browser=playwright.chromium.launch(headless=True)
            try:
                page=browser.new_page()
                page.route('**/*',lambda route:route.abort())
                page.set_content(form_html())
                page.evaluate("document.querySelector('.o_form_status_indicator_buttons').classList.add('invisible')")
                journal=LocalRecipeJournal();journal.trace=[];journal.out=Path(directory)
                actual_read=save._impl.read_saved_indicator
                def read(*args):
                    result=actual_read(*args)
                    if result['mode']=='saved':
                        page.evaluate("document.querySelector('.o_form_status_indicator_buttons').classList.remove('invisible')")
                    return result
                actual_check=journal.clock.check
                def check(stage):
                    actual_check(stage)
                    if stage=='reference_save_after_indicator_read':page.goto('about:blank#foreign-current-document')
                with patch.object(save._impl,'read_saved_indicator',side_effect=read), \
                     patch.object(journal.clock,'check',side_effect=check), \
                     patch.object(save,'_dirty_save') as delegate:
                    with self.assertRaisesRegex(RuntimeError,'native_save_current_document_changed'):
                        save.save_original_form(page,journal,'fixture',timeout_seconds=.3,
                            poll_seconds=.005,stable_seconds=.015)
                    delegate.assert_not_called()
                self.assertEqual(journal.actions,[]);self.assertEqual(journal.trace,[])
                self.assertFalse(list(Path(directory).glob('*-intent.private.json')))
            finally:browser.close()

    def test_original_sales_boundary_keeps_full100_roster_and_never_grants_split_credit(self):
        plan,_=qualification.prepare(metadata_fixture('official_hidden'))
        with patch.object(qualification._impl.workers,'private_json',return_value=plan), \
             patch.object(qualification,'_reference7_train',return_value={'current_train':True}):
            contract=qualification.boundary_review_contract(plan_path=__file__,worker_dir='original',
                run_dir='fresh-boundary',train_control_path='current-train',train_control_sha256='f'*64)
        first=next(index for index,row in enumerate(plan['native_core_plan']['tasks']) if row['family']=='sales')
        self.assertEqual(contract['original_ordinal'],first)
        self.assertEqual(contract['original_case_identity'],plan['native_core_plan']['tasks'][first])
        self.assertFalse(contract['task_roster_mutation_authorized'])
        self.assertFalse(contract['original_full100_intent_consumption_authorized'])
        self.assertFalse(contract['formal_or_full100_control_credit_authorized'])
        self.assertFalse(contract['negative_only_or_partial_skip_authorized'])
        with patch.object(qualification._impl,'_facade') as facade:
            with self.assertRaises(Exception):qualification.run_boundary(plan_path='missing',worker_dir='original',
                run_dir='fresh-boundary',train_control_path='current-train',train_control_sha256='f'*64,
                root_review_path='missing',root_review_sha256='e'*64)
            facade.assert_not_called()
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
            self.assertEqual(plan['schema'],'odoo-native-reference-qualification-plan-v7')
            self.assertEqual(plan['native_core_plan']['tasks'],metadata['tasks'])
            self.assertEqual(public['task_count'],count)
            self.assertEqual(plan['native_core_plan']['native_worker_binding'],workers.public_binding())
            self.assertFalse(plan['formal_registration_performed']);self.assertEqual(plan['historical_reference_credit'],0)
            binding=plan['reference_binding'];self.assertEqual(binding['prior_reference4_control_credit'],0)
            self.assertEqual((binding['max_actions'],binding['actor_seconds']),(90,720))
            self.assertTrue(binding['same_v14_adapter_actor_scorer_reset'])
            self.assertTrue(binding['dirty_native_save_click_required']);self.assertEqual(binding['prior_reference5_control_credit'],0)
            for name in ('tools/odoo_v066_scale_recipes_v6.py','tools/odoo_v066_scale_recipes_v7.py',
                'enterprise_fallback/odoo18/native_reference_save_v7.py','tools/odoo_v066_scale_recipes_v8.py',
                'tools/odoo_v066_native_reference_qualification_v7.py','enterprise_fallback/odoo18/native_reference_split_finalizer_v7.py',
                'tests/test_odoo_native_reference_save_v7.py','tests/test_odoo_native_reference_epoch_v7.py'):
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
             patch.object(qualification,'_reference7_train',side_effect=ValueError('missing actual Reference7 TRAIN')), \
             patch.object(qualification,'_run') as run:
            with self.assertRaisesRegex(ValueError,'missing actual Reference7 TRAIN'):
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
                    finalizer._v7_action_provenance(read,root,receipt,{}, {})
                url='http://127.0.0.1:8069/odoo/purchase/fixture'
                write('reference-save-000-intent.private.json',{'schema':'odoo-reference-native-save-intent-v7',
                    'one_guarded_click_required':True,'same_action_replay_authorized':False,
                    'selected_name':'Save manually','phase':'positive','document_url_sha256':sha256(url.encode()).hexdigest()})
                native={'kind':'form','url':url,'connected_current_document':True,'mode':'saved',
                    'root_visible':True,'buttons_count':1,'invalid_visible':False,'invisible_class':True,'buttons_visible':False}
                write('reference-save-000-result.private.json',{'schema':'odoo-reference-native-save-result-v7',
                    'status':'saved_native_indicator','one_native_save_click':True,'original_native14_guard_used':True,
                    'skip_performed':False,'same_action_replay_performed':False,'selected_name':'Save manually',
                    'phase':'positive','save_action_start_step':0,'save_action_end_step':1,
                    'started_monotonic':100,'ended_monotonic':101,'maximum_wait_seconds':30,
                    'samples':[{'monotonic':100.5,'native':native}]})
                write('actions/step-000-intent.private.json',{'normalized_action':{'type':'scroll'},'phase':'positive'})
                write('actions/step-001-intent.private.json',{'normalized_action':{'type':'click'},'phase':'positive'})
                result=finalizer._v7_action_provenance(finalizer.SavedReader(),root,receipt,{}, {})
                self.assertTrue(result['v7_native_commit_or_proved_saved_provenance_verified'])
                saved={**native,'mode':'saved','invisible_class':True,'buttons_visible':False}
                dirty={**native,'mode':'dirty','invisible_class':False,'buttons_visible':True}
                readiness={'schema':'odoo-reference-pre-click-stabilization-v7',
                    'initial_native_indicator':saved,'reclassified_native_indicator':dirty,
                    'document_url_sha256':sha256(url.encode()).hexdigest(),
                    'actor_action_count_before':0,'actor_action_count_after':0,
                    'no_save_or_other_gui_input_performed':True,'current_positive_dirty_state_required':True,
                    'same_action_retry_performed':False,'phase':'positive','samples':[]}
                write('reference-save-000-readiness.private.json',readiness)
                result=finalizer._v7_action_provenance(finalizer.SavedReader(),root,receipt,{}, {})
                self.assertEqual(result['reference_pre_click_saved_to_dirty_count'],1)
                write('reference-save-000-readiness.private.json',{**readiness,'actor_action_count_after':1})
                with self.assertRaisesRegex(ValueError,'Saved-to-Dirty evidence changed'):
                    finalizer._v7_action_provenance(finalizer.SavedReader(),root,receipt,{}, {})
                write('reference-save-000-readiness.private.json',readiness)
                write('actions/step-000-intent.private.json',{'normalized_action':{'type':'click'},'phase':'positive'})
                with self.assertRaisesRegex(ValueError,'unexpected input'):
                    finalizer._v7_action_provenance(finalizer.SavedReader(),root,receipt,{}, {})

    def test_already_saved_finalizer_requires_stable_native_proof_and_zero_new_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);root.chmod(0o700)
            def write(name,value):
                p=root/name;p.write_text(json.dumps(value));p.chmod(0o600);return p
            trace=write('trace.private.json',{'actions':[{}]})
            receipt={'refs':{'gui_trace':{'path':trace.name,'sha256':sha256(trace.read_bytes()).hexdigest()}}}
            url='http://127.0.0.1:8069/odoo/purchase/fixture'
            native={'kind':'form','url':url,'connected_current_document':True,'mode':'saved','root_visible':True,
                'buttons_count':1,'invalid_visible':False,'invisible_class':True,'buttons_visible':False}
            write('reference-save-001-intent.private.json',{'schema':'odoo-reference-native-save-intent-v7',
                'one_guarded_click_required':False,'already_saved_native_proof_required':True,
                'native_indicator_before':native,'same_action_replay_authorized':False,
                'selected_name':'Save manually','phase':'positive','document_url_sha256':sha256(url.encode()).hexdigest()})
            proof={'schema':'odoo-reference-native-save-result-v7','status':'already_saved_native_indicator',
                'one_native_save_click':False,'already_saved_before_operation':True,
                'positive_current_saved_indicator_verified':True,'visible_save_controls_absent_verified':True,
                'gui_input_performed':False,'required_dirty_commit_click_skipped':False,
                'original_post_reload_and_independent_sql_readback_still_required':True,
                'skip_performed':False,'same_action_replay_performed':False,'selected_name':'Save manually','phase':'positive',
                'save_action_start_step':1,'save_action_end_step':0,'actor_action_count_before':1,'actor_action_count_after':1,
                'started_monotonic':100,'ended_monotonic':101,'maximum_wait_seconds':30,'stable_saved_seconds':.25,
                'samples':[{'monotonic':100.1,'native':native},{'monotonic':100.5,'native':native}]}
            with patch.object(finalizer,'_prior_provenance',return_value={'prior_guard_audit':True}):
                write('reference-save-001-result.private.json',proof)
                result=finalizer._v7_action_provenance(finalizer.SavedReader(),root,receipt,{}, {})
                self.assertEqual(result['reference_already_saved_no_input_count'],1)
                self.assertEqual(result['reference_native_save_count'],0)
                for key,value in [('gui_input_performed',True),('actor_action_count_after',2),
                                  ('positive_current_saved_indicator_verified',False)]:
                    write('reference-save-001-result.private.json',{**proof,key:value})
                    with self.assertRaisesRegex(ValueError,'action counts changed'):
                        finalizer._v7_action_provenance(finalizer.SavedReader(),root,receipt,{}, {})
        with patch.object(qualification,'_run') as run:
            with self.assertRaises(Exception):qualification.run(plan_path='fixture',worker_dir='fixture',run_dir='fresh-unused')
            run.assert_not_called()

if __name__=='__main__':unittest.main()
