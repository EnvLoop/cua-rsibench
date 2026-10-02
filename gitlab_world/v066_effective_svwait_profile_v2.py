"""Fresh-clone-only correction of the package wrapper's SVWAIT30 override."""
from __future__ import annotations
import json
from . import v066_optional_telemetry_profile_v1 as previous
from .v066_optional_telemetry_profile_v1 import CRITICAL_SERVICES,OPTIONAL_SERVICES,SETTINGS,require,sha
VERSION='gitlab18.5-optional-telemetry-off-effective-svwait60-v2'
WAIT_SECONDS=60
WITNESS_PATH='/var/opt/gitlab/envloop-native-svwait-v6.private.jsonl'
CTL_PATH='/opt/gitlab/bin/gitlab-ctl'
CTL_SHA256='65e32e7af21742b5748c2244cff835702fea65410de2b723fd9fbf7bea2d669b'
HELPER_PATH='/opt/gitlab/embedded/cookbooks/runit/libraries/helpers.rb'
HELPER_SHA256='3e0d99fe6537db18c0627158a6f076f8249b7421d8f984ab2c4de2d68ed7f575'
# The actual helper dispatch receives documented -w60, overriding both wrapper
# SVWAIT30 and a missing resource sv_timeout. This is startup-only Ruby config,
# never an actor tool or a failed-startup retry.
WAIT_RUBY=r'''require 'json'; require 'digest'
module EnvLoopEffectiveSvwaitV6
 PATH = '/var/opt/gitlab/envloop-native-svwait-v6.private.jsonl'
 PROFILE = 'gitlab18.5-optional-telemetry-off-effective-svwait60-v2'
 def self.record(value)
  if File.exist?(PATH) || File.symlink?(PATH)
   st=File.lstat(PATH); raise 'Unsafe native wait witness' unless st.file? && !st.symlink? && st.uid==Process.uid && (st.mode & 077)==0 && st.size<65536
  end
  File.open(PATH, File::WRONLY|File::CREAT|File::APPEND|File::NOFOLLOW, 0600) do |f|
   f.flock(File::LOCK_EX)
   raise 'Native wait witness bound exceeded' if f.stat.size>=65536
   f.write(JSON.generate({'schema'=>'envloop-gitlab-effective-svwait-v6','profile'=>PROFILE,'pid'=>Process.pid,'uid'=>Process.uid,'created_ns'=>(Time.now.to_r*1000000000).to_i}.merge(value))+"\n")
   f.flush; f.fsync
  end
 end
 def sv_args
  args=super
  configured=new_resource.sv_timeout
  if new_resource.service_name=='nginx'
   raise 'Unexpected nginx runit timeout override' unless configured.nil? || configured==60
  end
  configured.nil? ? '-w 60 '+args : args
 end
 def safe_sv_shellout(command, options={})
  tracked=command=='-w 60 restart /opt/gitlab/service/nginx/log'
  if tracked
   EnvLoopEffectiveSvwaitV6.record({'stage'=>'helper_intent','command'=>command,'sv_bin'=>new_resource.sv_bin,'effective_svwait'=>ENV['SVWAIT'],'effective_wait_seconds'=>60,'process_call_not_yet_returned'=>true})
  end
  begin
   result=super(command,options)
  rescue Exception => error
   EnvLoopEffectiveSvwaitV6.record({'stage'=>'helper_unavailable','command'=>command,'error_class'=>error.class.name,'applied_inferred'=>false}) if tracked
   raise
  end
  EnvLoopEffectiveSvwaitV6.record({'stage'=>'helper_returned','command'=>command,'exitstatus'=>result.exitstatus,'effective_svwait'=>ENV['SVWAIT'],'effective_wait_seconds'=>60}) if tracked
  result
 end
end
raise 'Pinned gitlab-ctl source changed' unless Digest::SHA256.hexdigest(File.binread('/opt/gitlab/bin/gitlab-ctl'))=='65e32e7af21742b5748c2244cff835702fea65410de2b723fd9fbf7bea2d669b'
raise 'Pinned native runit helper changed' unless Digest::SHA256.hexdigest(File.binread('/opt/gitlab/embedded/cookbooks/runit/libraries/helpers.rb'))=='3e0d99fe6537db18c0627158a6f076f8249b7421d8f984ab2c4de2d68ed7f575'
_envloop_svwait_before=ENV['SVWAIT']
ENV['SVWAIT']='60'
EnvLoopEffectiveSvwaitV6.record({'stage'=>'config_effective','wrapper_svwait_before_config'=>_envloop_svwait_before,'effective_svwait'=>ENV['SVWAIT'],'effective_wait_seconds'=>60,'ctl_sha256'=>'65e32e7af21742b5748c2244cff835702fea65410de2b723fd9fbf7bea2d669b','helper_sha256'=>'3e0d99fe6537db18c0627158a6f076f8249b7421d8f984ab2c4de2d68ed7f575'})
raise 'Native runit provider missing' unless defined?(Chef::Provider::RunitService)
Chef::Provider::RunitService.prepend(EnvLoopEffectiveSvwaitV6) unless Chef::Provider::RunitService.ancestors.include?(EnvLoopEffectiveSvwaitV6)
'''
WAIT_SUFFIX='\n# Fixed fresh-clone effective runit startup wait and native helper witness.\n'+WAIT_RUBY
SUFFIX=previous.SUFFIX+WAIT_SUFFIX

