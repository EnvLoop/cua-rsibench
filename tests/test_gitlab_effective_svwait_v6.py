"""Real Ruby/source semantics and production witness/budget refusal; no Docker."""
import copy,json,os,subprocess,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from gitlab_world import v066_effective_svwait_profile_v2 as profile,v066_neutral_telemetry_coldboot_v6 as cold

START='2026-10-01T08:00:00.000000000Z'
NS=1790841600000000000

def witness():
 common={'schema':'envloop-gitlab-effective-svwait-v6','profile':profile.VERSION,'pid':32,'uid':0,'created_ns':NS}
 return [common|{'stage':'config_effective','wrapper_svwait_before_config':'30','effective_svwait':'60','effective_wait_seconds':60,'ctl_sha256':profile.CTL_SHA256,'helper_sha256':profile.HELPER_SHA256},common|{'stage':'helper_intent','command':'-w 60 restart /opt/gitlab/service/nginx/log','sv_bin':'/opt/gitlab/embedded/bin/sv','effective_svwait':'60','effective_wait_seconds':60,'process_call_not_yet_returned':True},common|{'stage':'helper_returned','command':'-w 60 restart /opt/gitlab/service/nginx/log','exitstatus':0,'effective_svwait':'60','effective_wait_seconds':60}]

def raw(rows):return ('\n'.join(json.dumps(x) for x in rows)+'\n').encode()

class WitnessTests(unittest.TestCase):
 def test_literal_alone_cannot_qualify(self):
  with self.assertRaises(ValueError):profile.validate_witness(raw(witness()[:1]),started_at=START)
 def test_actual_successful_wait_consumption(self):
  value=profile.validate_witness(raw(witness()),started_at=START)
  self.assertEqual(value['actual_effective_wait_seconds'],60);self.assertEqual(value['actual_nginx_logger_wait_calls_verified'],1)
  self.assertFalse(value['config_literal_alone_is_authority'])
 def test_nonzero_unknown_pending_foreign_stale_wrong_wait_and_bool_exit_rejected(self):
  for index,key,value in [(2,'exitstatus',1),(2,'exitstatus',False),(1,'effective_svwait','30'),(1,'command','restart /opt/gitlab/service/nginx/log'),(2,'pid',99),(0,'uid',False),(1,'created_ns',NS-1),(0,'helper_sha256','a'*64)]:
   rows=witness();rows[index][key]=value
   with self.subTest(key=key,value=value),self.assertRaises(ValueError):profile.validate_witness(raw(rows),started_at=START)
  for rows in [witness()[:2],witness()+[witness()[1]],witness()[:2]+[witness()[1]],[]]:
   with self.assertRaises(ValueError):profile.validate_witness(raw(rows),started_at=START)
 def test_profile_is_append_only_and_docker_environment_unchanged(self):
  base=b"external_url 'http://127.0.0.1:8018'\n"
  rendered=profile.render_clone_config(base);self.assertTrue(rendered.startswith(base));self.assertEqual(profile.render_clone_config(rendered),rendered)
  env=b'SVWAIT=60\nGITLAB_OMNIBUS_CONFIG=nginx["listen_port"] = 8018\n'
  self.assertEqual(profile.render_clone_environment(env),profile.previous.render_clone_environment(env))
  self.assertIn("ENV['SVWAIT']='60'",rendered.decode())
 def test_production_ruby_syntax(self):
  result=subprocess.run(['ruby','-c'],input=profile.WAIT_RUBY.encode(),capture_output=True,timeout=10)
  self.assertEqual(result.returncode,0,result.stderr.decode())
 def test_pinned_actual_helper_consumes_explicit60_after_wrapper_export30(self):
  # Supply the actual privately copied package files; their hashes are pinned.
  value=os.environ.get('ENVLOOP_GITLAB_SVWAIT_PACKAGE_SOURCE')
  if not value:self.skipTest('Pinned native package source not supplied')
  source=Path(value);helper=(source/'runit_helpers.rb').read_bytes();ctl=(source/'gitlab-ctl').read_bytes()
  self.assertEqual(profile.sha(helper),profile.HELPER_SHA256);self.assertEqual(profile.sha(ctl),profile.CTL_SHA256)
  self.assertIn(b'export SVWAIT=30',ctl)
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);(root/'helper.rb').write_bytes(helper);(root/'ctl').write_bytes(ctl)
   proof=root/'witness.jsonl';code=profile.WAIT_RUBY.replace(profile.WITNESS_PATH,str(proof)).replace(profile.CTL_PATH,str(root/'ctl')).replace(profile.HELPER_PATH,str(root/'helper.rb'))
   # Actual upstream helpers execute through a ShellOut stub that starts a
   # harmless real child process and reports its argv/ENV; no service exists.
   prelude="""require 'json';require 'open3';require 'ostruct'
module Chef
 module Provider;end
 module Log;def self.debug(*a);end;end
 module Mixin; module ShellOut
  def shell_out(command,**options)
   child='require "json";puts JSON.generate({"argv"=>ARGV,"svwait"=>ENV["SVWAIT"]})'
   argv=command.split.drop(1)
   stdout,stderr,status=Open3.capture3('ruby','-e',child,'--',*argv)
   puts stdout
   OpenStruct.new(exitstatus:status.exitstatus,error?:false)
  end
 end;end
end
"""
   script=prelude+'\n'+helper.decode()+"\nclass Chef::Provider::RunitService\n include RunitCookbook::Helpers\n def new_resource;OpenStruct.new(sv_timeout:nil,sv_verbose:false,sv_bin:'/opt/gitlab/embedded/bin/sv',service_dir:'/opt/gitlab/service',service_name:'nginx');end\nend\n"+code+"\nChef::Provider::RunitService.new.restart_log_service\n"
   result=subprocess.run(['bash','-c','export SVWAIT=30; exec ruby'],input=script.encode(),capture_output=True,timeout=10)
   self.assertEqual(result.returncode,0,result.stderr.decode())
   child=json.loads(result.stdout.splitlines()[-1]);self.assertEqual(child['argv'],['-w','60','restart','/opt/gitlab/service/nginx/log']);self.assertEqual(child['svwait'],'60')
   rows=[json.loads(x) for x in proof.read_bytes().splitlines()];self.assertEqual(rows[0]['wrapper_svwait_before_config'],'30');self.assertEqual(rows[1]['command'],'-w 60 restart /opt/gitlab/service/nginx/log');self.assertEqual(rows[-1]['exitstatus'],0)

