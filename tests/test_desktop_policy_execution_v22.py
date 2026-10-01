"""Actual twenty-task policy orchestration; synthetic sampler/episode surfaces."""
import json
import shutil
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from cursibench import full_study_runtime_v2 as runtime
from native_desktop_factory import policy_execution_v22 as runner
from native_desktop_factory import qwen_sampler_process_v21 as rpc
from tests import test_full_study_campaign_dispatch_v1 as old_fixture
from tests import v22_policy_runtime_fixture as v2


class PipelineTests(unittest.TestCase):
    def test_all_twenty_tasks_and_consumed_paid_ids_are_retained_for_base_and_four_checkpoint_slots(self):
        for owner in ['shared-base',*runtime.matrix.RESEARCHERS]:
            with self.subTest(owner=owner):
                f=old_fixture.FullStudyDispatchTests();f.setUp()
                try:
                    # Complete all four synthetic frozen rate cards before
                    # creating the new parent freeze; none is a real route.
                    protocol=json.loads(f.manifest_path.read_bytes())
                    for rid,ref in protocol['configurations']['researchers'].items():
                        config_path=f.root/ref['path'];config=json.loads(config_path.read_bytes())
                        route=config['assets']['provider_route'];route_path=config_path.parent/route['path']
                        value={'schema':'cua-agentrouterhub-rate-upper-v1','model':runtime.matrix.RESEARCHERS[rid],
                            'base_url':'https://sub2api.agentrouterhub.com','input_usd_per_million_tokens':'10',
                            'output_usd_per_million_tokens':'50','fixed_usd_per_call':'0','billing_multiplier_upper':'2'}
                        route_path.write_bytes(runtime.policy.canonical(value));route['sha256']=runtime.policy.sha(route_path.read_bytes())
                        config_path.write_bytes(runtime.policy.canonical(config));ref['sha256']=runtime.policy.sha(config_path.read_bytes())
                    f.manifest_path.write_bytes(runtime.policy.canonical(protocol));shutil.rmtree(f.prepared)
                    runtime.campaign.pre_campaign.prepare(f.manifest_path,f.prepared)
                    f.witness['protocol_manifest_sha256']=runtime.policy.sha(f.manifest_path.read_bytes())
                    f.witness['campaign_plan_sha256']=runtime.policy.sha((f.prepared/'campaign-plan.json').read_bytes())
                    study=v2.study(f.frozen());cell='desktop-native' 
                    f.runtime_gate_mock.side_effect=None
                    f.runtime_gate_mock.return_value={'runtime_spec_sha256':'d'*64,'toy_public_receipt_sha256':'e'*64,'runtime_gate_source_sha256':'f'*64}
                    if owner=='shared-base':
                        session=runtime.SharedBaseSession(study,cell);started=session.started;checkpoint=None
                    else:
                        path=v2.base_receipt(study,cell)
                        session=study.open_campaign(study.repo_root/'work'/owner,cell_id=cell,researcher_id=owner,now=lambda:f.clock[0])
                        report=lambda: {'reported_model':runtime.matrix.RESEARCHERS[owner],'status':'completed','usage':{'input_tokens':100,'output_tokens':50}}
                        with runtime.runtime_context(study),patch.object(old_fixture,'fake_researcher_receipt',report):
                            f.trained_candidate(session)
                            started=session.start_selection_attempt(round_index=1,attempt_id='selection-v22-'+owner)
                        checkpoint='tinker://fake/sampler_weights/ckpt-1'
                    salt=study.repo_root/'work/salt.private.json';runtime.campaign._private_write_new(salt,b'{"variant_salt":"synthetic-only"}\n')
                    seen=[];samplers=[]
                    class Sampler:
                        def __init__(self,*,journal_root,plan_sha256,**kw):
                            self.journal=Path(journal_root);self.journal.mkdir(mode=0o700)
                            self.plan=plan_sha256;samplers.append(self)
                        def start(self,**kw):return {'status':'ready'}
                        def close(self,success):
                            runtime.campaign._private_write_new(self.journal/'child-terminal.private.json',runtime.policy.canonical({
                                'provider_shutdown_acknowledged':True,'forced_termination':False,'success':success}))
                    class Worker:
                        def __init__(self):self.study=study
                        def _gate(self):return {'private_map':str(salt)}
                        def _policy(self):
                            cell=next(v for v in study.plan['cells'] if v['cell_id']=='desktop-native')
                            return cell,{},cell['sampling'],'1000'
                        def _packages(self,admitted,identities,split):return [{'identity':{k:r[k] for k in ('task_id','package_sha256')}} for r in identities]
                        def _episode(self,*,package,ordinal,batch,paid,**kw):
                            identity=package['identity'];seen.append(identity['task_id'])
                            for phase in ('actor','reset'):
                                paid.invoke(suffix='env-'+str(ordinal)+'-'+phase,category='e2b',identity=identity,
                                    request={'phase':phase,'lease_seconds':1200},provider=lambda _: {'status':'active'})
                            paid.invoke(suffix='sample-'+str(ordinal),category='tinker',identity=identity,
                                request={'frame_sha256':'f'*64,'step':0},provider=lambda _: {'status':'completed','elapsed_seconds':0.01,
                                    'usage':{'input_tokens':10,'image_tokens':5,'output_tokens':2}})
                            out=Path(batch)/'gui'/identity['task_id']/'evaluator';out.mkdir(mode=0o700,parents=True)
                            return ({**identity,'score':0,'saved_state_sha256':'d'*64,'verifier_receipt_sha256':'e'*64,'reset_receipt_sha256':'f'*64},out,[],0,'finished')
                    prospective=runner.integration.proposal();prospective['base_checkpoint_sha256']=session.started['checkpoint_path_sha256'] if owner=='shared-base' else prospective['base_checkpoint_sha256']
                    engine=SimpleNamespace(PaidCalls=runner.model.PaidCalls,DesktopProspectiveModelWorker=Worker)
                    with patch.object(runner,'current_episode_module',return_value=engine),patch.object(runner.transport,'ModelSampler',Sampler),patch.object(rpc,'delegated_pre_dispatch',return_value=f.runtime_gate_mock.return_value),patch.object(runner.integration,'proposal',return_value=prospective):
                        result=runner.run_selection(worker=Worker(),session=session,started=started,checkpoint_path=checkpoint,
                            output_dir=study.repo_root/'work'/('runtime-selection-'+owner),base=owner=='shared-base')
                    self.assertEqual(result['status'],'scored');self.assertEqual(len(seen),20);self.assertEqual(len(set(seen)),20)
                    self.assertEqual(len(samplers),20);self.assertTrue(all(s.plan==study.plan_sha256 for s in samplers))
                    self.assertEqual(len(result['paid_attempt_ids']),80);self.assertEqual(len(set(result['paid_attempt_ids'])),80)
                    self.assertEqual(result['performance_coverage']['completed_model_response_count'],20)
                    self.assertIsNone(result['actual_cost_usd']);self.assertFalse(result['invoice_complete'])
                finally:f.tearDown()
