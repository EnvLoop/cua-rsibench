"""Additive neutral v3 reads poststartup native Chef attributes without Cinc.

V1/V2 sources and failures remain frozen. Native node JSON never leaves the
container; only fixed typed settings, provenance and freshness are retained.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager,ExitStack
from datetime import datetime,timezone
import json
from pathlib import Path
import re
from unittest.mock import patch
from . import v066_neutral_telemetry_coldboot_v2 as previous
from .v066_neutral_telemetry_coldboot_v2 import source,runtime,factory,require,parse_services,tree_digests,EXPECTED_SETTINGS,profile,write_raw,known_absence
legacy=previous.legacy
SCHEMA='envloop-gitlab-neutral-telemetry-coldboot-plan-v3'
SOURCE_FILES=previous.SOURCE_FILES+('gitlab_world/v066_neutral_telemetry_coldboot_v3.py',
 'tests/test_gitlab_neutral_telemetry_coldboot_v3.py','docs/FULL_STUDY_GITLAB_NEUTRAL_TELEMETRY_V3_2026-10-01.md')
PINNED_V2='1bb06775acf7546dd29cd34b37813b77364c0b9116cce36a70fe0b2a8bcc2cf4'
NODE_NAME='gitlab-neutral.local'
NODE_PATH='/opt/gitlab/embedded/nodes/'+NODE_NAME+'.json'
NATIVE_PATTERNS=previous.NATIVE_PATTERNS+(r'cycle-[012]-native-attributes\.private\.json',)
SETTINGS_PATHS={s.split(' = ')[0]:['monitoring' if s.split('[')[0] in {'alertmanager','gitlab_exporter','node_exporter','postgres_exporter','prometheus','redis_exporter'} else 'gitlab',
 re.fullmatch(r"(\w+)\['(\w+)'\] = false",s)[1],re.fullmatch(r"(\w+)\['(\w+)'\] = false",s)[2]] for s in profile.SETTINGS}


def node_reader_ruby(*,path=NODE_PATH,node_name=NODE_NAME):
    require(path==NODE_PATH and node_name==NODE_NAME,'Native attribute path/name outside fixed clone schema')
    script="""require 'json';require 'digest';require 'time'
path=PATH;node_name=NODE;paths=JSON.parse(PATHS)
begin
 raise unless File.file?(path) && !File.symlink?(path)
 stat=File.stat(path);raise if stat.size>10485760
 raw=File.binread(path);j=JSON.parse(raw)
 rows={};effective={}
 paths.each do |key,names|
  rows[key]={}
  ['override','normal','default'].each do |layer|
   x=j[layer];present=true
   names.each do |name|
    unless x.is_a?(Hash) && x.key?(name);present=false;break;end
    x=x[name]
   end
   item={'present'=>present,'type'=>present ? x.class.name : 'Absent'}
   item['boolean']=x if present && (x==true || x==false)
   rows[key][layer]=item
  end
  chosen=['override','normal','default'].find{|layer|rows[key][layer]['present']}
  item=chosen && rows[key][chosen]
  effective[key]=item['boolean'] if item && item.key?('boolean')
 end
 result={'schema'=>'envloop-gitlab18.5-native-node-settings-v1','parse_status'=>true,
 'node_name_exact'=>j['name']==node_name,'artifact_sha256'=>Digest::SHA256.hexdigest(raw),
 'artifact_bytes'=>stat.size,'artifact_mtime_ns'=>stat.mtime.to_i*1000000000+stat.mtime.nsec,
 'artifact_regular_nonsymlink'=>true,'fixed_paths'=>paths,'fixed_settings'=>rows,'effective_settings'=>effective}
 puts JSON.generate(result)
rescue => error
 puts JSON.generate({'schema'=>'envloop-gitlab18.5-native-node-settings-v1','parse_status'=>false,'error_class'=>error.class.name})
