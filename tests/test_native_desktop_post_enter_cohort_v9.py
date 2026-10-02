"""The new cohort transport stops material oscillation, modal and replay."""
from __future__ import annotations
import copy
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from native_desktop_factory.post_enter_control_proxy_v9 import PostEnterControlProxyV9
from native_desktop_factory import v066_post_enter_epoch_v9 as epoch
from native_desktop_factory import v066_post_enter_control_attempt_v9 as worker
from native_desktop_factory import v066_post_enter_control_audit_v9 as audit
from native_desktop_factory import v066_post_enter_source_intake_v9 as intake
from tests.test_native_desktop_post_enter_train_probe_v1 import Guest,png


class EpochTests(unittest.TestCase):
    def proxy(self,guest,root,latency=2000):
        out=root/"task"/"positive";out.mkdir(parents=True,mode=0o700)
        current=[0]
        def clock():current[0]+=1_000_000;return current[0]
        def sleep(seconds):current[0]+=int(seconds*1e9)
        original=guest.screenshot
        def capture():current[0]+=latency*1_000_000;return original()
        guest.screenshot=capture
        proxy=PostEnterControlProxyV9(guest,storage_root=root,attempt_dir=out,document_filename="train.xlsx",clock=clock,sleep=sleep)
        proxy.current_actor_step=0
        return proxy,out

    def test_five_timed_realistic_latency_samples_and_fresh_next_frame(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);a,b=png("red"),png("blue");guest=Guest([a,b,b,b,b])
            proxy,out=self.proxy(guest,root);proxy.press("Enter")
            receipt={"profile_application_kind":"calc","post_enter_windows":1,
                     "actor_steps":[{"frame_id_sha256":"a"*64},{"frame_id_sha256":"b"*64}]}
            self.assertEqual(audit.post_enter_samples(root,out,[{"type":"key","key":"Enter"},{}],receipt),1)
            self.assertEqual(guest.actions,["Enter"])
            receipt["actor_steps"][1]["frame_id_sha256"]="a"*64
            with self.assertRaisesRegex(ValueError,"reused_pre_enter"):audit.post_enter_samples(root,out,[{"type":"key","key":"Enter"},{}],receipt)

    def test_modal_oscillation_and_three_material_states_stop_after_one_enter(self):
        a,b,c=png("red"),png("blue"),png("green")
        for frames,titles in [([a,b,a,b,b],None),([a,b,c,c,c],None),([a,b,b,b,b],["train.xlsx - LibreOffice Calc"]*2+["Save"]*3)]:
            with self.subTest(modal=titles is not None),TemporaryDirectory() as d:
                guest=Guest(frames,titles=titles);proxy,out=self.proxy(guest,Path(d))
                with self.assertRaises(ValueError):proxy.press("Enter")
                self.assertEqual(guest.actions,["Enter"])

    def test_remote_capture_exhaustion_is_not_accepted(self):
        with TemporaryDirectory() as d:
            guest=Guest([png("red")]*5);proxy,_out=self.proxy(guest,Path(d),latency=6500)
            with self.assertRaisesRegex(ValueError,"boundary"):proxy.press("Enter")
            self.assertEqual(guest.actions,["Enter"])

    def test_more_than_two_calc_edits_are_supported_within_action_bound(self):
        with TemporaryDirectory() as d:
            guest=Guest([png("red")]*20);proxy,out=self.proxy(guest,Path(d))
            for step in (0,3,6):proxy.current_actor_step=step;proxy.press("Enter")
            rows=(out/"post-enter-samples.ndjson").read_text().splitlines()
            self.assertEqual(len(rows),15);self.assertEqual(proxy.enter_count,3)
            proxy.enter_count=90
            with self.assertRaises(ValueError):proxy.press("Enter")
            self.assertEqual(len(guest.actions),3)

    def test_paid_execution_disabled_before_any_provider_or_private_read(self):
        with self.assertRaisesRegex(ValueError,"disabled"):worker.run_trio(freeze_path=Path("/missing"),permit_path=Path("/missing"))
        with self.assertRaisesRegex(ValueError,"disabled"):worker.execute(freeze_path=Path("/missing"),permit_path=Path("/missing"),task_id="x",attempt="positive")

    def test_actual_inconclusive_train_oscillation_is_preserved_without_gate(self):
        with TemporaryDirectory() as d:
            root=Path(d)
            a={"status":"three_public_train_guests_saved_state_and_reset_audited","positive_saved_workflows":2,"post_enter_raw_frames":10,
               "calc_cold_reset_original_bytes_verified":True,"provider_active_after":0}
            b={"status":"remaining_train_resets_audited_material_oscillation_inconclusive","combined_distinct_guests":6,
               "saved_wrong_target_score_zero":1,"separate_visual_modal_adjudications":1,"combined_original_byte_resets":3,
               "provider_active_after":0,"unresolved_writes":0,"same_intent_replay_authorized":False,
               "official_final_admissions":0,"official_model_results":0,"material_oscillation_proven":False,
               "no_action_probe_classifications":["caret_only_probe_material_oscillation_inconclusive"]}
            x,y=root/"v6.json",root/"v8.json";x.write_text(json.dumps(a));y.write_text(json.dumps(b))
            result=epoch.checked_train(x,y);self.assertIs(result["material_oscillation_proven"],False)
            b["saved_wrong_target_score_zero"]=0;y.write_text(json.dumps(b))
            with self.assertRaises(ValueError):epoch.checked_train(x,y)

    def test_metadata_projection_never_returns_oracle_or_instruction(self):
        value={"tasks":[{"source_groups":["wdi-country:ABC"],"oracle":{"iso3":"DEF"},"instruction":"XYZ"}],
               "ordered_future_country_iso":["GHI"]}
        self.assertEqual(intake.source_memberships(value),{"ABC","GHI"})

    def test_source_boundary_mutation_refused_before_source_capture(self):
        with TemporaryDirectory() as d:
            p=Path(d)/"candidate-inventory.json";p.write_text(json.dumps({"tasks":[{"source_groups":["wdi-country:ABC"]}]}))
            rows,_set=intake.boundary([p]);p.write_text(json.dumps({"tasks":[{"source_groups":["wdi-country:DEF"]}]}))
            with self.assertRaises(ValueError):intake.check_boundary(rows)

    def test_trio_intents_precede_callbacks_and_consumed_root_cannot_replay(self):
        with TemporaryDirectory() as d:
            root=Path(d);freeze=root/"freeze.json";permit=root/"permit.json"
            epoch.accounting._write_new(freeze,{"offline_fixture":True});epoch.accounting._write_new(permit,{"offline_fixture":True})
            row={"task_id":"fixture","package_sha256":"a"*64,"split":"selection"}
            value={"attempts_root":str(root/"attempts"),"roster":[row]};calls=[]
            def callback(**kw):
                out=root/"attempts"/"fixture"/kw["attempt"]
                self.assertTrue((out/"intent.json").is_file())
                self.assertTrue((out.parent/"trio-started.json").is_file())
                calls.append(kw["attempt"])
                return {"status":"cold_reset_observed" if kw["attempt"]=="cold-reset" else "control_passed"}
            with patch.dict(os.environ),patch.object(epoch,"validate",return_value=value),patch.object(epoch,"next_row",return_value=row),\
                    patch.object(epoch,"checked_permit"),patch.object(worker,"execute",side_effect=callback),\
                    patch.object(audit,"audit_trio",return_value={"official_final_admissions":0}):
                worker.run_trio(freeze_path=freeze,permit_path=permit,enable_paid_controls=True)
                self.assertEqual(calls,["positive","near-miss","cold-reset"])
                with self.assertRaisesRegex(ValueError,"cannot be replayed"):
                    worker.run_trio(freeze_path=freeze,permit_path=permit,enable_paid_controls=True)
                self.assertEqual(len(calls),3)

    def test_first_failed_attempt_forbids_second_guest(self):
        with TemporaryDirectory() as d:
            root=Path(d);freeze=root/"freeze.json";permit=root/"permit.json"
            epoch.accounting._write_new(freeze,{});epoch.accounting._write_new(permit,{})
            row={"task_id":"fixture","package_sha256":"a"*64,"split":"selection"};value={"attempts_root":str(root/"attempts"),"roster":[row]}
            with patch.dict(os.environ),patch.object(epoch,"validate",return_value=value),patch.object(epoch,"next_row",return_value=row),\
                    patch.object(epoch,"checked_permit"),patch.object(worker,"execute",return_value={"status":"failed"}) as callback:
                with self.assertRaisesRegex(ValueError,"no subsequent"):
                    worker.run_trio(freeze_path=freeze,permit_path=permit,enable_paid_controls=True)
                self.assertEqual(callback.call_count,1)
                self.assertFalse((root/"attempts/fixture/near-miss").exists())


if __name__=="__main__":unittest.main()
