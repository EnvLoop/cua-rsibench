"""Public reference CLI. Preparation/audit never construct a native environment."""
from pathlib import Path
import argparse,json,hashlib,sys
from .config import Config,fresh,canonical,digest
from .loader import source_binding
from .control import write

def review_contract(plan):
 if set(plan)!={'schema','config','source_binding','controls','observer','resource_policy','reference_sequence'} or plan['schema']!='public-odoo-reference-review-plan-v2':raise ValueError('public_plan_shape_invalid')
 Config(**plan['config']).validate()
 if plan['reference_sequence']!=['original_Save','one_guarded_current_active_form_tab_click','strict_readonly_observer','actor_end','independent_saved_SQL','full_owned_reset']:raise ValueError('public_v3_reference_sequence_changed')
 if plan['source_binding']!=source_binding() or plan['controls']!=['baseline0','positive1','wrong_object0'] or plan['observer']!={'timeout':30,'poll':.1,'stable':.25}:raise ValueError('public_plan_source_or_control_changed')
 if plan['resource_policy']!={'fresh_owned_namespace_only':True,'new_user_accounts':0,'models':0,'training':False,'automatic_retry':False,'existing_resources_cleanup':False}:raise ValueError('public_resource_policy_changed')
 return {'schema':'public-odoo-reference-exact-review-v2','approved':True,'plan_sha256':digest(plan),'source_binding_sha256':digest(plan['source_binding']),'config_sha256':digest(plan['config']),'native_bootstrap_and_one_trio_authorized':True,'same_action_retry_authorized':False,'formal_admissions':0}
def prepare(stage,workspace,port,context=''):
 stage=Path(stage).absolute()
 if stage.exists():raise ValueError('fresh preparation stage required')
 stage.mkdir(mode=0o700,parents=True);config=fresh(workspace,port,context).public()
 plan={'schema':'public-odoo-reference-review-plan-v2','config':config,'source_binding':source_binding(),'controls':['baseline0','positive1','wrong_object0'],'observer':{'timeout':30,'poll':.1,'stable':.25},'reference_sequence':['original_Save','one_guarded_current_active_form_tab_click','strict_readonly_observer','actor_end','independent_saved_SQL','full_owned_reset'],'resource_policy':{'fresh_owned_namespace_only':True,'new_user_accounts':0,'models':0,'training':False,'automatic_retry':False,'existing_resources_cleanup':False}}
 write(stage/'plan.json',plan);write(stage/'root-review-template.json',review_contract(plan));argv=[sys.executable,'-m','odoo_reference.cli','run','--plan',str(stage/'plan.json'),'--approval',str(stage/'root-approval.json'),'--approval-sha256','ROOT_REVIEWED_EXACT_APPROVAL_SHA256']
 write(stage/'argv.json',argv);return {'prepared':True,'plan_sha256':digest(plan),'source_binding_sha256':digest(plan['source_binding']),'project':config['project'],'native_calls':0,'models':0}
def run(plan_path,approval,expected_sha):
 def private_read(path):
  path=Path(path)
  if path.is_symlink() or not path.is_file() or path.stat().st_mode&0o077:raise ValueError('private_regular_plan_and_approval_required')
  return path.read_bytes()
 plan=json.loads(private_read(plan_path));contract=review_contract(plan);raw=private_read(approval)
 if hashlib.sha256(raw).hexdigest()!=expected_sha or json.loads(raw)!=contract:raise ValueError('exact_source_bound_root_approval_required')
 stage=Path(plan_path).parent;write(stage/'approval-consumed.json',{'approval_sha256':expected_sha,'plan_sha256':digest(plan),'automatic_retry':False})
 from .infra import bootstrap
 from .control import run_gui
 config=plan['config'];bootstrap(config)
 write(Path(config['workspace'])/'private/execution-plan.json',plan)
 out=Path(config['workspace'])/'private/control-trio';result=run_gui(config['workspace'],out,plan['source_binding'])
 from .audit import audit
 independent=audit(config['workspace'],out,plan['source_binding']);write(out/'independent-saved-audit.json',independent);return independent

def main(argv=None):
 parser=argparse.ArgumentParser(description='Public nontraining Odoo reference controls; no hidden tasks or model sampling')
 sub=parser.add_subparsers(dest='command',required=True)
 a=sub.add_parser('prepare');a.add_argument('--stage',required=True);a.add_argument('--workspace',required=True);a.add_argument('--port',type=int,required=True);a.add_argument('--docker-context',default='')
 a=sub.add_parser('run');a.add_argument('--plan',required=True);a.add_argument('--approval',required=True);a.add_argument('--approval-sha256',required=True)
 a=sub.add_parser('audit');a.add_argument('--workspace',required=True)
 args=parser.parse_args(argv)
 try:
  if args.command=='prepare':value=prepare(args.stage,args.workspace,args.port,args.docker_context)
  elif args.command=='run':value=run(args.plan,args.approval,args.approval_sha256)
  else:
   from .audit import audit
   workspace=Path(args.workspace);plan=json.loads((workspace/'private/execution-plan.json').read_bytes());value=audit(workspace,workspace/'private/control-trio',plan['source_binding'])
  print(json.dumps(value,sort_keys=True));return 0
 except BaseException as error:
  # Exceptions may contain private native/task context. Fixed public code/hash only.
  print(json.dumps({'status':'failed_preserve_no_retry','exception_class':type(error).__name__,'message_sha256':hashlib.sha256(str(error).encode()).hexdigest(),'models':0}),file=sys.stderr);return 1
if __name__=='__main__':raise SystemExit(main())
