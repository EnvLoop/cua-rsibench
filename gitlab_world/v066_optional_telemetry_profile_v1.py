"""Source-only, uniform optional monitoring profile for neutral cold-boot trial.

No task dispatch, Docker, reset, deletion, seed write or provider operation.
Only a fresh clone's generated config/environment may receive this suffix.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re

VERSION='gitlab18.5-optional-telemetry-off-v1'
OPTIONAL_SERVICES=('node-exporter','gitlab-exporter','redis-exporter','prometheus','alertmanager','postgres-exporter')
CRITICAL_SERVICES=('postgresql','redis','gitaly','puma','sidekiq','gitlab-workhorse','nginx')
SETTINGS=("prometheus_monitoring['enable'] = false", "alertmanager['enable'] = false",
    "gitlab_exporter['enable'] = false", "node_exporter['enable'] = false",
    "postgres_exporter['enable'] = false", "prometheus['enable'] = false",
    "redis_exporter['enable'] = false", "puma['exporter_enabled'] = false",
    "sidekiq['metrics_enabled'] = false")
SUFFIX='\n# Uniform optional telemetry profile; fresh clone upper only.\n'+'\n'.join(SETTINGS)+'\n'


def require(ok,code):
    if not ok:raise ValueError(code)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def render_clone_config(base:bytes)->bytes:
    text=base.decode('utf-8');require('\x00' not in text,'Unexpected clone config encoding')
    if text.endswith(SUFFIX):return base
    require(SUFFIX not in text,'Telemetry suffix is not at config end')
    return (text+SUFFIX).encode()


def render_clone_environment(base:bytes)->bytes:
    text=base.decode('utf-8');lines=text.splitlines()
    require([line for line in lines if line.startswith('SVWAIT=')]==['SVWAIT=60'],
        'Uniform profile keeps the existing SVWAIT60')
    indices=[i for i,line in enumerate(lines) if line.startswith('GITLAB_OMNIBUS_CONFIG=')]
    require(len(indices)==1,'Exactly one existing Omnibus environment setting required')
    suffix='; '+'; '.join(SETTINGS)
    i=indices[0]
    if not lines[i].endswith(suffix):
        require(suffix not in lines[i],'Telemetry environment suffix must be terminal')
        lines[i]+=suffix
    return ('\n'.join(lines)+'\n').encode()


def validate_rendered_environment(original:bytes,rendered:bytes):
    require(rendered==render_clone_environment(original),'Only the fixed optional telemetry suffix may change')
    old=original.decode().splitlines();new=rendered.decode().splitlines()
    require(len(old)==len(new) and all(a==b for a,b in zip(old,new) if not a.startswith('GITLAB_OMNIBUS_CONFIG=')),
        'Unrelated runtime environment changed')
    return {'profile':VERSION,'before_runtime_env_sha256':sha(original),
        'after_runtime_env_sha256':sha(rendered),'SVWAIT':'60','readiness_seconds':900,
        'action_seconds':720,'supervisor_seconds':7200,'critical_services_changed':False,
        'immutable_seed_write_permitted':False,'root_cause_established':False,
        'neutral_native_proof_complete':False,'new_task_dispatch_authorized':False,
        'model_calls':0,'provider_calls':0,'control_credit':0,'official_final_admitted':0}


def validate_neutral_probe_receipt(value,baseline):
    """Read a future neutral trial; never turn it into task or model credit."""
    require(value.get('profile')==VERSION and value.get('cycles_requested')==3 and
        value.get('new_task_ids_consumed')==0 and value.get('automatic_restart_attempts')==0 and
        value.get('wait_bounds')=={'SVWAIT':'60','readiness_seconds':900,'action_seconds':720,'supervisor_seconds':7200},
        'Neutral trial must keep task exclusion, no retry and existing bounds')
    cycles=value.get('cycles');require(type(cycles) is list and len(cycles)==3,'Three fresh neutral cycles required')
    ids=set()
    for n,cycle in enumerate(cycles):
        require(cycle.get('cycle')==n and cycle.get('healthy') is True and cycle.get('state_snapshot')==baseline and
            cycle.get('immutable_lower_seed_before')==cycle.get('immutable_lower_seed_after') and
            cycle.get('original_core_metadata_before')==cycle.get('original_core_metadata_after') and
            cycle.get('effective_settings')=={line.split(' = ')[0]:False for line in SETTINGS} and
            cycle.get('teardown_verified') is True and cycle.get('remaining_owned_container_count')==0,
            'Neutral cold boot/profile/baseline/seed/teardown evidence incomplete')
        services=cycle.get('services',{})
        require(all(services.get(name)=='running' for name in CRITICAL_SERVICES) and
            all(services.get(name) in {'disabled','absent'} for name in OPTIONAL_SERVICES),
            'Neutral profile lost a critical service or retained exporter')
        identity=cycle.get('container_id_sha256');require(type(identity) is str and re.fullmatch('[a-f0-9]{64}',identity) and identity not in ids,
            'Neutral cycles reused an owned container identity');ids.add(identity)
        refs=cycle.get('raw_evidence_sha256s',{})
        require(type(refs) is dict and {'startup_log','docker_state','service_status','effective_settings','baseline_snapshot','teardown'}<=set(refs) and
            all(type(digest) is str and re.fullmatch('[a-f0-9]{64}',digest) for digest in refs.values()),
            'Neutral raw readback/teardown evidence bindings missing')
    return {'status':'neutral_optional_telemetry_cold_boot_trial_validated_no_task_credit',
        'cycles':3,'new_task_dispatch_authorized':False,'model_calls':0,'provider_calls':0,
        'control_credit':0,'official_final_admitted':0}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime-env',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    raw=a.runtime_env.read_bytes();rendered=render_clone_environment(raw)
    require(not a.out.exists() and not a.out.is_symlink(),'Fresh clone environment output required')
    with a.out.open('xb') as stream:stream.write(rendered)
    a.out.chmod(0o600)
    print(json.dumps(validate_rendered_environment(raw,rendered),sort_keys=True))


if __name__=='__main__':main()
