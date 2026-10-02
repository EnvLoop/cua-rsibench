"""Offline profile-delta and neutral-readback checks; no native operation."""
import copy,unittest
from gitlab_world import v066_optional_telemetry_profile_v1 as profile


class ProfileTests(unittest.TestCase):
 def test_clone_config_append_and_environment_keep_all_unrelated_settings(self):
  config=b"external_url 'http://localhost:8018'\npostgresql['enable'] = true\n"
  result=profile.render_clone_config(config)
  self.assertTrue(result.startswith(config));self.assertEqual(profile.render_clone_config(result),result)
  env=b"SVWAIT=60\nGITLAB_OMNIBUS_CONFIG=external_url 'http://localhost:8018'\nTZ=UTC\n"
  changed=profile.render_clone_environment(env);check=profile.validate_rendered_environment(env,changed)
  self.assertEqual(profile.render_clone_environment(changed),changed)
  self.assertFalse(check['new_task_dispatch_authorized']);self.assertFalse(check['critical_services_changed'])
  self.assertIn(b'TZ=UTC\n',changed)
 def test_wait_or_nontelemetry_changes_cannot_be_smuggled_into_profile(self):
  env=b"SVWAIT=60\nGITLAB_OMNIBUS_CONFIG=external_url 'http://localhost:8018'\n"
  for bad in (env.replace(b'SVWAIT=60',b'SVWAIT=90'),env+b'EXTRA=unexpected\n'):
   with self.assertRaises(ValueError):profile.validate_rendered_environment(env,bad)
  with self.assertRaises(ValueError):profile.render_clone_environment(env+b'GITLAB_OMNIBUS_CONFIG=duplicate\n')
 def receipt(self):
  baseline={'sql':'exact33','git':'exact33'};cycles=[]
  for n in range(3):
   cycles.append({'cycle':n,'healthy':True,'state_snapshot':baseline,'immutable_lower_seed_before':{'seed':'same'},
    'immutable_lower_seed_after':{'seed':'same'},'original_core_metadata_before':{'core':'same'},
    'original_core_metadata_after':{'core':'same'},'effective_settings':{s.split(' = ')[0]:False for s in profile.SETTINGS},
    'teardown_verified':True,'remaining_owned_container_count':0,'container_id_sha256':str(n+1)*64,
    'services':{**{s:'running' for s in profile.CRITICAL_SERVICES},**{s:'disabled' for s in profile.OPTIONAL_SERVICES}},
    'raw_evidence_sha256s':{key:'a'*64 for key in ['startup_log','docker_state','service_status','effective_settings','baseline_snapshot','teardown']}})
  return {'profile':profile.VERSION,'cycles_requested':3,'cycles':cycles,'new_task_ids_consumed':0,'automatic_restart_attempts':0,
    'wait_bounds':{'SVWAIT':'60','readiness_seconds':900,'action_seconds':720,'supervisor_seconds':7200}},baseline
 def test_three_neutral_fresh_clones_teardown_is_zero_task_credit(self):
  receipt,baseline=self.receipt();result=profile.validate_neutral_probe_receipt(receipt,baseline)
  self.assertEqual(result['control_credit'],0);self.assertFalse(result['new_task_dispatch_authorized'])
 def test_critical_loss_seed_change_identity_reuse_and_missing_teardown_are_rejected(self):
  for kind in ['critical','seed','data','identity','teardown','retry','raw']:
   receipt,baseline=self.receipt()
   if kind=='critical':receipt['cycles'][0]['services']['postgresql']='disabled'
   elif kind=='seed':receipt['cycles'][0]['immutable_lower_seed_after']={'seed':'changed'}
   elif kind=='data':receipt['cycles'][0]['state_snapshot']={'sql':'changed'}
   elif kind=='identity':receipt['cycles'][1]['container_id_sha256']=receipt['cycles'][0]['container_id_sha256']
   elif kind=='teardown':receipt['cycles'][0]['remaining_owned_container_count']=1
   elif kind=='retry':receipt['automatic_restart_attempts']=1
   else:receipt['cycles'][0]['raw_evidence_sha256s'].pop('effective_settings')
   with self.assertRaises(ValueError):profile.validate_neutral_probe_receipt(receipt,baseline)


if __name__=='__main__':unittest.main()
