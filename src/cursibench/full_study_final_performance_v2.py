"""Actual final controller gates with amended money/clock semantics only.

Native worker evidence remains private, independently reopened, hash bound and
mandatory. Unknown usage cannot be settled, retried or projected as zero.
"""
from __future__ import annotations
import json
from pathlib import Path
from decimal import Decimal
from . import full_study_runtime_v2 as runtime
from . import full_study_final_dispatch_v1 as legacy
from . import full_study_policy_amendment_v2 as policy


def _usage(controller,value,command,attempt_dir):
    _,raw=legacy.private_reference(attempt_dir,value['usage'],'authentic_provider_usage')
    usage=json.loads(raw)
    if value['cost_usd'] is not None:
        cost=legacy.results.actual_usd(value['cost_usd'],'authentic final cost')
        expected={'schema','attempt_id','cost_basis','cost_usd','input_tokens','image_tokens','output_tokens','provider_billed_tokens','provider_invoice_sha256'}
        if set(usage)!=expected or usage['schema']!=legacy.USAGE_SCHEMA or usage['attempt_id']!=command['attempt_id'] or usage['cost_basis']!=value['cost_basis'] or usage['cost_usd']!=value['cost_usd'] or not all(type(usage[k]) is int and usage[k]>=0 for k in ('input_tokens','image_tokens','output_tokens')) or usage['image_tokens']>usage['input_tokens']:
            raise ValueError('authentic_known_usage_invalid')
        if value['cost_basis']=='provider_billed':
            if not legacy.evidence.is_hash(usage['provider_invoice_sha256']):raise ValueError('authentic_invoice_hash_required')
        else:raise ValueError('nominal_estimate_is_not_authentic_observed_cost')
        return cost,usage,raw
    fields={'schema','attempt_id','cost_basis','cost_usd','input_tokens','image_tokens','output_tokens',
            'provider_billed_tokens','provider_invoice_sha256','paid_calls'}
    if set(usage)!=fields or usage['schema']!='cua-full-study-authentic-unknown-usage-v2' or usage['attempt_id']!=command['attempt_id'] or usage['cost_basis']!='authentic_usage_unknown' or value['cost_basis']!='authentic_usage_unknown' or any(usage[k] is not None for k in ('cost_usd','provider_billed_tokens','provider_invoice_sha256')):
        raise ValueError('unknown_usage_or_invoice_must_stay_null')
    if any(v is not None and (type(v) is not int or v<0) for v in (usage['input_tokens'],usage['image_tokens'],usage['output_tokens'])):
        raise ValueError('unknown_token_counts_must_stay_null')
    seen=set();paid_ids=set();unknown=[];completed=0;completion_unknown=0;known_late=0;not_submitted=0
    for call in usage['paid_calls']:
        if type(call) is not dict or set(call) not in ({'attempt_id','kind','intent','result'},{'request_id','paid_attempt_id','kind','intent','result'}) or call['kind'] not in {'sample','setup','environment'}:
            raise ValueError('authentic_paid_set_invalid')
        identifier=call.get('request_id',call.get('attempt_id'));paid_id=call.get('paid_attempt_id',call.get('attempt_id'))
        if type(identifier) is not str or not identifier or identifier in seen or type(paid_id) is not str or not paid_id:
            raise ValueError('authentic_consumed_request_id_invalid')
        seen.add(identifier);paid_ids.add(paid_id)
        _,intent_raw=legacy.private_reference(attempt_dir,call['intent'],'consumed_paid_intent')
        intent=json.loads(intent_raw)
        if 'request_id' in call:
            if intent.get('request_id')!=identifier or intent.get('paid_attempt_id')!=paid_id or intent.get('same_request_replay_authorized') is not False:raise ValueError('actual_parent_paid_request_binding_changed')
        elif intent.get('attempt_id')!=identifier or intent.get('same_intent_replay_authorized') is not False:raise ValueError('consumed_paid_intent_changed')
        if call['result'] is None:
            if call['kind']!='sample':raise ValueError('environment_or_setup_incomplete')
            unknown.append(paid_id)
        else:
            _,result_raw=legacy.private_reference(attempt_dir,call['result'],'retained_paid_result')
            result=json.loads(result_raw)
            if call['kind']=='sample':
                if result.get('status')!='completed':raise ValueError('earlier_provider_fault_is_infrastructure_invalid')
                completed+=1
    if not seen:raise ValueError('authentic_paid_intents_required')
    if unknown:
        if len(unknown)!=1 or value['budget_performance'] is None:raise ValueError('only_proved_terminal_budget_uncertainty_allowed')
        _,proof_raw=legacy.private_reference(attempt_dir,value['budget_performance'],'checked_budget_performance')
        proof=json.loads(proof_raw)
        verified=runtime.verify_budget_artifacts(controller.gate.study,command['owner_slot'],proof['verification'])
        if proof['receipt']!=verified or verified['sample_paid_attempt_id']!=unknown[0] or verified['task_id']!=command['task_id'] or verified['package_sha256']!=command['package_sha256'] or verified['checkpoint_sha256']!=command['checkpoint_sha256'] or verified['performance']['score']!=value['score']:
            raise ValueError('final_budget_performance_not_independently_bound')
        if verified['inference']['completed_model_response_count']!=completed:raise ValueError('completed_response_count_changed')
        status=verified['inference'].get('status')
        completion_unknown=int(status=='completion_unknown_after_actor_deadline')
        known_late=int(status=='late_completed_withheld_from_gui')
        not_submitted=int(status=='not_submitted_before_actor_deadline')
        if completion_unknown+known_late+not_submitted!=1:raise ValueError('precise_deadline_inference_status_required')
    elif value['budget_performance'] is not None:
        raise ValueError('budget_unknown_response_must_not_be_invented')
    controller._last_inference={'completed_model_response_count':completed,'model_completion_unknown_count':completion_unknown,'retained_without_normalized_result_count':len(unknown),
        'known_late_withheld_response_count':known_late,'not_submitted_before_deadline_count':not_submitted,
        'paid_intent_count':len(paid_ids),'consumed_request_count':len(seen),'request_replayed':False,'actual_usd':None,'invoice_verified':False}
    return None,usage,raw


