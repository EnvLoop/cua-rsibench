"""Offline original selection-only authority and guarded recipe boundaries."""
from pathlib import Path
from hashlib import sha256
import asyncio
import copy
import json
from contextlib import contextmanager
import time
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from gitlab_world import v066_selection_reference_controls_v1 as controls
from playwright.async_api import async_playwright
from tests.test_native_surface_guard_policy_v1 import envelope as native_envelope, action as native_action


class SelectionControlTests(unittest.TestCase):
    def test_original_families_are_selection_only(self):
        self.assertEqual(controls.oracle.SELECTION_FAMILIES, {
            'issue_owner_transfer', 'false_positive_closure',
            'runbook_contact_annotation', 'reporter_member_expiry'})
        self.assertEqual(controls.MODES, (('baseline', 0.0), ('positive', 1.0), ('wrong_variant', 0.0)))

    def test_source_binding_preserves_native146_and_distinct_controller_authority(self):
        before = controls.models.public_binding()
        bound = controls.source_binding()
        self.assertEqual(bound['native_binding_sha256'], before['binding_sha256'])
        self.assertEqual(controls.models.public_binding(), before)
        self.assertEqual(len(before['source_sha256s']), 146)
        self.assertFalse(bound['model_lane_authority'])

    def test_disabled_run_cannot_read_authority_open_or_dispatch(self):
        with patch.object(controls, '_check_authority') as check, patch.object(controls.models, 'FullGitBackend') as backend:
            with self.assertRaisesRegex(ValueError, 'explicit_execution'):
                controls.run(review_path=Path('missing'), review_sha256='a'*64)
            check.assert_not_called(); backend.assert_not_called()

    def test_failed_output_cannot_audit_or_gain_source_credit(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root/'failure.private.json').write_text('{}')
            with patch.object(controls, '_check_authority', return_value={'output_root': folder}):
                with self.assertRaisesRegex(ValueError, 'failed_or_wrong_intent'):
                    controls.audit(review_path='unused', review_sha256='a'*64)

    def test_controller_budget_proxy_forwards_exact_action_and_never_changes_native_guard(self):
        calls=[]
        class Guard:
            lease={'expires_at':100}
            def clock(self): return 0
            async def dispatch(self, action): calls.append(action);return {'status':'applied','code':'ok'}
        active=SimpleNamespace(step=89,guard=Guard());proxy=controls._ReferenceActive(active)
        action={'type':'click','task_id':'unit','step':89}
        self.assertEqual(asyncio.run(proxy.guard.dispatch(action)),{'status':'applied','code':'ok'})
        self.assertIs(calls[0],action);self.assertIs(proxy.guard.lease,active.guard.lease)
        active.step=90
        with self.assertRaisesRegex(ValueError,'budget_expired'):asyncio.run(proxy.guard.dispatch(action))
        self.assertEqual(len(calls),1)

    def test_original_selection_contract_rejects_order_or_controller_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);path=root/'review.private.json'
            value={'schema':controls.SCHEMA,'explicit_selection_only_authority':True,
                'plan_ref':{'path':'plan'},'native_binding_ref':{'path':'binding'},
                'train_accept_ref':{'path':'train','sha256':'a'*64},
                'source_review_ref':{'path':'source','sha256':'b'*64},'output_root':'output',
                'ordered_selection20':[{'task_id':str(i)} for i in range(20)]}
            controls.world.write(path,value)
            with patch.object(controls,'review_contract',return_value=copy.deepcopy(value)):
                self.assertEqual(controls._check_authority(path,controls.ref(path)['sha256']),value)
            changed=copy.deepcopy(value);changed['ordered_selection20'].reverse()
            with patch.object(controls,'review_contract',return_value=changed):
                with self.assertRaisesRegex(ValueError,'root_review_changed'):
                    controls._check_authority(path,controls.ref(path)['sha256'])

    def test_exact_native_inputs_and_all146_bytes_are_unchanged(self):
        from gitlab_world import v066_uniform_model_workers_v15 as original
        self.assertIs(controls.models,original)
        self.assertIs(controls.selection.RealGitLabSelectionBackend,
                      original.selection.RealGitLabSelectionBackend)
        self.assertEqual(controls.models.public_binding()['binding_sha256'],
                         '07c1520799c160d4394f9f943601a83f18da825f0ce87b2faa776c66878608be')

    def test_authoritative_uri_rejects_other_project_branch_source_or_credentials(self):
        base=controls.world.runtime.BASE
        active=SimpleNamespace(project_path='owned/project',page=SimpleNamespace(
            url=base+'/owned/project/-/blob/main/security/kev-register.csv'))
        controls._owned_uri(active,'/-/blob/main/security/kev-register.csv')
        for url in ('http://127.0.0.1:8018/foreign/project/-/blob/main/security/kev-register.csv',
                    'http://127.0.0.1:8018/owned/project/-/blob/other/security/kev-register.csv',
                    'http://u:p@127.0.0.1:8018/owned/project/-/blob/main/security/kev-register.csv'):
            active.page.url=url
            with self.subTest(url=url),self.assertRaisesRegex(ValueError,'original_project_uri'):
                controls._owned_uri(active,'/-/blob/main/security/kev-register.csv')

    def test_exact_twenty_sixty_mode_loop_and_consumed_authority_without_paid_factory(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);out=root/'controls';review=root/'review.private.json'
            rows=[{'task_id':str(i),'package_sha256':f'{i+1:064x}'} for i in range(20)]
            binding=controls.models.public_binding();bpath=root/'binding.private.json';controls.world.write(bpath,binding)
            plan=root/'plan.private.json';controls.world.write(plan,{'source_sha256s':binding['source_sha256s']})
            authority={'output_root':str(out),'ordered_selection20':rows,
                'plan_ref':controls.ref(plan),'native_binding_ref':controls.ref(bpath)}
            controls.world.write(review,authority);sequence=[]
            class Active:
                step=0;post_restore_exact=True;environment_terminated=True;baseline_semantic={}
                def __init__(self):
                    self.guard=SimpleNamespace(lease={'expires_at':time.monotonic()+100},clock=time.monotonic)
                    self.original_task={};self.loop=SimpleNamespace(call=lambda coroutine:asyncio.run(coroutine))
                def observe(self,**_):return SimpleNamespace(frame_id='local')
                def dispatch(self,action):self.step+=1
                def read_saved_state(self):return {'independent_score':{'reward':1.0 if sequence[-1][1]=='positive' else 0.0}}
            class Backend:
                def __init__(self,*args,**kw):self.phase=None
                def set_output_root(self,path):self.folder=path
                @contextmanager
                def open(self,identity):yield Active()
            async def workflow(active,task,mode,path):sequence.append((int(path.parent.name[-3:]),mode))
            def audit_case(path,*_):return {'score':1.0 if path.name=='positive' else 0.0,'native_receipts':1}
            with patch.object(controls,'_check_authority',return_value=authority), \
                 patch.object(controls.world,'checked_plan',return_value=({'source_sha256s':binding['source_sha256s']},{})), \
                 patch.object(controls.models,'FullGitBackend',Backend), \
                 patch.object(controls.selection,'RealGitLabSelectionBackend',return_value=object()), \
                 patch.object(controls,'workflow',side_effect=workflow), \
                 patch.object(controls.reference,'normalize_model_action',return_value={'type':'finish'}), \
                 patch.object(controls,'_audit_case',side_effect=audit_case):
                result=controls.run(review_path=review,review_sha256=controls.ref(review)['sha256'],execute=True)
                self.assertEqual(sequence,[(i,mode) for i in range(20) for mode,_ in controls.MODES])
                self.assertEqual(result['completed_count'],20);self.assertTrue(result['source_visual_review_pending'])
                self.assertEqual(result['formal_admissions'],0)
                with self.assertRaises(ValueError):controls.run(review_path=review,review_sha256=controls.ref(review)['sha256'],execute=True)
                self.assertEqual(len(sequence),60)


