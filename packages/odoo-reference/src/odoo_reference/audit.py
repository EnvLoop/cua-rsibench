"""Independent saved production and native evidence replay. No live I/O."""
from pathlib import Path
import json,hashlib,math
from .control import validate_result,CLEANUP_KEYS,write
from .config import canonical,digest
from .loader import activate,source_binding

def require(ok,code):
 if not ok:raise RuntimeError(code)
def audit(workspace,out,expected_binding=None):
 factory,_,verify,_,_=activate(workspace)
 from .observer_audit import ImmutableSavedReader,audit3
 from enterprise_fallback.odoo18.odoo_v066_native_surface_adapter_v14 import audit_guard
 out=Path(out);read=ImmutableSavedReader();baseline,_=read.value(factory.PRIVATE/'baseline_snapshot.json');frozen,_=read.value(factory.PRIVATE/'baseline-filestore-manifest.json');gold,_=read.value(factory.PRIVATE/'development_gold.json')
 source_proof=audit_public_sources(baseline,frozen,gold)
 result,_=read.value(out/'result.json');validate_result(result);scores=[];actions=0;diagnostics=[]
 def score(where,case_id='PUBLIC-TRAIN-001'):
  snap,_=read.value(where/'sql.json');files,_=read.value(where/'filestore.json');paths,_=read.value(where/'store-paths.json')
  value=verify.evaluate(case_id,gold[case_id],baseline,snap)
  differences=verify.protected_source_file_differences(baseline,frozen,files)+verify.protected_source_store_path_differences(baseline,paths)
  return int(value['reward']==1 and not differences)
 scores.append(score(out/'baseline'))
 cold_sql,_=read.value(out/'baseline-cold/cold-sql.json');cold_files,_=read.value(out/'baseline-cold/cold-filestore.json');require(cold_sql==baseline and cold_files==frozen,'saved_full_cold_initial_baseline_not_exact')
 checkpoint,_=read.value(out/'checkpoint-bindings.json')
 for name,expected in checkpoint.items():require(hashlib.sha256(read.raw(factory.PRIVATE/name)).hexdigest()==expected,'saved_checkpoint_bytes_changed')
 require(set(checkpoint)=={'baseline.pgcustom','baseline-filestore.tgz','baseline-filestore-manifest.json','baseline_snapshot.json','checkpoint_receipt.json','development_gold.json'},'checkpoint_binding_incomplete')
 ck,_=read.value(factory.PRIVATE/'checkpoint_receipt.json')
 require(ck['db_sha256']==checkpoint['baseline.pgcustom'] and ck['filestore_sha256']==checkpoint['baseline-filestore.tgz'] and ck['filestore_manifest_sha256']==checkpoint['baseline-filestore-manifest.json'],'checkpoint_receipt_binding_changed')
 for phase in ('positive','negative'):
  root=out/phase;before,_=read.value(root/'before-sql.json');require(before==baseline,'saved_phase_baseline_changed');restore,_=read.value(root/'before-restore.json')
  cold_sql,_=read.value(root/'cold/cold-sql.json');cold_files,_=read.value(root/'cold/cold-filestore.json');require(cold_sql==baseline and cold_files==frozen,'saved_full_cold_baseline_not_exact')
  require(restore['business_snapshot_equal'] is True and restore['physical_filestore_equal_before_web_restart'] is True,'saved_phase_reset_unproven')
  audit_actor_clock(read,root)
  trace,_=read.value(root/'gui-trace.json');require(0<len(trace)<=90,'saved_actor_action_count_invalid')
  def rich(ref):
   require(set(ref)=={'schema','path','sha256','size','kind'} and ref['schema']=='native-guard-artifact-ref-v1','saved_guard_ref_invalid')
   _,raw=read.ref({'path':ref['path'],'sha256':ref['sha256']},root);require(len(raw)==ref['size'],'saved_guard_ref_size_changed');return raw
  for step,row in enumerate(trace):
   require(row['step']==step and row['phase']==phase,'saved_trace_order_or_phase_changed')
   intent,_=read.value(root/f'actions/step-{step:03d}-intent.private.json');result_row,_=read.value(root/f'actions/step-{step:03d}-result.private.json')
   _,raw=read.ref(row['frame'],root);require(intent['frame_ref']==row['frame'] and intent['phase']==phase,'saved_frame_intent_changed')
   _,intent_raw=read.ref(result_row['intent_ref'],root);require(intent_raw==canonical(intent),'saved_dispatch_intent_changed')
   dispatch=result_row['dispatch'];require(dispatch['status']=='applied' and dispatch['public_contract_receipt']==row['contract'],'saved_applied_dispatch_changed')
   proof=audit_guard(row['contract']['native_surface_guard'],raw,rich,action=intent['normalized_action']);require(proof['dispatch_status']=='applied','saved_guard_dispatch_unproven');actions+=1
  saves=sorted(root.glob('reference-save-*-result.private.json'));require(len(saves)==1,'saved_original_Save_proof_missing_or_repeated')
  proof,_=read.value(saves[0]);intent,_=read.value(root/(saves[0].name.replace('-result.private.json','-intent.private.json')))
  require(proof['phase']==intent['phase']==phase and proof['skip_performed'] is False and proof['same_action_replay_performed'] is False and intent['same_action_replay_authorized'] is False,'saved_original_Save_semantics_changed')
  samples=proof['samples'];require(samples and all(x['native']['mode'] in ('dirty','saved') and x['native']['kind']=='form' for x in samples),'saved_current_indicator_missing')
  last=samples[-1];require(last['native']['mode']=='saved' and last['native']['invisible_class'] is True and last['native']['buttons_visible'] is False,'saved_positive_indicator_missing')
  tail=[]
  for x in reversed(samples):
   if x['native']['mode']!='saved':break
   tail.append(x)
  require(tail and tail[0]['monotonic']-tail[-1]['monotonic']>=.25 and proof['ended_monotonic']-proof['started_monotonic']<=30,'saved_Save_stability_missing')
  if proof['status']=='saved_native_indicator':
   require(proof['one_native_save_click'] is True and proof['save_action_start_step']==proof['save_action_end_step'],'saved_dirty_Save_not_one_click')
   step=proof['save_action_start_step'];action,_=read.value(root/f'actions/step-{step:03d}-intent.private.json');require(action['normalized_action']['type']=='click','saved_Save_action_not_guarded_click')
  else:require(proof['status']=='already_saved_native_indicator' and proof['gui_input_performed'] is False and proof['actor_action_count_before']==proof['actor_action_count_after'],'saved_already_saved_input_changed')
  audit_post_save_focus(read,root,phase,proof)
  diagnostics.append(audit3(root));scores.append(score(root/'after'))
  if phase=='negative':
   require(score(root/'after','PUBLIC-WRONG-002')==1,'saved_wrong_object_change_not_committed')
  if phase=='positive':
   ref,_=read.value(root/'source-frame-ref.json');require(any(row['frame']==ref for row in trace),'source_frame_not_actual_guarded_observation');read.ref(ref,root)
 restored,_=read.value(out/'restored/sql.json');files,_=read.value(out/'restored/filestore.json');paths,_=read.value(out/'restored/store-paths.json');post,_=read.value(out/'post-restore.json')
 cold_sql,_=read.value(out/'restored-cold/cold-sql.json');cold_files,_=read.value(out/'restored-cold/cold-filestore.json');require(cold_sql==baseline and cold_files==frozen,'saved_full_cold_final_reset_not_exact')
 before_services,_=read.value(out/'services-before.json');after_services,_=read.value(out/'services-after.json')
 require(set(before_services)=={'db','web'} and before_services==after_services,'saved_owned_services_not_restored')
 computed={'SQL_exact':restored==baseline,'protected_filestore_exact':verify.protected_source_file_differences(baseline,frozen,files)==[], 'protected_store_paths_exact':verify.protected_source_store_path_differences(baseline,paths)==[], 'physical_before_web_restart_exact':post['physical_filestore_equal_before_web_restart'] is True,'business_before_web_restart_exact':post['business_snapshot_equal'] is True,'services_restored':before_services==after_services,'checkpoint_bytes_unchanged':True}
 require(computed==result['cleanup'] and scores==result['scores']==[0,1,0],'saved_scores_or_cleanup_not_independently_rederived')
 if expected_binding is not None:require(source_binding()==expected_binding,'saved_public_source_binding_changed')
 read.unchanged();manifest=[{'path':n,'sha256':h} for n,h in sorted(read.seen.items())]
 return {'schema':'public-odoo-reference-saved-audit-v1','scores':scores,'cleanup_verified':True,'wrong_object_change_independently_verified':True,'public_source_PDFs_independently_rederived':source_proof['public_source_PDFs'],'native_actions_reopened':actions,'diagnostic_pairs_reopened':sum(x['retained_native_pair_count'] for x in diagnostics),'selector_prefix_checks':sum(x['additive_selector_prefix_proof']['selector_prefix_checks'] for x in diagnostics),'evidence_manifest_sha256':digest(manifest),'models':0,'training':False,'qualification_granted':False,'formal_admissions':0}

