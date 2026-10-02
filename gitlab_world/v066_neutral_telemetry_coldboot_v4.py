"""Additive ordered shutdown: Sidekiq first while PostgreSQL/Redis remain up.

This repairs the observed SIGTERM aggregate-stop Sidekiq timeout without
changing service configuration, waits, image, task data or old attempts.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager,ExitStack
import json
from pathlib import Path
import re
import subprocess
from unittest.mock import patch
from . import v066_neutral_telemetry_coldboot_v3 as previous
from .v066_neutral_telemetry_coldboot_v3 import source,runtime,factory,require,parse_services,tree_digests,EXPECTED_SETTINGS,profile,write_raw,known_absence
legacy=previous.legacy
SCHEMA='envloop-gitlab-neutral-telemetry-coldboot-plan-v4'
SOURCE_FILES=previous.SOURCE_FILES+('gitlab_world/v066_neutral_telemetry_coldboot_v4.py',
 'tests/test_gitlab_neutral_telemetry_coldboot_v4.py','docs/FULL_STUDY_GITLAB_NEUTRAL_ORDERED_SHUTDOWN_V4_2026-10-01.md')
_node_reader=previous.node_reader_ruby
_validate_attributes=previous.validate_attributes
PINNED_V3='d0702eb7fbc8404c5bd6234eca641954416c5b62702b7b3cb3ec4cff208dfa6d'
SERVICE_NAMES=set(profile.CRITICAL_SERVICES)|set(profile.OPTIONAL_SERVICES)|{'gitlab-kas','logrotate','sshd'}
NATIVE_PATTERNS=previous.NATIVE_PATTERNS+(
 r'(original-ordered-sidekiq|original-restore-state-before|original-resumed-critical|cycle-[012]-ordered-sidekiq)(-(before|after|proof))?\.private\.json',
 r'(original-ordered-sidekiq|original-restore-state-before|original-resumed-critical|cycle-[012]-ordered-sidekiq)(-(before|after))?\.(stdout|stderr)\.private\.log',
 r'cycle-[012]-pre-order\.private\.json',r'cycle-[012]-pre-order\.private\.json\.(stdout|stderr)\.private\.log',
 r'cycle-[012]-stopped-state\.private\.json')


def node_reader_ruby():
    script=_node_reader()
    extra="""observed={};unknown=[]
 j.each do |layer,value|
  next unless value.is_a?(Hash)
  observed[layer]={}
  paths.each do |key,names|
   x=value;present=true
   names.each do |name|
    unless x.is_a?(Hash) && x.key?(name);present=false;break;end
    x=x[name]
   end
   row={'present'=>present,'type'=>present ? x.class.name : 'Absent'}
   row['boolean']=x if present && (x==true || x==false)
   observed[layer][key]=row
   unknown << layer if present && !['override','normal','default'].include?(layer)
  end
 end
 result['all_observed_attribute_layers']=observed
 result['unknown_service_value_layers']=unknown.uniq.sort
 puts JSON.generate(result)"""
    return script.replace(' puts JSON.generate(result)',extra)


def validate_attributes(value,*,started_at):
    result=_validate_attributes(value,started_at=started_at)
    require(value.get('unknown_service_value_layers')==[] and type(value.get('all_observed_attribute_layers')) is dict,
        'Unknown native service-value layer cannot be inferred')
    observed=value['all_observed_attribute_layers']
    require({'normal','default'}<=set(observed),'Observed native layers missing')
    for layer,rows in observed.items():
        require(set(rows)==set(EXPECTED_SETTINGS),'Observed fixed native fields missing')
        if layer in {'override','normal','default'}:require(rows=={key:layers[layer] for key,layers in value['fixed_settings'].items()},'Observed native layer differs from fixed projection')
        else:require(all(row=={'present':False,'type':'Absent'} for row in rows.values()),'Unknown service-value layer present')
    return result


def status_semantics(returncode,stdout,stderr):
    require(type(returncode) is int and returncode in {0,1} and not stderr.strip(),
        'Unknown service-status error cannot prove deliberately down state')
    require(stdout.strip(),'Empty service-status response')
    services=parse_services(stdout.decode())
    actual={re.match(r'^(run|down): ([^:]+):',line)[2] for line in stdout.decode().splitlines()}
    require(actual<=SERVICE_NAMES,'Unknown service status')
    if returncode==1:require(any(services[s]=='disabled' for s in actual),'Nonzero status lacks a known down service')
    return services


def raw_refs(out):
    result={}
    for path in sorted(out.iterdir()):
        require(path.is_file() and not path.is_symlink(),'Native output scope contains non-owned directory or link')
        if path.name in {'result.private.json','failure.private.json','manifest.private.json'}:continue
        require(path.name in previous.previous.NATIVE_INPUTS|previous.previous.NATIVE_FIXED or any(re.fullmatch(pattern,path.name) for pattern in NATIVE_PATTERNS),
            'Unknown output: supervision must use a separate private sibling')
        result[path.name]=source.sha(source.private(path))
    return result


@contextmanager
def version_scope():
    require(source.sha(Path(previous.__file__).read_bytes())==PINNED_V3,'Frozen v3 source changed')
    with previous.version_scope(),ExitStack() as stack:
        for name,value in [('SCHEMA',SCHEMA),('SOURCE_FILES',SOURCE_FILES),('raw_refs',raw_refs)]:stack.enter_context(patch.object(legacy,name,value))
        stack.enter_context(patch.object(previous,'node_reader_ruby',node_reader_ruby))
        stack.enter_context(patch.object(previous,'validate_attributes',validate_attributes))
        yield


def prepare(**kwargs):
    with version_scope():return legacy.prepare(**kwargs)


def checked_plan(path):
    with version_scope():return legacy.checked_plan(path)


def review(**kwargs):
    with version_scope():return legacy.review(**kwargs)


class NativeBackend(previous.NativeBackend):
    def __init__(self,doc,out):
        super().__init__(doc,out);self.original_sidekiq_stop_attempted=False;self.owned_stop_states={}
    def service_status(self,name,label):
        try:result=subprocess.run(['docker','--context',runtime.CONTEXT,'exec',name,'gitlab-ctl','status'],capture_output=True,timeout=60,check=False)
        except subprocess.TimeoutExpired as error:
            stdout,stderr=error.stdout or b'',error.stderr or b''
            self.record(label+'.private.json',{'returncode':None,'timed_out':True,'stdout_sha256':source.sha(stdout),'stderr_sha256':source.sha(stderr)})
            write_raw(self.out/(label+'.stdout.private.log'),stdout);write_raw(self.out/(label+'.stderr.private.log'),stderr);raise
        write_raw(self.out/(label+'.stdout.private.log'),result.stdout);write_raw(self.out/(label+'.stderr.private.log'),result.stderr)
        row={'returncode':result.returncode,'stdout_sha256':source.sha(result.stdout),'stderr_sha256':source.sha(result.stderr)}
        try:services=status_semantics(result.returncode,result.stdout,result.stderr)
        except Exception:
            self.record(label+'.private.json',row|{'semantic_status_valid':False});raise
        complete=row|{'services':services,'semantic_status_valid':True}
        self.record(label+'.private.json',complete);return complete
    def ordered_sidekiq_stop(self,name,label,*,allow_already_down=False):
        before=self.service_status(name,label+'-before')
        if allow_already_down and before['services'].get('sidekiq')=='disabled':
            # Failed/partial boot cleanup is not qualification evidence.
            self.record(label+'-proof.private.json',{'already_down_failed_boot_cleanup':True,'control_credit':0});return
        require(before['services'].get('sidekiq')=='running' and all(before['services'].get(s)=='running' for s in ['postgresql','redis']),
            'Sidekiq stop requires live dependencies and owned lifecycle scope')
        if name==self.doc['original_container']:self.original_sidekiq_stop_attempted=True
        sequence=self.seq;self.docker('exec',name,'gitlab-ctl','stop','sidekiq',timeout=120)
        after=self.service_status(name,label+'-after')
        require(after['services'].get('sidekiq')=='disabled' and all(after['services'].get(s)=='running' for s in ['postgresql','redis']),
            'Named Sidekiq stop did not preserve live dependencies')
        self.record(label+'-proof.private.json',{'before':before,'after':after,'sidekiq_stopped_before_dependencies':True,
            'stop_command_ref':f'command-{sequence:03d}.private.json'})
    def stop_original(self,before):
        self.ordered_sidekiq_stop(self.doc['original_container'],'original-ordered-sidekiq')
        super().stop_original(before)
    def docker(self,*args,timeout=120):
        result=super().docker(*args,timeout=timeout)
        if args and args[0]=='stop':
            name=args[-1]
            for index in self.owned_cycles:
                if name==self.doc['container_prefix']+'-'+str(index):
                    state=json.loads(super().docker('inspect','--format','{{json .State}}',name,timeout=30))
                    self.owned_stop_states[index]=state;self.record(f'cycle-{index}-stopped-state.private.json',state)
        return result
    def teardown(self,index):
        require(index in self.owned_cycles,'No ownership claim; colliding namespace must remain untouched')
        name=self.doc['container_prefix']+'-'+str(index);error=None
        try:
            if self.container_exists(name,f'cycle-{index}-pre-order.private.json'):
                state=json.loads(self.docker('inspect','--format','{{json .State}}',name,timeout=30))
                if state['Running']:self.ordered_sidekiq_stop(name,f'cycle-{index}-ordered-sidekiq',allow_already_down=True)
        except Exception as failure:error=failure
        proof=super().teardown(index)  # Always attempt owned removal/unmount after an ordering failure.
        if error is not None:raise error
        state=self.owned_stop_states.get(index)
        require(state is None or state['ExitCode']==0 and state['OOMKilled'] is False and state['Running'] is False,
            'Owned container process exit was not clean')
        return proof
    def resume_original(self,before):
        proof=runtime.proof(self.doc['original_container'])
        if proof['running'] and self.original_sidekiq_stop_attempted:
            status=self.service_status(self.doc['original_container'],'original-restore-state-before')
            if status['services'].get('sidekiq')=='disabled':
                # Roll back the deliberate lifecycle stop if Docker never stopped.
                self.docker('exec',self.doc['original_container'],'gitlab-ctl','start','sidekiq',timeout=120)
        result=super().resume_original(before)
        status=self.service_status(self.doc['original_container'],'original-resumed-critical')
        require(all(status['services'].get(s)=='running' for s in profile.CRITICAL_SERVICES),'Original critical services not restored')
        return result


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
    def ordered(label):
        proof=load(label+'-proof.private.json');before=load(label+'-before.private.json');after=load(label+'-after.private.json')
        for phase,row in [('before',before),('after',after)]:
            stem=label+'-'+phase
            stdout=source.private(out/(stem+'.stdout.private.log'));stderr=source.private(out/(stem+'.stderr.private.log'))
            require(row['stdout_sha256']==source.sha(stdout) and row['stderr_sha256']==source.sha(stderr) and
                status_semantics(row['returncode'],stdout,stderr)==row['services'],'Raw ordered status differs')
        require(before['services']['sidekiq']=='running' and after['services']['sidekiq']=='disabled' and
            all(row['services'][svc]=='running' for row in [before,after] for svc in ['postgresql','redis']) and
            proof['before']==before and proof['after']==after and proof['sidekiq_stopped_before_dependencies'] is True,
            'Sidekiq did not stop while dependencies remained alive')
        command=load(proof['stop_command_ref'])
        expected_name=doc['original_container'] if label=='original-ordered-sidekiq' else doc['container_prefix']+'-'+label.split('-')[1]
        require(command['returncode']==0 and command['argv']==['docker','--context',runtime.CONTEXT,'exec',expected_name,'gitlab-ctl','stop','sidekiq'],
            'Named stop command proof changed')
    ordered('original-ordered-sidekiq')
    restored_status=load('original-resumed-critical.private.json')
    restored_stdout=source.private(out/'original-resumed-critical.stdout.private.log')
    restored_stderr=source.private(out/'original-resumed-critical.stderr.private.log')
    require(status_semantics(restored_status['returncode'],restored_stdout,restored_stderr)==restored_status['services'] and
        all(restored_status['services'].get(s)=='running' for s in profile.CRITICAL_SERVICES),'Original critical services not restored')
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
        ordered(f'cycle-{index}-ordered-sidekiq')
        stopped_state=load(f'cycle-{index}-stopped-state.private.json')
        require(stopped_state['ExitCode']==0 and stopped_state['Running'] is False and stopped_state['OOMKilled'] is False,
            'Owned process did not stop cleanly')
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
    return {'status':'saved_three_neutral_v4_native_cycles_independently_replayed','result_sha256':source.sha(source.private(out/'result.private.json')),
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
