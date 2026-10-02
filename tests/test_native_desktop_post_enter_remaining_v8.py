"""Offline tests for immutable stop and only the three remaining TRAIN intents."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from native_desktop_factory import v066_post_enter_near_negative_v7 as old
from native_desktop_factory import v066_post_enter_remaining_v8 as runner
from native_desktop_factory import v066_post_enter_remaining_audit_v8 as audit


def sources():
    return {'cases':[{'case':case,'row':{'package_sha256':case,'input_sha256':case}} for case in ['wrong-target','modal-stop','no-action-probe']]}


class RemainingTests(unittest.TestCase):
    def test_paid_gate_and_root_acceptance_are_explicit_and_old_hash_is_immutable(self):
        with self.assertRaisesRegex(ValueError,'disabled'):
            runner.run(freeze_path=Path('/absent'),permit_path=Path('/absent'))
        with self.assertRaisesRegex(ValueError,'root acceptance'):
            audit.review(freeze_path=Path('/absent'),review_path=Path('/absent'),permit_path=Path('/absent'))
        with self.assertRaisesRegex(ValueError,'original PNG'):
            audit.record_visual_adjudication(old_freeze=Path('/absent'),old_run=Path('/absent'),out_path=Path('/absent'))
        with TemporaryDirectory() as directory:
            path=Path(directory)/'changed.json'; old._write_new(path,{'status':'rewritten_passed'})
            with self.assertRaisesRegex(ValueError,'old v7 freeze/run'):
                runner.old_bindings(old_freeze=path,old_run=path)

    def test_remaining_sequence_has_no_wrong_target_or_modal_replay(self):
        sequence=runner._sequence(sources())
        self.assertEqual([(p['source']['case'],p['attempt']) for p in sequence],
            [('modal-stop','cold-reset'),('no-action-probe','case'),('no-action-probe','cold-reset')])
        self.assertEqual(runner.MAX_GUESTS,3)
        self.assertEqual([p['original_v7_planned_ordinal'] for p in sequence],[3,4,5])
        self.assertNotIn(('modal-stop','case'),[(p['source']['case'],p['attempt']) for p in sequence])

    def test_three_only_schedule_stops_on_failure_and_run_root_cannot_replay(self):
        for fail in [False,True]:
            with self.subTest(failure=fail),TemporaryDirectory() as directory:
                base=Path(directory); root=base/'new-output'; freeze=base/'freeze.json';permit=base/'permit.json'
                old._write_new(freeze,{'freeze':'test'}); old._write_new(permit,{'permit':'test'})
                value={'output_root':str(root),'source_sha256s':{},'sequence':runner._sequence(sources())}
                calls=[]
                def fake_one(**kwargs):
                    calls.append((kwargs['source']['case'],kwargs['attempt'],kwargs['ordinal']))
                    out=root/f'{kwargs["ordinal"]:02d}-{kwargs["source"]["case"]}-{kwargs["attempt"]}'
                    out.mkdir(mode=0o700);old._write_new(out/'intent.json',{'lease_seconds':600})
                    status='stopped_for_reconciliation' if fail else ('cold_reset_observed' if kwargs['attempt']=='cold-reset' else 'no_action_probe_audited')
                    receipt={'status':status};old._write_new(out/'receipt.json',receipt);return receipt
                trap=SimpleNamespace(create=lambda **kwargs:self.fail('No provider create belongs to offline schedule test'))
                with patch.object(runner,'validate_source',return_value=value),patch.object(audit,'checked_permit',return_value={}),patch.object(runner.importlib.metadata,'version',side_effect=lambda name:runner.SDK_VERSIONS[name]),patch.dict(runner.os.environ,{'E2B_API_KEY':'offline-test-placeholder'}),patch.object(runner,'active_hashes',return_value=(set(),0)),patch.object(runner,'storage_audit',return_value={'dispatch_storage_ready':True}),patch.object(old,'_one',side_effect=fake_one),patch.dict('sys.modules',{'e2b_desktop':SimpleNamespace(Sandbox=trap)}),patch.object(audit,'audit',return_value={'status':'offline_schedule_test_only'}):
                    result=runner.run(freeze_path=freeze,permit_path=permit,enable_paid_remaining_train=True)
                    self.assertEqual(len(calls),1 if fail else 3)
                    self.assertEqual(result['new_full_lease_intents'],len(calls))
                    journal=json.loads((root/'run-receipt.json').read_bytes())
                    self.assertEqual(journal['original_v7_planned_ordinals'],[3,4,5])
                    self.assertEqual([p['original_v7_planned_ordinal'] for p in journal['attempts']],list(range(3,3+len(calls))))
                    self.assertEqual(len(list(root.glob('intent-ancestry-*.private.json'))),len(calls))
                    with self.assertRaisesRegex(ValueError,'replayed'):
                        runner.run(freeze_path=freeze,permit_path=permit,enable_paid_remaining_train=True)
                if not fail:self.assertEqual(calls,[('modal-stop','cold-reset',0),('no-action-probe','case',1),('no-action-probe','cold-reset',2)])

    def test_remaining_permit_cannot_widen_count_or_drop_old_evidence_binding(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);freeze=root/'freeze.json';old._write_new(freeze,{'freeze':'test'})
            value={'output_root':str(root/'new-output'),'source_sha256s':{'source.py':'a'*64},
                   'terminal_audit_sha256':'b'*64,'visual_adjudication_sha256':'c'*64,'prior_full_lease_accounting':{'past_full_lease_seconds':1800}}
            reviewed=root/'review.json';permit=root/'permit.json'
            with patch.object(runner,'validate_source',return_value=value),patch.object(audit,'storage_audit',return_value={'dispatch_storage_ready':True}):
                audit.review(freeze_path=freeze,review_path=reviewed,permit_path=permit,
                    independent_root_review_accepted=True,review_note='Offline independent test only',active_probe=lambda:(set(),0))
            audit.checked_permit(freeze_path=freeze,permit_path=permit,value=value)
            for changed in [{**value,'visual_adjudication_sha256':'d'*64},{**value,'terminal_audit_sha256':'e'*64}]:
                with self.assertRaisesRegex(ValueError,'permit binding changed'):
                    audit.checked_permit(freeze_path=freeze,permit_path=permit,value=changed)
            private=json.loads(permit.read_bytes());private['guest_maximum']=4;permit.write_bytes(old.encode(private))
            with self.assertRaisesRegex(ValueError,'permit binding changed'):
                audit.checked_permit(freeze_path=freeze,permit_path=permit,value=value)

    def test_visual_binding_requires_exact_raw_save_window_after_stimulus(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);out=root/'modal';out.mkdir(mode=0o700)
            frame=out/'frame.bin';frame.write_bytes(b'raw-original-frame');frame.chmod(0o600)
            ref={'private_path':'modal/frame.bin','bytes':len(frame.read_bytes()),'sha256':old.digest(frame.read_bytes())}
            before=out/'before.bin';before.write_bytes(b'before-frame');before.chmod(0o600)
            before_ref={'private_path':'modal/before.bin','bytes':len(before.read_bytes()),'sha256':old.digest(before.read_bytes())}
            sample={'probe_start_monotonic_ns':4,'frame':ref,'window_title_before':'Save','window_title_after':'Save',
                    'window_id_before':'modal','window_id_after':'modal','document_window_stable':False,
                    'application_frame_sha256':'f'*64,**{f'{x}_sha256':old.digest(v.encode()) for x,v in
                        [('window_title_before','Save'),('window_title_after','Save'),('window_id_before','modal'),('window_id_after','modal')]}}
            old._write_new(out/'samples.ndjson',sample)
            receipt={'actor_steps':[{'dispatch_after_monotonic_ns':1}]*6,'document_window_id':'document',
                'trusted_negative_stimulus':{'key':'Control+Shift+S','status':'applied','actor_step_count_before':6,
                    'dispatch_before_monotonic_ns':2,'dispatch_after_monotonic_ns':3,'before_frame':before_ref},
                'probe':{'actor_actions_during_or_after_probe':0,'raw_samples':1,'sample_ledger_sha256':old.digest(old._private(out/'samples.ndjson'))}}
            record={'out':out,'source':{'case':'modal-stop'},'receipt':receipt,'intent_sha256':'a'*64,'receipt_sha256':'b'*64}
            value={'output_root':str(root)}
            binding=audit._visual_binding(value=value,record=record)
            self.assertEqual(binding['original_v7_terminal_status'],'stopped_for_reconciliation')
            self.assertFalse(binding['original_modal_classifier_passed'])
            sample['window_title_after']='Open';(out/'samples.ndjson').write_bytes(old.encode(sample))
            receipt['probe']['sample_ledger_sha256']=old.digest(old._private(out/'samples.ndjson'))
            with self.assertRaisesRegex(ValueError,'Save window identity'):
                audit._visual_binding(value=value,record=record)

    def test_separate_visual_adjudication_cannot_claim_old_classifier_passed_or_change_frame(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);path=root/'visual.json'
            binding={'raw_frame_sha256':'a'*64,'original_modal_classifier_passed':False}
            visual={**binding,'schema':audit.VISUAL_SCHEMA,'decision':'native_file_save_dialog_visually_confirmed_at_window_boundary_stop',
                'basis':'independent_original_png_visual_inspection','visual_observations':['Cancel button','Name field','Save button'],
                'old_source_or_terminal_record_modified':False,'same_intent_replay_authorized':False,
                'official_final_admissions':0,'official_model_results':0}
            old._write_new(path,visual)
            with patch.object(audit,'_visual_binding',return_value=binding):
                audit.check_visual(value={},record={},visual_adjudication=path)
                for changed in [{**visual,'raw_frame_sha256':'b'*64},{**visual,'original_modal_classifier_passed':True},{**visual,'old_source_or_terminal_record_modified':True}]:
                    path.write_bytes(old.encode(changed))
                    with self.assertRaisesRegex(ValueError,'adjudication binding changed'):
                        audit.check_visual(value={},record={},visual_adjudication=path)

    def test_prepare_refuses_paid_probe_source_and_never_dispatches(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);work=root/'work';work.mkdir();(work/'gui-diagnostics').mkdir()
            source=sources();source.update(work_root=str(work),candidate_root=str(root/'candidate'),accounting_roots=[str(work)],
                output_root=str(work/'gui-diagnostics/old-output'),
                guest_public=str(root/'guest'),guest_public_sha256='a'*64,scoped_reference=str(root/'profile'),scoped_reference_sha256='b'*64)
            run={'permit_path':str(root/'old-permit'),'attempts':[{'receipt_sha256':str(i)} for i in range(3)]}
            params={'old_freeze':root/'old-freeze','old_run':root/'old-run','terminal_audit':root/'terminal',
                'visual_adjudication':root/'visual','output_root':work/'gui-diagnostics/new-output','freeze_path':root/'new-freeze','public_path':root/'new-public'}
            ledger={'used_package_sha256s':['modal-stop','no-action-probe']}
            with patch.object(runner,'old_bindings',return_value=(source,run)),patch.object(audit,'validate_terminal_records',return_value={}),patch.object(old,'lease_accounting',return_value=ledger):
                with self.assertRaisesRegex(ValueError,'only unused TRAIN source'):
                    runner.prepare(**params)
            self.assertFalse(params['output_root'].exists());self.assertFalse(params['freeze_path'].exists())


if __name__=='__main__':unittest.main()
