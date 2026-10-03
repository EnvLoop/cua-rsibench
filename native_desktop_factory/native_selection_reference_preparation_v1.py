"""Prepare the original selection20 reference scripts under current Source52.

This evaluator-only preparation never creates a guest or admits a model lane.
It reads selection packages only. Final task bodies and answers stay sealed.
Actual native source, focus, Save, state, reset and cleanup proof remain gates.
"""
import argparse
from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path

from . import admit, factory_v2
from . import native_editor_runtime_v52 as runtime
from . import selection_control_scripts_v10 as scripts
from .v066_control_plan import compile_script
from .common_native_guest_v31 import canonical, digest

SCHEMA='native52-original-selection20-reference-preparation-v1'
MODES=('positive','near-miss','cold-reset')


def require(value,message):
    if not value:raise ValueError(message)


def file_ref(path):
    path=Path(path)
    require(path.is_file() and not path.is_symlink(),'Regular owned preparation source required')
    return {'path':str(path.resolve()),'sha256':sha256(path.read_bytes()).hexdigest()}


def prepare(*,candidate_root,inventory_sha256,runtime_sha256,output):
    output=Path(output)
    require('.private' in str(output),'Evaluator-private preparation output required')
    require(not output.exists() and not output.is_symlink(),'Fresh private preparation output required')
    root=Path(candidate_root).resolve();inventory=root/'candidate-inventory.json'
    inventory_ref=file_ref(inventory)
    require(inventory_ref['sha256']==inventory_sha256,'Original inventory hash changed')
    value=json.loads(inventory.read_bytes());rows=value['tasks']
    require(value.get('design_revision')=='v2-distinct-structures' and
            Counter(row['split'] for row in rows)=={'train':20,'selection':20,'final_candidate':100},
            'Original full study allocation required')
    require(len({row['task_id'] for row in rows})==140,'Original task identities overlap')
    manifest=runtime.source_manifest()
    require(digest(canonical(manifest))==runtime_sha256 and len(manifest['source_sha256s'])==100 and
            manifest['task_policy']=={'max_actions':90,'actor_seconds':720,'lease_seconds':1200},
            'Exact current Source100 required')
    selected=[row for row in rows if row['split']=='selection']
    require(Counter(row['workflow'] for row in selected)=={name:5 for name in scripts.SELECTION_PROFILES},
            'All four original selection families required')
    prepared=[]
    for row in selected:
        require(row['template_group']==factory_v2.TEMPLATES['selection'][row['workflow']],
                'Original two-target selection template changed')
        directory,baseline,oracle=admit._package(root,row)
        require(oracle['split']=='selection' and len(oracle['targets'])==2,
                'Original selection double-target structure required')
        layout=scripts.selection_layout_metadata(directory,row)
        modes=[]
        for mode in MODES:
            script=scripts.actor_script(directory,oracle,mode)
            actions,guards=compile_script(script)
            require(len(actions)<=90 and (not actions if mode=='cold-reset' else bool(actions)),
                    'Original native action budget changed')
            modes.append({'mode':mode,'reference_script':script,
                          'reference_script_sha256':sha256(script.encode()).hexdigest(),
                          'primitive_actions':actions,'trusted_guard_counts':dict(guards),
                          'actor_actions':len(actions),'native_dispatch_performed':False})
        prepared.append({'identity':{name:row[name] for name in
                           ('task_id','package_sha256','input_sha256','workflow','template_group')},
                         'package_ref':file_ref(directory/'package.json'),
                         'oracle_ref':file_ref(directory/'oracle.json'),
                         'instruction_ref':file_ref(directory/'actor_task.txt'),
                         'layout':layout,'reference_modes':modes})
    source_root=Path(__file__).resolve().parents[1]
    names=('native_desktop_factory/native_selection_reference_preparation_v1.py',
           'native_desktop_factory/selection_control_scripts_v10.py',
           'native_desktop_factory/v066_control_plan.py',
           'native_desktop_factory/admit.py',
           'native_desktop_factory/factory.py',
           'native_desktop_factory/factory_v2.py',
           'native_desktop_factory/calibrate_sweep.py',
           'native_desktop_factory/final_admission_preflight_v065.py',
           'native_desktop_factory/verify.py',
           'native_desktop_factory/source.py')
    result={'schema':SCHEMA,'inventory_ref':inventory_ref,
            'runtime_source_manifest_sha256':runtime_sha256,
            'runtime_source_sha256s':manifest['source_sha256s'],
            'preparation_source_sha256s':{name:file_ref(source_root/name)['sha256'] for name in names},
            'selection_task_count':20,'original_modes':list(MODES),'maximum_selection_guest_intents':60,
            'task_policy':{'max_actions':90,'actor_seconds':720,'lease_seconds':1200},
            'prepared_tasks':prepared,'selection_package_bodies_verified':20,
            'final_task_or_oracle_bodies_opened':0,'native_creates':0,'model_calls':0,'tinker_calls':0,
            'native_qualification_passed':False,'model_lane_authorized':False,
            'original120_cohort_gate_changed':False,'old_control_credit':0,
            'pending_native_execution_requirements':['current physical ownership and focus for every primitive',
                 'current application-specific native Save proof',
                 'independent original saved-artifact and collateral verifier',
                 'distinct positive, near-miss and cold-reset guests',
                 'exact baseline reset, raw native receipts and owned cleanup',
                 'complete per-task source visual review and all seven actor paths']}
    output.parent.mkdir(parents=True,exist_ok=True)
    raw=(json.dumps(result,sort_keys=True,indent=2)+'\n').encode()
    descriptor=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(descriptor,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    return {'schema':SCHEMA,'output_ref':file_ref(output),'selection_tasks_prepared':20,
            'selection_script_cases_compiled':60,'final_bodies_opened':0,
            'native_creates':0,'model_calls':0,'tinker_calls':0,'native_qualification_passed':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate-root','inventory-sha256','runtime-sha256','output'):
        parser.add_argument('--'+name,required=True)
    print(json.dumps(prepare(**vars(parser.parse_args())),sort_keys=True))


if __name__=='__main__':main()
