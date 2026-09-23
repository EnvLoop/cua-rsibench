"""Real Kanboard task scenarios. Raw task data visible in the app; answers host-only."""
import random
from .hard_tasks import optimal_release


def build_case(kind='triage',seed=51):
    rng=random.Random(seed);project=f'Northstar Operations {seed}'
    tasks=[];targets={}
    if kind=='basic':
        tasks=[{'reference':'OPS-101','title':'Restore webhook delivery','description':'Production webhook incident.'}]
        targets={'OPS-101':{'owner':'Chen','priority':3,'score':8}}
        instruction=f'In project {project}, assign OPS-101 to Chen, set priority 3 and complexity 8. Preserve all other data.'
        description='Active operations project.'
    elif kind=='triage':
        policy='Only non-archived incidents in APAC with customer tier Premium and age_hours >= 24 need escalation. Use the latest dated APPROVED revision in comments, not the original description, DRAFT notes, or older approved comments. Assign eligible incidents to Chen, priority 3, complexity 8. Do not change other incidents or the runbook. Do not modify the similarly named 2025 Archive project.'
        description='Source of truth: RUNBOOK task. Original descriptions may be stale.'
        tasks.append({'reference':'RUNBOOK','title':'Approved APAC escalation runbook','description':policy})
        for i in range(9):
            ref=f'OPS-{seed}{i:02}';region='APAC' if i%3!=0 else 'EMEA';tier='Premium' if i%2 else 'Standard';age=rng.randrange(12,46);archived=i==7
            if i in (1,5):region='APAC';tier='Premium';age=30+i;archived=False
            latest=f'2026-09-23 09:00 APPROVED revision 2. reference={ref}; region={region}; tier={tier}; age_hours={age}; archived={str(archived).lower()}.'
            tasks.append({'reference':ref,'title':['Northstar API retries','North Star API retry','Northstar queue pressure'][i%3]+f' / {i+1}',
                          'description':f'Original import for {ref}: region=APAC; tier=Premium; age_hours=48. This import may be stale. Consult comments.',
                          'comments':['2026-09-20 09:00 APPROVED revision 1. region=APAC; tier=Premium; age_hours=48; archived=false.',latest,
                                      '2026-09-24 09:00 DRAFT revision 3 (unapproved). region=APAC; tier=Premium; age_hours=72; archived=false.']})
            if not archived and region=='APAC' and tier=='Premium' and age>=24:targets[ref]={'owner':'Chen','priority':3,'score':8}
        instruction=f'Execute the approved escalation runbook in project {project}. Resolve current incident facts from approved comment revisions. Only update incidents that qualify; preserve all others.'
    elif kind=='allocation':
        source=[];ids=[f'REL-{seed}-{i:02}' for i in range(12)]
        for i,id in enumerate(ids):
            source.append({'id':id,'cost':rng.randrange(8,36),'hours':rng.randrange(1,9),'value':rng.randrange(15,70),'requires':ids[i-2] if i in (3,7,11) else 'none','exclusive_group':'G1' if i in (2,8) else ('G2' if i in (5,10) else 'none'),'blocked':'yes' if i==6 else 'no'})
        selected=optimal_release(source,120,25)
        policy='Select releases maximizing total value with total cost <= 120 and hours <= 25. Required releases must also be selected. At most one release per exclusive group; blocked releases cannot be selected. Tie-break: minimize cost, then lexicographically smallest sorted list of references. For selected releases only, assign Rivera, priority 3, complexity 5. Leave all other tasks untouched. Use APPROVED revision 2 in each description; original import values are obsolete.'
        tasks.append({'reference':'RUNBOOK','title':'Release investment committee mandate','description':policy})
        for i,row in enumerate(source):
            details='; '.join(f'{k}={v}' for k,v in row.items())
            tasks.append({'reference':row['id'],'title':f'Release candidate / Cluster {i//3} / {i}',
                          'description':'OLD IMPORT: cost=1, hours=1, value=100. Superseded.\n\nAPPROVED revision 2:\n'+details})
            if row['id'] in selected:targets[row['id']]={'owner':'Rivera','priority':3,'score':5}
        instruction=f'In project {project}, prepare the optimal release set using the RUNBOOK constraints and approved cost/value data. Update only selected releases as instructed. Preserve other tasks and the archive project.'
        description='Investment planning. Current approved data are on each task, not in old imports.'
    else:raise ValueError(kind)
    return {'id':f'kanboard-{kind}-{seed}','kind':kind,'project':project,'description':description,'tasks':tasks,'instruction':instruction,'targets':targets}


def verify(baseline,final,mapping,targets):
    import copy
    expected=copy.deepcopy(baseline)
    for ref,changes in targets.items():
        row=next(r for r in expected['tasks'] if r['id']==mapping['tasks'][ref])
        row.update(owner_id=mapping['users'][changes['owner']],priority=changes['priority'],score=changes['score'])
    # Ignore only application-maintained timestamps; preserve descriptions, references,
    # assignments, project membership, comments and all non-target task properties.
    def canonical(data):
        result=copy.deepcopy(data)
        for rows in result.values():
            for row in rows:
                for key in ('date_modification','date_moved','last_modified','last_login'):row.pop(key,None)
                for key in ('time_spent','time_estimated'):
                    if key in row and row[key] is None:row[key]=0
            rows.sort(key=lambda r:str(r.get('id',sorted(r.items()))))
        return result
    a=canonical(final);e=canonical(expected)
    wrong=[]
    for table in e:
        if a.get(table)!=e[table]:wrong.append(table)
    target_ok=0
    for ref,changes in targets.items():
        actual=next((r for r in final.get('tasks',[]) if r['id']==mapping['tasks'][ref]),{})
        if all(actual.get(k)==v for k,v in {'owner_id':mapping['users'][changes['owner']],'priority':changes['priority'],'score':changes['score']}.items()):target_ok+=1
    return {'success':not wrong,'wrong_tables':wrong,'correct_target_tasks':target_ok,'target_tasks':len(targets)}


