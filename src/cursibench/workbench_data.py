"""Synthetic enterprise-like data. Ground truth stays outside browser/controller messages."""
import copy
import hashlib
import json
import random
from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class Case:
    id: str
    split: str
    family: str
    instruction: str
    records: list
    source: list
    policy: str
    fields: dict
    expected: list
    template: str

    def visible(self):
        return {k:v for k,v in asdict(self).items() if k not in ('expected','split','template')}


def suite(seed=230923):
    rng=random.Random(seed);cases=[]
    for split_idx, split in enumerate(('train','acceptance','test')):
        for family in ('payables','inventory','support'):
            prefix=f'{split_idx+1}{rng.randrange(10,99)}'
            ids=[f'{family[:2].upper()}-{prefix}-{i:02}' for i in range(1,7)]
            if family=='payables':
                source=[];records=[]
                for i,id in enumerate(ids):
                    gross=rng.randrange(20,90)*100;credit=rng.randrange(1,6)*100
                    source.extend([{'id':id,'revision':1,'gross':gross+300,'credit':0,'currency':'USD','receipt':'yes'},
                                   {'id':id,'revision':2,'gross':gross,'credit':credit,'currency':'USD' if i%2==0 else 'CNY','receipt':'no' if i==3 else 'yes'}])
                    records.append({'id':id,'entity':'Orchid Labs' if i%2==0 else 'Orchid Laboratory','currency':'USD' if i%2==0 else 'CNY','archived':i==5,'payable':'0','status':'Pending'})
                policy='Use the highest numeric revision for each ID. Only act on non-archived USD rows. Payable = gross - credit. If latest receipt is no, status Hold; otherwise Ready. Leave all other fields and records unchanged.'
                if split=='acceptance': policy=policy.replace('USD rows','CNY rows')
                if split=='test': policy=policy.replace('gross - credit','gross - 2 * credit')
                fields={'payable':'text','status':['Pending','Ready','Hold']}
                expected=copy.deepcopy(records)
                for row in expected:
                    latest=max((x for x in source if x['id']==row['id']),key=lambda x:x['revision'])
                    if not row['archived'] and row['currency']==('CNY' if split=='acceptance' else 'USD'):
                        row.update(payable=str(latest['gross']-(2 if split=='test' else 1)*latest['credit']),status='Hold' if latest['receipt']=='no' else 'Ready')
            elif family=='inventory':
                records=[{'id':id,'sku':'Cable / USB-C' if i%2==0 else 'Cable / USB-A','warehouse':'East' if i%2==0 else 'West','archived':i==5,'reorder':'0','status':'Open'} for i,id in enumerate(ids)]
                source=[{'id':id,'on_hand':rng.randrange(2,12),'reserved':rng.randrange(0,5),'incoming':rng.randrange(0,5),'target':16} for id in ids]
                policy='For non-archived East warehouse rows, compute reorder = max(0, target - on_hand + reserved - incoming). Set status Ordered if reorder > 0 else Clear. Leave other rows unchanged.'
                if split=='acceptance':policy=policy.replace('East','West')
                if split=='test':policy=policy.replace(' - incoming','')
                fields={'reorder':'text','status':['Open','Ordered','Clear']};expected=copy.deepcopy(records)
                for row in expected:
                    data=next(x for x in source if x['id']==row['id'])
                    if not row['archived'] and row['warehouse']==('West' if split=='acceptance' else 'East'):
                        n=max(0,data['target']-data['on_hand']+data['reserved']-(0 if split=='test' else data['incoming']))
                        row.update(reorder=str(n),status='Ordered' if n>0 else 'Clear')
            else:
                records=[{'id':id,'customer':'Northstar' if i%2==0 else 'North Star','region':'APAC' if i%2==0 else 'EMEA','archived':i==5,'owner':'Unassigned','priority':'Normal'} for i,id in enumerate(ids)]
                source=[{'id':id,'tier':'Premium' if i%3==0 else 'Standard','age_hours':rng.randrange(5,40),'impact':'Outage' if i%2==0 else 'Question'} for i,id in enumerate(ids)]
                policy='For non-archived APAC rows: assign owner Chen. Priority Urgent when age_hours >= 24 or tier is Premium, otherwise Normal. Leave all other rows unchanged.'
                if split=='acceptance':policy=policy.replace('APAC','EMEA').replace('Chen','Rivera')
                if split=='test':policy=policy.replace(' or tier is Premium',' and tier is Premium')
                fields={'owner':'text','priority':['Normal','Urgent']};expected=copy.deepcopy(records)
                for row in expected:
                    d=next(x for x in source if x['id']==row['id'])
                    if not row['archived'] and row['region']==('EMEA' if split=='acceptance' else 'APAC'):
                        urgent=(d['age_hours']>=24 and d['tier']=='Premium') if split=='test' else (d['age_hours']>=24 or d['tier']=='Premium')
                        row.update(owner='Rivera' if split=='acceptance' else 'Chen',priority='Urgent' if urgent else 'Normal')
            rng.shuffle(records);rng.shuffle(source)
            # Preserve initial display ordering in expected state as part of integrity checks.
            expected=[next(x for x in expected if x['id']==r['id']) for r in records]
            cases.append(Case(f'{family}-{split}',split,family,'Follow the policy in the Rules tab, reconcile against the Source tab, then save the queue. Preserve unrelated rows.',records,source,policy,fields,expected,f'{family}-{split}-v1'))
    return cases


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def verify_case(case, final):
    if not isinstance(final,dict) or set(final)!={'records','source','policy'}:
        return {'success':False,'integrity':False,'reason':'invalid saved state'}
    integrity=final['source']==case.source and final['policy']==case.policy
    original={r['id']:r for r in case.records};expected={r['id']:r for r in case.expected}
    if not isinstance(final['records'],list):return {'success':False,'integrity':False,'reason':'invalid records'}
    try:actual={r['id']:r for r in final['records']}
    except (TypeError,KeyError):return {'success':False,'integrity':False,'reason':'malformed record'}
    identity=len(actual)==len(final['records'])==len(expected) and set(actual)==set(expected)
    untouched=identity and all(actual[id]==original[id] for id in expected if original[id]==expected[id])
    return {'success':bool(integrity and identity and final['records']==case.expected),
            'integrity':bool(integrity and identity and untouched),
            'correct_records':sum(actual.get(id)==row for id,row in expected.items()),'total_records':len(expected)}