class ReadinessTests(unittest.TestCase):
    def test_actual_local_chromium_semantic_csv_readiness_and_refusals(self):
        async def check():
            async with async_playwright() as p:
                browser=await p.chromium.launch(headless=True)
                try:
                    page=await browser.new_page()
                    await page.route('**/*',lambda route:route.abort())
                    active=SimpleNamespace(page=page,guard=SimpleNamespace(lease={'expires_at':time.monotonic()+2}))
                    headers='<tr>'+''.join('<th>'+x+'</th>' for x in ('asset_id','cve_id','vendor','product','site','disposition'))+'</tr>'
                    table='<table><thead>'+headers+'</thead><tbody><tr><td>unit-asset</td><td>unit-cve</td><td>vendor</td><td>product</td><td>site</td><td>active</td></tr></tbody></table>'
                    await page.set_content('<p>unit-cve outside loading table</p>'+table)
                    await controls._readable(active,page.get_by_role('table'),['unit-cve'],table=True)
                    await controls._readable(active,page.get_by_role('table'),[],table=True,
                        target_row=['unit-asset','unit-cve','vendor','product','site','active'])
                    active.guard.lease['expires_at']=time.monotonic()+.04
                    with self.assertRaises((ValueError,TimeoutError)):
                        await controls._readable(active,page.get_by_role('table'),[],table=True,
                            target_row=['wrong-asset','unit-cve','vendor','product','site','active'])
                    active.guard.lease['expires_at']=time.monotonic()+.04
                    with self.assertRaises((ValueError,TimeoutError)):
                        await controls._readable(active,page.get_by_role('table'),[],table=True,
                            target_row=['unit-asset','unit-cve','vendor','product','site','watch'])
                    for html in ('<p>unit-cve</p><table><thead>'+headers+'</thead><tbody></tbody></table>',
                                 table.replace('<td>site</td>','<td></td>'),table+table):
                        await page.set_content(html);active.guard.lease['expires_at']=time.monotonic()+.04
                        with self.assertRaises((ValueError,TimeoutError)):
                            await controls._readable(active,page.get_by_role('table'),['unit-cve'],table=True)
                    await page.set_content('<div id="mount">loading</div>')
                    await page.evaluate('html=>{setTimeout(()=>{document.querySelector("#mount").innerHTML=html},25);}',table)
                    active.guard.lease['expires_at']=time.monotonic()+1
                    await controls._readable(active,page.get_by_role('table'),['unit-cve'],table=True)
                    self.assertEqual(await page.get_by_role('table').count(),1)
                finally:await browser.close()
        asyncio.run(check())


class NativeAuditLinkTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.root=Path(self.directory.name);self.turn=self.root/'turn-000';self.turn.mkdir(mode=0o700)
        self.identity={'task_id':'visible-task-1','package_sha256':'e'*64}
        def artifact(relative,value,kind):
            path=self.root/relative;path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
            raw=value if isinstance(value,bytes) else controls.models.common.canonical(value)
            path.write_bytes(raw);path.chmod(0o600)
            return {'schema':'native-guard-artifact-ref-v1','path':relative,
                'sha256':sha256(raw).hexdigest(),'size':len(raw),'kind':kind}
        self.artifact=artifact
        self.obs=native_envelope('observation');self.cur=native_envelope('predispatch');self.action=native_action(step=0)
        for envelope in (self.obs,self.cur):
            envelope['step']=0
            phase=envelope['phase']
            envelope['raw_image']=artifact('turn-000/'+phase+'.png',b'offline immutable pixels','raw_'+phase+'_image')
            envelope['raw_envelope']=artifact('turn-000/'+phase+'-native.private.json',{'offline_native':True},'native_'+phase+'_envelope')
            artifact('turn-000/'+phase+'-envelope.private.json',envelope,'native_observation_envelope')
        lease_evidence=artifact('turn-000/lease-check.private.json',{'kernel_lock_active':True},'lease_check')
        check={'schema':'native-surface-lease-check-v1','lease_sha256':controls.policy.digest(self.cur['lease']),
               'status':'active','checked_at':21.0,'expires_at':50.0,'evidence':lease_evidence}
        decision=controls.policy.decision(self.obs,self.cur,self.action,lease_check=lambda _:check,now=21.0)
        self.assertEqual(decision['status'],'accepted')
        artifact('turn-000/decision.private.json',decision,'native_decision')
        intent=artifact('turn-000/intent.private.json',{'action':self.action,'decision_sha256':controls.policy.digest(decision)},'action_intent')
        driver=artifact('turn-000/driver.private.json',{'result':'succeeded'},'driver_result')
        artifact('turn-000/nonce.private.json',{'frame_id':self.action['frame_id'],'consumed':True},'dispatch_receipt')
        self.receipt={'schema':'native-surface-dispatch-receipt-v1','policy_sha256':controls.policy.POLICY_SHA,
            'decision_sha256':controls.policy.digest(decision),'action_sha256':controls.policy.digest(self.action),
            'frame_id':self.action['frame_id'],'step':0,'status':'applied','reason':'native_driver_succeeded',
            'turn_consumed':True,'nonce_invalidated':True,'intent':intent,'driver_result':'succeeded','driver_evidence':driver}
        self.receipt_path=self.turn/'receipt.private.json';artifact('turn-000/receipt.private.json',self.receipt,'dispatch_receipt')

    def test_actual_policy_reaudit_binds_every_receipt_edge(self):
        self.assertEqual(controls._audit_native(self.root,self.identity),1)
        for key,value in (('action_sha256','0'*64),('decision_sha256','0'*64),('frame_id','other-frame')):
            bad=copy.deepcopy(self.receipt);bad[key]=value
            self.artifact('turn-000/receipt.private.json',bad,'dispatch_receipt')
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'receipt_action_decision_or_intent_link'):
                controls._audit_native(self.root,self.identity)
        bad=copy.deepcopy(self.receipt)
        bad['intent']=self.artifact('other-intent.private.json',{'action':self.action,'decision_sha256':self.receipt['decision_sha256']},'action_intent')
        self.artifact('turn-000/receipt.private.json',bad,'dispatch_receipt')
        with self.assertRaisesRegex(ValueError,'receipt_action_decision_or_intent_link'):
            controls._audit_native(self.root,self.identity)

    def test_changed_deep_lease_evidence_is_reopened_and_refused(self):
        self.artifact('turn-000/lease-check.private.json',{'kernel_lock_active':False},'lease_check')
        with self.assertRaises(Exception):controls._audit_native(self.root,self.identity)

    def test_current_document_change_during_read_only_sample_refuses(self):
        async def check():
            async with async_playwright() as p:
                browser=await p.chromium.launch(headless=True)
                try:
                    page=await browser.new_page();await page.route('**/*',lambda route:route.abort())
                    await page.set_content('<p>expected visible source</p>')
                    active=SimpleNamespace(page=page,guard=SimpleNamespace(lease={'expires_at':time.monotonic()+1}))
                    locator=page.locator('body');actual=locator.inner_text
                    async def text():
                        value=await actual();await page.evaluate("location.hash='other-source'");return value
                    with patch.object(locator,'inner_text',side_effect=text):
                        with self.assertRaisesRegex(ValueError,'document_changed'):
                            await controls._readable(active,locator,['expected'])
                finally:await browser.close()
        asyncio.run(check())


if __name__ == '__main__': unittest.main()
