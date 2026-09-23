"""Multi-task evidence aggregation with strict infrastructure/result separation."""
import collections
import json
import hashlib
from pathlib import Path
from .gui_contract import json_object


def summarize(path,expected_tasks):
    root=Path(path)/'harbor/checkpoint-browser'
    job_path=root/'result.json'
    if not job_path.exists():return {'status':'not_started','score':None,'tasks':[]}
    job=json.loads(job_path.read_text());rows=[]
    for result_path in sorted(root.glob('*/result.json')):
        raw=json.loads(result_path.read_text());error=raw.get('exception_info')
        reward=(raw.get('verifier_result') or {}).get('rewards',{}).get('reward')
        valid=not error and type(reward) in (int,float) and reward in (0,1)
        row={'task':raw['task_name'],'score':float(reward) if valid else None,
             'error_type':error.get('exception_type') if error else (None if valid else 'MissingVerifierResult')}
        evidence=result_path.parent/'verifier/evidence.json'
        if evidence.exists():row['verification']=json.loads(evidence.read_text())
        trace_path=result_path.parent/'agent/trace.json'
        if trace_path.exists():
            trace=json.loads(trace_path.read_text());actions=[];invalid=0;observations=[];unknown_controls=0
            for event in trace:
                try:
                    action=json_object(event['response'])['action'];actions.append(action['type'])
                    controls={str(c['id']) for c in event['observation']['controls']}
                    if action['type'] not in ('back','done') and str(action.get('control')) not in controls:unknown_controls+=1
                except (ValueError,KeyError,TypeError):actions.append('invalid_response')
                invalid+=bool(event.get('outcome',{}).get('error'))
                observations.append(hashlib.sha256(event['observation'].get('text','').encode()).hexdigest())
            row['diagnostics']={'actions':len(trace),'invalid_actions':invalid,'action_types':dict(collections.Counter(actions)),
                                'finished_with_done':bool(trace and trace[-1]['outcome'].get('done')),'unknown_control_references':unknown_controls,'unique_visible_states':len(set(observations)),'most_repeated_visible_state':max(collections.Counter(observations).values(),default=0)}
        rows.append(row)
    names=[r['task'] for r in rows]
    identity_ok=len(names)==len(set(names)) and set(names)==set(expected_tasks)
    complete=bool(job.get('finished_at')) and identity_ok and all(r['score'] is not None for r in rows)
    return {'status':'scored' if complete else ('infrastructure_error' if job.get('finished_at') else 'running'),
            'score':sum(r['score'] for r in rows)/len(rows) if complete else None,
            'expected_tasks':list(expected_tasks),'task_identity_matches':identity_ok,'tasks':rows}


def selection_feedback(summary):
    """No evaluation prompts, source IDs, answers, or private scoring code cross this boundary."""
    return {'status':summary['status'],'score':summary['score'],'by_task_family':[
        {'family':row['task'].split('-')[1], 'score':row['score'],'error_type':row['error_type'],
         'correct_targets':row.get('verification',{}).get('correct_target_tasks'),
         'required_targets':row.get('verification',{}).get('target_tasks'),
         'diagnostics':row.get('diagnostics')}
        for row in summary['tasks']]}
