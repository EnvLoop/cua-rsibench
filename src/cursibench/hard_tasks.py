"""Difficulty calibration cases with independently computed exact answers.

Task variants share templates: this is explicitly instance-disjoint evaluation,
not unseen-workflow generalization. All amounts use integer cents or whole units.
"""
import copy
import itertools
import math
import random
from .workbench_data import Case


def reconciliation(seed,split='calibration'):
    rng=random.Random(seed);records=[];source=[]
    for i in range(12):
        id=f'INV-{seed%1000:03}-{i:02}';gross=rng.randrange(400,1200);tax=100 if i%2 else 200
        records.append({'id':id,'vendor':'Northstar Services' if i%2 else 'North Star Services','currency':'USD' if i%3 else 'EUR','archived':i in (4,11),'payable_cents':'0','status':'Pending'})
        source += [
            {'kind':'invoice','id':id,'revision':1,'valid':'yes','value':gross+60,'state':'posted','unit':'net cents'},
            {'kind':'invoice','id':id,'revision':2,'valid':'yes','value':gross,'state':'posted','unit':'net cents'},
            {'kind':'invoice','id':id,'revision':3,'valid':'no' if i%3 else 'yes','value':gross+90,'state':'draft' if i%3 else 'posted','unit':'net cents'},
            {'kind':'credit','id':id,'revision':1,'valid':'yes','value':rng.randrange(20,90),'state':'settled','unit':'cents'},
            {'kind':'credit','id':id,'revision':2,'valid':'yes','value':rng.randrange(10,50),'state':'pending','unit':'cents'},
            {'kind':'tax','id':id,'revision':1,'valid':'yes','value':tax,'state':'current','unit':'basis points'},
            {'kind':'dispute','id':id,'revision':1,'valid':'yes','value':0,'state':'open' if i in (2,8) else 'closed','unit':'n/a'},
        ]
    policy='''Reconcile only non-archived USD invoices. Match by exact ID, not vendor name. Choose the highest revision invoice that is valid=yes AND state=posted (ignore drafts even if newer). Subtract only settled credits; do NOT subtract pending credits. Compute tax on the resulting net amount, using the tax row in basis points: payable_cents = round_half_up((invoice_net - settled_credits) * (10000 + tax_bps) / 10000). All numbers are integer cents; round half upward, never banker rounding. If any dispute is open, set status Hold and payable_cents 0 regardless of calculated amount. Otherwise status Ready. Keep archived and non-USD rows exactly unchanged. Save and confirm.'''
    expected=copy.deepcopy(records)
    for row in expected:
        if row['archived'] or row['currency']!='USD':continue
        data=[x for x in source if x['id']==row['id']]
        net=max((x for x in data if x['kind']=='invoice' and x['valid']=='yes' and x['state']=='posted'),key=lambda x:x['revision'])['value']
        credit=sum(x['value'] for x in data if x['kind']=='credit' and x['state']=='settled')
        bps=next(x['value'] for x in data if x['kind']=='tax')
        cents=((net-credit)*(10000+bps)+5000)//10000
        hold=any(x['kind']=='dispute' and x['state']=='open' for x in data)
        row.update(payable_cents='0' if hold else str(cents),status='Hold' if hold else 'Ready')
    rng.shuffle(source)
    return Case(f'reconcile-{seed}',split,'reconciliation', 'Close the payable queue according to Rules. Consult Source for all versions and adjustments. Do not alter unrelated rows.',records,source,policy,{'payable_cents':'text','status':['Pending','Ready','Hold']},expected,'reconciliation-v2')


def optimal_release(source,budget,capacity):
    """Enumerate every feasible subset; independent of the UI and agent policy."""
    best=None;chosen=None
    for bits in itertools.product((0,1),repeat=len(source)):
        ids={r['id'] for r,b in zip(source,bits) if b}
        if any(r['requires']!='none' and r['requires'] not in ids for r,b in zip(source,bits) if b):continue
        if any(r['blocked']=='yes' for r,b in zip(source,bits) if b):continue
        groups=[r['exclusive_group'] for r,b in zip(source,bits) if b and r['exclusive_group']!='none']
        if len(groups)!=len(set(groups)):continue
        cost=sum(r['cost'] for r,b in zip(source,bits) if b);hours=sum(r['hours'] for r,b in zip(source,bits) if b)
        if cost>budget or hours>capacity:continue
        value=sum(r['value'] for r,b in zip(source,bits) if b)
        # Lexicographically smallest sorted ID list wins final tie.
        key=(-value,cost,tuple(sorted(ids)))
        if best is None or key<best:best=key;chosen=ids
    return chosen


