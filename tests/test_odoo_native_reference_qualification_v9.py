"""Qualification9 preserves Native14 purchase gates and separate CRM evidence."""
from hashlib import sha256
from pathlib import Path
from types import CodeType
from contextlib import ExitStack
import json
import tempfile
import unittest
from unittest.mock import patch
from tools import odoo_v066_native_reference_qualification_v9 as q
from tools import odoo_v066_native_reference_qualification_v8 as old
from tools import odoo_v066_scale_recipes_v9 as recipes
from enterprise_fallback.odoo18 import native_surface_workers_v14 as workers
from enterprise_fallback.odoo18 import native_reference_viewport_v8 as ui
from test_odoo_native_surface_qualification_v14 import metadata_fixture
from enterprise_fallback.odoo18 import partition_factory
from PIL import Image


def executable(code):
    return (code.co_code,code.co_names,code.co_varnames,
        tuple(executable(x) if isinstance(x,CodeType) else x for x in code.co_consts))


class Qualification9Tests(unittest.TestCase):
    def test_ui_native_and_canonical_purchase_core_are_exactly_unchanged(self):
        snapshots={m:(Path(m.__file__).read_bytes(),dict(vars(m))) for m in (ui,old,workers,recipes)}
        oldbinding=ui.reference_binding();binding=q.reference_binding()
        self.assertEqual(binding['ui_reference8_ancestor_binding_sha256'],oldbinding['reference_binding_sha256'])
        self.assertEqual(binding['canonical_native14_train_family'],'purchase')
        self.assertTrue(set(oldbinding['source_sha256s'])<=set(binding['source_sha256s']))
        self.assertIs(q.reference.candidate_module(workers.public_binding(),binding).recipes,recipes)
        a=q._impl._facade(binding);b=old._impl._facade(oldbinding)
        self.assertEqual(executable(a.run.__code__),executable(b.run.__code__))
        self.assertEqual(executable(a.finalize_train_control.__code__),executable(b.finalize_train_control.__code__))
        self.assertIs(a.workers.validate_train_control,workers.validate_train_control)
        self.assertIn('purchase',a.run.__code__.co_consts)
        self.assertEqual(workers.public_binding()['binding_sha256'],
            '558f82222096b398898948a4de162c290e8af82b2d6c55fd8f6b5831a3c8390c')
        for m,(raw,values) in snapshots.items():
            self.assertEqual(Path(m.__file__).read_bytes(),raw);self.assertEqual(dict(vars(m)),values)
        self.assertEqual(ui.reference_binding(),oldbinding)

    def test_all_original_metadata_preserved_with_two_additive_source_files(self):
        for split,count in (('train',20),('selection',20),('official_hidden',100)):
            metadata=metadata_fixture(split);plan,public=q.prepare(metadata);q.validate_plan(plan)
            self.assertEqual(plan['native_core_plan']['tasks'],metadata['tasks'])
            self.assertEqual(public['task_count'],count)
            for name in ('tools/odoo_v066_native_reference_qualification_v9.py',
                'tests/test_odoo_native_reference_qualification_v9.py'):
                self.assertEqual(plan['reference_binding']['source_sha256s'][name],
                    sha256((workers.ROOT/name).read_bytes()).hexdigest())

    def test_public_crm_and_failed77_are_separate_whole_original_cases(self):
        for split,kind,expected in (('train','original_public_crm_calibration',15),
            ('official_hidden','original_failed_crm77_boundary',77)):
            plan,_=q.prepare(metadata_fixture(split))
            with patch.object(q._impl.workers,'private_json',return_value=plan):
                contract=q.case_review_contract(plan_path=__file__,worker_dir='original',run_dir='fresh',kind=kind)
            self.assertEqual(contract['original_ordinal'],expected)
            self.assertEqual(contract['original_case_identity'],plan['native_core_plan']['tasks'][expected])
            self.assertTrue(contract['whole_original_case_0_1_0_only'])
            self.assertEqual(contract['canonical_native14_train_control_credit'],0)
            self.assertEqual(contract['full100_control_credit'],0)
            self.assertFalse(contract['original_full100_or_purchase_train_intent_consumption_authorized'])
        with patch.object(q._impl,'_facade') as facade:
            with self.assertRaises(Exception):q.run_case(plan_path='missing',worker_dir='original',run_dir='fresh',
                kind='original_public_crm_calibration',root_review_path='missing',root_review_sha256='a'*64)
            facade.assert_not_called()

    def test_full_split_refuses_old_missing_crm_proofs_before_run_or_intent(self):
        plan,_=q.prepare(metadata_fixture('official_hidden'))
        with patch.object(q._impl.workers,'private_json',return_value=plan), \
             patch.object(q,'_purchase_train',return_value={'actual_purchase':True}), \
             patch.object(q,'_checked_case_source_proof',side_effect=ValueError('missing genuine current CRM proof')), \
             patch.object(q,'_run') as run:
            with self.assertRaisesRegex(ValueError,'missing genuine current CRM proof'):
                q.run(plan_path='fixture',worker_dir='original',run_dir='fresh',execute=True,
                    train_control_path='canonical-purchase',train_control_sha256='b'*64)
            run.assert_not_called()

    def test_no_source_qualification_write_without_exact_independent_review(self):
        contract={'actual_source':'current','readable':True}
        with patch.object(q,'case_source_review_contract',return_value=contract), \
             patch.object(q._impl.workers,'private_json',return_value={'actual_source':'old','readable':True}), \
             patch.object(q._impl.core,'_write_new') as write:
            with self.assertRaisesRegex(Exception,'Exact independent current CRM'):
                q.finalize_case_source(plan_path='fixture',worker_dir='original',run_dir='fresh',
                    kind='original_public_crm_calibration',source_review_path='old',source_review_sha256='c'*64)
            write.assert_not_called()


