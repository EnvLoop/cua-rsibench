"""Actual CampaignSession API with synthetic artifacts and fake providers."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from cursibench import full_study_campaign_dispatch_v1 as campaign
from native_desktop_factory import prospective_model_worker_v11 as desktop
from tests import test_full_study_campaign_dispatch_v1 as fixture_module


class CheckpointResultTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture_module.FullStudyDispatchTests(methodName='runTest')
        self.fixture.setUp()

    def tearDown(self):
        self.fixture.tearDown();self.fixture.doCleanups()

    def trained(self):
        _,session=self.fixture.campaign('desktop-native')
        self.fixture.trained_candidate(session)
        return session,session._events('tinker_checkpoint')[0]

    def registered(self,*,request_changes=None,result_changes=None):
        """Consistently hashed negative artifacts, never live provider calls."""
        _,session=self.fixture.campaign('desktop-native')
        rendered,dataset=self.fixture.proposed_train_batch(session)
        training,training_sha=session.study.student_training_configuration()
        request={'schema':'cua-full-study-tinker-sft-request-v1',
            'model':campaign.TINKER_MODEL,'cell_id':'desktop-native',
            'researcher_id':'astra','round_index':1,
            'dataset_manifest_sha256':campaign._sha(dataset.read_bytes()),
            'rendered_batch_sha256':campaign._sha(campaign._canonical(rendered.receipt)),
            'training_config_sha256':training_sha,'optimizer_steps':2,
            'batch_size':1,'scheduled_tokens':40,'max_sample_tokens':48}
        expected='tinker://fake/sampler_weights/checkpoint-1'
        result={'checkpoint_path':expected,'observed_base_model':campaign.TINKER_MODEL,
            'optimizer_steps_completed':2,'sample_token_count':5,
            'sample_token_sha256':'a'*64,'sdk_operation_count':8}
        request.update(request_changes or {});result.update(result_changes or {})
        session.dispatch_paid(attempt_id='tinker-001',category='tinker',
            work=request,request=request,reserve_usd='0.001',
            resource_reservation={'candidate_submissions':'1'},provider=lambda _:result)
        event=session.journal.append('tinker_checkpoint',{
            'round_index':1,'paid_attempt_id':'tinker-001',
            'dataset_manifest_sha256':request['dataset_manifest_sha256'],
            'training_config_sha256':training_sha,
            'checkpoint_path_sha256':campaign._sha(expected.encode()),
            'optimizer_steps':2,'scheduled_tokens':40,
            'epoch_seconds':int(session.now())})
        return session,event

    def test_real_sft_result_api_reads_canonical_field_and_preserves_journal(self):
        session,event=self.trained();before=session.journal.path.read_bytes()
        result=session.checkpoint_result(event)
        self.assertIs(type(session),campaign.CampaignSession)
        self.assertEqual(result['checkpoint_path'],'tinker://fake/sampler_weights/ckpt-1')
        self.assertNotIn('sampler_path',result)
        self.assertEqual(session.journal.path.read_bytes(),before)

    def test_wrong_cell_or_researcher_is_rejected_even_with_consistent_paid_hashes(self):
        for changed in ({'cell_id':'gitlab'},{'researcher_id':'luna6'}):
            with self.subTest(changed=changed):
                # Each nested fixture gets its own real journal/ledger.
                self.fixture.tearDown();self.fixture.doCleanups();self.fixture.setUp()
                session,event=self.registered(request_changes=changed)
                with self.assertRaisesRegex(campaign.DispatchError,'checkpoint_request_not_current_campaign_lineage'):
                    session.checkpoint_result(event)

    def test_changed_checkpoint_unknown_result_field_and_wrong_base_rejected(self):
        for changed in ({'checkpoint_path':'tinker://fake/sampler_weights/other'},
                        {'sampler_path':'tinker://fake/sampler_weights/checkpoint-1'},
                        {'observed_base_model':'Qwen/other'},
                        {'optimizer_steps_completed':True}):
            with self.subTest(changed=changed):
                self.fixture.tearDown();self.fixture.doCleanups();self.fixture.setUp()
                session,event=self.registered(result_changes=changed)
                with self.assertRaisesRegex(campaign.DispatchError,'checkpoint_result_not_current_campaign_lineage'):
                    session.checkpoint_result(event)

    def test_unregistered_checkpoint_event_and_changed_private_result_rejected(self):
        session,event=self.trained()
        changed=copy.deepcopy(event);changed['data']['checkpoint_path_sha256']='b'*64
        with self.assertRaisesRegex(campaign.DispatchError,'checkpoint_event_not_registered_in_session'):
            session.checkpoint_result(changed)
        path=session.directory/'tinker-001.result.private.json'
        path.write_text('{}');path.chmod(0o600)
        with self.assertRaisesRegex(campaign.DispatchError,'paid_result_bytes_changed_or_missing'):
            session.checkpoint_result(event)

    def test_private_request_permissions_and_source_changed_after_sft_refused(self):
        session,event=self.trained()
        request=session.directory/'tinker-001.request.private.json'
        request.chmod(0o644)
        with self.assertRaisesRegex(campaign.DispatchError,'paid_request_bytes_changed_or_missing'):
            session.checkpoint_result(event)
        request.chmod(0o600)
        with patch.object(session.study,'student_training_configuration',
                          return_value=({**session.study.student_training_configuration()[0]},'b'*64)):
            with self.assertRaisesRegex(campaign.DispatchError,'checkpoint_request_not_current_campaign_lineage'):
                session.checkpoint_result(event)

    def desktop_checkpoint_gate(self,session,event):
        checkpoint=session.checkpoint_result(event)['checkpoint_path']
        started=session.start_selection_attempt(round_index=1,attempt_id='desktop-selected-001')
        worker=desktop.DesktopProspectiveModelWorker(study=session.study,
            admissions_path=Path('not-opened'),proposal_path=Path('not-opened'))
        out=session.directory/'never-created-selection'
        with patch.object(worker,'_gate',return_value={}),\
             patch.object(worker,'_policy',return_value=({}, {}, {}, '0.001')),\
             patch.object(worker,'_packages',side_effect=RuntimeError('stop_before_environment_and_sampler')) as packages:
            with self.assertRaisesRegex(RuntimeError,'stop_before_environment_and_sampler'):
                worker._run_selection(session=session,started=started,
                    checkpoint_path=checkpoint,out_dir=out,base=False)
            self.assertEqual(packages.call_count,1)
        self.assertFalse(out.exists())

    def test_desktop_selected_path_uses_actual_session_api_before_first_model_or_gui_call(self):
        session,event=self.trained();self.desktop_checkpoint_gate(session,event)

    def test_desktop_rejects_unknown_field_before_environment_and_sampler(self):
        session,event=self.registered(result_changes={'sampler_path':'tinker://fake/sampler_weights/checkpoint-1'})
        started=session.start_selection_attempt(round_index=1,attempt_id='desktop-selected-001')
        worker=desktop.DesktopProspectiveModelWorker(study=session.study,
            admissions_path=Path('not-opened'),proposal_path=Path('not-opened'))
        with patch.object(worker,'_gate',return_value={}),\
             patch.object(worker,'_policy',return_value=({}, {}, {}, '0.001')),\
             patch.object(worker,'_packages') as packages:
            with self.assertRaisesRegex(campaign.DispatchError,'checkpoint_result_not_current_campaign_lineage'):
                worker._run_selection(session=session,started=started,
                    checkpoint_path='tinker://fake/sampler_weights/checkpoint-1',
                    out_dir=session.directory/'never-created-selection',base=False)
            packages.assert_not_called()


if __name__=='__main__':unittest.main()
