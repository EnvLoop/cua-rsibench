"""Three one-shot neutral COW boots; no task, GUI, model or seed mutation.

Native execution is original-checkout-only and explicitly root reviewed.
The preserved active container is stopped and resumed with the same identity.
All probe containers and overlay paths are uniquely owned by one plan.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager,ExitStack
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
from unittest.mock import patch

from . import reset,runtime,verify,bootstrap,operators,factory
from . import v066_prospective_cohort_v6 as source
from . import v066_prospective_cohort_runtime_v6 as scoped
from . import v066_prospective_cohort_controller_v6 as controller
from . import v066_optional_telemetry_profile_v1 as profile

SCHEMA='envloop-gitlab-neutral-telemetry-coldboot-plan-v1'
SOURCE_FILES=('gitlab_world/v066_neutral_telemetry_coldboot_v1.py',
    'gitlab_world/v066_optional_telemetry_profile_v1.py','tests/test_gitlab_neutral_telemetry_coldboot_v1.py',
    'docs/FULL_STUDY_GITLAB_NEUTRAL_TELEMETRY_EXECUTION_2026-10-01.md')
WAIT_BOUNDS={'SVWAIT':'60','readiness_seconds':900,'action_seconds':720,'supervisor_seconds':7200}
EXPECTED_SETTINGS={s.split(' = ')[0]:False for s in profile.SETTINGS}
PINNED_UPSTREAM={'prometheus.rb':'a5c60b932ac43f2d285b3075d70b8e7f4ebfd67b32b1a51e36a12f98d96ba44c',
 'services.rb':'3deea9781eb8f5eb16698a423edf13fa8e1f4963d34430ad9159034bd605c35b',
 'services_helper.rb':'395cb2e418188dfe69fcdf0fbc580bdf0b2e90b11825558c198e381f48fdb13c',
 'runit_helpers.rb':'3e0d99fe6537db18c0627158a6f076f8249b7421d8f984ab2c4de2d68ed7f575'}
BOUND_FILES=('baseline-persisted-state.json','bootstrap-progress.json','operator-bootstrap-private.json',
    'operator-credentials-private.json','runtime.env','cow-reset-state.json','world-private.json',
    'cohort-plan.private.json','bootstrap-receipt.private.json')


def require(ok,code):
    if not ok:raise ValueError(code)


def hashes(root):return {n:source.sha((root/n).read_bytes()) for n in SOURCE_FILES}


def write_raw(path,raw):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    return {'path':path.name,'sha256':source.sha(raw)}


def render_environment(base,port):
    require(type(port) is int and 8020<=port<=8099,'Neutral loopback port outside fixed diagnostic range')
    text=profile.render_clone_environment(base).decode()
    require(text.count('http://127.0.0.1:8018')==1 and text.count("nginx['listen_port'] = 8018")==1,
        'Exact original URL and Nginx port required')
    # The immutable base gitlab.rb also sets8018 and wins over Omnibus ENV.
    # Neutral resource isolation changes only the host mapping, never app origin.
    return text.encode()



def parse_services(raw):
    services={}
    for line in raw.splitlines():
        match=re.match(r'^(run|down): ([^:]+):',line)
        require(match is not None,'Unexpected service status line')
        require(match[2] not in services,'Duplicate service status')
        services[match[2]]='running' if match[1]=='run' else 'disabled'
    for item in profile.OPTIONAL_SERVICES:services.setdefault(item,'absent')
    return services


def effective_reader_ruby():
    # Official18.5 SettingsDSL.sanitized_config places exporters under monitoring
    # and Puma/Sidekiq/prometheus_monitoring under gitlab; node keys use underscores.
    pairs={s.split(' = ')[0]:re.fullmatch(r"(\w+)\['(\w+)'\] = false",s).groups() for s in profile.SETTINGS}
    paths={k:['monitoring' if a in {'alertmanager','gitlab_exporter','node_exporter','postgres_exporter','prometheus','redis_exporter'} else 'gitlab',a,b]
        for k,(a,b) in pairs.items()}
    return "require 'json'; begin; raw=STDIN.read; start=raw.index('{'); raise if start.nil?; j=JSON.parse(raw[start..-1]); paths="+json.dumps(paths)+"; out={}; paths.each{|k,p| x=j; p.each{|n| raise unless x.is_a?(Hash) && x.key?(n); x=x[n]}; raise unless x==true || x==false; out[k]=x}; puts JSON.generate(out); rescue; STDERR.puts 'effective settings unavailable'; exit 1; end"


def raw_refs(out):
    return {p.name:source.sha(source.private(p)) for p in sorted(out.iterdir())
        if p.is_file() and p.name not in {'result.private.json','failure.private.json','manifest.private.json'}}


def prepare(*,freeze,out,upstream_bindings,port=8026):
    require(type(port) is int and 8020<=port<=8099,'Neutral loopback port outside fixed diagnostic range')
    value=source.validate_source(freeze);epoch=Path(value['epoch_root']);root=Path(value['evaluator_root'])
    plan,plan_sha,baseline=controller.baseline_inputs(value,freeze)
    cow=json.loads(source.private(epoch/'cow-reset-state.json'))
    require(cow['clone_generation']==32 and cow['last_readback_equal'] is True,'Retained cleanup32 required')
    upstream=json.loads(source.private(upstream_bindings))
    require({n:r['sha256'] for n,r in upstream.items()}==PINNED_UPSTREAM,'Pinned18.5 source bindings incomplete')
    for name,row in upstream.items():
        require('18.5.0%2Bce.0' in row['url'] and source.sha(source.private(upstream_bindings.parent/name))==row['sha256'],
            'Pinned official source bytes changed')
    out=Path(out).absolute();require(not out.exists() and not out.is_symlink(),'Fresh exclusive neutral plan directory required')
    out.mkdir(mode=0o700)
    token=source.sha(str(out).encode())[:12];prefix='envloop-gitlab-neutral-telemetry-'+token
    raw=source.private(epoch/'runtime.env')
    env=render_environment(raw,port)
    write_raw(out/'neutral-runtime.env',env)
    for n in ['baseline-persisted-state.json','bootstrap-progress.json','operator-bootstrap-private.json','operator-credentials-private.json']:
        write_raw(out/n,source.private(epoch/n))
    doc={'schema':SCHEMA,'status':'source_prepared_no_native_operation','evaluator_root':str(root),
        'epoch_root':str(epoch),'source_freeze_path':str(freeze),'source_freeze_sha256':source.sha(source.private(freeze)),
        'source_sha256s':hashes(Path(__file__).resolve().parents[1]),'frozen_source_sha256s':value['source_sha256s'],
        'cohort_plan_sha256':plan_sha,'original_container':value['clone_container_name'],'image':runtime.IMAGE,
        'image_id':runtime.IMAGE_ID,'original_base':'http://127.0.0.1:8018','port':port,'internal_port':8018,'neutral_base':f'http://127.0.0.1:{port}',
        'container_prefix':prefix,'vm_root':'/var/lib/'+prefix,'seed_lowerdirs':cow['seed_volume_lowerdirs'],
        'original_metadata_sha256s':{n:source.sha(source.private(epoch/n)) for n in BOUND_FILES},
        'protected_bound_metadata_sha256s':value['bound_metadata_sha256s'],
        'neutral_runtime_env_sha256':source.sha(env),'profile':profile.VERSION,'cycles':3,
        'upstream_source_bindings':upstream,'upstream_bindings_path':str(upstream_bindings),'upstream_bindings_sha256':source.sha(source.private(upstream_bindings)),
        'wait_bounds':WAIT_BOUNDS,
        'baseline_business_sha256':baseline['business_sha256'],'task_ids_consumed':0,'automatic_restart_attempts':0,
        'original_data_env_config_mutation_authorized':False,'immutable_lower_seed_mutation_authorized':False,
        'execute_authorized':False,'model_calls':0,'provider_calls':0,'control_credit':0,'official_final_admitted':0}
    digest=source.write_new(out/'plan.private.json',doc)
    return {'status':doc['status'],'plan_sha256':digest,'cycles':3,'native_calls':0,'control_credit':0}


def checked_plan(path):
    doc=json.loads(source.private(path));root=Path(doc['evaluator_root']);out=path.parent
    require(doc.get('schema')==SCHEMA and doc.get('source_sha256s')==hashes(Path(__file__).resolve().parents[1]) and
        doc.get('cycles')==3 and doc.get('automatic_restart_attempts')==0 and doc.get('task_ids_consumed')==0 and
        doc.get('execute_authorized') is False and doc.get('original_data_env_config_mutation_authorized') is False,
        'Neutral source/plan boundary changed')
    value=source.validate_source(Path(doc['source_freeze_path']));epoch=Path(doc['epoch_root'])
    require(value['evaluator_root']==str(root) and value['epoch_root']==str(epoch) and
        source.sha(source.private(Path(doc['source_freeze_path'])))==doc['source_freeze_sha256'] and
        source.sha(source.private(out/'neutral-runtime.env'))==doc['neutral_runtime_env_sha256'] and
        {n:source.sha(source.private(epoch/n)) for n in BOUND_FILES}==doc['original_metadata_sha256s'] and
        {p:source.sha(Path(p).read_bytes()) for p in doc['protected_bound_metadata_sha256s']}==doc['protected_bound_metadata_sha256s'],
        'Protected original seed/config/source metadata changed')
    for n in ['baseline-persisted-state.json','bootstrap-progress.json','operator-bootstrap-private.json','operator-credentials-private.json']:
        require(source.sha(source.private(out/n))==doc['original_metadata_sha256s'][n],'Neutral operator/baseline copy changed')
    require(re.fullmatch('envloop-gitlab-neutral-telemetry-[a-f0-9]{12}',doc['container_prefix']) and
        doc['vm_root']=='/var/lib/'+doc['container_prefix'],'Owned neutral namespace malformed')
    require(doc.get('wait_bounds')==WAIT_BOUNDS and doc.get('profile')==profile.VERSION and doc.get('image')==runtime.IMAGE and
        doc.get('image_id')==runtime.IMAGE_ID and doc.get('original_container')==value['clone_container_name'] and
        doc.get('internal_port')==8018 and doc.get('original_base')=='http://127.0.0.1:8018' and doc.get('neutral_base')==f"http://127.0.0.1:{doc['port']}" and
        source.private(out/'neutral-runtime.env')==render_environment(source.private(epoch/'runtime.env'),doc['port']) and
        doc.get('frozen_source_sha256s')==value['source_sha256s'] and
        doc.get('protected_bound_metadata_sha256s')==value['bound_metadata_sha256s'] and
        doc.get('immutable_lower_seed_mutation_authorized') is False,'Fixed runtime/profile binding changed')
    cow=json.loads(source.private(epoch/'cow-reset-state.json'))
    require(cow['clone_generation']==32 and cow['last_readback_equal'] is True and cow['seed_volume_lowerdirs']==doc['seed_lowerdirs'],
        'Retained cleanup32/immutable seed binding changed')
    upstream_path=Path(doc['upstream_bindings_path'])
    require(source.sha(source.private(upstream_path))==doc['upstream_bindings_sha256'] and
        json.loads(source.private(upstream_path))==doc['upstream_source_bindings'] and
        {n:r['sha256'] for n,r in doc['upstream_source_bindings'].items()}==PINNED_UPSTREAM and
        {n:source.sha(source.private(upstream_path.parent/n)) for n in PINNED_UPSTREAM}==PINNED_UPSTREAM,
        'Pinned official18.5 source bytes changed')
    _,plan_sha,baseline=controller.baseline_inputs(value,Path(doc['source_freeze_path']))
    require(plan_sha==doc['cohort_plan_sha256'] and baseline['business_sha256']==doc['baseline_business_sha256'],
        'Exact33 baseline binding changed')
    return doc,value,baseline


def review(*,plan,permit,accepted=False,note=''):
    require(accepted is True and note.strip(),'Independent source review and rationale required')
    doc,_,_=checked_plan(plan)
    require(not permit.exists() and not permit.is_symlink(),'Fresh one-use neutral permit required')
    value={'schema':'envloop-gitlab-neutral-telemetry-root-permit-v1','plan_path':str(plan),
        'plan_sha256':source.sha(source.private(plan)),'source_sha256s':doc['source_sha256s'],
        'accepted':True,'note':note,'cycles':3,'native_only_neutral':True,'task_ids_consumed':0,
        'model_calls':0,'control_credit':0,'official_final_admitted':0}
    digest=source.write_new(permit,value);return {'status':'neutral_permit_written_no_native_operation','permit_sha256':digest}


class NativeBackend:
    def __init__(self,doc,out):self.doc,self.out,self.seq=doc,out,0;self.owned_cycles=set()
    def command(self,args,*,timeout=120):
        number=self.seq;self.seq+=1
        try:result=subprocess.run(args,capture_output=True,timeout=timeout,check=False)
        except subprocess.TimeoutExpired as error:
            self.record(f'command-{number:03d}.private.json',{'argv':args,'returncode':None,'timed_out':True})
            write_raw(self.out/f'command-{number:03d}.stdout.private.log',error.stdout or b'')
            write_raw(self.out/f'command-{number:03d}.stderr.private.log',error.stderr or b'');raise
        self.record(f'command-{number:03d}.private.json',{'argv':args,'returncode':result.returncode,'timed_out':False})
        write_raw(self.out/f'command-{number:03d}.stdout.private.log',result.stdout)
        write_raw(self.out/f'command-{number:03d}.stderr.private.log',result.stderr)
        require(result.returncode==0,'Neutral native command failed; no automatic retry')
        return result.stdout.decode()
    def record(self,name,value):return write_raw(self.out/name,factory.canonical(value))
    def journal(self,stage,index=None):
        path=self.out/'lifecycle.private.jsonl'
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
        with os.fdopen(fd,'wb') as stream:
            stream.write(factory.canonical({'stage':stage,'cycle':index,'created_utc':source.now()})+b'\n');stream.flush();os.fsync(stream.fileno())
    def container_exists(self,name,label):
        args=['docker','--context',runtime.CONTEXT,'inspect','--format','{{.Id}}',name]
        result=subprocess.run(args,capture_output=True,timeout=30,check=False)
        self.record(label,{'returncode':result.returncode,'stdout_sha256':source.sha(result.stdout),'stderr_sha256':source.sha(result.stderr)})
        write_raw(self.out/(label+'.stdout.private.log'),result.stdout);write_raw(self.out/(label+'.stderr.private.log'),result.stderr)
        if result.returncode==0:return True
        require(result.returncode==1 and ('No such object: '+name).encode() in result.stderr,
            'Docker inspect failed without proving owned container absence')
        return False
    def docker(self,*args,timeout=120):return self.command(['docker','--context',runtime.CONTEXT,*args],timeout=timeout).strip()
    def vm(self,script,*,timeout=120):return self.command(['colima','ssh','--profile','cua-gitlab','--','sudo','sh','-lc',script],timeout=timeout).strip()
    @contextmanager
    def scope(self,name,vmroot,base,private):
        value=self.doc
        with ExitStack() as stack:
            for module,entries in [(runtime,{'WORLD':name,'BASE':base,'PRIVATE':private}),
                (bootstrap,{'PROGRESS_FILE':private/'bootstrap-progress.json'}),
                (operators,{'RECEIPT':private/'operator-bootstrap-private.json'}),
                (reset,{'VM_ROOT':vmroot,'vm_shell':self.vm}),
                (verify,{'_ids':lambda:scoped.ids_for_progress(private/'bootstrap-progress.json'),
                    'verify_bootstrap':lambda snapshot:scoped.validate_snapshot(snapshot,33)})]:
                for key,item in entries.items():stack.enter_context(patch.object(module,key,item))
            yield
    def lease_proof(self):
        result=scoped.no_old_worker(Path(self.doc['evaluator_root']))
        result['supervisor_locks_exclusive']=True;return result
    def protected(self):
        epoch=Path(self.doc['epoch_root']);metadata={n:source.sha(source.private(epoch/n)) for n in BOUND_FILES}
        core={n:source.sha((Path(self.doc['evaluator_root'])/n).read_bytes()) for n in self.doc['frozen_source_sha256s']}
        ancestors={p:source.sha(Path(p).read_bytes()) for p in self.doc['protected_bound_metadata_sha256s']}
        return {'metadata':metadata,'core':core,'ancestor_metadata':ancestors}
    def seed_content(self):
        # Read immutable lower file content, including modes and symlink text.
        # Special FIFO/socket/device files are stat-only; never opened.
        script="""import hashlib,json,os,stat
