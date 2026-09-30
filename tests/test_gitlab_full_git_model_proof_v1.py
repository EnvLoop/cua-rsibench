"""Offline full-tree model integration tests; all task/application/provider data are fixtures."""
from __future__ import annotations
import copy
from contextlib import contextmanager
from decimal import Decimal
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from gitlab_world import full_git_model_oracle_v1 as oracle
from gitlab_world import full_git_model_workers_v1 as workers
from gitlab_world import full_git_final_worker_v1 as final_worker
from gitlab_world import full_git_shared_base_execution_v1 as shared
from gitlab_world import train_teacher_oracle_v066, selection_oracle_v066, verify
from cursibench import full_study_final_dispatch_v1 as final, full_study_matrix_v1 as matrix
from cursibench.scale_action_output_v066 import normalize_model_action
from tests import test_gitlab_saved_git_oracle_v1 as f
from tests import test_gitlab_selection_worker_v066 as old_fixture


def scenario(partition, family):
    project=copy.deepcopy(f.PROJECT);project['partition']=partition
    project['full_path']=partition+'/fixture'
    progress=copy.deepcopy(f.PROGRESS);progress['issue_iids']['historical_duplicate']=2
    task={'task_id':'opaque-model-task','partition':partition,'project_family':project['full_path'],
          'template_group':family,'oracle':{'cve':'CVE-2030-0001','expected_priority':'priority::p2'}}
    before=f.baseline()
    for issue in before['db']['issues']:issue['state_id']=1
    f.seal(before)
    files={path:raw.encode() for path,raw in project['files'].items()}
    after=copy.deepcopy(before)
    if partition=='final_candidate_unsealed':
        after,files=f.changed(family)
        for issue in after['db']['issues']:issue['state_id']=1
    elif family=='issue_label_from_alert':after['db']['issue_label_links']=[{'id':202,'target_id':101,'label_id':201}]
    elif family=='issue_due_from_register':after['db']['issues'][0]['due_date']=project['policy']['issue_due']
    elif family=='milestone_window_from_policy':
        after['db']['milestones']=[{'id':501,'project_id':1,'title':project['policy']['milestone_title'],
                                  'start_date':project['policy']['milestone_start'],'due_date':project['policy']['milestone_due']}]
    elif family=='guest_member_from_roster':
        after['db']['members'].append({'id':303,'source_id':1,'user_id':12,'access_level':10,'expires_at':None})
    elif family=='issue_owner_transfer':after['db']['issue_assignees']=[{'issue_id':101,'user_id':10}]
    elif family=='false_positive_closure':after['db']['issues'][1]['state_id']=2
    elif family=='reporter_member_expiry':
        after['db']['members'].append({'id':303,'source_id':1,'user_id':12,'access_level':20,'expires_at':project['policy']['access_expiry']})
    elif family=='runbook_contact_annotation':
        files['docs/response-runbook.md']=project['files']['docs/response-runbook.md'].replace('Current contact: pending','Current contact: @fixture-oncall').encode()
        after['git']['1']['refs']['refs/heads/main']='d'*40
        after['git']['1']['main_blobs_sha256']={p:f.saved.sha256(raw) for p,raw in files.items()}
    else:raise AssertionError(family)
    f.seal(after)
    sidecar,raws=f.sidecar(before,after,files)
    return task,project,progress,before,after,sidecar,raws


def git_reader(sidecar, raws, events, reset):
    def git(pid,*args):
        assert pid==1 and not reset[0], 'Git capture happened after cold reset'
        events.append(('git',args))
        if args[0]=='diff':return raws[sidecar['diff_ref']['path']]
        if args[0]=='ls-tree':
            key='before_tree_ref' if args[-1]==sidecar['before_main_sha'] else 'after_tree_ref'
            return raws[sidecar[key]['path']]
        if args[0]=='show':return raws[sidecar['main_blob_refs'][args[1].split(':',1)[1]]['path']]
        raise AssertionError(args)
    return git


class NativeFixture(old_fixture.FakeSelectionSession):
    def __init__(self, identity, task, before):
        super().__init__(identity)
        self.original_task=task
        self.task={**identity,'visible_instruction':'Complete this selection record.'}
        self.baseline_semantic={'business_snapshot':before,'seed_lowerdirs_sha256':'b'*64}
        self.loop=SimpleNamespace(call=lambda value:value)
        self._check_scoped=lambda:True
        self._reload=lambda:'d'*64


