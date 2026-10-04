"""Provenance, partial failure, original-source and no-dispatch regressions."""
from contextlib import ExitStack
from hashlib import sha256
from pathlib import Path
import copy
import json
import fcntl
import os
import tempfile
import time
import unittest
from unittest.mock import patch
from gitlab_world import v066_selection_reference_continuation_v1 as c


def exact_original_private_evidence_available():
    # Availability only. Present but corrupted evidence must run and fail its audit.
    required=[c.PRIOR/'root-selection-only-review-approved.private.json',
        c.PRIOR/'independent-terminal-partial-boot-audit.private.json',
        c.PRIOR/'independent-case000-trio-audit.private.json',
        c.PRIOR/'controls.private/intent.private.json',c.PRIOR/'controls.private/failure.private.json',
        c.PRIOR/'controls.private/task-000/trio.private.json',
        c.DIAGNOSTIC/'independent-terminal-cold-start-audit-20261004.private.json',
        c.DIAGNOSTIC/'terminal-restoration.private.json',
        c.DIAGNOSTIC/'diagnostic.private/native-runtime/owned-lifecycle-end.private.json']
    for mode,_ in c.MODES:
        case=c.PRIOR/f'controls.private/task-000/{mode}'
        required.extend([case/'result.private.json',case/'artifacts/baseline.private.json',
            case/'artifacts/saved-artifact.private.json',case/'artifacts/native-runtime/original-before.private.json',
            case/'artifacts/native-runtime/original-resumed.private.json'])
    return all(path.is_file() for path in required)


class ContinuationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve();self.out=self.root/'controls.private'
        self.identities=[{'task_id':f'original-{i:02d}','package_sha256':f'{i+1:064x}'} for i in range(20)]

    def write(self,path,value):c.world.write(path,value)

    def trio(self,directory,ordinal,identity):
        directory.mkdir(mode=0o700,parents=True);entries=[]
        for mode,score in c.MODES:
            folder=directory/mode;folder.mkdir(mode=0o700)
            self.write(folder/'result.private.json',{'score':score,'native_receipts':1,'model_calls':0,'reset_exact':True})
            entries.append({'mode':mode,'expected':score,'result_ref':c.ref(folder/'result.private.json')})
        row={'ordinal':ordinal,'identity':identity,'modes':entries};self.write(directory/'trio.private.json',row)
        return row

    def authority(self):
        old=self.root/'retained/task-000';self.trio(old,0,self.identities[0])
        plan=self.root/'plan.private.json';self.write(plan,{'source_sha256s':{}})
        binding=self.root/'binding.private.json';self.write(binding,{})
        return {'ordered_selection20':self.identities,'fresh_ordered_suffix':self.identities[1:],
            'retained_trio':{'trio_ref':c.ref(old/'trio.private.json')},'plan_ref':c.ref(plan),
            'native_binding_ref':c.ref(binding),'output_root':str(self.out),'startup_evidence_without_case_credit':{},
            'model_calls':0,'formal_admissions':0}

    def saved_audit(self,folder,*_):return c.private(folder/'result.private.json')

    @unittest.skipUnless(exact_original_private_evidence_available(),
        'requires exact original private GitLab evidence; public offline fixtures do not claim this audit passed')
    def test_actual_saved_old_trio_and_startup_evidence_reaudit_with_native_constructors_trapped(self):
        traps=[(c.world,'TaskWorld'),(c.world.cold,'NativeBackend'),(c.models,'FullGitBackend'),(c.original.selection,'RealGitLabSelectionBackend')]
        with ExitStack() as stack:
            mocks=[stack.enter_context(patch.object(module,name,side_effect=AssertionError('native dispatch forbidden'))) for module,name in traps]
            old=c._original_authority();retained,boundary=c._saved_evidence(old)
            for mock in mocks:mock.assert_not_called()
        self.assertEqual(retained['ordinal'],0);self.assertEqual([x['audit']['score'] for x in retained['audited_cases']],[0.,1.,0.])
        self.assertEqual(boundary['failed_task001_baseline']['case_credit'],0)
        self.assertEqual(boundary['unscored_success']['case_credit'],0)
        self.assertFalse(boundary['kas_fix_or_underlying_permission_resource_cause_proven'])

    def test_real_source_binding_keeps_workflow_native146_guard_and_actor_limits_unchanged(self):
        value=c.source_binding();self.assertIs(c.workflow,c.original.workflow)
        self.assertEqual(value['native_binding_sha256'],c.NATIVE_BINDING)
        self.assertEqual(value['original_controller_binding']['binding_sha256'],c.V3_BINDING)
        self.assertEqual(len(c.world.source_hashes()),146)
        self.assertEqual(c.models.public_binding()['matched_actor_budget']['max_actions'],90)
        self.assertEqual(c.models.public_binding()['matched_actor_budget']['wall_seconds'],720)
        self.assertFalse(value['model_or_final_authority'])

    def test_wrong_identity_partial_or_reordered_trio_cannot_join(self):
        directory=self.root/'trio';row=self.trio(directory,0,self.identities[0])
        with patch.object(c.original,'_audit_case',side_effect=self.saved_audit) as audit:
            self.assertEqual(len(c.audit_trio(directory,0,self.identities[0],{},self.root/'plan')['audited_cases']),3)
            for bad in (row|{'identity':self.identities[1]},row|{'modes':row['modes'][:2]},row|{'modes':list(reversed(row['modes']))}):
                with patch.object(c,'private',side_effect=lambda p,*_:bad if Path(p).name=='trio.private.json' else json.loads(Path(p).read_bytes())):
                    with self.assertRaisesRegex(ValueError,'whole_trio'):c.audit_trio(directory,0,self.identities[0],{},self.root/'plan')
            self.assertEqual(audit.call_count,3)

    def test_mode_result_ref_or_real_saved_score_change_refuses(self):
        directory=self.root/'trio';row=self.trio(directory,0,self.identities[0]);bad=copy.deepcopy(row)
        bad['modes'][0]['result_ref']=bad['modes'][1]['result_ref']
        with patch.object(c,'private',side_effect=lambda p,*_:bad if Path(p).name=='trio.private.json' else json.loads(Path(p).read_bytes())),patch.object(c.original,'_audit_case') as audit:
            with self.assertRaisesRegex(ValueError,'provenance_ref'):c.audit_trio(directory,0,self.identities[0],{},self.root/'plan')
            audit.assert_not_called()
        with patch.object(c.original,'_audit_case',return_value={'score':1.,'native_receipts':1,'model_calls':0,'reset_exact':True}):
            with self.assertRaisesRegex(ValueError,'saved_case'):c.audit_trio(directory,0,self.identities[0],{},self.root/'plan')

    def test_transitive_artifact_namespace_detects_changed_old_bytes_and_refuses_symlink(self):
        directory=self.root/'immutable';directory.mkdir(mode=0o700)
        p=directory/'raw.private.json';self.write(p,{'same_identity':True})
        before=c.artifact_namespace_ref(directory);p.write_bytes(b'{"same_identity":true,"changed":true}')
        self.assertNotEqual(before,c.artifact_namespace_ref(directory));self.assertFalse(before['copied_or_relabeled_as_fresh'])
        (directory/'alias').symlink_to(p)
        with self.assertRaisesRegex(ValueError,'symlink'):c.artifact_namespace_ref(directory)

    def test_join_rejects_duplicate_identity_omitted_suffix_and_old_results_relabeled_fresh(self):
        authority=self.authority();fresh=[{'ordinal':i,'identity':self.identities[i],
            'provenance':'fresh_original_suffix_trio','fresh_in_continuation':True,
            'trio_ref':{'path':str(self.out/f'task-{i:03d}/trio.private.json'),'sha256':'a'*64}} for i in range(1,20)]
        joined=c.join_rows(authority,fresh);self.assertFalse(joined[0]['fresh_in_continuation']);self.assertEqual(len(joined),20)
        with self.assertRaisesRegex(ValueError,'ninetee'):c.join_rows(authority,fresh[:-1])
        for field,value in (('identity',self.identities[0]),('trio_ref',authority['retained_trio']['trio_ref']),('fresh_in_continuation',False)):
            bad=copy.deepcopy(fresh);bad[0][field]=value
            with self.assertRaisesRegex(ValueError,'provenance'):c.join_rows(authority,bad)

    def test_no_execute_cannot_read_authority_or_open_runtime(self):
        with patch.object(c,'check_authority') as authority,patch.object(c,'check_worker_parent') as parent:
            with self.assertRaisesRegex(ValueError,'explicit_execution'):
                c.run(review_path='missing',review_sha256='a'*64,supervisor_intent_sha256='b'*64)
            authority.assert_not_called();parent.assert_not_called()

    def test_authority_source_or_roster_change_is_refused(self):
        path=self.root/'review.private.json';value={'schema':c.SCHEMA,'output_root':str(self.out),'identity':'original'}
        self.write(path,value)
        with patch.object(c,'review_contract',return_value=value|{'identity':'changed'}):
            with self.assertRaisesRegex(ValueError,'exact_current_root'):c.check_authority(path,c.ref(path)['sha256'])

    def test_worker_requires_exact_parent_and_live_exclusive_kernel_lease(self):
        intent={'pid':os.getppid(),'one_worker_only':True};p=self.root/'supervisor-start.private.json';self.write(p,intent)
        fd=os.open(self.root/'supervisor-lease.private.lock',os.O_CREAT|os.O_EXCL|os.O_RDWR,0o600)
        try:
            with self.assertRaisesRegex(ValueError,'kernel_lease'):c.check_worker_parent(self.root,c.ref(p)['sha256'])
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            self.assertEqual(c.check_worker_parent(self.root,c.ref(p)['sha256']),intent)
            with patch.object(c.os,'getppid',return_value=0):
                with self.assertRaisesRegex(ValueError,'supervisor_parent'):c.check_worker_parent(self.root,c.ref(p)['sha256'])
        finally:fcntl.flock(fd,fcntl.LOCK_UN);os.close(fd)

    def test_host_reserve_does_not_alter_native_or_actor_limits(self):
        c.host_reserve(1260,clock=lambda:0)
        with self.assertRaisesRegex(ValueError,'no_new_case'):c.host_reserve(1259.9,clock=lambda:0)
        self.assertEqual(c.HOST_SECONDS,86400);self.assertEqual(c.CLEANUP_GRACE_SECONDS,1500)

    def test_primary_startup_and_cleanup_failures_remain_separate(self):
        primary=ValueError('startup failure');cleanup=OSError('restoration unavailable');cleanup.__context__=primary
        result=c.exception_evidence(cleanup)
        self.assertEqual(result['original_primary_exception']['error'],'startup failure')
        self.assertEqual(result['separate_outer_or_cleanup_exceptions'][0]['error'],'restoration unavailable')

    def run_fixture(self,fail=False):
        authority=self.authority();review=self.root/c.ROOT_APPROVAL_NAME;self.write(review,authority)
        self.write(self.root/'supervisor-start.private.json',{'offline_fixture_only':True})
        calls=[]
        def case(folder,identity,mode,score,*_,**_kwargs):
            calls.append((int(folder.parent.name[-3:]),mode,identity))
            if fail and mode=='positive':raise ValueError('fixture failed before whole trio')
            folder.mkdir(mode=0o700);self.write(folder/'result.private.json',{'score':score,'native_receipts':1,'reset_exact':True,'model_calls':0})
            return {'mode':mode,'expected':score,'result_ref':c.ref(folder/'result.private.json')}
        with patch.object(c,'check_authority',return_value=authority),patch.object(c,'check_worker_parent',return_value={'authority_ref':c.ref(review),'worker_deadline_monotonic':time.monotonic()+100000}),patch.object(c.world,'checked_plan',return_value=({'source_sha256s':{}},{})),patch.object(c.models,'validate_binding',return_value={}),patch.object(c,'run_case',side_effect=case),patch.object(c,'source_binding',return_value={}),patch.object(c,'audit',return_value={'tasks':20,'cases':60}):
            if fail:
                with self.assertRaisesRegex(ValueError,'before whole trio'):c.run(review_path=review,review_sha256=c.ref(review)['sha256'],supervisor_intent_sha256='b'*64,execute=True)
            else:c.run(review_path=review,review_sha256=c.ref(review)['sha256'],supervisor_intent_sha256='b'*64,execute=True)
        return authority,calls

    def test_exact57_new_cases_original_order_and_direct_retained_ref(self):
        authority,calls=self.run_fixture()
        self.assertEqual([(i,m) for i,m,_ in calls],[(i,m) for i in range(1,20) for m,_ in c.MODES])
        result=c.private(self.out/'result.private.json');self.assertEqual(result['retained_original_cases'],3);self.assertEqual(result['fresh_cases'],57)
        self.assertEqual(result['rows'][0]['trio_ref'],authority['retained_trio']['trio_ref'])
        self.assertFalse((self.out/'task-000').exists())

    def test_partial_failure_retains_old_provenance_and_completed_case_but_no_new_whole_trio(self):
        authority,calls=self.run_fixture(fail=True);failure=c.private(self.out/'failure.private.json')
        self.assertEqual([(i,m) for i,m,_ in calls],[(1,'baseline'),(1,'positive')])
        self.assertEqual(failure['new_whole_trio_refs'],[]);self.assertEqual(len(failure['new_completed_case_refs']),1)
        self.assertEqual(failure['retained_trio_ref'],authority['retained_trio']['trio_ref'])
        self.assertFalse((self.out/'task-001/trio.private.json').exists());self.assertFalse((self.out/'result.private.json').exists())
        with patch.object(c,'check_authority',return_value=authority):
            with self.assertRaisesRegex(ValueError,'cannot_qualify'):c.audit(review_path='unused',review_sha256='a'*64)

    def test_aggregate_reaudits_all20_original_identities_and60_saved_cases(self):
        authority,calls=self.run_fixture();review=self.root/c.ROOT_APPROVAL_NAME;result=c.private(self.out/'result.private.json')
        audited=[]
        def saved(folder,identity,*args):audited.append((folder,identity));return self.saved_audit(folder)
        actual_private=c.private
        def standalone_fixture_private(path,*args):
            p=Path(path)
            if p.name.endswith('startup-proof.private.json') and (p.is_relative_to(c.PRIOR) or p.is_relative_to(c.DIAGNOSTIC)):
                return {'identity':{'container_id_sha256':'d'*64}}
            return actual_private(path,*args)
        with patch.object(c,'check_authority',return_value=authority),patch.object(c,'source_binding',return_value={}),patch.object(c.models,'validate_binding',return_value={}),patch.object(c.original,'_audit_case',side_effect=saved),patch.object(c,'audit_fresh_provenance') as fresh,patch.object(c,'private',side_effect=standalone_fixture_private):
            actual=c.audit(review_path=review,review_sha256=c.ref(review)['sha256'])
        self.assertEqual(actual['cases'],len(audited));self.assertEqual(len(audited),60)
        self.assertEqual([identity for _,identity in audited],[identity for identity in self.identities for _ in c.MODES])
        self.assertTrue(all('retained' in str(folder) for folder,_ in audited[:3]))
        self.assertEqual(fresh.call_count,57)

    def test_actual_worker_native_time_and_clone_boundary_rejects_copied_old_case(self):
        stage=self.root;folder=stage/'case';native=folder/'artifacts/native-runtime';native.mkdir(mode=0o700,parents=True)
        authority={'path':'approved','sha256':'f'*64}
        self.write(stage/'supervisor-start.private.json',{'pid':42,'authority_ref':authority,'worker_started_monotonic':90,'worker_deadline_monotonic':1000})
        self.write(stage/'worker-start.private.json',{'pid':123,'supervisor_pid':42})
        self.write(stage/'worker-process-start.private.json',{'pid':123,'ppid':42,'authority_ref':authority,'started_monotonic':100,'supervisor_ref':c.ref(stage/'supervisor-start.private.json')})
        worker_ref=c.ref(stage/'worker-process-start.private.json')
        self.write(folder/'fresh-case-intent.private.json',{'schema':'gitlab-continuation-fresh-case-intent-v1','identity':self.identities[1],'mode':'baseline','worker_pid':123,'worker_ref':worker_ref,'authority_ref':authority,'started_monotonic':110})
        self.write(native/'owned-lifecycle-start.private.json',{'started_monotonic':111})
        self.write(native/'owned-lifecycle-end.private.json',{'started_monotonic':111,'ended_monotonic':121})
        for i in (0,1):self.write(native/f'cycle-{i}-startup-proof.private.json',{'identity':{'container_id_sha256':str(i)*64}})
        complete={'schema':'gitlab-continuation-fresh-case-completed-v1','intent_ref':c.ref(folder/'fresh-case-intent.private.json'),'worker_ref':worker_ref,'worker_pid':123,'native_start_ref':c.ref(native/'owned-lifecycle-start.private.json'),'native_end_ref':c.ref(native/'owned-lifecycle-end.private.json'),'completed_monotonic':122}
        p=folder/'fresh-case-completed.private.json';self.write(p,complete);entry={'fresh_provenance_ref':c.ref(p)}
        seen=set();c.audit_fresh_provenance(folder,entry,self.identities[1],'baseline',stage,seen);self.assertEqual(len(seen),2)
        with self.assertRaisesRegex(ValueError,'clone_identity_reused'):c.audit_fresh_provenance(folder,entry,self.identities[1],'baseline',stage,seen)
        # A whole old artifact set copied into the fresh path still predates its actual worker.
        (native/'owned-lifecycle-start.private.json').write_text('{"started_monotonic":30}')
        (native/'owned-lifecycle-end.private.json').write_text('{"started_monotonic":30,"ended_monotonic":40}')
        complete.update(native_start_ref=c.ref(native/'owned-lifecycle-start.private.json'),native_end_ref=c.ref(native/'owned-lifecycle-end.private.json'))
        p.write_text(json.dumps(complete));entry={'fresh_provenance_ref':c.ref(p)}
        with self.assertRaisesRegex(ValueError,'old_artifacts'):c.audit_fresh_provenance(folder,entry,self.identities[1],'baseline',stage,set())


if __name__=='__main__':unittest.main()