roots=ROOTS
out={}
def fail(error):raise error
for role,root in roots.items():
 h=hashlib.sha256();count=0
 r=os.lstat(root);assert stat.S_ISDIR(r.st_mode);h.update(json.dumps(['.',r.st_ino,r.st_dev,r.st_mode,r.st_uid,r.st_gid,r.st_size,r.st_mtime_ns,r.st_ctime_ns],separators=(',',':')).encode())
 for folder,dirs,files in os.walk(root,followlinks=False,onerror=fail):
  dirs.sort();files.sort()
  for name in sorted(dirs+files):
   p=os.path.join(folder,name);s=os.lstat(p);relative=os.path.relpath(p,root)
   h.update(json.dumps([relative,s.st_ino,s.st_dev,s.st_mode,s.st_uid,s.st_gid,s.st_size,s.st_mtime_ns,s.st_ctime_ns],separators=(',',':')).encode())
   if stat.S_ISLNK(s.st_mode):h.update(os.readlink(p).encode())
   elif stat.S_ISREG(s.st_mode):
    with open(p,'rb') as f:
     while True:
      b=f.read(1048576)
      if not b:break
      h.update(b)
   count+=1
 out[role]={'tree_content_sha256':h.hexdigest(),'entries':count}
print(json.dumps(out,sort_keys=True))
""".replace('ROOTS',repr(self.doc['seed_lowerdirs']))
        return json.loads(self.vm("python3 - <<'NEUTRAL_SEED_HASH'\n"+script+"\nNEUTRAL_SEED_HASH",timeout=900))
    def original_before(self):
        with self.scope(self.doc['original_container'],'/unused',self.doc['original_base'],Path(self.doc['epoch_root'])):
            proof=runtime.proof(runtime.WORLD);snap=verify.state_snapshot()
            require(proof['running'] is True and proof['health']=='healthy' and proof['image_id']==runtime.IMAGE_ID,'Preserved33 must be healthy')
            trees=self.git_trees(snap,'original-before')
        result={'identity':runtime.stable_identity(proof),'snapshot':snap,'full_git_trees':trees}
        self.record('original-before.private.json',result);return result
    def stop_original(self,before):
        self.docker('stop','--time','300',self.doc['original_container'],timeout=330)
        proof=runtime.proof(self.doc['original_container'])
        state=json.loads(self.docker('inspect','--format','{{json .State}}',self.doc['original_container'],timeout=30))
        self.record('original-stopped-state.private.json',state)
        self.record('original-stopped.private.json',proof)
        require(not proof['running'] and state['ExitCode']==0 and not state['OOMKilled'] and
            runtime.stable_identity(proof)==before['identity'],'Graceful preserved33 stop changed identity or did not exit cleanly')
    def git_trees(self,snapshot,label):
        result={}
        require(len(snapshot['project_ids'])==33,'Exact33 Git roster required')
        for ordinal,pid in enumerate(snapshot['project_ids']):
            refs=snapshot['git'][str(pid)]['refs'];rows={}
            for ref_ordinal,(ref,commit) in enumerate(sorted(refs.items())):
                raw=verify._git(pid,'ls-tree','-r','-z','--full-tree',commit)
                require(raw and raw.endswith(b'\0'),'Complete NUL-delimited Git tree required')
                path=f'{label}-git-{ordinal:02d}-ref-{ref_ordinal:02d}.private.bin'
                rows[ref]={'commit':commit,'raw_ref':write_raw(self.out/path,raw),'tree_sha256':source.sha(raw)}
            result[str(pid)]=rows
        return result
    def configure_upper(self,index,vmroot):
        config=vmroot+'/config/merged/gitlab.rb';lower=self.doc['seed_lowerdirs']['config']+'/gitlab.rb'
        script="""import hashlib,json,os