def _actor_clock(controller,value,command,attempt_dir):
    _,raw=legacy.private_reference(attempt_dir,value['actor_clock'],'actor_clock')
    clock=json.loads(raw)
    if clock.get('schema')!='cua-full-study-final-actor-clock-v2' or clock.get('attempt_id')!=command['attempt_id'] or clock.get('max_actions')!=90 or clock.get('actor_seconds_limit')!=720 or clock.get('lease_seconds_limit')!=1200 or clock.get('actor_wall_time_ms')!=value['wall_time_ms'] or clock.get('lifecycle_wall_time_ms')!=value['lifecycle_wall_time_ms'] or clock.get('native_actions_after_deadline')!=0 or clock.get('evaluation_outside_actor_clock') is not True or type(value['lifecycle_wall_time_ms']) is not int or value['lifecycle_wall_time_ms']<value['wall_time_ms']:
        raise ValueError('separate_actor_and_lifecycle_clock_required')


def _settle(controller,attempt_id,outcome,checked):
    if checked['cost'] is None:
        # The parent final paid intent is consumed, performance may complete,
        # billing remains separately unresolved. No settlement fabricated.
        if controller._last_inference['retained_without_normalized_result_count']:
            controller.gate.budget.mark_uncertain(attempt_id,'provider')
        controller.journal.append('authentic_usage_unknown_v2',{'attempt_id':attempt_id,
            'usage_sha256':checked['usage_sha256'],'performance_status':outcome['status'],
            'amendment_sha256':controller.gate.study.amendment_sha256,**controller._last_inference})
    else:controller.gate.budget.settle(attempt_id,outcome['cost_usd'],checked['usage_sha256'])


