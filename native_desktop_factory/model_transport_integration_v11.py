"""Additive worker/profile ratifier and four-researcher runtime binding.

The proposal command is source-only. Admissions require all 120 completed new
control trios before any gold is opened. Constructing the real six-cell study
then verifies its 600 official admissions and public pre-campaign witness.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime,timezone
import json
from pathlib import Path
from unittest.mock import patch

from cursibench import full_study_campaign_dispatch_v1 as campaign
from cursibench import full_study_matrix_v1 as matrix
from cursibench import shared_action_bundle_v066 as common
from cursibench.scale_vision_proxy import digest as vision_digest
from . import selection_control_bounded_epoch_v17 as controls
from . import selection_control_bounded_worker_v17 as control_worker
from . import v066_post_enter_control_audit_v9 as control_audit
from . import v066_final_freeze as action_freeze
from . import uniform_model_transport_v11 as transport
from .factory import digest
from .official_scorer_freeze import scorer_bundle

ROOT=Path(__file__).resolve().parents[1]
SCHEMA='cua-native-desktop-uniform-model-transport-proposal-v11'
ADMISSIONS_SCHEMA='cua-native-desktop-prospective120-model-admissions-private-v11'
SOURCE_PATHS=tuple(dict.fromkeys((*controls.SOURCE_FILES,*common.SOURCE_PATHS,
 'native_desktop_factory/uniform_model_transport_v11.py',
 'native_desktop_factory/model_transport_integration_v11.py',
 'native_desktop_factory/prospective_model_worker_v11.py',
 'native_desktop_factory/shared_base_model_execution_v11.py',
 'native_desktop_factory/qwen_sampler_process_v11.py',
 'native_desktop_factory/train_weak_base_pilot_v11.py',
 'tests/test_native_desktop_uniform_model_transport_v11.py',
 'tests/test_native_desktop_sampler_process_pilot_v11.py')))


def canonical(value):return common.canonical(value)
def require(condition,code):
 if not condition:raise ValueError(code)


def proposal(root:Path=ROOT):
 sources={name:digest((root/name).read_bytes()) for name in SOURCE_PATHS}
 runtime=digest(canonical(sources))
 return {'schema':SCHEMA,'status':'source_only_no_campaign_authority',
  'source_sha256s':sources,'worker_runtime_sha256':runtime,
  'adapter_source_sha256':sources['native_desktop_factory/uniform_model_transport_v11.py'],
  'shared_action_bundle_sha256':common.build(root)['bundle_sha256'],
  'verifier_sha256':scorer_bundle()[0],'model':matrix.STUDENT,
  'renderer':transport.RENDERER,'image_processor':transport.PROCESSOR,
  'action_profile':'scale-action-profile-v0.6.6','max_actor_actions':90,
  'max_actor_wall_seconds':720,'lease_seconds_each':1200,
  'selection_tasks':20,'final_tasks':100,'configuration_owners':['shared-base',*matrix.RESEARCHERS],
  'researcher_models':matrix.RESEARCHERS,'base_and_selected_transport_identical':True,
  'passive_focus_readiness':'v12-full-frame-before-observation',
  'calc_post_enter_transport':'v9-neutral-five-sample','sampler_runtime':'verified-clean-subprocess',
  'sampling_kinds':['base','checkpoint'],'checkpoint_changes_transport_policy':False,
  'bounded_guest_transport_recipe':transport.bounded_transport.RECIPE,
  'bounded_guest_transport_source_sha256':sources['native_desktop_factory/bounded_guest_transport_v17.py'],
  'base_checkpoint_sha256':vision_digest(matrix.STUDENT),
  'task_identity_gold_score_branch_in_transport':False,'evaluator_scripts_used_as_model':False,
  'required_new_control_trios':120,'required_six_cell_admissions':600,
  'dispatch_enabled':False,'model_calls':0,'official_model_results':0}


def validate_ratification(path:Path):
 """Same common grammar/six profiles; Desktop binds the actual new entrypoint."""
 raw=path.read_bytes();value=json.loads(raw);expected=action_freeze.source_hashes()
 require(set(value)=={'schema','status','ratified_utc','action_profile','common_source_sha256s','cell_profiles',
                     'base_and_selected_identical','hidden_final_model_attempts_before_ratification'} and
  value['schema']=='cua-six-cell-action-profile-v066-ratification-v1' and value['status']=='ratified_pre_result' and
  value['action_profile']=='scale-action-profile-v0.6.6' and value['common_source_sha256s']==expected and
  value['base_and_selected_identical'] is True and value['hidden_final_model_attempts_before_ratification']==0,
  'v11_common_ratification_changed')
 stamp=datetime.fromisoformat(value['ratified_utc'])
 require(stamp.tzinfo is not None and stamp.astimezone(timezone.utc)<=datetime.now(timezone.utc),'v11_ratification_time_invalid')
 profiles=value['cell_profiles'];require(set(profiles)==set(matrix.CELLS),'v11_six_profiles_required')
 for name,profile in profiles.items():
  require(set(profile)=={'common_source_sha256s','adapter_sha256'} and profile['common_source_sha256s']==expected and
          type(profile['adapter_sha256']) is str and len(profile['adapter_sha256'])==64 and
          all(c in '0123456789abcdef' for c in profile['adapter_sha256']),'v11_adapter_profile_invalid')
 require(profiles['desktop-native']['adapter_sha256']==digest(Path(transport.__file__).read_bytes()),'v11_actual_model_transport_not_ratified')
 return value,digest(raw)


@contextmanager
def runtime_context():
 """Explicit future harness entrypoint; immutable validators stay on disk."""
 from cursibench import full_study_shared_base_selection_v1 as shared
 from . import shared_base_model_execution_v11 as base_bridge
 from cursibench import full_study_qwen_runtime_gate_v1 as qwen_gate
 from .qwen_sampler_process_v11 import delegated_pre_dispatch
 with patch.object(action_freeze,'validate_ratification',validate_ratification),\
      patch.object(shared,'verify_receipt',base_bridge.verify_receipt),\
      patch.object(qwen_gate,'pre_dispatch',delegated_pre_dispatch):yield


def prepare_admissions(*,control_freeze:Path,proposal_path:Path,output:Path,enable_control_audit:bool=False):
 require(enable_control_audit is True,'v11_complete_control_audit_disabled')
 require(json.loads(proposal_path.read_bytes())==proposal(),'v11_worker_proposal_changed')
 value=controls.validate(control_freeze);root=Path(value['attempts_root'])
 # Fail on an incomplete/partial campaign before any additional oracle read.
 require(len(list(root.glob('*/trio-started.json')))==120 and
         len(list(root.glob('*/*/child-started.json')))==360 and
         len(list(root.glob('*/*/receipt.json')))==360,'v11_all120_terminal_trios_required')
 audits=[]
 with control_worker.context():
  for row in value['roster']:audits.append(control_audit.audit_trio(value=value,row=row))
  control_audit.audit_all(control_freeze)
 rows=[]
 for row,audit in zip(value['roster'],audits):
  rows.append({**row,'status':'qualified_by_new_native_gui_saved_trio',
               'control_trio_audit_sha256':digest(canonical(audit)),
               'control_receipt_sha256s':[r['receipt_sha256'] for r in audit['receipts']]})
 result={'schema':ADMISSIONS_SCHEMA,'status':'120_new_controls_admitted_pending_six_cell_freeze',
  'control_freeze_path':str(control_freeze.resolve()),'control_freeze_sha256':digest(control_freeze.read_bytes()),
  'proposal_sha256':digest(proposal_path.read_bytes()),'worker_runtime_sha256':proposal()['worker_runtime_sha256'],
  'source_snapshot_sha256':digest((Path(value['candidate_root'])/'candidate-inventory.json').read_bytes()),
  'roster':rows,'cohort_counts':{'selection':20,'final_candidate':100},'historical_controls_carried':0,
  'candidate_root':value['candidate_root'],'private_map':value['private_map'],'guest_public':value['guest_public'],
  'scoped_reference':value['scoped_reference'],'model_calls':0,'official_model_results':0}
 controls.accounting._write_new(output,result);return {'status':result['status'],'admissions_sha256':digest(output.read_bytes()),'model_calls':0}


def checked_admissions(path:Path,proposal_path:Path):
 value=json.loads(controls.private(path));p=proposal()
 require(json.loads(proposal_path.read_bytes())==p and value.get('schema')==ADMISSIONS_SCHEMA and
         value.get('status')=='120_new_controls_admitted_pending_six_cell_freeze' and
         value.get('proposal_sha256')==digest(proposal_path.read_bytes()) and
         value.get('worker_runtime_sha256')==p['worker_runtime_sha256'] and
         value.get('cohort_counts')=={'selection':20,'final_candidate':100} and
         value.get('historical_controls_carried')==value.get('model_calls')==value.get('official_model_results')==0,
         'v11_current120_admission_binding_missing')
 control=controls.validate(Path(value['control_freeze_path']))
 require(digest(Path(value['control_freeze_path']).read_bytes())==value['control_freeze_sha256'] and
         len(value['roster'])==120 and
         [{k:r[k] for k in control['roster'][0]} for r in value['roster']]==control['roster'] and
         all(r['status']=='qualified_by_new_native_gui_saved_trio' and len(r['control_receipt_sha256s'])==3 for r in value['roster']),
         'v11_admitted_roster_or_control_epoch_changed')
 root=Path(control['attempts_root'])
 for row in value['roster']:
  refs=[digest(controls.private(root/row['task_id']/phase/'receipt.json')) for phase in ['positive','near-miss','cold-reset']]
  require(refs==row['control_receipt_sha256s'],'v11_admitted_native_receipt_changed')
 return value


def bind_frozen_study(study,*,admissions_path:Path,proposal_path:Path):
 require(type(study) is campaign.FrozenStudy,'v11_real_six_cell_frozen_study_required')
 value=checked_admissions(admissions_path,proposal_path);p=proposal()
 ratification,sha=validate_ratification(study.ratification_path)
 require(ratification==study.ratification and sha==study.ratification_sha256 and
         study.plan['campaign_count']==24 and study.plan['distinct_official_task_identities']==600 and
         study.plan['cell_ids']==list(matrix.CELLS),'v11_six_cell_eligibility_changed')
 cell=next(r for r in study.plan['cells'] if r['cell_id']=='desktop-native')
 require(cell['matched_bindings']['runtime']==p['worker_runtime_sha256'] and
         cell['matched_bindings']['source_snapshot']==value['source_snapshot_sha256'] and
         cell['matched_bindings']['verifier']==p['verifier_sha256'] and
         cell['execution']['max_actions_per_task']==90 and cell['execution']['max_wall_seconds_per_task']==720 and
         float(cell['sampling']['temperature'])==0,'v11_model_runtime_or_policy_not_matched')
 # The same source-bound harness asset routes the base and all four owners.
 configs=study.plan['configuration_bindings'];harness_sha=digest(proposal_path.read_bytes())
 require(configs['student']['asset_sha256']['harness']==harness_sha and
         set(configs['researchers'])==set(matrix.RESEARCHERS) and
         all(configs['researchers'][name]['asset_sha256']['harness']==harness_sha for name in matrix.RESEARCHERS),
         'v11_all_four_configurations_must_bind_common_worker_harness')
 expected=[{k:r[k] for k in ['task_id','package_sha256']} for r in value['roster'] if r['split']=='selection']
 require([{k:r[k] for k in ['task_id','package_sha256']} for r in study.task_views('desktop-native')['selection']]==expected and
         cell['base_checkpoint_sha256']==p['base_checkpoint_sha256'],'v11_selection_view_or_base_checkpoint_not_current_cohort')
 study._desktop_v11_admissions_path=admissions_path;study._desktop_v11_proposal_path=proposal_path
 return value


def make_frozen_study(*,admissions_path:Path,proposal_path:Path,**kwargs):
 checked_admissions(admissions_path,proposal_path)
 with runtime_context():study=campaign.FrozenStudy(**kwargs)
 bind_frozen_study(study,admissions_path=admissions_path,proposal_path=proposal_path)
 return study


def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=['proposal','admissions'])
 parser.add_argument('--output',type=Path,required=True);parser.add_argument('--proposal',type=Path)
 parser.add_argument('--control-freeze',type=Path);parser.add_argument('--enable-control-audit',action='store_true');args=parser.parse_args()
 if args.mode=='proposal':
  controls.accounting._write_new(args.output,proposal(),public=True)
  result={'status':'source_only_no_campaign_authority','proposal_sha256':digest(args.output.read_bytes()),'dispatch_enabled':False}
 else:result=prepare_admissions(control_freeze=args.control_freeze,proposal_path=args.proposal,output=args.output,enable_control_audit=args.enable_control_audit)
 print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
