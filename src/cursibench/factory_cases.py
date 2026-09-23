"""Compile researcher-generated training states under a fixed application contract."""
import copy
import hashlib
import json
import re
from .hard_tasks import optimal_release

FACT_FIELDS=('number','state','created_at','updated_at','closed_at','labels','comment_count','source_url')
SCALAR_FIELDS={'number','state','created_at','updated_at','comment_count'}


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def object_keys(value,allowed,required=()):
    if not isinstance(value,dict):raise ValueError('object required')
    if set(value)-set(allowed):raise ValueError('unknown fields: '+', '.join(sorted(set(value)-set(allowed))))
    if set(required)-set(value):raise ValueError('missing required fields')


def integer(value,low,high):
    if type(value) is not int or not low<=value<=high:raise ValueError(f'integer in {low}..{high} required')
    return value


def code_block(value):
    # JSON strings escape newlines; escaped angle brackets cannot create active HTML.
    encoded=json.dumps(value,indent=2,ensure_ascii=True).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    return '```json\n'+encoded+'\n```'


class SourceRegistry:
    """Owned by the controller, never copied wholesale to a researcher workspace."""
    def __init__(self,snapshot,training_ids,protected_ids,partition="train"):
        if partition not in ("train","selection","final"):raise ValueError("unknown source partition")
        self.partition=partition
        self.snapshot=copy.deepcopy(snapshot)
        self.rows={r['number']:r for r in self.snapshot['records']}
        if len(self.rows)!=len(self.snapshot['records']):raise ValueError('duplicate source identity')
        self.allowed=frozenset(training_ids);self.protected=frozenset(protected_ids)
        if not self.allowed or self.allowed & self.protected:raise ValueError('source partitions overlap or are empty')
        if not (self.allowed|self.protected)<=self.rows.keys():raise ValueError('unknown registry source')
        self.source_hash=digest(self.snapshot)

    def resolve(self,numbers):
        if not isinstance(numbers,list) or not 1<=len(numbers)<=16:raise ValueError('1..16 training sources required')
        if any(type(n) is not int or n not in self.allowed for n in numbers):raise ValueError('only approved training sources are allowed')
        if len(set(numbers))!=len(numbers):raise ValueError('duplicate source identity')
        return [copy.deepcopy(self.rows[n]) for n in numbers]

    def training_input(self):
        if self.partition!="train":raise ValueError("evaluation source registry cannot be exported as training input")
        return {'source_repo':self.snapshot['source_repo'],'snapshot_sha256':self.source_hash,
                'records':self.resolve(sorted(self.allowed)) if len(self.allowed)<=16 else [copy.deepcopy(self.rows[n]) for n in sorted(self.allowed)],
                'source_split':'train','collected_at':self.snapshot['collected_at']}


def predicate(spec,depth=0):
    if not isinstance(spec,dict):raise ValueError('predicate object required')
    if depth>3:raise ValueError('predicate too deep')
    if set(spec)=={'all'} or set(spec)=={'any'}:
        key=next(iter(spec));children=spec[key]
        if not isinstance(children,list) or not 1<=len(children)<=4:raise ValueError('invalid predicate children')
        compiled=[predicate(c,depth+1) for c in children]
        function=all if key=='all' else any
        return lambda row:function(f(row) for f,_ in compiled),'('+(' AND ' if key=='all' else ' OR ').join(text for _,text in compiled)+')'
    object_keys(spec,{'field','op','value'},{'field','op','value'})
    field,op,value=spec['field'],spec['op'],spec['value']
    if field not in SCALAR_FIELDS|{'labels'}:raise ValueError('unapproved source field')
    if field in ('number','comment_count'):integer(value,0,10**9)
    elif not isinstance(value,str) or len(value)>120:raise ValueError('invalid predicate value')
    if op not in ('eq','neq','gte','lte','contains'):raise ValueError('unknown predicate operation')
    if field=='labels' and op!='contains':raise ValueError('labels support contains only')
    if field!='labels' and op=='contains':raise ValueError('contains supports labels only')
    def matches(row):
        left=row[field]
        if op=='eq':return left==value
        if op=='neq':return left!=value
        if op=='gte':return left>=value
        if op=='lte':return left<=value
        return value in left
    return matches,f'source {field} {op} {json.dumps(value)}'


