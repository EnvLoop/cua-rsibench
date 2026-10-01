"""Metadata preparation and fresh native TRAIN/20/100 trusted controls."""
import argparse
import asyncio
from hashlib import sha256
import json
from pathlib import Path
import time
from .native_surface_workers_v1 import Inputs,ROOT,require,private_json,public_binding,study_source_snapshot,write
from .native_queue_runtime_v2 import run_task
from .native_surface_budget_performance_v2 import audit_episode
from . import seed,verify


class ReferenceSampler:
    """Evaluator-only ordinary GUI recipe; no target/gold reaches a model."""
    trusted_control=True
    def __init__(self,case,mode):
        self.case=case;self.mode=mode;self.stage=0;self.index=0;self.attempt_id='trusted-native-control';self.calls=0
        self.edits=(case['target_variants'] if mode=='positive' else
            [{**case['untouched_comparators'][0],'initial_price':case['untouched_comparators'][0]['price'],
                'target_price':case['target_variants'][0]['target_price']}] if mode=='wrong_variant' else [])
    def bind_native_adapter(self,adapter,loop):self.adapter=adapter
    async def control_sample(self,observation):
        from .native_reference_bulk_price_v2 import control_sample
        return await control_sample(self,observation)


def prepare(*,plan_path,plan_sha256,lane_path,lane_sha256,output,final_output_root):
    """Explicit evaluator preparation; no GUI/provider and no qualification."""
    output=Path(output);require(not output.exists() and not output.is_symlink(),'fresh_metadata_output_required');output.mkdir(mode=0o700,parents=True)
    lane=private_json(lane_path,lane_sha256);raw=Path(plan_path).read_bytes()
    require(sha256(raw).hexdigest()==plan_sha256,'control_plan_changed');plan=json.loads(raw)
    require(plan['schema']=='envloop-magento-catalog-candidates-v1','original_magento_candidate_plan_required')
    roster={'schema':'magento-native-roster-metadata-v1','plan_sha256':plan_sha256,
        'splits':{k:[{f:r[f] for f in ('task_id','package_sha256')} for r in plan['cases'][k]] for k in
            ('train','selection','official_candidate')}}
    for split,count in [('train',20),('selection',20),('official_candidate',100)]:require(len(roster['splits'][split])==count,'full_roster_required')
    binding=public_binding();write(output,'binding.private.json',binding);write(output,'study-source-snapshot.private.json',study_source_snapshot());write(output,'roster.private.json',roster)
    ref={'path':str((output/'roster.private.json').resolve()),'sha256':sha256((output/'roster.private.json').read_bytes()).hexdigest()}
    lane={**lane,'schema':'magento-native-owned-lane-admission-v1','source_binding_sha256':binding['binding_sha256'],
        'native_train_positive_negative_reset_reviewed':False,'roster_metadata_ref':ref}
    write(output,'lane.private.json',lane)
    args={'plan_path':str(Path(plan_path).resolve()),'plan_sha256':plan_sha256,'binding_path':str((output/'binding.private.json').resolve()),
        'binding_sha256':sha256((output/'binding.private.json').read_bytes()).hexdigest(),'lane_path':str((output/'lane.private.json').resolve()),
        'lane_sha256':sha256((output/'lane.private.json').read_bytes()).hexdigest(),'output_root':str(Path(final_output_root).resolve())}
    write(output,'inputs.private.json',args)
    return {'status':'metadata_only_not_qualified','inputs':str(output/'inputs.private.json'),'source_binding_sha256':binding['binding_sha256']}


