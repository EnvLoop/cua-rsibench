"""Authentic append-only paid ledger without dollar ceilings under policy v2.

Amounts are estimates or reconciled evidence, never authorization caps. Unknown
charges stay null. Scope/time/compute controllers remain mandatory counterparts.
"""
from __future__ import annotations
from contextlib import contextmanager
from decimal import Decimal
import fcntl
import json
import os
from pathlib import Path

from . import full_study_budget_v1 as old
from . import full_study_policy_amendment_v2 as policy

SCHEMA='cua-full-study-authentic-uncapped-dollar-ledger-v2'


class StudyBudgetLedger:
    def __init__(self,path,plan,amendment):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        if self.path.is_symlink() or self.path.parent.is_symlink():raise ValueError('unsafe_ledger_path')
        self.lock_path=self.path.with_name('.'+self.path.name+'.lock')
        self.plan_sha256,_,original=old._plan_limits(plan)
        self.amendment_sha256=policy.validate(amendment,plan)
        self.global_cap=None
        self.limits={owner:{'all_in':None,'categories':{k:None for k in row['categories']}}
                     for owner,row in original.items()}
        for owner,row in self.limits.items():
            cell,slot=owner.split(':')
            if slot=='shared-base' and cell in ('powerpoint-web','excel-web'):
                row['categories'].pop('e2b',None);row['categories']['storage_application']=None
        with self._lock():
            if not self.path.exists():self._append({'schema':SCHEMA,'kind':'header',
                'plan_sha256':self.plan_sha256,'amendment_sha256':self.amendment_sha256,
                'global_ceiling_usd':None,'previous':None})
            self._load()

    @contextmanager
    def _lock(self):
        fd=os.open(self.lock_path,os.O_CREAT|os.O_RDWR,0o600)
        with os.fdopen(fd,'r+') as stream:
            fcntl.flock(stream,fcntl.LOCK_EX);yield

    def _append(self,value):
        value={**value,'hash':policy.sha(policy.canonical(value))}
        fd=os.open(self.path,os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
        with os.fdopen(fd,'wb') as stream:stream.write(policy.canonical(value));stream.flush();os.fsync(stream.fileno())

    def _load(self):
        if self.path.stat().st_mode&0o077:raise ValueError('private_ledger_required')
        rows=[json.loads(line) for line in self.path.read_bytes().splitlines()];state={};previous=None
        if not rows:raise ValueError('empty_ledger')
        for index,row in enumerate(rows):
            value={k:v for k,v in row.items() if k!='hash'}
            if row.get('previous')!=previous or row.get('hash')!=policy.sha(policy.canonical(value)):
                raise ValueError('ledger_hash_chain_broken')
            previous=row['hash']
            if index==0:
                if value!={'schema':SCHEMA,'kind':'header','plan_sha256':self.plan_sha256,
                    'amendment_sha256':self.amendment_sha256,'global_ceiling_usd':None,'previous':None}:
                    raise ValueError('frozen_policy_or_plan_changed')
                continue
            identifier=row['attempt_id'];kind=row['kind']
            if not old.ATTEMPT.fullmatch(identifier):raise ValueError('invalid_attempt_id')
            if kind=='reserve':
                owner=row['owner'];category=row['category'];quote=old._dollar(row['nominal_quote_usd'],'nominal quote')
                if identifier in state or owner not in self.limits or category not in self.limits[owner]['categories'] or quote<=0:
                    raise ValueError('invalid_or_duplicate_reservation')
                old._hash(row['work_sha256'],'work')
                if any(v['work_sha256']==row['work_sha256'] and v['status']!='cancelled' for v in state.values()):
                    raise ValueError('same_work_already_consumed')
                state[identifier]={'owner':owner,'category':category,'work_sha256':row['work_sha256'],
                    'reserved_usd':row['nominal_quote_usd'],'actual_usd':None,'status':'pending','evidence_sha256':None}
            elif kind=='dispatch_started':
                if identifier not in state or state[identifier]['status']!='pending':raise ValueError('dispatch_out_of_order')
                old._hash(row['request_sha256'],'exact request');state[identifier].update(status='dispatched',request_sha256=row['request_sha256'])
            elif kind=='uncertain':
                if identifier not in state or state[identifier]['status']!='dispatched' or row['failure_type'] not in {'provider','transport','environment','verifier'}:
                    raise ValueError('uncertain_out_of_order')
                state[identifier].update(status='uncertain',failure_type=row['failure_type'])
            elif kind=='settle':
                if identifier not in state or state[identifier]['status'] not in {'dispatched','uncertain'}:raise ValueError('settle_out_of_order')
                actual=old._dollar(row['actual_usd'],'actual observed usage');old._hash(row['evidence_sha256'],'trusted usage')
                state[identifier].update(status='settled',actual_usd=row['actual_usd'],evidence_sha256=row['evidence_sha256'],
                    exceeded_nominal_quote=actual>old._dollar(state[identifier]['reserved_usd'],'nominal quote'))
            elif kind=='cancel':
                if identifier not in state or state[identifier]['status'] not in {'pending','dispatched','uncertain'}:raise ValueError('cancel_out_of_order')
                old._hash(row['no_charge_sha256'],'no-charge evidence');state[identifier].update(status='cancelled',evidence_sha256=row['no_charge_sha256'])
            else:raise ValueError('unknown_ledger_event')
        return rows,state

    def _event(self,kind,identifier,**fields):
        rows,_=self._load();self._append({'schema':SCHEMA,'kind':kind,'attempt_id':identifier,
                                        **fields,'previous':rows[-1]['hash']})
        return dict(self._load()[1][identifier])

    def reserve(self,attempt_id,owner,category,amount_usd,work_sha256):
        with self._lock():
            _,state=self._load()
            if attempt_id in state:raise ValueError('attempt_consumed_no_resubmit')
            old._hash(work_sha256,'work');quote=old._dollar(amount_usd,'nominal quote')
            if not old.ATTEMPT.fullmatch(attempt_id) or owner not in self.limits or category not in self.limits[owner]['categories'] or quote<=0:
                raise ValueError('unknown_owner_category_or_invalid_quote')
            if any(v['work_sha256']==work_sha256 and v['status']!='cancelled' for v in state.values()):raise ValueError('same_work_already_consumed')
            return self._event('reserve',attempt_id,owner=owner,category=category,nominal_quote_usd=amount_usd,work_sha256=work_sha256)

    def mark_dispatched(self,attempt_id,request_sha256):
        with self._lock():
            old._hash(request_sha256,'exact request')
            if self._load()[1].get(attempt_id,{}).get('status')!='pending':raise ValueError('dispatch_out_of_order')
            return self._event('dispatch_started',attempt_id,request_sha256=request_sha256)

    def mark_uncertain(self,attempt_id,failure_type):
        with self._lock():
            state=self._load()[1].get(attempt_id,{})
            if state.get('status')=='uncertain' and state.get('failure_type')==failure_type:return dict(state)
            if state.get('status')!='dispatched' or failure_type not in {'provider','transport','environment','verifier'}:raise ValueError('uncertain_out_of_order')
            return self._event('uncertain',attempt_id,failure_type=failure_type)

    def settle(self,attempt_id,actual_usd,evidence_sha256):
        with self._lock():
            old._dollar(actual_usd,'actual observed usage');old._hash(evidence_sha256,'trusted usage')
            state=self._load()[1].get(attempt_id,{})
            if state.get('status')=='settled':
                if state['actual_usd']!=actual_usd or state['evidence_sha256']!=evidence_sha256:raise ValueError('settlement_changed')
                return dict(state)
            if state.get('status') not in {'dispatched','uncertain'}:raise ValueError('settle_out_of_order')
            return self._event('settle',attempt_id,actual_usd=actual_usd,evidence_sha256=evidence_sha256)

    def cancel_with_no_charge(self,attempt_id,no_charge_sha256):
        with self._lock():
            old._hash(no_charge_sha256,'no-charge evidence');state=self._load()[1].get(attempt_id,{})
            if state.get('status') not in {'pending','dispatched','uncertain'}:raise ValueError('cancel_out_of_order')
            return self._event('cancel',attempt_id,no_charge_sha256=no_charge_sha256)

    def snapshot(self):
        with self._lock():
            _,state=self._load();unresolved=[v for v in state.values() if v['status'] not in {'settled','cancelled'}]
            observed=sum((old._dollar(v['actual_usd'],'actual') for v in state.values() if v['status']=='settled'),Decimal(0))
            nominal=sum((old._dollar(v['reserved_usd'],'nominal') for v in unresolved),Decimal(0))
            return {'schema':'cua-full-study-authentic-budget-snapshot-v2','plan_sha256':self.plan_sha256,
                'amendment_sha256':self.amendment_sha256,'global_ceiling_usd':None,'paid_dispatch_frozen':False,
                'known_observed_usd':str(observed),'unresolved_nominal_quote_usd':str(nominal),
                'actual_total_usd':None if unresolved else str(observed),'billing_complete':not unresolved,
                **{status+'_attempts':sum(v['status']==status for v in state.values()) for status in ['pending','dispatched','uncertain','settled','cancelled']}}

    def owner_attempts(self,owner):
        with self._lock():
            if owner not in self.limits:raise ValueError('unknown_owner')
            return {k:dict(v) for k,v in self._load()[1].items() if v['owner']==owner}