def audit_actor_clock(read,root):
 """Reopen the actual start/end and each native IO, independently of claims."""
 start,_=read.value(root/'actor-clock/start.private.json');end,_=read.value(root/'actor-clock/end.private.json')
 def finite(v):return type(v) in (int,float) and math.isfinite(v)
 a=start['actor_started_monotonic'];d=start['actor_deadline_monotonic'];e=end['actor_ended_monotonic'];ack=end['raw_end_acknowledged_monotonic']
 require(all(finite(x) for x in (a,d,e,ack,end['actor_elapsed_seconds'],end['raw_elapsed_until_ack_seconds'])) and a<=e<=ack<=d==a+720,'saved_actor_times_invalid')
 require(start['actor_seconds_limit']==720 and end['actor_started_monotonic']==a and end['actor_deadline_monotonic']==d and end['actor_elapsed_seconds']==e-a and end['raw_elapsed_until_ack_seconds']==ack-a,'saved_actor_duration_not_rederived')
 require(end['task_id']==start['task_id'] and end['package_sha256']==start['package_sha256'] and end['model_outcome']=='public_reference_control_complete' and end['deadline_proof'] is None and type(end['native_actions_after_deadline']) is int and end['native_actions_after_deadline']==0 and end['evaluation_outside_actor_clock'] is True,'saved_actor_outcome_or_boundary_changed')
 events=end['native_io'];require(type(events) is list and events,'saved_actual_native_io_missing');last=a
 for event in events:
  require(set(event)=={'operation','started_monotonic','completed_monotonic','status','intent','completion'} and event['status']=='returned' and type(event['operation']) is str,'saved_native_io_not_returned')
  begin,finish=event['started_monotonic'],event['completed_monotonic'];require(finite(begin) and finite(finish) and last<=begin<=finish<=e,'saved_native_io_outside_actor_deadline');last=finish
  def rich(ref):
   require(set(ref)=={'schema','path','sha256','size','kind'} and ref['schema']=='native-guard-artifact-ref-v1','saved_actor_io_ref_invalid')
   _,raw=read.ref({'path':ref['path'],'sha256':ref['sha256']},root);require(len(raw)==ref['size'],'saved_actor_io_ref_size_changed');return json.loads(raw)
  intent=rich(event['intent']);completion=rich(event['completion'])
  require(intent['schema']==completion['schema']=='odoo-actor-native-io-v1' and intent['task_id']==completion['task_id']==start['task_id'] and intent['package_sha256']==completion['package_sha256']==start['package_sha256'] and intent['absolute_actor_deadline']==completion['absolute_actor_deadline']==d,'saved_native_io_actor_binding_changed')
  require(intent['status']=='intent_before_native_io' and intent['completed_monotonic'] is None and intent['operation']==completion['operation']==event['operation'] and intent['started_monotonic']==completion['started_monotonic']==begin and completion['completed_monotonic']==finish and completion['status']=='returned' and completion['intent']==event['intent'],'saved_native_io_event_not_reopened')
 read.unchanged();return {'native_io_count':len(events),'actor_elapsed_seconds':e-a,'all_native_io_returned_before_actor_end':True}