def run_controls(*,inputs,split,output,enable_live=False,train_index=None):
    require(enable_live and split in ('train','selection','official_candidate'),'explicit_native_control_run_required')
    require(inputs.binding==public_binding(),'control_source_changed')
    if split!='train':
        # Preparation may open roster metadata; the full controls may proceed
        # only after reopening the actual current TRAIN/reset/visual proof.
        inputs.validate_train_admission()
    identities=inputs.roster['splits'][split]
    if split=='train':require(type(train_index) is int and 0<=train_index<20,'explicit_train_case_required');identities=[identities[train_index]]
    output=Path(output);require(not output.exists() and not output.is_symlink(),'fresh_control_namespace_required');output.mkdir(mode=0o700,parents=True)
    results=[]
    for ordinal,identity in enumerate(identities):
        case=inputs.load(identity,split);trio={}
        for mode,expected in [('baseline',0),('positive',1),('wrong_variant',0)]:
            folder=output/f'attempt-{ordinal:03d}'/mode;folder.mkdir(mode=0o700,parents=True)
            sampler=ReferenceSampler(case,mode)
            row=asyncio.run(run_task(case=case,task=identity,output=folder,runtime=inputs.runtime(),sampler=sampler,
                username=inputs.username(),attempt_id=f'control-{ordinal:03d}-{mode}',paid_attempt_id=None))
            write(folder,'native-row.private.json',row);audit_episode(folder,row,provider_close_required=False)
            require(row['score']==expected,'native_reference_trio_score_failed')
            trio[mode]={'score':row['score'],'episode_root':str(folder.resolve()),'native_row_sha256':sha256((folder/'native-row.private.json').read_bytes()).hexdigest()}
        results.append({**identity,'trio':trio})
    summary={'schema':'magento-native-surface-control-set-v1','source_binding_sha256':inputs.binding['binding_sha256'],
        'split':split,'task_count':len(results),'tasks':results,'model_calls':0,'formal_registration_performed':False,
        'old_development_control_credit':0}
    write(output,'controls.private.json',summary);return summary


def admit_train(*,inputs_path,controls_path,controls_sha256,visual_review_path,visual_review_sha256,output):
    values=private_json(inputs_path);inputs=Inputs(**values,control_preparation_only=True)
    output=Path(output);require(not output.exists() and not output.is_symlink(),'fresh_train_admission_namespace_required');output.mkdir(mode=0o700,parents=True)
    lane={**inputs.lane,'native_train_positive_negative_reset_reviewed':True,
        'native_train_controls_ref':{'path':str(Path(controls_path).resolve()),'sha256':controls_sha256},
        'root_source_visual_review_ref':{'path':str(Path(visual_review_path).resolve()),'sha256':visual_review_sha256}}
    write(output,'lane.private.json',lane)
    values={**values,'lane_path':str((output/'lane.private.json').resolve()),'lane_sha256':sha256((output/'lane.private.json').read_bytes()).hexdigest()}
    admitted=Inputs(**values);write(output,'inputs.private.json',values)
    return {'status':'current_train_trio_and_root_visual_review_reopened','inputs':str(output/'inputs.private.json'),
        'source_binding_sha256':admitted.binding['binding_sha256']}

def main():
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='command',required=True)
    prep=sub.add_parser('prepare')
    for name in ('plan-path','plan-sha256','lane-path','lane-sha256','output','final-output-root'):prep.add_argument('--'+name,required=True)
    admit=sub.add_parser('admit-train')
    for name in ('inputs-path','controls-path','controls-sha256','visual-review-path','visual-review-sha256','output'):admit.add_argument('--'+name,required=True)
    run=sub.add_parser('controls');run.add_argument('--inputs',required=True);run.add_argument('--split',choices=('train','selection','official_candidate'),required=True)
    run.add_argument('--train-index',type=int);run.add_argument('--output',required=True);run.add_argument('--enable-live',action='store_true')
    args=vars(parser.parse_args());command=args.pop('command')
    if command=='prepare':result=prepare(**args)
    elif command=='admit-train':result=admit_train(**args)
    else:
        values=private_json(args.pop('inputs'));inputs=Inputs(**values,control_preparation_only=True)
        result=run_controls(inputs=inputs,**args)
    print(json.dumps({'status':'source_bound_controls_complete' if command=='controls' else 'metadata_only_not_qualified',
        'task_count':result.get('task_count'),'source_binding_sha256':result.get('source_binding_sha256')}))

if __name__=='__main__':
    from magento_catalog_factory.native_surface_facade_v1 import main as registered_main
    registered_main()