class BackendFixture:
    def __init__(self, active, events, reset):self.active,self.events,self.reset=active,events,reset
    @contextmanager
    def open(self, _identity):
        try:yield self.active
        finally:
            self.events.append(('cold_reset',))
            self.reset[0]=True
            self.active.reset_semantic=copy.deepcopy(self.active.baseline_semantic)
            self.active.post_restore_exact=True
            self.active.environment_terminated=True


def binding_file(root):
    value=workers.public_binding();path=root/'binding.private.json'
    path.write_bytes(workers.canonical(value));path.chmod(0o600)
    return value,path,workers.digest(path.read_bytes())


class FullGitOracleTests(unittest.TestCase):
    def test_original_train_selection_and_final_positive_verdicts_are_exact(self):
        partitions=[('train',train_teacher_oracle_v066.TRAIN_FAMILIES),
                    ('selection',selection_oracle_v066.SELECTION_FAMILIES),
                    ('final_candidate_unsealed',f.FAMILIES)]
        for partition,families in partitions:
            for family in families:
                task,project,progress,before,after,sidecar,raws=scenario(partition,family)
                audited=oracle.audit_model_saved_task(task,before,after,project=project,progress=progress,
                    captured_git=sidecar,read_ref=lambda ref:raws[ref['path']],partition=partition,
                    expected_sourcebindings=oracle.source_bindings())
                with patch.object(verify,'_context',return_value=(project,progress)), \
                     patch.object(verify,'_git',side_effect=git_reader(sidecar,raws,[],[False])):
                    original=(train_teacher_oracle_v066.evaluate_train_task if partition=='train' else
                              selection_oracle_v066.evaluate_selection_task if partition=='selection' else
                              verify.evaluate_final_task)(task,before,after)
                self.assertEqual(audited['verdict'],original,(partition,family))
                self.assertEqual(audited['reward'],1.0)
                self.assertTrue(audited['full_git_tree_verified'])
                self.assertFalse(audited['historical_projection_allowed'])

    def test_protected_business_mutation_preserves_every_original_negative_verdict(self):
        for partition,families in [('train',train_teacher_oracle_v066.TRAIN_FAMILIES),
                                  ('selection',selection_oracle_v066.SELECTION_FAMILIES),
                                  ('final_candidate_unsealed',f.FAMILIES)]:
            for family in families:
                task,project,progress,before,after,sidecar,raws=scenario(partition,family)
                after['db']['issues'][1]['title']='Protected business field changed'
                f.seal(after)
                sidecar['after_business_sha256']=after['business_sha256']
                audited=oracle.audit_model_saved_task(task,before,after,project=project,progress=progress,
                    captured_git=sidecar,read_ref=lambda ref:raws[ref['path']],partition=partition,
                    expected_sourcebindings=oracle.source_bindings())
                with patch.object(verify,'_context',return_value=(project,progress)), \
                     patch.object(verify,'_git',side_effect=git_reader(sidecar,raws,[],[False])):
                    original=(train_teacher_oracle_v066.evaluate_train_task if partition=='train' else
                              selection_oracle_v066.evaluate_selection_task if partition=='selection' else
                              verify.evaluate_final_task)(task,before,after)
                self.assertEqual(audited['verdict'],original,(partition,family))
                self.assertEqual(audited['reward'],0.0)

    def test_partial_ci_extra_path_mode_and_same_commit_tree_fail_closed(self):
        task,project,progress,before,after,_,_=scenario('final_candidate_unsealed',f.FAMILIES[4])
        bad,files=f.changed(f.FAMILIES[4],True)
        for issue in bad['db']['issues']:issue['state_id']=1
        f.seal(bad)
        sidecar,raws=f.sidecar(before,bad,files)
        result=oracle.audit_model_saved_task(task,before,bad,project=project,progress=progress,captured_git=sidecar,
            read_ref=lambda ref:raws[ref['path']],partition=task['partition'],expected_sourcebindings=oracle.source_bindings())
        self.assertEqual(result['reward'],0.0)
        self.assertFalse(result['verdict']['no_regression'])
        task,project,progress,before,after,sidecar,raws=scenario('selection','runbook_contact_annotation')
        files={p:raw.encode() for p,raw in project['files'].items()}
        files['docs/response-runbook.md']=raws[sidecar['main_blob_refs']['docs/response-runbook.md']['path']]
        for extra in ({'unrelated.txt':('100644','blob','f'*40)},
                      {'docs/response-runbook.md':('100755','blob',f.object_id(files['docs/response-runbook.md']))}):
            sidecar,raws=f.sidecar(before,after,files,extra=extra)
            with self.assertRaises(f.saved.SavedGitEvidenceError):
                oracle.audit_model_saved_task(task,before,after,project=project,progress=progress,captured_git=sidecar,
                    read_ref=lambda ref:raws[ref['path']],partition='selection',expected_sourcebindings=oracle.source_bindings())
        sidecar,raws=f.sidecar(before,before,{p:r.encode() for p,r in project['files'].items()},extra={'unknown.txt':('100644','blob','f'*40)})
        with self.assertRaises(f.saved.SavedGitEvidenceError):
            oracle.audit_model_saved_task(task,before,before,project=project,progress=progress,captured_git=sidecar,
                read_ref=lambda ref:raws[ref['path']],partition='selection',expected_sourcebindings=oracle.source_bindings())
        with self.assertRaises(f.saved.SavedGitEvidenceError):
            oracle.audit_model_saved_task(task,before,after,project=project,progress=progress,captured_git=None,
                read_ref=None,partition='selection',expected_sourcebindings=oracle.source_bindings())


    def test_unrelated_native_git_edit_preserves_normal_original_model_negative(self):
        for partition,family in (('train','issue_due_from_register'),('selection','issue_owner_transfer')):
            task,project,progress,before,after,sidecar,raws=scenario(partition,family)
            after['git']['1']['refs']['refs/heads/main']='d'*40
            f.seal(after)
            files={p:r.encode() for p,r in project['files'].items()}
            sidecar,raws=f.sidecar(before,after,files,extra={'unrelated.txt':('100644','blob','f'*40)})
            audited=oracle.audit_model_saved_task(task,before,after,project=project,progress=progress,captured_git=sidecar,
                read_ref=lambda ref:raws[ref['path']],partition=partition,expected_sourcebindings=oracle.source_bindings())
            with patch.object(verify,'_context',return_value=(project,progress)):
                original=(train_teacher_oracle_v066.evaluate_train_task if partition=='train' else
                          selection_oracle_v066.evaluate_selection_task)(task,before,after)
            self.assertEqual(audited['verdict'],original)
            self.assertEqual(audited['reward'],0.0)


