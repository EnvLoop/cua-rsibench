"""Persistent selection registry for executable data-factory research.

The registry accepts only complete evaluations of its frozen task set. Final
selection becomes immutable before any final-test result may be recorded.
"""
import copy
import fcntl
import hashlib
import json
import os
import time
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()


def valid_scores(summary,tasks):
    if summary.get('status')!='scored':return None
    rows=summary.get('tasks',[])
    names=[r.get('task') for r in rows]
    if len(names)!=len(set(names)) or set(names)!=set(tasks):return None
    if any(type(r.get('score')) not in (int,float) or r['score'] not in (0,1) or r.get('error_type') for r in rows):return None
    scores={r['task']:float(r['score']) for r in rows}
    if summary.get('score')!=sum(scores.values())/len(scores):return None
    return scores


class CampaignRegistry:
    def __init__(self,path,protocol=None):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.lock_path=self.path.with_suffix('.lock')
        with self._lock():
            if not self.path.exists():
                if protocol is None:raise ValueError('new registry requires a frozen protocol')
                if not protocol.get('selection_tasks') or not protocol.get('final_tasks'):raise ValueError('task identities required')
                if set(protocol['selection_tasks']) & set(protocol['final_tasks']):raise ValueError('selection/final task identities overlap')
                self._save({'protocol':copy.deepcopy(protocol),'protocol_hash':digest(protocol),'created_at':time.time(),
                            'baseline':None,'attempts':[],'selected':'base','best_score':None,'used_training_tokens':0,'final_selection':None,'final_results':[]})
            state=self._read()
            if protocol is not None and digest(protocol)!=state['protocol_hash']:raise ValueError('protocol is immutable')

    def _lock(self):
        class Lock:
            def __enter__(lock):
                lock.file=self.lock_path.open('a');fcntl.flock(lock.file,fcntl.LOCK_EX)
            def __exit__(lock,*args):lock.file.close()
        return Lock()

    def _read(self):
        state=json.loads(self.path.read_text())
        if digest(state['protocol'])!=state['protocol_hash']:raise ValueError('protocol integrity failure')
        return state

    def _save(self,state):
        temp=self.path.with_suffix('.tmp');temp.write_text(json.dumps(state,indent=2));os.chmod(temp,0o600);temp.replace(self.path)

    def set_baseline(self,summary):
        with self._lock():
            state=self._read()
            if state['baseline'] is not None:raise ValueError('baseline already frozen')
            if valid_scores(summary,state['protocol']['selection_tasks']) is None:raise ValueError('complete matched baseline required')
            state['baseline']=copy.deepcopy(summary);state['best_score']=summary['score'];self._save(state)

    def register(self,attempt_id,dataset_hash,training_manifest,training_tokens,summary):
        with self._lock():
            state=self._read();protocol=state['protocol']
            if state['baseline'] is None or state['final_selection'] is not None:raise ValueError('search is not open')
            if any(r['attempt_id']==attempt_id for r in state['attempts']):raise ValueError('duplicate attempt id')
            if any(r['dataset_hash']==dataset_hash for r in state['attempts']):raise ValueError('reuse the cached candidate for an identical dataset')
            if len(state['attempts'])>=protocol['max_attempts']:raise ValueError('attempt budget exhausted')
            if type(training_tokens) is not int or training_tokens<=0 or state['used_training_tokens']+training_tokens>protocol['training_token_budget']:raise ValueError('training budget exceeded')
            scores=valid_scores(summary,protocol['selection_tasks']);incumbent=state['baseline'] if state['selected']=='base' else next(r['evaluation'] for r in state['attempts'] if r['attempt_id']==state['selected'])
            prior=valid_scores(incumbent,protocol['selection_tasks'])
            no_regression=scores is not None and all(scores[t]>=prior[t] for t in prior)
            improved=scores is not None and summary['score']>state['best_score']
            admitted=improved and (no_regression or protocol.get('promotion')=='strict_score')
            record={'attempt_id':attempt_id,'dataset_hash':dataset_hash,'training_manifest':str(training_manifest),'training_tokens':training_tokens,
                    'evaluation':copy.deepcopy(summary),'promoted':admitted,'no_regression':no_regression,'registered_at':time.time()}
            state['attempts'].append(record);state['used_training_tokens']+=training_tokens
            if admitted:state['selected']=attempt_id;state['best_score']=summary['score']
            self._save(state);return copy.deepcopy(record)

    def freeze_selection(self,reason):
        with self._lock():
            state=self._read()
            if state['final_selection'] is not None:return copy.deepcopy(state['final_selection'])
            if state['baseline'] is None or not state['attempts']:raise ValueError('baseline and attempted research required')
            chosen=None if state['selected']=='base' else next(x for x in state['attempts'] if x['attempt_id']==state['selected'])
            selection={'candidate':state['selected'],'training_manifest':chosen['training_manifest'] if chosen else None,
                       'selection_score':state['best_score'],'frozen_at':time.time(),'reason':reason,'protocol_hash':state['protocol_hash']}
            state['final_selection']=selection;self._save(state);return copy.deepcopy(selection)

    def record_final(self,label,summary,started_at):
        with self._lock():
            state=self._read();selection=state['final_selection']
            if selection is None:raise ValueError('freeze selection before final evaluation')
            if started_at<selection['frozen_at']:raise ValueError('final evaluation started before selection was frozen')
            if any(x['label']==label for x in state['final_results']):raise ValueError('duplicate final execution')
            # Invalid executions are retained, never converted to score zero.
            scores=valid_scores(summary,state['protocol']['final_tasks'])
            state['final_results'].append({'label':label,'started_at':started_at,'evaluation':copy.deepcopy(summary),'valid':scores is not None})
            self._save(state)

    def snapshot(self):
        with self._lock():return copy.deepcopy(self._read())