def compile_case(spec,registry):
    common={'id','source_numbers','mode','changes','notes'}
    modes={'direct':{'select_numbers'},'rank':{'where','order_by','limit'},'allocation':{'planning','cost_limit','hour_limit'}}
    if not isinstance(spec,dict) or not isinstance(spec.get('mode'),str) or spec.get('mode') not in modes:raise ValueError('unknown task mode')
    object_keys(spec,common|modes[spec['mode']],{'id','source_numbers','mode','changes'})
    if not isinstance(spec['id'],str) or not re.fullmatch(r'[a-z][a-z0-9-]{2,47}',spec['id']):raise ValueError('invalid case id')
    changes=spec['changes'];object_keys(changes,{'owner','priority','score'},{'owner','priority','score'})
    if changes['owner'] not in ('Chen','Rivera','Singh'):raise ValueError('unknown assignee')
    integer(changes['priority'],1,3);integer(changes['score'],1,13)
    notes=spec.get('notes','')
    if not isinstance(notes,str) or len(notes)>2000:raise ValueError('notes too long')
    rows=registry.resolve(spec['source_numbers']);numbers={r['number'] for r in rows};planning={}
    if spec['mode']=='direct':
        selected=spec.get('select_numbers')
        if not isinstance(selected,list) or any(type(n) is not int or n not in numbers for n in selected):raise ValueError('invalid explicit selection')
        if len(selected)!=len(set(selected)):raise ValueError('duplicate selection')
        policy='Update exactly these source references: '+', '.join(f'GH-{n}' for n in selected)+'.'
    elif spec['mode']=='rank':
        match,description=predicate(spec.get('where',{}))
        ordering=spec.get('order_by')
        if not isinstance(ordering,list) or not 1<=len(ordering)<=3:raise ValueError('1..3 sort fields required')
        selected=sorted([r for r in rows if match(r)],key=lambda r:r['number'])
        names=[]
        for item in reversed(ordering):
            object_keys(item,{'field','direction'},{'field','direction'})
            if item['field'] not in SCALAR_FIELDS or item['direction'] not in ('asc','desc'):raise ValueError('invalid ordering')
            selected.sort(key=lambda r:r[item['field']],reverse=item['direction']=='desc')
        for item in ordering:names.append(f"source {item['field']} {item['direction']}")
        limit=integer(spec.get('limit'),1,4);selected=[r['number'] for r in selected[:limit]]
        policy=f'Select up to {limit} records satisfying {description}. Sort by '+', then '.join(names)+', then smaller source number. Source state may differ from local task status.'
    else:
        budget=integer(spec.get('cost_limit'),1,200);hours=integer(spec.get('hour_limit'),1,40)
        if not isinstance(spec.get('planning'),list) or len(spec['planning'])!=len(rows):raise ValueError('one planning entry per source required')
        entries=[]
        for row in spec['planning']:
            object_keys(row,{'number','cost','hours','value','requires','exclusive_group','blocked'},{'number','cost','hours','value'})
            number=row['number']
            if type(number) is not int or number not in numbers or number in planning:raise ValueError('invalid planning source')
            for field,low,high in [('cost',1,100),('hours',1,20),('value',0,200)]:integer(row[field],low,high)
            requirement=row.get('requires')
            if requirement is not None and (type(requirement) is not int or requirement not in numbers or requirement==number):raise ValueError('invalid dependency')
            group=row.get('exclusive_group','none')
            if not isinstance(group,str) or not re.fullmatch(r'[A-Za-z0-9-]{1,30}',group):raise ValueError('invalid exclusion group')
            if type(row.get('blocked',False)) is not bool:raise ValueError('blocked must be boolean')
            entry={'id':f'GH-{number}','cost':row['cost'],'hours':row['hours'],'value':row['value'],
                   'requires':f'GH-{requirement}' if requirement else 'none','exclusive_group':group,
                   'blocked':'yes' if row.get('blocked') else 'no'}
            planning[number]=entry;entries.append(entry)
        selected=[int(ref[3:]) for ref in optimal_release(entries,budget,hours)]
        policy=f'Maximize total planning value with total cost <= {budget} and hours <= {hours}. Dependencies must be included; at most one item per exclusion group other than none; blocked items are excluded. Break value ties by minimum cost, then the lexicographically smallest sorted reference list.'
    if not 1<=len(selected)<=4:raise ValueError('task must select between 1 and 4 records')
    policy+=f" For selected records only, assign {changes['owner']}, priority {changes['priority']}, complexity {changes['score']}. Preserve everything else, including descriptions, comments, the RUNBOOK and archive project. Workflow rules, staff and planning inputs are synthetic benchmark constructs; source issue facts are authentic."
    tasks=[{'reference':'RUNBOOK','title':'Generated workflow policy','description':code_block({'policy':policy,'synthetic_workflow_notes':notes})}]
    for row in rows:
        description='SOURCE SNAPSHOT (authentic public metadata)\n\n'+code_block({k:row[k] for k in FACT_FIELDS})
        if row['number'] in planning:description+='\n\nSYNTHETIC PLANNING INPUTS\n\n'+code_block(planning[row['number']])
        tasks.append({'reference':f"GH-{row['number']}",'title':row['title'],'description':description})
    project='Training workspace '+spec['id']
    case={'id':'factory-'+spec['id'],'kind':'factory-'+spec['mode'],'project':project,
          'description':'Training-only generated workflow. Read the RUNBOOK. Public issue facts with synthetic workflow rules.',
          'tasks':tasks,'instruction':f'Carry out the RUNBOOK in project {project}. Save and verify every required change, preserve unrelated records, and leave the archive untouched.',
          'targets':{f'GH-{n}':copy.deepcopy(changes) for n in selected},'source_numbers':list(spec['source_numbers']),
          'provenance':{'source_split':registry.partition,'snapshot_sha256':registry.source_hash,'recipe_sha256':digest(spec),
                        'source_repo':registry.snapshot['source_repo'],'synthetic_fields':['workflow policy','staff','planning inputs','archive distractors','project name','notes']}}
    return case


def semantic_case_key(case):
    return digest({key:case[key] for key in ('tasks','targets','source_numbers')})