class FullGitIntegrationTests(unittest.TestCase):
    def test_every_partition_capture_precedes_reset_and_reopens_without_live_lookup(self):
        for partition,family in (('train','issue_due_from_register'),('selection','runbook_contact_annotation'),
                                 ('final_candidate_unsealed',f.FAMILIES[4])):
            task,project,progress,before,after,sidecar,raws=scenario(partition,family)
            events,reset=[],[False];identity={'task_id':task['task_id'],'package_sha256':'a'*64}
            active=NativeFixture(identity,task,before);active.finished=True
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory);root.chmod(0o700);(root/'artifacts').mkdir(mode=0o700)
                binding=workers.public_binding()
                backend=workers.FullGitBackend(BackendFixture(active,events,reset),partition=partition,binding=binding)
                backend.set_output_root(root)
                with patch.object(verify,'state_snapshot',side_effect=lambda:after if not reset[0] else (_ for _ in ()).throw(AssertionError('snapshot after reset'))), \
                     patch.object(verify,'_context',return_value=(project,progress)), \
                     patch.object(verify,'_git',side_effect=git_reader(sidecar,raws,events,reset)):
                    with backend.open(identity) as session:saved=session.read_saved_state()
                self.assertEqual(events[-1],('cold_reset',))
                self.assertEqual(len([row for row in events if row[0]=='git']),9)
                with patch.object(verify,'_context',side_effect=AssertionError('live lookup after reset')), \
                     patch.object(verify,'_git',side_effect=AssertionError('live Git after reset')):
                    audited=workers._verify_saved_proof(root/'artifacts',saved,identity,before,binding)
                self.assertEqual(audited['reward'],1.0)
                self.assertEqual(saved['full_git_original_verdict'],audited['verdict'])
                if partition=='final_candidate_unsealed':
                    self.assertEqual(saved['independent_score']['reward'],audited['verdict']['score'])
                    self.assertEqual(saved['independent_score']['checks_passed'],audited['verdict']['no_regression'])
                diff=root/'artifacts'/'full-git-proof'/'diff.private.txt';diff.write_bytes(b'fake.txt\n')
                with self.assertRaises(ValueError):workers._verify_saved_proof(root/'artifacts',saved,identity,before,binding)

    def test_uncertain_exit_retains_one_pre_reset_capture_without_model_credit(self):
        task,project,progress,before,after,sidecar,raws=scenario('selection','issue_owner_transfer')
        events,reset=[],[False];identity={'task_id':task['task_id'],'package_sha256':'a'*64}
        active=NativeFixture(identity,task,before)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);root.chmod(0o700);(root/'artifacts').mkdir(mode=0o700)
            binding=workers.public_binding();backend=workers.FullGitBackend(BackendFixture(active,events,reset),partition='selection',binding=binding);backend.set_output_root(root)
            with patch.object(verify,'state_snapshot',return_value=after),patch.object(verify,'_context',return_value=(project,progress)), \
                 patch.object(verify,'_git',side_effect=git_reader(sidecar,raws,events,reset)):
                with self.assertRaisesRegex(TimeoutError,'uncertain'):
                    with backend.open(identity):raise TimeoutError('uncertain fixture response')
            saved=workers.private_json(root/'artifacts'/'full-git-proof'/'captured-saved.private.json')
            self.assertEqual(saved['full_git_capture_reason'],'terminal_backend_exit_before_reset_no_model_credit')
            self.assertEqual(events[-1],('cold_reset',))
            with self.assertRaises(ValueError):workers._verify_saved_proof(root/'artifacts',saved,identity,before,binding)

    def test_teacher_and_selection_wrappers_run_original_loops_and_post_reset_audits(self):
        for partition,family in (('train','issue_due_from_register'),('selection','issue_owner_transfer')):
            task,project,progress,before,after,sidecar,raws=scenario(partition,family)
            identity={'task_id':task['task_id'],'package_sha256':'a'*64}
            events,reset=[],[False];active=NativeFixture(identity,task,before)
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory);root.chmod(0o700);binding,path,file_sha=binding_file(root)
                cohort=root/'cohort.private.json';cohort.write_text('{}');cohort.chmod(0o600)
                if partition=='train':
                    worker=workers.train_worker(full_git_binding_path=path,full_git_binding_file_sha256=file_sha,
                        private_output_root=root,cohort_freeze_path=cohort,enable_live=True)
                else:worker=workers.selection_worker(full_git_binding_path=path,full_git_binding_file_sha256=file_sha,cohort_freeze_path=cohort,enable_live=True)
                worker.backend.backend=BackendFixture(active,events,reset)
                output=root/'episode'
                with patch.object(workers.cohort_source,'validate_source',return_value={}), \
                     patch.object(workers.cohort_scope,'cohort_context',side_effect=lambda _value:__import__('contextlib').nullcontext()), \
                     patch.object(verify,'state_snapshot',return_value=after),patch.object(verify,'_context',return_value=(project,progress)), \
                     patch.object(verify,'_git',side_effect=git_reader(sidecar,raws,events,reset)):
                    if partition=='train':
                        output.mkdir(mode=0o700);(output/'frames').mkdir(mode=0o700)
                        def sample(observation,current):
                            action=normalize_model_action('{"type":"finish"}',observation,current_frame_id=current())
                            row={'action':action,'step':observation.step,'frame_id':observation.frame_id,'frame_sha256':observation.screenshot['sha256'],'teacher_result_sha256':'d'*64}
                            return {'action':action,'trace_row':row,'teacher_result_sha256':'d'*64}
                        with patch.object(workers.teacher.GitLabTrainEpisodeWorker,'_require_ratification',return_value=None):
                            result=worker.run_episode(task={**identity,'visible_instruction':active.task['visible_instruction']},out_dir=output,sample_teacher=sample,dispatch_e2b=lambda *_a,**_k:None)
                        self.assertTrue(result['episode_receipt_sha256'])
                    else:
                        started={'attempt_id':'selection-fixture','checkpoint_path_sha256':'a'*64}
                        session=old_fixture.FakeCampaign(root,[identity],started)
                        def provider(request,_prompt):
                            return {'schema':'envloop-gitlab-v066-selection-sampler-result-v1','status':'completed','reported_model':workers.selection.MODEL,
                                'checkpoint_path_sha256':'a'*64,'text':'{"type":"finish"}','stop_reason':'stop','elapsed_seconds':0.01,
                                'usage':{'input_tokens':request['input_tokens'],'image_tokens':request['image_tokens'],'output_tokens':5,'prompt_cache_hit_tokens':None,'provider_billed_tokens':None,'basis':'rendered_input_and_returned_output_not_invoice'}}
                        result=worker._task_episode(session=session,started=started,identity=identity,ordinal=1,out_dir=output,
                            training={'max_supervised_tokens':32768,'prefill_usd_per_million_tokens':'1','sample_usd_per_million_tokens':'2','billing_multiplier_upper':'1'},
                            policy={'seed':23,'temperature':0.0,'max_output_tokens':64,'max_actions_per_task':2,'max_wall_seconds_per_task':720},
                            app_quote=Decimal('0.5'),vision=old_fixture.FakeVision(),checkpoint_sha256='a'*64,sampler_provider=provider)
                        self.assertEqual(result['result_row']['score'],1)
                self.assertTrue((output/'artifacts'/'full-git-post-reset-audit.private.json').is_file())
                self.assertEqual(events[-1],('cold_reset',))
                self.assertIsNone(worker.backend.output_root)

    def test_shared_base_entry_always_supplies_full_git_worker_and_frozen_base_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);root.chmod(0o700);binding,path,file_sha=binding_file(root)
            cohort=root/'cohort-source.private.json';cohort.write_text('{}');cohort.chmod(0o600)
            study=SimpleNamespace(plan={'cells':[{'cell_id':'gitlab','base_checkpoint_sha256':'a'*64}]})
            with patch.object(shared.execution,'_verify_base_freeze',return_value={'freeze_receipt_sha256':'b'*64}), \
                 patch.object(shared.execution,'run_gitlab_shared_base',side_effect=lambda _study,_reconcile,**kw:kw['worker_factory']()) as original:
                worker=shared.run_gitlab_shared_base(study,lambda row:row,full_git_binding_path=path,
                    full_git_binding_file_sha256=file_sha,cohort_freeze_path=root/'cohort-source.private.json')
            self.assertIsInstance(worker.backend,workers.FullGitBackend)
            session=SimpleNamespace(cell=study.plan['cells'][0],study=study)
            with patch.object(shared.execution,'_verify_base_freeze',return_value={'freeze_receipt_sha256':'b'*64}):
                self.assertEqual(worker._resolve_checkpoint_path(session,'a'*64),workers.selection.MODEL)
                with self.assertRaises(ValueError):worker._resolve_checkpoint_path(session,'c'*64)
            changed=copy.deepcopy(binding);changed['source_sha256s']['gitlab_world/full_git_model_oracle_v1.py']='0'*64
            with self.assertRaises(ValueError):workers.validate_binding(changed)

    def test_trusted_budget_and_admission_dependency_drift_refuses_source_binding(self):
        binding=workers.public_binding()
        required=('full_study_budget_v1','full_study_campaign_dispatch_v1','full_study_teacher_adapter_v1',
                  'full_study_results_v1','full_study_shared_base_selection_v1','full_study_selection_paid_coverage_v1')
        for name in required:
            path='src/cursibench/'+name+'.py'
            self.assertIn(path,binding['source_sha256s'])
            original=Path.read_bytes
            def changed(candidate):
                return b'changed_source = True\n' if candidate==workers.ROOT/path else original(candidate)
            with self.subTest(path=path),patch.object(Path,'read_bytes',changed),self.assertRaises(ValueError):
                workers.validate_binding(binding)


if __name__=='__main__':unittest.main()
