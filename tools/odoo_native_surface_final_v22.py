"""Prepare closed Odoo v22 final source or consume one already-reserved command."""
from pathlib import Path
import argparse,json
from cursibench import full_study_campaign_dispatch_v1 as parent,full_study_runtime_v2 as v22
from enterprise_fallback.odoo18 import native_surface_final_worker_v22 as worker


def load_gate(spec):
 worker.require(set(spec)=={'schema','qualified_parent','amendment_path','manifest_path','policy_witness_path','final_gate'} and
  spec['schema']=='odoo-real-v22-final-execution-spec-v1','real_v22_final_spec_required')
 args={k:Path(v) if k.endswith('_path') or k in ('repo_root','prepared_dir') else v for k,v in spec['qualified_parent'].items()}
 qualified=parent.FrozenStudy(**args)
 study=v22.FrozenStudy(qualified_parent=qualified,amendment=json.loads(worker.private(spec['amendment_path'])),
  manifest=json.loads(worker.private(spec['manifest_path'])),witness_bytes=worker.private(spec['policy_witness_path']))
 fields=spec['final_gate'];worker.require(set(fields)=={'matrix_manifest_path','prepared_matrix_dir','completion_index_path','final_public_commit_sha1','policy_final_witness_path'},'real_v22_final_gate_spec_required')
 return v22.FinalGate(study,matrix_manifest_path=Path(fields['matrix_manifest_path']),prepared_matrix_dir=Path(fields['prepared_matrix_dir']),
  completion_index_path=Path(fields['completion_index_path']),final_public_commit_sha1=fields['final_public_commit_sha1'],policy_final_witness_bytes=worker.private(fields['policy_final_witness_path']))


def main(argv=None):
 p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='operation',required=True)
 prep=sub.add_parser('prepare-source');prep.add_argument('--output-dir',type=Path,required=True)
 run=sub.add_parser('run-once')
 for name in ('runtime-spec','runtime-spec-sha256','worker-config','worker-config-sha256','command','command-sha256','output-dir'):run.add_argument('--'+name,required=True)
 run.add_argument('--execute',action='store_true');a=p.parse_args(argv)
 if a.operation=='prepare-source':
  out=a.output_dir;worker.require(not out.exists() and not out.is_symlink(),'fresh_v22_final_source_directory_required');out.mkdir(mode=0o700,parents=True)
  worker.write(out,'native-binding.private.json',worker.workers.public_binding());worker.write(out,'final-source-binding.private.json',worker.source_binding())
  worker.write(out,'study-source-snapshot.private.json',worker.study_source_snapshot());return 0
 worker.require(a.execute,'final_explicit_live_required')
 def read(path,expected):
  raw=worker.private(path);worker.require(worker.digest(raw)==expected,'v22_private_execution_input_changed');return json.loads(raw)
 gate=load_gate(read(a.runtime_spec,a.runtime_spec_sha256));config=read(a.worker_config,a.worker_config_sha256)
 expected={'native_worker_module','native_binding_path','native_binding_file_sha256','source_binding_path','source_binding_file_sha256',
  'worker_dir','final_output_root','local_cost_authority_path','local_cost_authority_sha256'}
 worker.require(set(config)==expected,'final_worker_config_unknown_field')
 for key in ('native_binding_path','source_binding_path','worker_dir','final_output_root','local_cost_authority_path'):config[key]=Path(config[key])
 command=read(a.command,a.command_sha256);instance=worker.final_worker_factory(gate=gate,enable_live=True,**config)
 outcome=instance.run_once(command,Path(a.output_dir));worker.write(Path(a.output_dir),'worker-outcome.private.json',outcome);return 0

if __name__=='__main__':raise SystemExit(main())