def audit_public_sources(baseline,frozen,gold):
 from .fixture import cases,document
 rows=baseline['attachments'];count=0
 for case in cases():
  matches=[row for row in rows if row['res_model']=='purchase.order' and row['res_id']==gold[case['id']]['order_id'] and row['name']==case['id']+'-source.pdf']
  require(len(matches)==1,'public_source_attachment_not_unique')
  row=matches[0];raw=document(case);checksum=hashlib.sha1(raw).hexdigest();path='filestore/bench/'+checksum[:2]+'/'+checksum
  require(row['checksum']==checksum and row['file_size']==len(raw) and row['store_fname']==checksum[:2]+'/'+checksum and frozen.get(path)==hashlib.sha256(raw).hexdigest(),'public_source_attachment_bytes_not_rederived');count+=1
 return {'public_source_PDFs':count,'public_source_bytes_rederived':True}

def audit_post_save_focus(read,root,phase,manual_save):
 from .focus import valid_tab,TAB_SELECTOR
 proof,_=read.value(root/'post-save-focus-proof.private.json');attempt,_=read.value(root/'post-save-focus-attempt.private.json');step=proof['action_step']
 require(proof['schema']=='public-v3-post-Save-owned-focus-proof-v1' and proof['phase']==attempt['phase']==phase and attempt['selector']==TAB_SELECTOR and attempt['selected_handle_count']==1 and proof['actor_action_count_before']==step and proof['actor_action_count_after']==step+1 and proof['no_extra_Save_or_retry'] is True and proof['strict_observer_follows'] is True,'saved_public_v3_focus_sequence_changed')
 require(proof['original_Save_proof_sha256']==attempt['original_Save_proof_sha256']==digest(manual_save) and manual_save['ended_monotonic']<=proof['started_monotonic']<=proof['ended_monotonic'],'saved_public_v3_original_Save_binding_changed')
 before,after=proof['before_selection'],proof['after_selection'];pre_meta=proof['after_selection_before_native_metadata'];require(valid_tab(pre_meta) and pre_meta['focused_same_element'] is True and pre_meta['native_path']==before['native_path'], 'saved_public_v5_pre_metadata_same_DOM_control_missing');require(attempt['selected_native_facts']==[before] and attempt['capture_truncated'] is False and valid_tab(before) and valid_tab(after) and before['native_path']==after['native_path'] and after['focused_same_element'] is True,'saved_public_v3_same_active_tab_focus_unproven')
 action,_=read.value(root/f'actions/step-{step:03d}-intent.private.json');dispatch,_=read.value(root/f'actions/step-{step:03d}-result.private.json');_,bound_intent=read.ref(dispatch['intent_ref'],root);require(bound_intent==canonical(action) and dispatch['dispatch']['status']=='applied','saved_public_v3_focus_click_not_applied_or_intent_unbound');selected=action['selected_native_control'];require(action['phase']==phase and action['normalized_action']['type']=='click' and valid_tab(selected) and selected['native_path']==before['native_path'] and sha_URL(selected['document_url'])==proof['document_url_sha256'],'saved_public_v3_current_guarded_tab_control_unproven')
 obs,_=read.value(root/f'surface-guard/turn-{step:03d}/observation-native.private.json');require(any(t['ref']==selected['element_ref'] for t in obs['targets']),'saved_public_v3_tab_ref_not_in_native_observation')
 native=proof['native_after'];start,_=read.value(root/'actor-clock/start.private.json');boundary,_=read.value(root/'surface-guard/lease-boundary.private.json');envelope,_=read.value(root/f'surface-guard/turn-{step:03d}/observation-envelope.private.json')
 require(native['visible'] is True and native['top_window'] is True and native['app_shell'] is True and native['account_principal']==boundary['native_avatar_principal'] and native['native_window_sha256']==boundary['window_sha256'] and native['focus_owned_app'] is True and native['focus']['tag'] not in ('body','html') and native['focus']['ref']==after['element_ref'] and sha_URL(native['physical_url'])==sha_URL(before['document_url'])==sha_URL(after['document_url'])==proof['document_url_sha256'],'saved_public_v3_native_focus_or_surface_unproven')
 for held in (attempt['held_before'],proof['held_after_click'],proof['held_after_capture']):
  require(held['lock_sha256']==boundary['lock_sha256'] and held['credentials_sha256']==boundary['credential_file_sha256'] and held['lease_descriptor_sha256']==digest(envelope['lease']) and held['actor_deadline_monotonic']==start['actor_deadline_monotonic'] and held['lease_deadline_monotonic']==envelope['lease']['expires_at'] and held['lease_events_appended']==0 and proof['started_monotonic']<=held['checked_monotonic']<=proof['ended_monotonic']<min(held['actor_deadline_monotonic'],held['lease_deadline_monotonic']),'saved_public_v3_held_binding_or_clocks_changed')
 require(proof['started_monotonic']<=native['native_capture_monotonic']<=proof['after_selection_read_started_monotonic']<=proof['after_selection_read_ended_monotonic']<=proof['ended_monotonic']<min(start['actor_deadline_monotonic'],envelope['lease']['expires_at']),'saved_public_v3_focus_outside_original_clocks')
 intents=list(root.glob('reference-priority-autosave-*-intent.private.json'));require(len(intents)==1,'saved_public_v3_observer_missing');intent,_=read.value(intents[0]);require(proof['ended_monotonic']<=intent['started_monotonic'] and intent['actor_action_count_before']==step+1,'saved_public_v3_focus_not_before_strict_observer')
 read.unchanged();return {'one_current_guarded_tab_click':True,'eligible_owned_focus_proven':True}
def sha_URL(value):return hashlib.sha256(value.encode()).hexdigest()