config=CONFIG;lower=LOWER;suffix=SUFFIX
assert os.path.isfile(config) and not os.path.islink(config)
base=open(lower,'rb').read();actual=open(config,'rb').read()
assert actual==base and suffix not in base
fd=os.open(config,os.O_WRONLY|os.O_APPEND|os.O_NOFOLLOW)
with os.fdopen(fd,'wb') as f:f.write(suffix);f.flush();os.fsync(f.fileno())
new=open(config,'rb').read();assert new==base+suffix
print(json.dumps({'base_sha256':hashlib.sha256(base).hexdigest(),'clone_config_sha256':hashlib.sha256(new).hexdigest(),'suffix_sha256':hashlib.sha256(suffix).hexdigest(),'exact_suffix_only':True}))
""".replace('CONFIG',repr(config)).replace('LOWER',repr(lower)).replace('SUFFIX',repr(profile.SUFFIX.encode()))
        raw=self.vm("python3 - <<'NEUTRAL_CONFIG'\n"+script+"\nNEUTRAL_CONFIG")
        result=json.loads(raw);self.record(f'cycle-{index}-config-delta.private.json',result);return result
    def boot(self,index):
        name=self.doc['container_prefix']+'-'+str(index);vmroot=self.doc['vm_root']+'/cycle-'+str(index)
        # Refuse preexisting container and VM root; these are never reused.
        require(not self.container_exists(name,f'cycle-{index}-preexisting.private.json'),'Neutral container namespace already exists')
        self.vm('set -eu; test ! -e '+shlex.quote(vmroot)+'; mkdir '+shlex.quote(vmroot))
        self.owned_cycles.add(index)
        with self.scope(name,vmroot,self.doc['neutral_base'],self.out):
            for role,lower in self.doc['seed_lowerdirs'].items():reset._mount(role,lower)
            config_delta=self.configure_upper(index,vmroot)
            args=['run','-d','--name',name,'--hostname','gitlab-neutral.local','--restart','no',
                '--env-file',str(self.out/'neutral-runtime.env'),'-p',f"127.0.0.1:{self.doc['port']}:8018"]
            for role,dest in runtime.DESTS.items():args+=['-v',vmroot+'/'+role+'/merged:'+dest]
            args.append(runtime.IMAGE);self.docker(*args)
            ready=scoped.wait_cohort();snapshot=verify.state_snapshot()
            trees=self.git_trees(snapshot,f'cycle-{index}')
            inspected=runtime.inspect(name)
            expected_env=[line for line in source.private(self.out/'neutral-runtime.env').decode().splitlines() if line and not line.startswith('#')]
            actual_env=inspected['Config']['Env']
            require(all([v for v in actual_env if v.split('=',1)[0]==line.split('=',1)[0]]==[line] for line in expected_env) and
                inspected['HostConfig']['RestartPolicy']=={'Name':'no','MaximumRetryCount':0},'Actual clone runtime environment/restart policy changed')
            startup_proof={'identity':runtime.stable_identity(ready),'running':ready['running'],'health':ready['health'],
                'runtime_env_values_exact':True,'restart_policy':inspected['HostConfig']['RestartPolicy'],'SVWAIT':'60'}
            self.record(f'cycle-{index}-startup-proof.private.json',startup_proof)
            state=self.docker('inspect','--format','{{json .State}}',name,timeout=30)
            write_raw(self.out/f'cycle-{index}-state.private.json',state.encode())
            self.capture_logs(index,name)
            status=self.docker('exec',name,'gitlab-ctl','status',timeout=60)
            write_raw(self.out/f'cycle-{index}-services.private.log',status.encode())
            services=parse_services(status)
            # Full show-config stays inside the container; only nine booleans
            # and a fixed parser error can leave the subprocess.
            command='set -o pipefail; gitlab-ctl show-config 2>/dev/null | /opt/gitlab/embedded/bin/ruby -e '+shlex.quote(effective_reader_ruby())
            effective=self.docker('exec',name,'bash','-lc',command,timeout=120)
            write_raw(self.out/f'cycle-{index}-effective.private.json',effective.encode())
            return {'cycle':index,'healthy':True,'state_snapshot':snapshot,'container_id_sha256':ready['container_id_sha256'],
                'services':services,'effective_settings':json.loads(effective),'full_git_trees':trees,'config_delta':config_delta,
                'startup_proof':startup_proof,'snapshot_ref':write_raw(self.out/f'cycle-{index}-snapshot.private.json',factory.canonical(snapshot))}
    def capture_logs(self,index,name):
        result=subprocess.run(['docker','--context',runtime.CONTEXT,'logs','--timestamps',name],capture_output=True,timeout=60,check=False)
        write_raw(self.out/f'cycle-{index}-startup.stdout.private.log',result.stdout)
        write_raw(self.out/f'cycle-{index}-startup.stderr.private.log',result.stderr)
        require(result.returncode==0,'Owned clone raw startup logs unavailable')
    def teardown(self,index):
        require(index in self.owned_cycles,'No ownership claim; colliding namespace must remain untouched')
        name=self.doc['container_prefix']+'-'+str(index);vmroot=self.doc['vm_root']+'/cycle-'+str(index)
        log_failure=None
        if self.container_exists(name,f'cycle-{index}-pre-teardown.private.json'):
            if not (self.out/f'cycle-{index}-state.private.json').exists():
                state=self.docker('inspect','--format','{{json .State}}',name,timeout=30)
                write_raw(self.out/f'cycle-{index}-state.private.json',state.encode())
            if not (self.out/f'cycle-{index}-startup.stdout.private.log').exists():
                try:self.capture_logs(index,name)
                except Exception as error:
                    log_failure=error;self.record(f'cycle-{index}-log-retention-failure.private.json',
                        {'exception_type':type(error).__name__,'error_sha256':source.sha(str(error).encode())})
            self.docker('stop','--time','300',name,timeout=330);self.docker('rm',name,timeout=120)
        require(not self.container_exists(name,f'cycle-{index}-post-teardown.private.json'),'Owned neutral container remains')
        with self.scope(name,vmroot,self.doc['neutral_base'],self.out):
            for role in runtime.DESTS:
                base=vmroot+'/'+role
                self.vm('set -eu; if mountpoint -q '+shlex.quote(base+'/merged')+'; then umount '+shlex.quote(base+'/merged')+'; fi; test ! -e '+shlex.quote(base+'/merged')+' || ! mountpoint -q '+shlex.quote(base+'/merged'))
        require(vmroot.startswith(self.doc['vm_root']+'/cycle-') and self.doc['vm_root'].startswith('/var/lib/envloop-gitlab-neutral-telemetry-'),
            'Teardown outside uniquely owned neutral VM subtree')
        self.vm('set -eu; rm -rf '+shlex.quote(vmroot)+'; test ! -e '+shlex.quote(vmroot))
        proof={'cycle':index,'owned_container_absent':True,'owned_overlay_mounts_absent':True,'owned_vm_subtree_absent':True,'vm_root':vmroot}
        write_raw(self.out/f'cycle-{index}-teardown.private.json',factory.canonical(proof))
        if log_failure is not None:raise log_failure
        return proof
    def resume_original(self,before):
        proof=runtime.proof(self.doc['original_container'])
        require(runtime.stable_identity(proof)==before['identity'],'Preserved33 identity changed before resume')
        if not proof['running']:self.docker('start',self.doc['original_container'])
        with self.scope(self.doc['original_container'],'/unused',self.doc['original_base'],Path(self.doc['epoch_root'])):
            ready=scoped.wait_cohort();snapshot=verify.state_snapshot()
            trees=self.git_trees(snapshot,'original-resumed')
        require(tree_digests(trees)==tree_digests(before['full_git_trees']),'Preserved33 complete Git tree not restored')
        require(runtime.stable_identity(ready)==before['identity'] and snapshot==before['snapshot'],
            'Preserved33 lifecycle/business baseline not restored')
        result={'same_identity':True,'exact_business_snapshot':True,'healthy':True,'identity':runtime.stable_identity(ready),'snapshot':snapshot,'full_git_trees':trees}
        self.record('original-resumed.private.json',result);return result


def tree_digests(trees):
    return {pid:{ref:(row['commit'],row['tree_sha256']) for ref,row in refs.items()} for pid,refs in trees.items()}


def execute_cycles(doc,baseline,backend):
    """Real effects are isolated in a backend; the single-boot algorithm is shared."""
    before=backend.original_before();require(before['snapshot']==baseline,'Preserved33 entry is not exact baseline')
    protected=backend.protected();seed=backend.seed_content();cycles=[];paused=False
    backend.record('protected-before.private.json',protected);backend.record('seed-before.private.json',seed)
    result={'status':'three_fresh_neutral_cold_boots_verified','cycles':cycles,'task_ids_consumed':0,
        'new_task_dispatch_authorized':False,'model_calls':0,'provider_calls':0,'control_credit':0,'official_final_admitted':0}
    try:
        paused=True;backend.journal('preserved33_graceful_stop_intent');backend.stop_original(before)
        for index in range(3):
            backend.journal('owned_neutral_boot_intent',index)
            cycle=None;teardown=None
            try:
                cycle=backend.boot(index)
                require(cycle['healthy'] is True and cycle['state_snapshot']==baseline,'Neutral clone changed baseline')
                require(tree_digests(cycle['full_git_trees'])==tree_digests(before['full_git_trees']),'Neutral complete Git tree changed')
                require(cycle['config_delta']['exact_suffix_only'] is True and cycle['config_delta']['suffix_sha256']==source.sha(profile.SUFFIX.encode()),
                    'Fresh upper configuration changed beyond fixed suffix')
                require(cycle['effective_settings']==EXPECTED_SETTINGS,'Effective telemetry profile not false')
                require(all(cycle['services'].get(s)=='running' for s in profile.CRITICAL_SERVICES) and
                    all(cycle['services'].get(s) in {'disabled','absent'} for s in profile.OPTIONAL_SERVICES),'Critical/optional service mismatch')
            finally:
                backend.journal('owned_neutral_teardown_intent',index);teardown=backend.teardown(index)
            require(all(teardown.get(k) is True for k in ['owned_container_absent','owned_overlay_mounts_absent','owned_vm_subtree_absent']),
                'Neutral teardown incomplete')
            seed_after=backend.seed_content();protected_after=backend.protected()
            backend.record(f'cycle-{index}-seed-after.private.json',seed_after)
            backend.record(f'cycle-{index}-protected-after.private.json',protected_after)
            require(seed_after==seed and protected_after==protected,'Protected seed/config/source changed during neutral cycle')
            cycles.append({**cycle,'teardown':teardown});backend.journal('owned_neutral_cycle_verified',index)
        require(len({c['container_id_sha256'] for c in cycles})==3,'Neutral container identity reused')
        return result
    finally:
        if paused:
            backend.journal('preserved33_resume_intent');result['preserved33_resume']=backend.resume_original(before)
        after=backend.protected();seed_after=backend.seed_content()
        backend.record('protected-exit.private.json',after);backend.record('seed-exit.private.json',seed_after)
        require(after==protected and seed_after==seed,'Preserved source/seed metadata changed on exit')
        backend.journal('preserved33_exit_verified')


def run(*,plan,permit,execute=False,backend_factory=NativeBackend):
    require(execute is True,'Explicit reviewed neutral lifecycle execution required')
    doc,value,baseline=checked_plan(plan);p=json.loads(source.private(permit))
    require(p.get('schema')=='envloop-gitlab-neutral-telemetry-root-permit-v1' and p.get('accepted') is True and
        p.get('plan_path')==str(plan) and p.get('plan_sha256')==source.sha(source.private(plan)) and
        p.get('source_sha256s')==doc['source_sha256s'] and p.get('cycles')==3 and p.get('task_ids_consumed')==0 and
        p.get('note','').strip(),'Exact neutral root permit changed')
    require(Path(__file__).resolve().parents[1]==Path(doc['evaluator_root']),'Only original evaluator may execute neutral lifecycle')
    out=plan.parent;require(not (out/'run-intent.private.json').exists(),'Consumed neutral run cannot replay')
    locks=[]
    try:
        for folder in ['controls','audit-only-continuation-controls-v1','post-reset-continuation-controls-v2']:
            fd=os.open(Path(doc['epoch_root'])/folder/'.supervisor.lock',os.O_WRONLY|os.O_NOFOLLOW);locks.append(fd)
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        backend=backend_factory(doc,out);proof=backend.lease_proof()
        require(proof.get('old_worker_processes')==0 and proof.get('supervisor_locks_exclusive') is True,'Actual worker/lease proof failed')
        source.write_new(out/'run-intent.private.json',{'schema':'envloop-gitlab-neutral-telemetry-run-intent-v1',
            'plan_sha256':source.sha(source.private(plan)),'permit_sha256':source.sha(source.private(permit)),
            'worker_and_lease_proof':proof,'cycles':3,'one_use':True,'task_ids_consumed':0,'created_utc':source.now()})
        result=execute_cycles(doc,baseline,backend);result['raw_file_sha256s']=raw_refs(out);source.write_new(out/'result.private.json',result)
        return {k:v for k,v in result.items() if k not in {'cycles','raw_file_sha256s','preserved33_resume'}}|{'neutral_cycles_verified':3,'result_sha256':source.sha(source.private(out/'result.private.json'))}
    except Exception as error:
        if (out/'run-intent.private.json').exists() and not (out/'failure.private.json').exists():
            source.write_new(out/'failure.private.json',{'status':'terminal_neutral_failure_no_retry','exception_type':type(error).__name__,
                'error_sha256':source.sha(str(error).encode()),'task_ids_consumed':0,'control_credit':0,'official_final_admitted':0,
                'raw_file_sha256s':raw_refs(out)})
        raise
    finally:
        for fd in locks:fcntl.flock(fd,fcntl.LOCK_UN);os.close(fd)


def audit(*,plan,permit):
    """Reopen every retained byte and replay neutral semantics without native calls."""
    doc,_,baseline=checked_plan(plan);out=plan.parent
    result=json.loads(source.private(out/'result.private.json'))
    require(not (out/'failure.private.json').exists() and result.get('status')=='three_fresh_neutral_cold_boots_verified',
        'Terminal failure or missing native success cannot be credited')
    refs=result.get('raw_file_sha256s',{})
    require(refs==raw_refs(out),'Retained raw evidence set/content changed')
    def load(name):
        require(name in refs and Path(name).name==name,'Missing owned raw evidence binding')
        return json.loads(source.private(out/name))
    intent=load('run-intent.private.json');p=json.loads(source.private(permit))
    require(intent['plan_sha256']==source.sha(source.private(plan)) and intent['permit_sha256']==source.sha(source.private(permit)) and
        p['accepted'] is True and p['plan_sha256']==intent['plan_sha256'] and p['source_sha256s']==doc['source_sha256s'] and
        intent['worker_and_lease_proof']['old_worker_processes']==0 and intent['worker_and_lease_proof']['supervisor_locks_exclusive'] is True,
        'One-use plan/permit/native lease binding changed')
    before=load('original-before.private.json');resumed=load('original-resumed.private.json')
    stopped=load('original-stopped.private.json');stopped_state=load('original-stopped-state.private.json')
    require(before['snapshot']==baseline and resumed['snapshot']==baseline and before['identity']==resumed['identity'] and
        runtime.stable_identity(stopped)==before['identity'] and stopped['running'] is False and
        stopped_state['ExitCode']==0 and stopped_state['OOMKilled'] is False and resumed['healthy'] is True and
        result['preserved33_resume']==resumed,'Preserved33 lifecycle/baseline raw proof changed')
    seed=load('seed-before.private.json');protected=load('protected-before.private.json')
    require(seed==load('seed-exit.private.json') and protected==load('protected-exit.private.json'),
        'Protected raw seed/source/config exit changed')
    require(protected['metadata']==doc['original_metadata_sha256s'] and protected['core']==doc['frozen_source_sha256s'] and protected['ancestor_metadata']==doc['protected_bound_metadata_sha256s'],
        'Protected raw source/metadata binding changed')
    def check_trees(trees,snapshot):
        require(set(trees)==set(snapshot['git']) and len(trees)==33,'Full33 Git readback missing')
        for pid,rows in trees.items():
            require(set(rows)==set(snapshot['git'][pid]['refs']),'Git ref roster changed')
            for ref,row in rows.items():
                raw_ref=row['raw_ref'];name=raw_ref['path'];raw=source.private(out/name)
                require(name in refs and Path(name).name==name and raw_ref['sha256']==refs[name]==row['tree_sha256']==source.sha(raw) and
                    row['commit']==snapshot['git'][pid]['refs'][ref] and raw and raw.endswith(b'\0'), 'Raw full Git tree binding changed')
                for entry in raw[:-1].split(b'\0'):
                    require(re.fullmatch(rb'(100644|100755|120000|160000) (blob|commit) [a-f0-9]{40}\t[^\0]+',entry),
                        'Unexpected NUL-delimited Git tree entry')
    check_trees(before['full_git_trees'],baseline);check_trees(resumed['full_git_trees'],baseline)
    require(tree_digests(before['full_git_trees'])==tree_digests(resumed['full_git_trees']),'Preserved full Git tree changed')
    require(len(result['cycles'])==3 and len({c['container_id_sha256'] for c in result['cycles']})==3,'Three distinct raw neutral identities missing')
    for index,cycle in enumerate(result['cycles']):
        require(cycle['cycle']==index and cycle['healthy'] is True and cycle['state_snapshot']==baseline and
            load(f'cycle-{index}-snapshot.private.json')==baseline,'Raw neutral baseline changed')
        effective=load(f'cycle-{index}-effective.private.json');services=parse_services(source.private(out/f'cycle-{index}-services.private.log').decode())
        state=load(f'cycle-{index}-state.private.json');startup=load(f'cycle-{index}-startup-proof.private.json')
        config=load(f'cycle-{index}-config-delta.private.json');teardown=load(f'cycle-{index}-teardown.private.json')
        require(effective==cycle['effective_settings']==EXPECTED_SETTINGS and services==cycle['services'] and
            all(services.get(s)=='running' for s in profile.CRITICAL_SERVICES) and
            all(services.get(s) in {'disabled','absent'} for s in profile.OPTIONAL_SERVICES), 'Raw native service/config semantics changed')
        require(state['Running'] is True and state['ExitCode']==0 and state['OOMKilled'] is False and state['Health']['Status']=='healthy' and
            startup==cycle['startup_proof'] and startup['identity']['container_id_sha256']==cycle['container_id_sha256'] and
            startup['identity']['image_id']==runtime.IMAGE_ID and startup['identity']['ports']=={'8018/tcp':[{'HostIp':'127.0.0.1','HostPort':str(doc['port'])}]} and startup['restart_policy']=={'Name':'no','MaximumRetryCount':0} and
            startup['SVWAIT']=='60' and startup['runtime_env_values_exact'] is True,'Raw native startup boundary changed')
        require(config==cycle['config_delta'] and config['exact_suffix_only'] is True and config['suffix_sha256']==source.sha(profile.SUFFIX.encode()) and
            teardown==cycle['teardown'] and all(teardown.get(k) is True for k in ['owned_container_absent','owned_overlay_mounts_absent','owned_vm_subtree_absent']),
            'Raw clone config delta/teardown changed')
        require(load(f'cycle-{index}-seed-after.private.json')==seed and load(f'cycle-{index}-protected-after.private.json')==protected,
            'Raw protected metadata changed during neutral cycle')
        check_trees(cycle['full_git_trees'],baseline)
        require(tree_digests(cycle['full_git_trees'])==tree_digests(before['full_git_trees']),'Neutral full Git tree changed')
        for suffix in ['stdout','stderr']:
            require(f'cycle-{index}-startup.{suffix}.private.log' in refs,'Actual native startup log missing')
        post=load(f'cycle-{index}-post-teardown.private.json')
        require(post['returncode']==1 and ('No such object: '+doc['container_prefix']+'-'+str(index)).encode() in
            source.private(out/f'cycle-{index}-post-teardown.private.json.stderr.private.log'),'Raw owned container absence unproved')
    journal=[json.loads(line) for line in source.private(out/'lifecycle.private.jsonl').splitlines()]
    expected=[('preserved33_graceful_stop_intent',None)]
    for index in range(3):expected += [('owned_neutral_boot_intent',index),('owned_neutral_teardown_intent',index),('owned_neutral_cycle_verified',index)]
    expected += [('preserved33_resume_intent',None),('preserved33_exit_verified',None)]
    require([(r['stage'],r['cycle']) for r in journal]==expected,'Native lifecycle chronology includes retry or missing phase')
    require(all(result.get(k)==0 for k in ['task_ids_consumed','model_calls','provider_calls','control_credit','official_final_admitted']) and
        result['new_task_dispatch_authorized'] is False,'Neutral trial cannot authorize task/model credit')
    return {'status':'saved_three_neutral_native_cycles_independently_replayed','result_sha256':source.sha(source.private(out/'result.private.json')),
        'neutral_cycles_verified':3,'raw_files_verified':len(refs),'task_ids_consumed':0,'control_credit':0,'official_final_admitted':0,
        'new_task_dispatch_authorized':False}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['prepare','review','run','audit'])
    for key in ['freeze','out','upstream-bindings','plan','permit']:p.add_argument('--'+key,type=Path)
    p.add_argument('--port',type=int,default=8026);p.add_argument('--accept-root-review',action='store_true')
    p.add_argument('--note',default='');p.add_argument('--execute',action='store_true');a=p.parse_args()
    if a.mode=='prepare':result=prepare(freeze=a.freeze,out=a.out,upstream_bindings=a.upstream_bindings,port=a.port)
    elif a.mode=='review':result=review(plan=a.plan,permit=a.permit,accepted=a.accept_root_review,note=a.note)
    elif a.mode=='run':result=run(plan=a.plan,permit=a.permit,execute=a.execute)
    else:result=audit(plan=a.plan,permit=a.permit)
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