def public_issue_case(seed=51,snapshot_path='datasets/public/kanboard_issues.json'):
    """Use real metadata; selection policy and staff assignment are explicitly synthetic."""
    import json,hashlib
    from pathlib import Path
    data=json.loads(Path(snapshot_path).read_text());all_rows=data['records']
    offset=(seed-51)%max(1,len(all_rows)-12)
    rows=all_rows[offset:offset+12]
    open_rows=[r for r in rows if r['state']=='open']
    chosen=sorted(open_rows,key=lambda r:(r['updated_at'],r['number']))[:3]
    project=f'Kanboard Public Issue Review {seed}'
    policy='''Review the imported GitHub backlog using the immutable SOURCE SNAPSHOT in each issue description. Source state refers to GitHub and may differ from the local imported task status. Among source-state=open issues in this project, select the THREE with oldest source updated_at timestamps (ascending UTC; break ties by smaller issue number). Assign only these three to Chen, priority 3, complexity 8. Leave every other task, its description, comments and the RUNBOOK unchanged. Ignore the similarly named 2025 Archive project. This scheduling/assignment policy is synthetic; source issue metadata is real.'''
    tasks=[{'reference':'RUNBOOK','title':'Public backlog review policy','description':policy}]
    for row in rows:
        facts={k:row[k] for k in ('number','state','created_at','updated_at','closed_at','labels','comment_count','source_url')}
        tasks.append({'reference':f"GH-{row['number']}",'title':row['title'],
                      'description':'SOURCE SNAPSHOT (real public GitHub metadata)\n\n'+json.dumps(facts,indent=2)+'\n\nCollected at '+data['collected_at']+'\nNo original body or author identity is copied. Staff assignments and review policy are benchmark constructs.'})
    targets={f"GH-{r['number']}":{'owner':'Chen','priority':3,'score':8} for r in chosen}
    return {'id':f'kanboard-public-{seed}','kind':'public','project':project,'description':'Review queue imported from public kanboard/kanboard issues. Refer to RUNBOOK. Not affiliated with upstream maintainers.',
            'tasks':tasks,'instruction':f'Carry out the RUNBOOK review policy in project {project}. Select the three oldest-updated unresolved source issues, update only them, and preserve the historical archive.',
            'targets':targets,'provenance':{'snapshot_sha256':hashlib.sha256(Path(snapshot_path).read_bytes()).hexdigest(),'source_repo':data['source_repo'],'collected_at':data['collected_at'],'real_fields':['title','number','state','timestamps','labels','comment_count','source_url'],'synthetic_fields':['staff','assignment policy','local project','historical distractor copies']}}


def public_allocation_case(seed=51,snapshot_path='datasets/public/kanboard_issues.json'):
    """Real issue metadata plus explicitly constructed resource planning estimates."""
    import json,random
    from pathlib import Path
    from .hard_tasks import optimal_release
    data=json.loads(Path(snapshot_path).read_text());rng=random.Random(seed)
    rows=data['records'][:12];source=[]
    open_ids=[f"GH-{r['number']}" for r in rows if r['state']=='open']
    for i,row in enumerate(rows):
        id=f"GH-{row['number']}"
        source.append({'id':id,'cost':rng.randrange(8,30),'hours':rng.randrange(2,9),
                       'value':10+min(row['comment_count'],12)*3+(8 if 'triage needed' in row['labels'] else 0),
                       'requires':open_ids[0] if id in open_ids[-2:] else 'none',
                       'exclusive_group':'review-A' if i in (1,5) else 'none','blocked':'yes' if row['state']=='closed' else 'no'})
    selected=optimal_release(source,70,17)
    project=f'Public Issue Capacity Planning {seed}'
    policy='''Plan a feasible maintenance batch from the imported public issues. Maximize total planning value, with total cost <= 70 and total engineer hours <= 17. Blocked=yes issues cannot be chosen. A required issue must also be chosen. At most one issue per exclusive_group other than none. Tie-break maximum-value sets by minimum cost, then lexicographically smallest sorted reference list. For selected issues ONLY assign Rivera, priority 3, complexity 5. Preserve all others, comments, descriptions and archive. Planning values, effort/cost estimates, dependencies and exclusivity groups are synthetic benchmark scheduling inputs; GitHub metadata are authentic. Read each issue's planning inputs and source status.'''
    tasks=[{'reference':'RUNBOOK','title':'Maintenance batch approval policy','description':policy}]
    for row,planning in zip(rows,source):
        tasks.append({'reference':planning['id'],'title':row['title'],'description':'REAL SOURCE METADATA:\n'+json.dumps(row,indent=2)+'\n\nCONSTRUCTED PLANNING INPUTS (not upstream estimates):\n'+json.dumps(planning,indent=2)})
    return {'id':f'kanboard-public-allocation-{seed}','kind':'public-allocation','project':project,'description':'Capacity-constrained maintenance planning on authentic public backlog metadata.',
            'tasks':tasks,'instruction':f'Execute the maintenance batch policy in RUNBOOK for project {project}. Select the optimal feasible set and modify only selected issues as instructed.',
            'targets':{ref:{'owner':'Rivera','priority':3,'score':5} for ref in selected},
            'provenance':{'source_repo':data['source_repo'],'snapshot_sha256':data['records_sha256'],'constructed_fields':['planning values','costs','hours','dependencies','groups','staff','policy']}}
