"""First-valid final recovery for proven pre-agent build failures only."""
import copy
from .factory_campaign import valid_scores


def replace_build_failures(original, retries, expected_tasks):
    rows=copy.deepcopy(original['tasks']);names=[r['task'] for r in rows]
    if len(names)!=len(set(names)) or set(names)!=set(expected_tasks):raise ValueError('original final task identities mismatch')
    eligible={r['task'] for r in rows if r.get('error_type')=='BuildException' and r.get('score') is None}
    retry_names=[r['task'] for r in retries]
    if len(retry_names)!=len(set(retry_names)) or set(retry_names)!=eligible:raise ValueError('retry set must exactly cover pre-agent build failures')
    updates={r['task']:r for r in retries}
    rows=[copy.deepcopy(updates.get(r['task'],r)) for r in rows]
    valid=all(type(r.get('score')) in (int,float) and r['score'] in (0,1) and not r.get('error_type') for r in rows)
    result={'status':'scored' if valid else 'infrastructure_error','score':sum(r['score'] for r in rows)/len(rows) if valid else None,
        'expected_tasks':list(expected_tasks),'task_identity_matches':True,'tasks':rows}
    if valid and valid_scores(result,expected_tasks) is None:raise ValueError('invalid recovered score')
    return result