class BackendBudgetTests(unittest.TestCase):
 def backend(self,root):return cold.NativeBackend({'owned_lifecycle_seconds':1200},root)
 def test_expired_no_new_native_process(self):
  with tempfile.TemporaryDirectory() as folder:
   b=self.backend(Path(folder));b.deadline=time.monotonic()-1
   with patch.object(cold.previous.NativeBackend,'command') as driver,self.assertRaises(ValueError):b.command(['native','read'])
   driver.assert_not_called()
 def test_actual_command_timeout_is_clipped_once_and_durable(self):
  with tempfile.TemporaryDirectory() as folder:
   b=self.backend(Path(folder));b.deadline=time.monotonic()+.1
   def unavailable(*args,**kwargs):raise TimeoutError('Unknown child completion')
   with patch.object(cold.previous.NativeBackend,'command',side_effect=unavailable) as driver,self.assertRaises(TimeoutError):b.command(['native','read'],timeout=90)
   driver.assert_called_once();self.assertLessEqual(driver.call_args.kwargs['timeout'],.1)
   self.assertTrue((Path(folder)/'command-000-bounded-intent.private.json').exists());self.assertTrue((Path(folder)/'command-000-bounded-unavailable.private.json').exists())
 def test_deadline_does_not_skip_known_owned_rollback_and_cannot_grant_credit(self):
  with tempfile.TemporaryDirectory() as folder:
   b=self.backend(Path(folder));b.deadline=time.monotonic()-1;b._closing=True
   with patch.object(cold.previous.NativeBackend,'command',return_value='actual-returned') as driver:self.assertEqual(b.command(['owned','rollback']),'actual-returned')
   driver.assert_called_once()
   with self.assertRaises(ValueError):b.finish_lifecycle()
   j=json.loads((Path(folder)/'owned-lifecycle-end.private.json').read_bytes());self.assertFalse(j['within_limit'])
 def test_frozen_v5_sources_and_scope_restored(self):
  original=cold.legacy.profile
  with cold.version_scope():self.assertIs(cold.legacy.profile,profile)
  self.assertIs(cold.legacy.profile,original)