class ActualProofCheckerTamperTests(unittest.TestCase):
    """Local fabricated evidence only; real checker/contracts/autosave decoder.

    Only the production SQL/native audit and source-asset generator are stubbed.
    No real application state, world call, qualification, or source review occurs.
    """
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.root=Path(self.directory.name);self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.asset=b'Explicit offline original-source fixture; no world or qualification'
        self.stack.enter_context(patch.object(partition_factory,'source_asset',return_value=self.asset))

    def write(self,path,value):
        path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        path.write_text(json.dumps(value,sort_keys=True,separators=(',',':')));path.chmod(0o600)
        return q._ref(path)

    def setup_bundle(self,kind='original_public_crm_calibration'):
        split='train' if kind=='original_public_crm_calibration' else 'official_hidden'
        metadata=metadata_fixture(split)
        for row in metadata['tasks']:
            if row['family']=='crm':row['source_asset_sha256']=sha256(self.asset).hexdigest()
        self.plan,_=q.prepare(metadata);self.binding=self.plan['reference_binding'];core=self.plan['native_core_plan']
        self.ordinal=15 if split=='train' else 77;self.metadata=core['tasks'][self.ordinal];self.kind=kind
        self.plan_path=self.root/'plan.private.json';self.write(self.plan_path,self.plan)
        self.worker=self.root/'worker';self.run=self.worker/'private/v066_reference8_qualification9_case_controls/unit-case'
        self.attempt=self.run/'attempt-000';self.attempt.mkdir(mode=0o700,parents=True)
        self.write(self.worker/'private/partition_cases.json',{'cases':{'crm':[{'id':self.metadata['task_id'],'family':'crm'}]}})
        (self.attempt/'frames').mkdir(mode=0o700)
        png=self.attempt/'frames/local-source.png';Image.new('RGB',(640,480),'white').save(png);png.chmod(0o600)
        frame={'path':'frames/local-source.png','sha256':sha256(png.read_bytes()).hexdigest()}
        self.audit={'native_guard_action_count':2,'independent_baseline_reward':0,
            'independent_positive_reward':1,'independent_wrong_object_reward':0,
            'full_pre_web_filestore_reset_exact':True,'original_services_restored':True}
        self.write(self.attempt/'independent-audit.private.json',self.audit)
        url='http://127.0.0.1:8095/odoo/local-crm-fixture';urlsha=sha256(url.encode()).hexdigest()
        native={'kind':'form','mode':'saved','connected_current_document':True,'url':url,
            'root_visible':True,'buttons_count':1,'invalid_visible':False,
            'invisible_class':True,'buttons_visible':False}
        self.trace={'actions':[{'frame':frame},{'frame':frame}]}
        self.write(self.attempt/'gui-trace.private.json',self.trace)
        self.receipt={'family':'crm','task_id':self.metadata['task_id'],'package_sha256':self.metadata['package_sha256'],
            'refs':{'source_frame':frame,'gui_trace':{'path':'gui-trace.private.json',
                'sha256':q._ref(self.attempt/'gui-trace.private.json')['sha256']}}}
        self.write(self.attempt/'attempt.private.json',self.receipt)
        for index,phase in enumerate(('positive','negative')):
            step=index+1
            action={'step':index,'frame_id':f'local-{index}','dispatch_state':'intent_durable_before_gui_action',
                'phase':phase,'normalized_action':{'step':index,'frame_id':f'local-{index}',
                    'type':'click','target':{'x':20,'y':20}},'optional_native_facet_resolution':None,
                'native_candidate_viewport_resolution':{'candidate_bounds':{'x':10,'y':10,'width':20,'height':20},
                    'viewport':[640,480],'candidate_resolved_after_observation':True,
                    'status':'current_candidate_inside_viewport','scroll_selected_before_intent':False}}
            self.write(self.attempt/f'actions/step-{index:03d}-intent.private.json',action)
            samples=[{'monotonic':10,'native':native},{'monotonic':10.5,'native':native}]
            intent={'schema':'odoo-reference-native-save-intent-v7','phase':phase,'selected_name':'Save manually',
                'same_action_replay_authorized':False,'one_guarded_click_required':False,
                'already_saved_native_proof_required':True,'native_indicator_before':native,'document_url_sha256':urlsha}
            saveproof={'schema':'odoo-reference-native-save-result-v7','phase':phase,'selected_name':'Save manually',
                'status':'already_saved_native_indicator','skip_performed':False,'same_action_replay_performed':False,
                'one_native_save_click':False,'already_saved_before_operation':True,
                'positive_current_saved_indicator_verified':True,'visible_save_controls_absent_verified':True,
                'gui_input_performed':False,'required_dirty_commit_click_skipped':False,
                'original_post_reload_and_independent_sql_readback_still_required':True,
                'save_action_start_step':step,'save_action_end_step':step-1,
                'actor_action_count_before':step,'actor_action_count_after':step,
                'stable_saved_seconds':.25,'started_monotonic':10,'ended_monotonic':10.5,
                'maximum_wait_seconds':30,'samples':samples}
            self.write(self.attempt/f'reference-save-{step:03d}-intent.private.json',intent)
            self.write(self.attempt/f'reference-save-{step:03d}-result.private.json',saveproof)
            auto_intent={'schema':'odoo-reference-priority-autosave-intent-v8','phase':phase,
                'policy':q.AUTOSAVE_POLICY,'gui_input_authorized':False,'same_action_retry_authorized':False,
                'trigger_action_step':index,'actor_action_count_before':step,
                'document_url_sha256':urlsha,'started_monotonic':10}
            auto_proof={'schema':'odoo-reference-priority-autosave-result-v8','phase':phase,
                'status':'positive_current_priority_autosave_verified','document_url_sha256':urlsha,
                'started_monotonic':10,'ended_monotonic':10.5,'maximum_wait_seconds':30,'stable_saved_seconds':.25,
                'actor_action_count_before':step,'actor_action_count_after':step,'trigger_action_step':index,
                'gui_input_performed':False,'same_action_retry_performed':False,
                'unchanged_reference7_save_reload_and_independent_sql_readback_still_required':True,'samples':samples}
            self.write(self.attempt/f'reference-priority-autosave-{step:03d}-intent.private.json',auto_intent)
            self.write(self.attempt/f'reference-priority-autosave-{step:03d}-result.private.json',auto_proof)
        facade=q._impl._facade(self.binding)
        self.native_audit=self.stack.enter_context(patch.object(facade,'audit_case',return_value=self.audit))
        self.stack.enter_context(patch.object(q._impl,'_facade',return_value=facade))
        provenance=q.saved_finalizer._v8_action_provenance(q.saved_finalizer.SavedReader(),self.attempt,self.receipt,self.audit,self.binding)
        self.write(self.attempt/'priority-autosave-provenance.private.json',provenance)
        self.result={'schema':'odoo-reference8-qualification9-whole-crm-case-result-v1','kind':kind,
            'scores':[0,1,0],'reset_exact':True,'services_restored':True,
            'reference_binding_sha256':self.binding['reference_binding_sha256'],
            'native_binding_sha256':core['native_worker_binding_sha256'],'original_ordinal':self.ordinal,
            'priority_autosave_provenance_ref':q._ref(self.attempt/'priority-autosave-provenance.private.json'),
            'audit_ref':q._ref(self.attempt/'independent-audit.private.json')}
        self.write(self.run/'case-result.private.json',self.result)
        self.write(self.run/'case-intent.private.json',q.case_review_contract(plan_path=self.plan_path,
            worker_dir=self.worker,run_dir=self.run,kind=kind))
        self.review=q.case_source_review_contract(plan_path=self.plan_path,worker_dir=self.worker,run_dir=self.run,kind=kind)
        self.review_path=self.root/'source-review.private.json';self.write(self.review_path,self.review)
        self.proof={'schema':'odoo-reference8-qualification9-case-source-qualified-v1','kind':kind,
            'reference_binding_sha256':self.binding['reference_binding_sha256'],'formal_admissions':0,
            'canonical_native14_train_control_credit':0,'run_dir':str(self.run),'worker_dir':str(self.worker),
            'plan_ref':q._ref(self.plan_path),'actual_case_result_ref':q._ref(self.run/'case-result.private.json'),
            'independent_source_review_ref':q._ref(self.review_path)}
        self.proof_path=self.root/'proof.private.json';self.write(self.proof_path,self.proof)

    def check(self):
        return q._checked_case_source_proof(self.proof_path,q._ref(self.proof_path)['sha256'],self.binding,self.kind)

    def rewrite_proof(self):self.write(self.proof_path,self.proof)

    def rewrite_result(self):
        self.write(self.run/'case-result.private.json',self.result)
        self.proof['actual_case_result_ref']=q._ref(self.run/'case-result.private.json');self.rewrite_proof()

    def test_genuine_local_bundle_calls_actual_checker_and_real_autosave_decoder(self):
        self.setup_bundle();self.assertEqual(self.check(),self.proof);self.native_audit.assert_called_once()

    def test_original77_local_bundle_uses_actual_hidden_split_and_same_decoder(self):
        self.setup_bundle('original_failed_crm77_boundary')
        self.assertEqual(self.ordinal,77);self.assertEqual(self.plan['native_core_plan']['split'],'official_hidden')
        self.assertEqual(self.check(),self.proof);self.native_audit.assert_called_once()

    def test_rehashed_source_approval_tamper_cannot_pass_actual_contract(self):
        self.setup_bundle();self.review['source_matches_package']=False;self.write(self.review_path,self.review)
        self.proof['independent_source_review_ref']=q._ref(self.review_path);self.rewrite_proof()
        with self.assertRaisesRegex(Exception,'source approval no longer matches'):self.check()

    def test_rehashed_autosave_provenance_tamper_is_recomputed_and_refused(self):
        self.setup_bundle();p=self.attempt/'priority-autosave-provenance.private.json';v=json.loads(p.read_bytes())
        v['reference_priority_autosave_wait_count']=99;self.write(p,v)
        self.result['priority_autosave_provenance_ref']=q._ref(p);self.rewrite_result()
        self.review=q.case_source_review_contract(plan_path=self.plan_path,worker_dir=self.worker,run_dir=self.run,kind=self.kind)
        self.write(self.review_path,self.review);self.proof['independent_source_review_ref']=q._ref(self.review_path);self.rewrite_proof()
        with self.assertRaisesRegex(Exception,'autosave provenance or audit ref changed'):self.check()

    def test_actual_autosave_trigger_or_samples_cannot_be_replaced_by_stored_provenance(self):
        self.setup_bundle();p=self.attempt/'reference-priority-autosave-002-result.private.json';v=json.loads(p.read_bytes())
        v['samples'][-1]['native']['mode']='dirty';self.write(p,v)
        with self.assertRaisesRegex(Exception,'native sample changed|stable saved interval'):self.check()

    def test_priority_trigger_must_still_be_original_click_in_actual_decoder(self):
        self.setup_bundle();p=self.attempt/'actions/step-001-intent.private.json';v=json.loads(p.read_bytes())
        v['normalized_action']['type']='type';self.write(p,v)
        with self.assertRaisesRegex(Exception,'trigger is not original guarded click'):self.check()

    def test_result_hash_ref_change_fails_safe_reader(self):
        self.setup_bundle();self.proof['actual_case_result_ref']['sha256']='0'*64;self.rewrite_proof()
        with self.assertRaises(Exception):self.check()

    def test_original_ordinal_native_binding_kind_and_source_binding_tamper_refuse(self):
        self.setup_bundle()
        for key,bad in [('original_ordinal',16),('native_binding_sha256','0'*64),
            ('kind','original_failed_crm77_boundary'),('reference_binding_sha256','0'*64)]:
            with self.subTest(field=key):
                initial=self.result[key];self.result[key]=bad;self.rewrite_result()
                with self.assertRaises(Exception):self.check()
                self.result[key]=initial;self.rewrite_result()
        self.proof['reference_binding_sha256']='0'*64;self.rewrite_proof()
        with self.assertRaisesRegex(Exception,'separate CRM source proof'):self.check()

    def test_rehashed_original_case_declaration_tamper_refuses(self):
        self.setup_bundle();p=self.run/'case-intent.private.json';v=json.loads(p.read_bytes())
        v['whole_original_case_0_1_0_only']=False;self.write(p,v)
        with self.assertRaisesRegex(Exception,'whole-case declaration changed'):self.check()

    def test_changed_trusted_sql_readback_does_not_match_saved_audit(self):
        self.setup_bundle();self.native_audit.return_value=self.audit|{'independent_positive_reward':0}
        with self.assertRaisesRegex(Exception,'saved production audit or result changed'):self.check()


if __name__=='__main__':unittest.main()