end
"""
    return script.replace('PATHS',json.dumps(json.dumps(SETTINGS_PATHS))).replace('PATH',json.dumps(path)).replace('NODE',json.dumps(node_name))


def docker_started_ns(value):
    match=re.fullmatch(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,9}))?Z',value)
    require(match is not None,'Native Docker start timestamp outside fixed UTC schema')
    seconds=int(datetime.strptime(match[1],'%Y-%m-%dT%H:%M:%S').replace(tzinfo=timezone.utc).timestamp())
    return seconds*1000000000+int((match[2] or '').ljust(9,'0'))


def validate_attributes(value,*,started_at):
    require(value.get('schema')=='envloop-gitlab18.5-native-node-settings-v1' and value.get('parse_status') is True and
        value.get('node_name_exact') is True and value.get('artifact_regular_nonsymlink') is True and
        type(value.get('artifact_bytes')) is int and 0<value['artifact_bytes']<=10485760 and
        re.fullmatch('[a-f0-9]{64}',value.get('artifact_sha256','')) and value.get('fixed_paths')==SETTINGS_PATHS,
        'Native compiled attribute schema/provenance missing')
    require(type(value.get('artifact_mtime_ns')) is int and value['artifact_mtime_ns']>=docker_started_ns(started_at),
        'Native compiled attributes predate this clone boot')
    require(value.get('effective_settings')==EXPECTED_SETTINGS and set(value.get('fixed_settings',{}))==set(SETTINGS_PATHS),
        'Effective native compiled telemetry values differ')
    for key,rows in value['fixed_settings'].items():
        require(set(rows)=={'override','normal','default'},'Unbound Chef attribute layer')
        # All nine explicit profile values must survive into native normal attrs.
        # Defaults alone cannot qualify a missing/ignored profile declaration.
        require(rows['normal']=={'present':True,'type':'FalseClass','boolean':False},
            'Declared telemetry setting missing from native normal attributes')
        for row in rows.values():
            if row.get('present'):
                require(row.get('type') in {'TrueClass','FalseClass'} and type(row.get('boolean')) is bool,
                    'Native typed setting is not boolean')
            else:require(row=={'present':False,'type':'Absent'},'Unexpected absent attribute payload')
        chosen=next(rows[layer] for layer in ['override','normal','default'] if rows[layer]['present'])
        require(chosen['boolean'] is False,'Chef precedence overrides declared false value')
    return {'native_all_nine_false':True,'fresh_poststartup_artifact':True}


def raw_refs(out):
    result={}
    for path in sorted(out.iterdir()):
        require(path.is_file() and not path.is_symlink(),'Native output scope contains non-owned directory or link')
        if path.name in {'result.private.json','failure.private.json','manifest.private.json'}:continue
        require(path.name in previous.NATIVE_INPUTS|previous.NATIVE_FIXED or any(re.fullmatch(pattern,path.name) for pattern in NATIVE_PATTERNS),
            'Unknown output: supervision must use a separate private sibling')
        result[path.name]=source.sha(source.private(path))
    return result


@contextmanager
def version_scope():
    require(source.sha(Path(previous.__file__).read_bytes())==PINNED_V2,'Frozen v2 reader source changed')
    with previous.version_scope(),ExitStack() as stack:
        for name,value in [('SCHEMA',SCHEMA),('SOURCE_FILES',SOURCE_FILES),('raw_refs',raw_refs)]:stack.enter_context(patch.object(legacy,name,value))
        yield


def prepare(**kwargs):
    with version_scope():return legacy.prepare(**kwargs)


def checked_plan(path):
    with version_scope():return legacy.checked_plan(path)


def review(**kwargs):
    with version_scope():return legacy.review(**kwargs)


class NativeBackend(previous.NativeBackend):
    def boot(self,index):
        name=self.doc['container_prefix']+'-'+str(index);vmroot=self.doc['vm_root']+'/cycle-'+str(index)
        require(not self.container_exists(name,f'cycle-{index}-preexisting.private.json'),'Neutral container namespace already exists')
        script=self.parent_check_script()+"\nos.mkdir("+repr(vmroot)+",0o700)\n"
        self.vm("python3 - <<'NEUTRAL_CYCLE_CLAIM'\n"+script+"\nNEUTRAL_CYCLE_CLAIM");self.owned_cycles.add(index)
        with self.scope(name,vmroot,self.doc['neutral_base'],self.out):
            for role,lower in self.doc['seed_lowerdirs'].items():legacy.reset._mount(role,lower)
            config_delta=self.configure_upper(index,vmroot)
            args=['run','-d','--name',name,'--hostname',NODE_NAME,'--restart','no','--env-file',str(self.out/'neutral-runtime.env'),
                '-p',f"127.0.0.1:{self.doc['port']}:8018"]
            for role,dest in runtime.DESTS.items():args+=['-v',vmroot+'/'+role+'/merged:'+dest]
            args.append(runtime.IMAGE);self.docker(*args)
            ready=legacy.scoped.wait_cohort()
            state=json.loads(self.docker('inspect','--format','{{json .State}}',name,timeout=30));self.record(f'cycle-{index}-state.private.json',state)
            snapshot=legacy.verify.state_snapshot()
            snapshot_ref=self.record(f'cycle-{index}-snapshot.private.json',snapshot)  # Durable before any later reader can fail.
            trees=self.git_trees(snapshot,f'cycle-{index}')
            inspected=runtime.inspect(name);expected_env=[line for line in source.private(self.out/'neutral-runtime.env').decode().splitlines() if line and not line.startswith('#')]
            actual_env=inspected['Config']['Env']
            require(all([v for v in actual_env if v.split('=',1)[0]==line.split('=',1)[0]]==[line] for line in expected_env) and
                inspected['HostConfig']['RestartPolicy']=={'Name':'no','MaximumRetryCount':0},'Actual clone runtime environment/restart policy changed')
            startup={'identity':runtime.stable_identity(ready),'running':ready['running'],'health':ready['health'],
                'runtime_env_values_exact':True,'restart_policy':inspected['HostConfig']['RestartPolicy'],'SVWAIT':'60'}
            self.record(f'cycle-{index}-startup-proof.private.json',startup);self.capture_logs(index,name)
            status=self.docker('exec',name,'gitlab-ctl','status',timeout=60);write_raw(self.out/f'cycle-{index}-services.private.log',status.encode())
            services=parse_services(status)
            raw=self.docker('exec',name,'/opt/gitlab/embedded/bin/ruby','-e',node_reader_ruby(),timeout=30)
            attributes=json.loads(raw);self.record(f'cycle-{index}-native-attributes.private.json',attributes)
            validate_attributes(attributes,started_at=state['StartedAt'])
            self.record(f'cycle-{index}-effective.private.json',attributes['effective_settings'])
            return {'cycle':index,'healthy':True,'state_snapshot':snapshot,'container_id_sha256':ready['container_id_sha256'],
                'services':services,'effective_settings':attributes['effective_settings'],'full_git_trees':trees,'config_delta':config_delta,
                'startup_proof':startup,'snapshot_ref':snapshot_ref}


def run(*,plan,permit,execute=False,backend_factory=NativeBackend):
    raw_refs(plan.parent)
    with version_scope():return legacy.run(plan=plan,permit=permit,execute=execute,backend_factory=backend_factory)


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
    owner=load('parent-ownership.private.json');parent_teardown=load('parent-teardown.private.json')
    token=source.sha(factory.canonical({'vm_root':doc['vm_root'],'source_sha256s':doc['source_sha256s']}))
    require(owner==result['parent_ownership'] and owner['exclusive_parent_created'] is True and owner['mode']==0o700 and
        owner['owner_token_sha256']==source.sha(token.encode()) and parent_teardown==result['parent_teardown'] and
        parent_teardown=={'parent_claimed':True,'owned_parent_absent':True,'unowned_paths_removed':False},
        'Raw parent namespace ownership/absence unproved')
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
        attributes=load(f'cycle-{index}-native-attributes.private.json')
        validate_attributes(attributes,started_at=load(f'cycle-{index}-state.private.json')['StartedAt'])
        require(attributes['effective_settings']==cycle['effective_settings'],'Native compiled settings and cycle receipt differ')
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
        require(known_absence(post['returncode'],source.private(out/f'cycle-{index}-post-teardown.private.json.stdout.private.log'),
            source.private(out/f'cycle-{index}-post-teardown.private.json.stderr.private.log'),doc['container_prefix']+'-'+str(index)),'Raw owned container absence unproved')
    journal=[json.loads(line) for line in source.private(out/'lifecycle.private.jsonl').splitlines()]
    expected=[('parent_namespace_claim_intent',None),('preserved33_graceful_stop_intent',None)]
    for index in range(3):expected += [('owned_neutral_boot_intent',index),('owned_neutral_teardown_intent',index),('owned_neutral_cycle_verified',index)]
    expected += [('parent_namespace_release_intent',None),('preserved33_resume_intent',None),('preserved33_exit_verified',None)]
    require([(r['stage'],r['cycle']) for r in journal]==expected,'Native lifecycle chronology includes retry or missing phase')
    require(all(result.get(k)==0 for k in ['task_ids_consumed','model_calls','provider_calls','control_credit','official_final_admitted']) and
        result['new_task_dispatch_authorized'] is False,'Neutral trial cannot authorize task/model credit')
    return {'status':'saved_three_neutral_v3_native_cycles_independently_replayed','result_sha256':source.sha(source.private(out/'result.private.json')),
        'neutral_cycles_verified':3,'raw_files_verified':len(refs),'task_ids_consumed':0,'control_credit':0,'official_final_admitted':0,
        'new_task_dispatch_authorized':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=['prepare','review','run','audit'])
    for key in ['freeze','out','upstream-bindings','plan','permit']:parser.add_argument('--'+key,type=Path)
    parser.add_argument('--port',type=int,default=8026);parser.add_argument('--accept-root-review',action='store_true')
    parser.add_argument('--note',default='');parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    if args.mode=='prepare':result=prepare(freeze=args.freeze,out=args.out,upstream_bindings=args.upstream_bindings,port=args.port)
    elif args.mode=='review':result=review(plan=args.plan,permit=args.permit,accepted=args.accept_root_review,note=args.note)
    elif args.mode=='run':result=run(plan=args.plan,permit=args.permit,execute=args.execute)
    else:result=audit(plan=args.plan,permit=args.permit)
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