class ProductionBootTests(unittest.TestCase):
 def test_two_actual_backend_boot_paths_require_distinct_native_wait_witnesses(self):
  from tests import test_gitlab_neutral_telemetry_coldboot_v3 as attrs_tests
  from tests.test_gitlab_neutral_telemetry_coldboot_v1 import snapshot
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);doc={'owned_lifecycle_seconds':1200,'container_prefix':'envloop-gitlab-neutral-telemetry-'+'a'*12,'vm_root':'/var/lib/envloop-gitlab-neutral-telemetry-'+'a'*12,'neutral_base':'http://127.0.0.1:8018','port':8018,'source_sha256s':{},'seed_lowerdirs':{r:'/immutable/'+r for r in cold.runtime.DESTS}}
   cold.write_raw(root/'neutral-runtime.env',b'SVWAIT=60\n')
   b=cold.NativeBackend(doc,root);b.parent_claim={'inode':1,'device':1}
   attributes=attrs_tests.attrs();attributes['all_observed_attribute_layers']={layer:{k:v[layer] for k,v in attributes['fixed_settings'].items()} for layer in ['normal','default']};attributes['unknown_service_value_layers']=[]
   evidence=witness()
   from gitlab_world.v066_neutral_telemetry_coldboot_v3 import docker_started_ns
   for row in evidence:row['created_ns']=docker_started_ns(attrs_tests.START)+1
   calls=[]
   def docker(*args,**kwargs):
    calls.append(args)
    if args[0]=='inspect':return json.dumps({'Running':True,'StartedAt':attrs_tests.START})
    if args[0]=='exec' and args[2]=='gitlab-ctl':return '\n'.join('run: '+s+': (pid1) 1s' for s in profile.CRITICAL_SERVICES)
    if args[0]=='exec' and profile.WITNESS_PATH in args[-1]:return raw(evidence).decode()
    if args[0]=='exec':return json.dumps(attributes)
    return 'owned'
   ready=lambda digit:{'container_id_sha256':digit*64,'image_ref':cold.runtime.IMAGE,'image_id':cold.runtime.IMAGE_ID,'mounts':{},'ports':{},'running':True,'health':'healthy'}
   with patch.object(b,'vm',return_value=''),patch.object(b,'container_exists',return_value=False),patch.object(b,'configure_upper',return_value={'exact_suffix_only':True}) as upper,patch.object(b,'docker',side_effect=docker),patch.object(b,'capture_logs'),patch.object(b,'git_trees',return_value={}),patch.object(cold.legacy.verify,'state_snapshot',return_value=snapshot()),patch.object(cold.runtime,'inspect',return_value={'Image':cold.runtime.IMAGE_ID,'State':{'Running':True,'Health':{'Status':'healthy'}},'Config':{'Env':['SVWAIT=60']},'HostConfig':{'RestartPolicy':{'Name':'no','MaximumRetryCount':0}}}),patch.object(cold.runtime,'_http_ready',return_value=True),patch.object(cold.runtime,'proof',side_effect=[ready('1'),ready('2')]):
    first=b.boot(0);second=b.boot(1)
   self.assertNotEqual(first['container_id_sha256'],second['container_id_sha256']);self.assertEqual(upper.call_count,2)
   self.assertEqual(sum(x[0]=='run' for x in calls),2)
   self.assertEqual(len(list(root.glob('cycle-*-effective-wait-witness.private.jsonl'))),2)
   for index in [0,1]:self.assertTrue(json.loads((root/f'cycle-{index}-effective-wait-result.private.json').read_bytes())['fresh_after_native_start'])
 def test_missing_witness_fails_one_boot_without_reconfigure_or_boot_retry(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);b=cold.NativeBackend({'owned_lifecycle_seconds':1200,'container_prefix':'owned'},root)
   cold.write_raw(root/'cycle-0-state.private.json',json.dumps({'StartedAt':START}).encode())
   with patch.object(cold.previous.NativeBackend,'boot',return_value={'healthy':True}) as boot,patch.object(b,'docker',return_value='') as read:
    with self.assertRaises(ValueError):b.boot(0)
   boot.assert_called_once_with(0);read.assert_called_once()
   self.assertTrue((root/'cycle-0-effective-wait-unavailable.private.json').exists())

if __name__=='__main__':unittest.main()