class FinalController:
    def __new__(cls,gate,**kwargs):
        if type(gate) is not runtime.FinalGate:raise ValueError('real_witnessed_v2_final_gate_required')
        module=runtime._checked_final_namespace()
        module.FinalGate=runtime.FinalGate
        module._usage_v2=_usage;module._actor_clock_v2=_actor_clock;module._settle_v2=_settle
        cls_actual=module.FinalController
        module.FinalJournal.rows=runtime._method(legacy.FinalJournal.rows,[(
            "'attempt_uncertain', 'task_result'}",
            "'attempt_uncertain', 'task_result', 'authentic_usage_unknown_v2'}")],globals_extra=module.__dict__)
        module.FinalJournal.append=runtime._method(legacy.FinalJournal.append,[(
            "'attempt_uncertain', 'task_result'}",
            "'attempt_uncertain', 'task_result', 'authentic_usage_unknown_v2'}")],globals_extra=module.__dict__)
        # Replace the old usage-shape block exactly; _usage already validates
        # known authentic schema or strict nullable usage and consumed calls.
        source=runtime.textwrap.dedent(runtime.inspect.getsource(legacy.FinalController._validate_outcome))
        source=source.replace("'provider_latency_ms', 'timeout_subtype', 'action_profile',", "'provider_latency_ms', 'timeout_subtype', 'action_profile', 'actor_clock', 'lifecycle_wall_time_ms', 'budget_performance',")
        source=source.replace("{'provider_billed', 'published_rate_nominal'}", "{'provider_billed', 'published_rate_nominal', 'authentic_usage_unknown'}")
        start=source.index("    cost = results.actual_usd(value['cost_usd'], 'final task cost')")
        end=source.index("    reset_path, reset_raw = private_reference",start)
        source=source[:start]+"    _actor_clock_v2(self,value,command,attempt_dir)\n    cost,usage,usage_raw=_usage_v2(self,value,command,attempt_dir)\n    usage_path=attempt_dir/value['usage']['path']\n"+source[end:]
        source=source.replace("and\n                (value['timeout_subtype'] == 'none' or value['score'] == 0)", "")
        source=source.replace("value['provider_latency_ms'] <= value['wall_time_ms']","value['provider_latency_ms'] <= value['lifecycle_wall_time_ms']")
        start=source.index('    require(cost <= results.actual_usd(');end=source.index('    metric = {',start)
        source=source[:start]+source[end:]
        ns=dict(module.__dict__);exec(compile(source,'checked-final-outcome-null-cost-v2','exec'),ns)
        checked_outcome=ns['_validate_outcome']
        def with_retained_clocks(self,*args,**kwargs):
            checked,paths=checked_outcome(self,*args,**kwargs)
            value=checked['value']
            checked['artifact_refs'].update(actor_clock=value['actor_clock'],budget_performance=value['budget_performance'])
            checked['metric']['lifecycle_wall_time_ms']=value['lifecycle_wall_time_ms']
            return checked,paths
        cls_actual._validate_outcome=with_retained_clocks
        cls_actual._attempt=runtime._method(legacy.FinalController._attempt,[(
            "        self.gate.budget.settle(attempt_id, outcome['cost_usd'],\n                                checked['usage_sha256'])",
            "        _settle_v2(self,attempt_id,outcome,checked)"),
            ("'cost_usd': str(checked['cost'])", "'cost_usd': None if checked['cost'] is None else str(checked['cost'])",2)],globals_extra=module.__dict__)
        cls_actual.run_task=runtime._method(legacy.FinalController.run_task,[(
            "                require(prior['status'] == 'invalid',",
            "                previous=self.gate.budget.owner_attempts(cell_id+':'+owner).get(prior['attempt_id'])\n                require(previous is not None and previous['status'] in ('settled','cancelled'),'unreconciled_invalid_attempt_no_retry')\n                require(prior['status'] == 'invalid',"),
            ("                return {'status': 'invalid_reconciled_retry_available',",
            "                if self.gate.budget.owner_attempts(cell_id+':'+owner)[attempt['attempt_id']]['status'] not in ('settled','cancelled'):\n                    return {'status':'invalid_usage_unknown_no_retry','attempt_id':attempt['attempt_id']}\n                return {'status': 'invalid_reconciled_retry_available',")],globals_extra=module.__dict__)
        cls_actual._verify_frozen_inputs=runtime._method(legacy.FinalController._verify_frozen_inputs,[(
            'self.gate.frozen.manifest_sha256 and','self.gate.frozen.protocol_manifest_sha256 and')])
        instance=cls_actual(gate,**kwargs);instance._last_inference={}
        # Materialization must audit v2 nullable usage rather than call the
        # historical results auditor that rejects unknown authentic costs.
        instance.materialize_execution=_materialize.__get__(instance,type(instance))
        return instance


def _materialize(self,cell_id,owner):
    with self._locked():
        tasks=self._task_order(cell_id,owner);events=self.journal.rows()[1:]
        rows={r['data']['task_id']:r['data'] for r in events if r['kind']=='task_result' and r['data']['cell_id']==cell_id and r['data']['owner_slot']==owner}
        if len(rows)!=100 or set(rows)!={r['task_id'] for r in tasks}:raise ValueError('all_100_independently_scored_tasks_required')
        result_rows=[rows[t['task_id']]['task'] for t in tasks];costs=[]
        for row in result_rows:
            for attempt in row['attempts']:
                out=self.output_dir/attempt['attempt_id'];path=out/'attempt-receipt.private.json'
                receipt,raw=legacy.private_json(path,self.gate.work_root,'retained_final_attempt')
                if policy.sha(raw)!=attempt['receipt_sha256']:raise ValueError('retained_final_attempt_changed')
                for name,ref in receipt['artifact_refs'].items():
                    if ref is not None:legacy.private_reference(out,ref,name)
                record=self.gate.budget.owner_attempts(cell_id+':'+owner)[attempt['attempt_id']]
                if receipt['cost_usd'] is None:
                    if record['actual_usd'] is not None or record['status'] not in {'dispatched','uncertain'}:raise ValueError('unknown_bill_was_fabricated')
                elif record['status']!='settled' or record['actual_usd']!=receipt['cost_usd']:raise ValueError('authentic_charge_not_reconciled')
                costs.append(receipt['cost_usd'])
        value={'schema':'cua-full-study-final-performance-execution-v2','cell_id':cell_id,'owner_slot':owner,
            'checkpoint_sha256':(self.cells[cell_id]['base'] if owner=='shared-base' else self.cells[cell_id]['researcher_plans'][owner])['bindings']['checkpoint'],
            'amendment_sha256':self.gate.study.amendment_sha256,'status':'complete','tasks':result_rows,
            'cost_usd':None if any(v is None for v in costs) else str(sum((Decimal(v) for v in costs),Decimal(0))),
            'invoice_complete':not any(v is None for v in costs),'dollar_ceiling_usd':None}
        owner_dir=self.output_dir/(cell_id+'-'+owner);owner_dir.mkdir(mode=0o700,exist_ok=True)
        path=owner_dir/'final-performance-execution-v2.private.json';raw=policy.canonical(value)
        if path.exists():
            if path.read_bytes()!=raw:raise ValueError('final_performance_materialization_changed')
        else:legacy.private_write_new(path,raw)
        return {'cell_id':cell_id,'owner_slot':owner,'final_execution':legacy.reference(self.gate.work_root,path)}
