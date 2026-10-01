"""Run one already-reserved sealed Magento command through the real v22 gate."""
import argparse
from pathlib import Path
from cursibench import full_study_campaign_dispatch_v1 as parent
from cursibench import full_study_runtime_v2 as runtime
from magento_catalog_factory.native_surface_workers_v1 import final_worker_factory,private_json,require


def load_gate(spec):
    require(set(spec)=={'schema','qualified_parent','amendment_path','manifest_path','policy_witness_path','final_gate'} and
        spec['schema']=='magento-real-v22-final-execution-spec-v1','real_v22_final_spec_required')
    old={k:Path(v) if k.endswith('_path') or k in ('repo_root','prepared_dir') else v for k,v in spec['qualified_parent'].items()}
    qualified=parent.FrozenStudy(**old)
    study=runtime.FrozenStudy(qualified_parent=qualified,amendment=private_json(spec['amendment_path']),
        manifest=private_json(spec['manifest_path']),witness_bytes=Path(spec['policy_witness_path']).read_bytes())
    fields=spec['final_gate'];require(set(fields)=={'matrix_manifest_path','prepared_matrix_dir','completion_index_path',
        'final_public_commit_sha1','policy_final_witness_path'},'real_v22_final_gate_spec_required')
    return runtime.FinalGate(study,matrix_manifest_path=Path(fields['matrix_manifest_path']),
        prepared_matrix_dir=Path(fields['prepared_matrix_dir']),completion_index_path=Path(fields['completion_index_path']),
        final_public_commit_sha1=fields['final_public_commit_sha1'],policy_final_witness_bytes=Path(fields['policy_final_witness_path']).read_bytes())


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('runtime-spec','runtime-spec-sha256','inputs','inputs-sha256','command','command-sha256','output'):p.add_argument('--'+name,required=True)
    p.add_argument('--enable-live',action='store_true');args=p.parse_args()
    gate=load_gate(private_json(args.runtime_spec,args.runtime_spec_sha256))
    worker=final_worker_factory(gate=gate,inputs_path=args.inputs,inputs_sha256=args.inputs_sha256,enable_live=args.enable_live)
    command=private_json(args.command,args.command_sha256)
    result=worker.run_once(command,Path(args.output))
    # This worker cannot reserve a command, register a final task, or replay a
    # request. The authoritative FinalController performs outcome admission.
    from cursibench.full_study_final_dispatch_v1 import canonical
    print(canonical(result).decode(),end='')

if __name__=='__main__':main()
