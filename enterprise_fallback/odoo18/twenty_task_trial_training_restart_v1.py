"""One explicitly authorized fresh attempt after failed Odoo20 SFT.

No prior forward/backward is replayed or prior weights relabelled. V2 data
validation and original 192-step/result formats remain intact. A separate
one-use authority claim protects the fresh model attempt; the old claim stays.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
from types import SimpleNamespace
from . import twenty_task_trial_training_v1 as base
from . import twenty_task_trial_training_v2 as data
from . import tinker_trial_recovery_v1 as recovery


def run(*, plan_path, plan_sha, manifest_path, manifest_sha, output_root,
        restart_authority_path, restart_authority_sha, prior_output_root,
        execute=False, trust_owned_rendered=False):
    base.require(execute is True, 'explicit_fresh_restart_dispatch_required')
    inputs = data.load_inputs(plan_path=plan_path,plan_sha=plan_sha,manifest_path=manifest_path,
                             manifest_sha=manifest_sha,trust_owned_rendered=trust_owned_rendered)
    decision = recovery.checked_restart_authority(restart_authority_path,restart_authority_sha,
                                                   inputs=inputs,prior_root=prior_output_root)
    out = Path(output_root)
    base.require(not out.is_symlink() and out.resolve() == Path(decision['new_output_root']) and
                 out.parent.resolve() == inputs.namespace and not out.exists(), 'reviewed_fresh_restart_output_required')
    base.require(bool(os.environ.get('TINKER_API_KEY')), 'tinker_key_required_before_dispatch')
    claim = inputs.namespace/('tinker-fresh-restart-authority-'+decision['restart_claim_identity']+'-consumed.private.json')
    base.require(not claim.exists(), 'fresh_restart_authority_already_consumed_no_replay')
    # Exclusive fsynced claim precedes every client, configuration read, model
    # creation or SDK request, even if later output creation/setup fails.
    base.write(claim, {'schema':'envloop-odoo20-fresh-restart-authority-consumed-v1',
        'dataset_identity':inputs.identity, 'restart_authority_sha256':restart_authority_sha,
        'restart_authority_ref':{'path':str(Path(restart_authority_path).resolve()),'sha256':restart_authority_sha},
        'prior_output_root':str(Path(prior_output_root).resolve()), 'output_root':str(out.resolve()),
        'automatic_replay_authorized':False, 'prior_unknown_request_replayed':False, 'actual_cost_usd':None})
    out.mkdir(mode=0o700)
    authority = base.private_json(restart_authority_path,restart_authority_sha,root=inputs.namespace)
    restart = {'restart_authority_sha256':restart_authority_sha,
        'restart_claim_identity':decision['restart_claim_identity'], 'prior_output_root':str(Path(prior_output_root).resolve()),
        'prior_training_request_sha256':decision['training_request_sha256'],
        'prior_consumed_claim_ref':authority['prior_consumed_claim_ref'],
        'prior_terminal_ref':authority['prior_terminal_ref'],
        'billing_access_receipt_ref':authority['billing_access_receipt_ref'],
        'execution_source_sha256s':authority['execution_source_sha256s'],
        'fresh_base_model_attempt':True, 'prior_model_state_carried':False,
        'prior_unknown_forward_backward_resubmitted':False, 'automatic_replay_authorized':False}
    base.write(out/'training-request.private.json', {'schema':'envloop-odoo20-tinker-training-request-v1',
        'dataset_identity':inputs.identity, 'trial_plan_sha256':plan_sha,'manifest_sha256':manifest_sha,
        'training_asset_sha256':inputs.training_sha,'model':base.MODEL,
        'teacher_model':inputs.plan['models']['teacher'],'datum_count':len(inputs.datums),
        'fixed_training_settings':inputs.training,'scheduled_tokens':inputs.scheduled_tokens,
        'actual_cost_usd':None,'formal_large_study_credit':0,'automatic_replay_authorized':False,
        'explicit_fresh_restart':restart,
        'training_restart_authority_ref':{'path':str(Path(restart_authority_path).resolve()),'sha256':restart_authority_sha}})
    scoped_base_train = recovery._clone(base.train_real, {
        'no_retry_service_class':lambda:recovery.recovery_ready_service_class(out)})
    scoped_base = SimpleNamespace(**{**vars(base),'train_real':scoped_base_train})
    scoped_lineage_train = recovery._clone(data.train_real, {'base':scoped_base})
    result = scoped_lineage_train(inputs,out)
    recovery.check_execution_sources(authority['execution_source_sha256s'])
    base.write(out/'restart-execution-source-check.private.json', {
        'schema':'envloop-odoo20-restart-execution-source-check-v1', 'checked_after_training':True,
        'execution_source_sha256s':authority['execution_source_sha256s'], 'source_bytes_unchanged':True})
    return {'status':'actual_pilot_training_checkpoint_saved','dataset_identity':inputs.identity,
        'checkpoint_path_sha256':base.digest(result['checkpoint_path'].encode()),
        'optimizer_steps_completed':result['optimizer_steps_completed'],'actual_cost_usd':None,
        'formal_large_study_credit':0,'explicit_fresh_restart_authority_sha256':restart_authority_sha}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for field in ('plan-path','plan-sha','manifest-path','manifest-sha','output-root',
                  'restart-authority-path','restart-authority-sha','prior-output-root'):
        parser.add_argument('--'+field,required=True)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--trust-owned-rendered',action='store_true')
    print(json.dumps(run(**vars(parser.parse_args())),sort_keys=True))


if __name__=='__main__':main()