def allocation(seed,split='calibration',n=14):
    rng=random.Random(seed);source=[];records=[];ids=[f'PO-{seed%1000:03}-{i:02}' for i in range(n)]
    for i,id in enumerate(ids):
        source.append({'id':id,'cost':rng.randrange(8,36),'hours':rng.randrange(1,9),'value':rng.randrange(15,70),'requires':ids[i-2] if i in (3,7,11) else 'none','exclusive_group':'G1' if i in (2,8) else ('G2' if i in (5,10) else 'none'),'blocked':'yes' if i==6 else 'no'})
        records.append({'id':id,'supplier':'Vector Labs' if i%2 else 'Vector Laboratory','decision':'Pending'})
    budget=140;capacity=29;selected=optimal_release(source,budget,capacity)
    policy=f'''Select a set of purchase orders to maximize TOTAL value, subject to TOTAL cost <= {budget} and TOTAL hours <= {capacity}. An order may be Released only if its required order is also Released. At most one order in each exclusive_group may be Released. Blocked=yes orders may not be Released. All listed orders must end as Release or Hold. Among maximum-value feasible sets choose the one with smallest total cost; if still tied choose the lexicographically smallest sorted list of released IDs. Read every Source row. This is a global selection problem; choosing the largest individual values or ratios may be suboptimal. Save and confirm.'''
    expected=copy.deepcopy(records)
    for row in expected:row['decision']='Release' if row['id'] in selected else 'Hold'
    return Case(f'allocation-{seed}',split,'budget-allocation','Prepare the globally optimal purchase-order release set under Rules. All orders require a final decision.',records,source,policy,{'decision':['Pending','Release','Hold']},expected,'allocation-v2')


def assignment_solution(tickets,agents):
    """Exhaustive assignment oracle; minimize weighted completion penalty."""
    best=None;answer=None
    for choices in itertools.product(range(len(agents)),repeat=len(tickets)):
        load=[0]*len(agents);valid=True;penalty=0
        for t,a in zip(tickets,choices):
            agent=agents[a]
            if t['skill'] not in agent['skills'].split(','):valid=False;break
            load[a]+=t['hours']
            penalty+=t['weight']*(agent['delay']+t['hours'])
        if not valid or any(load[i]>a['capacity'] for i,a in enumerate(agents)):continue
        names=tuple(agents[x]['id'] for x in choices)
        key=(penalty,max(load),names)
        if best is None or key<best:best=key;answer=names
    if answer is None:raise ValueError('infeasible seed')
    return answer


def dispatch(seed,split='calibration'):
    rng=random.Random(seed)
    agents=[{'id':'Chen','skills':'DB,API','capacity':11,'delay':1},{'id':'Rivera','skills':'API,UI','capacity':10,'delay':2},{'id':'Singh','skills':'DB,UI','capacity':12,'delay':0}]
    tickets=[{'id':f'TKT-{seed%1000:03}-{i:02}','skill':['DB','API','UI'][i%3],'hours':rng.randrange(2,5),'weight':rng.randrange(1,6)} for i in range(8)]
    answer=assignment_solution(tickets,agents)
    records=[{'id':t['id'],'customer':'Aster' if i%2 else 'Aster Cloud','assignee':'Unassigned','status':'Open'} for i,t in enumerate(tickets)]
    source=[dict(kind='ticket',**t) for t in tickets]+[dict(kind='agent',**a) for a in agents]
    # Use equal columns on all source rows so the workbench displays all fields.
    keys=('kind','id','skill','hours','weight','skills','capacity','delay')
    source=[{k:r.get(k,'-') for k in keys} for r in source]
    policy='''Assign every ticket to exactly one eligible agent and set status Scheduled. Required ticket skill must be in agent skills. Sum of ticket hours assigned to each agent must not exceed that agent capacity. Minimize total penalty = sum over tickets of ticket.weight * (chosen_agent.delay + ticket.hours). If tied minimize the maximum total assigned hours of any agent. If still tied, take the lexicographically smallest tuple of assignee names in ascending ticket-ID order. All data are in Source; '-' means not applicable. Read all records before committing. Save and confirm.'''
    expected=copy.deepcopy(records)
    for row,owner in zip(expected,answer):row.update(assignee=owner,status='Scheduled')
    return Case(f'dispatch-{seed}',split,'capacity-dispatch','Produce the optimal feasible assignment of the entire ticket queue under Rules.',records,source,policy,{'assignee':['Unassigned','Chen','Rivera','Singh'],'status':['Open','Scheduled']},expected,'dispatch-v2')


def calibration_suite(seed=41):
    return [factory(seed) for factory in (reconciliation,allocation,dispatch)]
