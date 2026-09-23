"""Researcher-selected native GUI demonstrations with source-split enforcement."""
import argparse,json
from pathlib import Path
from .agentrouter import response_receipt
from .kanboard_cases import verify
from .kanboard_runner import CONTRACT
from .campaign_runtime import json_object
from .workbench_data import digest


def extract(teacher_result):
    r=json.loads(Path(teacher_result).read_text())
    if r.get('infrastructure_error'):raise ValueError('teacher has infrastructure error')
    if r['case']!='kanboard-public-51':raise ValueError('only source-disjoint train pack 51 may supply demonstrations')
    check=verify(r['baseline'],r['final'],r['mapping'],r['expected_targets'])
    if not check['success']:raise ValueError('teacher did not pass independent saved-state verification')
    from .kanboard_cases import public_issue_case
    case=public_issue_case(51);records=[];memory='';last=None
    for event in r['trace']:
        try:data=json_object(event['response'])
        except ValueError:
            last=event['outcome'];continue
        if not event['outcome'].get('error'):
            prompt=CONTRACT+'\n'+json.dumps({'task':case['instruction'],'observation':event['observation'],'memory':memory,'last_action':last})
            records.append({'source_split':'train','source_issue_pack':51,'source_trace_sha256':digest(r),
                            'source_verification':check,'record_id':event['step'],'messages':[{'role':'user','content':prompt},{'role':'assistant','content':event['response']}]})
        memory=str(data.get('memory',memory))[:6000];last=event['outcome']
    return records


def research(records,researcher,feedback,parent_recipe=None):
    # Researcher sees only train corpus plus aggregate evaluation feedback. It cannot
    # fabricate test records; the accepted output is a bounded index selection.
    inventory=[]
    for row in records:
        answer=json_object(row['messages'][-1]['content'])
        inventory.append({'record_id':row['record_id'],'action':answer.get('action'),'prompt_bytes':len(row['messages'][0]['content'].encode())})
    instruction='You are the data researcher in a fixed Tinker training / E2B Harbor computer-use evaluation chain. Choose 1..32 training demonstration IDs from the verified TRAIN inventory, with repeats allowed. Diagnose model failure using only aggregate feedback. Favor behavior-aligned coverage: discovering policy, preserving facts in memory, reasoning about targets, filling native forms, saving and stopping. You may change only data selection and mixture. You may optionally request augmentation=bijective_numeric_control_aliases to relabel observer-assigned control references consistently while preserving all source facts and actions. Otherwise use augmentation=none. Return JSON {"hypothesis":"...","record_ids":[integers],"augmentation":"none or bijective_numeric_control_aliases","expected_effect":"..."}. Do not invent record IDs or change the evaluator, model or training settings.'
    text,receipt=response_receipt(instruction+'\n'+json.dumps({'train_inventory':inventory,'representative_train_records':[records[0],next(r for r in records if json_object(r['messages'][-1]['content']).get('action',{}).get('type')=='select'),records[-1]],'aggregate_feedback':feedback,'parent_recipe':parent_recipe}),researcher,1800,180)
    recipe=json_object(text);ids=recipe.get('record_ids')
    allowed={r['record_id']:r for r in records}
    if not isinstance(ids,list) or not 1<=len(ids)<=32 or any(type(i) is not int or i not in allowed for i in ids):raise ValueError('researcher proposed invalid training IDs')
    augmentation=recipe.get('augmentation','none')
    if augmentation not in ('none','bijective_numeric_control_aliases'):raise ValueError('unknown augmentation')
    selected=[allowed[i] for i in ids]
    if augmentation=='bijective_numeric_control_aliases':selected=[alias_controls(r,2300+j) for j,r in enumerate(selected)]
    return recipe,selected,receipt



def alias_controls(record,seed):
    """Semantics-preserving augmentation: only observation IDs + selected action ID change.

    IDs are observer-assigned references, not application record IDs or source facts.
    The original trajectory remains real; this transformed observation is labeled synthetic.
    """
    import copy,random
    clone=copy.deepcopy(record);header,body=clone['messages'][0]['content'].split('\n',1)
    payload=json.loads(body);controls=payload['observation']['controls']
    ids=[str(c['id']) for c in controls]
    if len(ids)!=len(set(ids)):raise ValueError('duplicate visible control IDs')
    values=random.Random(seed).sample(range(1000,10000),len(ids));mapping=dict(zip(ids,map(str,values)))
    action=json_object(clone['messages'][-1]['content'])
    kind=action['action']['type'];id=str(action['action'].get('control',''))
    if kind not in ('done','back') and id not in mapping:raise ValueError('demonstration references unavailable control')
    for control in controls:control['id']=mapping[str(control['id'])]
    if id in mapping:action['action']['control']=mapping[id]
    clone['messages'][0]['content']=header+'\n'+json.dumps(payload)
    clone['messages'][-1]['content']=json.dumps(action)
    clone['augmentation']={'kind':'bijective_numeric_control_aliases','seed':seed,'source_record':record['record_id']}
    return clone


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--teacher',required=True);p.add_argument('--out',required=True);p.add_argument('--researcher',default='gpt-6-astra');a=p.parse_args()
    out=Path(a.out);out.mkdir(parents=True,exist_ok=False);records=extract(a.teacher)
    recipe,selected,receipt=research(records,a.researcher,{'prior_smoke_reward':0,'failure':'premature finish or action schema mismatch after a tiny 1-step SFT run; no capability improvement demonstrated'})
    (out/'recipe.json').write_text(json.dumps(recipe,indent=2));(out/'researcher-receipt.json').write_text(json.dumps(receipt,indent=2))
    (out/'train_messages.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in selected))
    (out/'manifest.json').write_text(json.dumps({'source_split':'train','source_pack':51,'teacher_records':len(records),'selected_records':len(selected),'dataset_hash':digest(selected),'researcher':a.researcher},indent=2))
    print(json.dumps({'researcher':a.researcher,'selected':len(selected),'hypothesis':recipe.get('hypothesis')}))
