"""Source preparation or one explicitly reviewed paid public TRAIN pilot."""
import argparse,json
from pathlib import Path
from enterprise_fallback.odoo18 import native_public_train_pilot_v22 as pilot


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='operation',required=True)
    prepare=sub.add_parser('prepare-source');prepare.add_argument('--output',type=Path,required=True)
    request_parser=sub.add_parser('prepare-request')
    for field in ('worker-dir','native-binding','native-binding-sha256','train-control','train-control-sha256','task-id','attempt-id','output-run','output-stage'):
        request_parser.add_argument('--'+field,required=True)
    request_parser.add_argument('--seed',type=int,default=0);request_parser.add_argument('--max-output-tokens',type=int,default=4096)
    run=sub.add_parser('run-once')
    for field in ('request','request-sha256','root-review','root-review-sha256'):run.add_argument('--'+field,required=True)
    run.add_argument('--execute',action='store_true');args=parser.parse_args(argv)
    if args.operation=='prepare-source':
        pilot.legacy.final.private_write_new(args.output,pilot.legacy.final.canonical(pilot.source_binding()));return 0
    if args.operation=='prepare-request':
        worker=Path(args.worker_dir).resolve();pilot.require(worker.name=='train','pilot_public_train_partition_required')
        manifest=json.loads(pilot.private(worker/'private/task_set_manifest.json'))
        rows=manifest.get('train');pilot.require(type(rows) is list and len(rows)==20,'pilot_full_public_train_manifest_required')
        matches=[row for row in rows if row['task_id']==args.task_id];pilot.require(len(matches)==1,'pilot_unique_public_train_task_required')
        request={'schema':'odoo-public-train-model-pilot-request-v22','attempt_id':args.attempt_id,'worker_dir':str(worker),
            'output_root':str(Path(args.output_run).resolve()),'native_binding':{'path':str(Path(args.native_binding).resolve()),'sha256':args.native_binding_sha256},
            'train_control':{'path':str(Path(args.train_control).resolve()),'sha256':args.train_control_sha256},'task':matches[0],
            'training_config':{'model':'Qwen/Qwen3.8-27B','seed':args.seed,'sample_max_tokens':args.max_output_tokens},
            'source_binding_sha256':pilot.source_binding()['binding_sha256']}
        review={'schema':'odoo-public-train-model-pilot-root-review-v22','request_sha256':pilot.digest(pilot.legacy.final.canonical(request)),
            'source_binding_sha256':request['source_binding_sha256'],'one_public_train_paid_pilot_authorized':False,
            'formal_registration_authorized':False,'automatic_retry_authorized':False}
        stage=Path(args.output_stage);pilot.require(not stage.exists() and not stage.is_symlink(),'pilot_fresh_metadata_stage_required');stage.mkdir(parents=True,mode=0o700)
        pilot.write(stage,'request.private.json',request);pilot.write(stage,'unsigned-root-review.private.json',review)
        pilot.write(stage,'source-binding.private.json',pilot.source_binding());return 0
    def read(path,expected):
        raw=pilot.private(path);pilot.require(pilot.digest(raw)==expected,'pilot_reviewed_input_changed');return json.loads(raw)
    request=read(args.request,args.request_sha256);review=read(args.root_review,args.root_review_sha256)
    instance=pilot.PublicTrainPilot(request,review,enable_live=args.execute);instance.run_once();return 0

if __name__=='__main__':raise SystemExit(main())
