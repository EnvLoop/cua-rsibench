"""Prepare source-only Odoo final bindings or run one already gated reservation.

The run path does not reserve, select, retry, or admit a task. It reconstructs
both existing real study gates and requires an exact already-dispatched command.
"""
from __future__ import annotations
import argparse
from pathlib import Path
from cursibench import full_study_campaign_dispatch_v1 as campaign
from cursibench import full_study_final_dispatch_v1 as final
from enterprise_fallback.odoo18 import native_surface_final_worker_v1 as worker


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='operation',required=True)
    prepare=sub.add_parser('prepare-source')
    prepare.add_argument('--native-worker-module',required=True)
    prepare.add_argument('--output-dir',type=Path,required=True)
    run=sub.add_parser('run-once')
    for name in ('repo-root','manifest','prepared-dir','ratification','matrix-manifest','prepared-matrix-dir','completion-index','worker-config','command','output-dir'):
        run.add_argument('--'+name,type=Path,required=True)
    for name in ('public-commit','final-public-commit'):
        run.add_argument('--'+name,required=True)
    run.add_argument('--execute',action='store_true')
    args=parser.parse_args(argv)
    if args.operation=='prepare-source':
        out=args.output_dir
        worker.require(not out.exists() and not out.is_symlink(),'final_source_directory_consumed')
        out.mkdir(parents=True,mode=0o700)
        worker.require(out.stat().st_mode&0o077==0,'final_source_directory_not_private')
        worker.write(out,'native-binding.private.json',worker._worker_module(args.native_worker_module).public_binding())
        worker.write(out,'final-source-binding.private.json',worker.source_binding(args.native_worker_module))
        worker.write(out,'study-source-snapshot.private.json',worker.study_source_snapshot(args.native_worker_module))
        return 0
    worker.require(args.execute,'final_explicit_live_required')
    frozen=campaign.FrozenStudy(repo_root=args.repo_root,manifest_path=args.manifest,prepared_dir=args.prepared_dir,
        ratification_path=args.ratification,public_commit_sha1=args.public_commit)
    gate=final.FinalGate(frozen=frozen,matrix_manifest_path=args.matrix_manifest,prepared_matrix_dir=args.prepared_matrix_dir,
        completion_index_path=args.completion_index,final_public_commit_sha1=args.final_public_commit)
    config,raw=final.private_json(args.worker_config,gate.work_root,'odoo_final_worker_config')
    expected={'native_worker_module','native_binding_path','native_binding_file_sha256','source_binding_path','source_binding_file_sha256',
        'worker_dir','final_output_root','local_cost_authority_path','local_cost_authority_sha256'}
    worker.require(set(config)==expected,'final_worker_config_unknown_field')
    for name in ('native_binding_path','source_binding_path','worker_dir','final_output_root','local_cost_authority_path'):
        config[name]=Path(config[name])
    command,_=final.private_json(args.command,gate.work_root,'odoo_already_dispatched_command')
    instance=worker.final_worker_factory(gate=gate,enable_live=True,**config)
    outcome=instance.run_once(command,args.output_dir)
    worker.write(args.output_dir,'worker-outcome.private.json',outcome)
    return 0


if __name__=='__main__':raise SystemExit(main())
