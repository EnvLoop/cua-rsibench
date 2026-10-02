"""Saved-only original oracle AND queue timing/lifecycle replay, no activation."""
from hashlib import sha256
from pathlib import Path
import base64,json
from cursibench import native_surface_guard_policy_v1 as policy
from . import native_queue_profile_v2 as profile,native_queue_runtime_v2 as runtime
from .native_surface_budget_performance_v1 import audit_episode as original_audit


def audit_episode(root,row,*,provider_close_required=True):
 root=Path(root)
 profile.require(row.get('native_queue_profile')==profile.PROFILE and type(row.get('original_sql_score')) is int,'Current native queue epoch required')
 old={**row,'score':row['original_sql_score']}
 result=original_audit(root,old,provider_close_required=provider_close_required)
 startup=runtime._read(root,'queue/startup.private.json');owner=profile.validate_owner(startup['native'],startup['scope_token'])
 close=runtime._read(root,'queue/close.private.json');profile.validate_exit({'exit_available':True,'exit':close['exit'],'supervisor_pid_absent':close['supervisor_pid_absent']},owner)
 for stream in ['stdout','stderr']:
  raw=(root/f'queue/consumer.{stream}.private.bin').read_bytes();profile.require(sha256(raw).hexdigest()==close['exit'][stream+'_sha256'],'Native consumer close stream changed')
 baseline=runtime._read(root,'queue/baseline.private.json');profile.validate_queue(baseline)
 reset=runtime._read(root,'queue/reset.private.json');profile.require(reset.get('full_channel_exact') is True and reset.get('fresh_app_b_before_original_cleanup') is True and reset['baseline']==reset['restored']==baseline,'Fresh native queue reset not exact')
 lifecycle=runtime._read(root,'queue/lifecycle.private.json');profile.require(lifecycle['seconds_limit']==1200 and 0<=lifecycle['ended_monotonic']-lifecycle['started_monotonic']<=1200 and lifecycle['original_clone_reset_completed'] is True and startup['observed_monotonic']>=lifecycle['started_monotonic'] and close['observed_monotonic']<=lifecycle['ended_monotonic'],'Actual native queue lifecycle budget/closure changed')
 verdict=runtime.queue_verdict(root);policy.verify_artifact(root,row['queue_clock_verdict'])
 profile.require(verdict==runtime._read(root,row['queue_clock_verdict']['path']) and row['score']==int(row['original_sql_score']==1 and verdict['score']==1),'Independent queue clock/final verdict changed')
 return result|{'independent_queue_clock':verdict,'score':row['score'],'native_queue_profile':profile.PROFILE}


def verifier_sha256():
 from .native_surface_workers_v1 import ROOT
 payload={name:sha256((ROOT/name).read_bytes()).hexdigest() for name in ['magento_catalog_factory/verify.py','magento_catalog_factory/native_queue_profile_v2.py','magento_catalog_factory/native_queue_runtime_v2.py','magento_catalog_factory/native_surface_budget_performance_v2.py']}
 return sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def verify_budget_performance(*,study,owner_slot,verification):
 from types import FunctionType
 from . import native_surface_budget_performance_v1 as prior
 reader=FunctionType(prior.verify_budget_performance.__code__,{**prior.verify_budget_performance.__globals__,'audit_episode':audit_episode},prior.verify_budget_performance.__name__)
 result=reader(study=study,owner_slot=owner_slot,verification=verification)
 root=Path(verification['episode_root'])
 result['evidence_sha256'].update({name:sha256((root/name).read_bytes()).hexdigest() for name in ['queue/startup.private.json','queue/probes.private.json','queue/verifier.private.json','queue/close.private.json','queue/reset.private.json','queue/lifecycle.private.json']})
 return result


def prepare_budget_performance(**kwargs):
 import inspect,textwrap
 from . import native_surface_budget_performance_v1 as prior
 source=textwrap.dedent(inspect.getsource(prior.prepare_budget_performance))
 old="'magento_catalog_factory.native_surface_budget_performance_v1'"
 profile.require(source.count(old)==1,'Frozen budget descriptor branch changed')
 namespace={**prior.prepare_budget_performance.__globals__,'audit_episode':audit_episode,'verify_budget_performance':verify_budget_performance,'__file__':__file__}
 exec(compile(source.replace(old,"'magento_catalog_factory.native_surface_budget_performance_v2'"),'magento-native-queue-budget-descriptor-v2','exec'),namespace)
 return namespace['prepare_budget_performance'](**kwargs)
