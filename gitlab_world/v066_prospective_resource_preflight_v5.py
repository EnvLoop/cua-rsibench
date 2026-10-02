"""Read-only resource/original-state proof before any prospective clone intent."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shlex
from . import runtime,reset,verify
from . import v066_prospective_cohort_v5 as source

MIN_VM_MEMORY_BYTES=10*1024**3
CLONE_DISK_FREE_FLOOR_BYTES=8*1024**3


def preflight(value:dict)->dict:
    if runtime.CONTEXT!='colima-cua-gitlab':raise ValueError('Prospective resource proof requires original dedicated Docker context')
    info=json.loads(runtime.docker('info','--format','{{json .}}'))
    memory=info.get('MemTotal');cpus=info.get('NCPU')
    if type(memory) is not int or memory<MIN_VM_MEMORY_BYTES or type(cpus) is not int or cpus<3:
        raise ValueError('Two GitLab runtimes require at least10GiB VM memory and3CPUs; resize maintenance first')
    lower=value['original_seed_lowerdirs']
    raw=reset.vm_shell("df -B1 --output=avail /var/lib/docker | tail -n 1; du -sb -- "+
                       ' '.join(shlex.quote(lower[role]) for role in ('config','logs','data')),timeout=120)
    lines=raw.splitlines()
    if len(lines)!=4:raise ValueError('Read-only Docker disk/seed-size proof incomplete')
    available=int(lines[0].strip());sizes=[]
    for role,line in zip(('config','logs','data'),lines[1:]):
        count,path=line.split(maxsplit=1)
        if path!=lower[role] or int(count)<0:raise ValueError('Original seed-size paths changed')
        sizes.append(int(count))
    required=sum(sizes)+CLONE_DISK_FREE_FLOOR_BYTES
    if available<required:raise ValueError('VM disk lacks measured seed-copy bytes plus8GiB floor')
    proof=runtime.proof(runtime.WORLD)
    if proof.get('running') is not True or proof.get('health')!='healthy' or proof.get('image_id')!=runtime.IMAGE_ID:
        raise ValueError('Original GitLab runtime is not healthy at resource preflight')
    baseline=json.loads(source.private(Path(value['original_private_root'])/'baseline-persisted-state.json'))
    if verify.state_snapshot()!=baseline or len(baseline['project_ids'])!=31:
        raise ValueError('Original31-project SQL/Git baseline changed before clone bootstrap')
    return {'schema':'envloop-gitlab-prospective-resource-readonly-private-v5',
            'context':runtime.CONTEXT,'docker_vm_memory_bytes':memory,'docker_vm_cpu_count':cpus,
            'minimum_vm_memory_bytes':MIN_VM_MEMORY_BYTES,'vm_disk_available_bytes':available,
            'original_seed_copy_bytes':sum(sizes),'required_vm_disk_available_bytes':required,
            'disk_free_floor_bytes':CLONE_DISK_FREE_FLOOR_BYTES,'original_runtime_proof':proof,
            'original31_business_sha256':baseline['business_sha256'],
            'original31_exact_readback':True,'application_or_vm_mutations':0,
            'model_calls':0,'official_final_admitted':0}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--freeze',type=Path,required=True)
    p.add_argument('--private-out',type=Path,required=True);a=p.parse_args()
    value=source.validate_source(a.freeze)
    if Path(__file__).resolve().parents[1]!=Path(value['evaluator_root']):raise ValueError('Resource readback must use original evaluator checkout')
    result=preflight(value);source.write_new(a.private_out,result)
    print(json.dumps({k:result[k] for k in ('schema','docker_vm_memory_bytes','docker_vm_cpu_count','original31_exact_readback','application_or_vm_mutations','model_calls','official_final_admitted')},sort_keys=True))


if __name__=='__main__':main()