def render_clone_config(base:bytes)->bytes:
 text=base.decode();require('\x00' not in text,'Unexpected clone config encoding')
 if text.endswith(SUFFIX):return base
 require(WAIT_SUFFIX not in text,'Effective wait suffix must be terminal and unique')
 return previous.render_clone_config(base)+WAIT_SUFFIX.encode()

def render_clone_environment(base:bytes)->bytes:
 # The actual process correction is in gitlab.rb after the wrapper export.
 # Keep every Docker environment byte outside the existing telemetry suffix.
 return previous.render_clone_environment(base)

def validate_rendered_environment(original,rendered):
 value=previous.validate_rendered_environment(original,rendered)
 return value|{'profile':VERSION,'package_wrapper_overrides_docker_svwait':True,'native_effective_wait_witness_required':True,'effective_wait_seconds':60}

def witness_reader_ruby():
 return "require 'json';p="+json.dumps(WITNESS_PATH)+";s=File.lstat(p);raise unless s.file? && !s.symlink? && s.uid==0 && (s.mode & 077)==0 && s.size>0 && s.size<65536;print File.binread(p)"

def validate_witness(raw:bytes,*,started_at):
 from .v066_neutral_telemetry_coldboot_v3 import docker_started_ns
 require(type(raw) is bytes and 0<len(raw)<65536,'Native effective-wait witness absent or unbounded')
 rows=[json.loads(line) for line in raw.splitlines()];require(0<len(rows)<=128,'Native wait witness row bound exceeded')
 start=docker_started_ns(started_at);pending=None;returned=0;config=False
 for row in rows:
  require(row.get('schema')=='envloop-gitlab-effective-svwait-v6' and row.get('profile')==VERSION and type(row.get('pid')) is int and row['pid']>0 and type(row.get('uid')) is int and row['uid']==0 and type(row.get('created_ns')) is int and row['created_ns']>=start,'Native process wait provenance/freshness changed')
  if row['stage']=='config_effective':
   require(row.get('wrapper_svwait_before_config') in {'30','60'} and row.get('effective_svwait')=='60' and row.get('effective_wait_seconds')==60 and row.get('ctl_sha256')==CTL_SHA256 and row.get('helper_sha256')==HELPER_SHA256,'Native process effective configuration differs')
   config=True
  elif row['stage']=='helper_intent':
   require(config and pending is None and row.get('command')=='-w 60 restart /opt/gitlab/service/nginx/log' and row.get('sv_bin')=='/opt/gitlab/embedded/bin/sv' and row.get('effective_svwait')=='60' and row.get('effective_wait_seconds')==60 and row.get('process_call_not_yet_returned') is True,'Actual startup helper command differs')
   pending=row
  elif row['stage']=='helper_returned':
   require(pending is not None and row.get('command')==pending['command'] and row['pid']==pending['pid'] and row['created_ns']>=pending['created_ns'] and type(row.get('exitstatus')) is int and row['exitstatus']==0 and row.get('effective_svwait')=='60' and row.get('effective_wait_seconds')==60,'Actual startup helper did not complete successfully')
   returned+=1;pending=None
  else:raise ValueError('Native startup helper unavailable or unknown stage')
 require(config and pending is None and returned>0,'A config literal cannot replace actual successful helper consumption')
 return {'profile':VERSION,'actual_nginx_logger_wait_calls_verified':returned,'actual_effective_wait_seconds':60,'raw_witness_sha256':sha(raw),'fresh_after_native_start':True,'config_literal_alone_is_authority':False}
