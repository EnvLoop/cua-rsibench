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
                            'baseline':None,'attempts':[],'reservations':{},'selected':'base','best_score':None,'used_training_tokens':0,'final_selection':None,'final_results':[]})
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
        state.setdefault('reservations',{})
        return state

    def _save(self,state):
        temp=self.path.with_suffix('.tmp');temp.write_text(json.dumps(state,indent=2));os.chmod(temp,0o600);temp.replace(self.path)

    def set_baseline(self,summary):
        with self._lock():
            state=self._read()
            if state['baseline'] is not None:raise ValueError('baseline already frozen')
            if valid_scores(summary,state['protocol']['selection_tasks']) is None:raise ValueError('complete matched baseline required')
            state['baseline']=copy.deepcopy(summary);state['best_score']=summary['score'];self._save(state)

    def reserve_training(self,attempt_id,dataset_hash,token_bound):
        with self._lock():
            state=self._read();protocol=state['protocol']
            if state['baseline'] is None or state['final_selection'] is not None:raise ValueError('search is not open')
            if type(token_bound) is not int or token_bound<=0:raise ValueError('positive token reservation required')
            if attempt_id in state['reservations']:
                old=state['reservations'][attempt_id]
                if old['dataset_hash']!=dataset_hash or old['token_bound']!=token_bound:raise ValueError('reservation id collision')
                return copy.deepcopy(old)
            if any(x['attempt_id']==attempt_id or x['dataset_hash']==dataset_hash for x in state['attempts']):raise ValueError('attempt or dataset already evaluated')
            if any(x['dataset_hash']==dataset_hash for x in state['reservations'].values()):raise ValueError('dataset already reserved')
            if len(state['attempts'])+len(state['reservations'])>=protocol['max_attempts']:raise ValueError('attempt budget exhausted')
            pending=sum(x['token_bound'] for x in state['reservations'].values())
            if state['used_training_tokens']+pending+token_bound>protocol['training_token_budget']:raise ValueError('training budget exhausted before execution')
            record={'dataset_hash':dataset_hash,'token_bound':token_bound,'reserved_at':time.time()}
            state['reservations'][attempt_id]=record;self._save(state);return copy.deepcopy(record)

    def record_training_failure(self,attempt_id,reason,known_tokens=None):
        with self._lock():
            state=self._read();reserved=state['reservations'].get(attempt_id)
            if reserved is None:raise ValueError('training failure has no reservation')
            # An interrupted execution retains its full reservation unless trusted
            # training accounting establishes a smaller amount.
            tokens=reserved['token_bound'] if known_tokens is None else known_tokens
            if type(tokens) is not int or not 0<=tokens<=reserved['token_bound']:raise ValueError('invalid failure accounting')
            state['attempts'].append({'attempt_id':attempt_id,'dataset_hash':reserved['dataset_hash'],
                'training_manifest':None,'training_tokens':tokens,'evaluation':{'status':'training_error','score':None,'tasks':[]},
                'promoted':False,'no_regression':False,'failure_reason':reason,'registered_at':time.time(),'accounting':'pre-execution reservation'})
            state['used_training_tokens']+=tokens;del state['reservations'][attempt_id];self._save(state)

    def record_submission_rejection(self,attempt_id,dataset_hash,report):
        """A completed research round with no training is visible, not a zero score."""
        with self._lock():
            state=self._read()
            if state['baseline'] is None or state['final_selection'] is not None:raise ValueError('search is not open')
            if attempt_id in state['reservations']:raise ValueError('resolve training reservation first')
            if any(x['attempt_id']==attempt_id for x in state['attempts']):raise ValueError('duplicate attempt id')
            if len(state['attempts'])+len(state['reservations'])>=state['protocol']['max_attempts']:raise ValueError('attempt budget exhausted')
            if report.get('accepted') is not False:raise ValueError('a failed preflight report is required')
            state['attempts'].append({'attempt_id':attempt_id,'dataset_hash':dataset_hash,
                'training_manifest':None,'training_tokens':0,
                'evaluation':{'status':'submission_rejected','score':None,'tasks':[]},
                'promoted':False,'no_regression':False,'submission_feedback':copy.deepcopy(report),
                'registered_at':time.time(),'accounting':'no training executed'})
            self._save(state)

    def register(self,attempt_id,dataset_hash,training_manifest,training_tokens,summary,historical_import=False,evaluation_path=None,operational_version=None):
        with self._lock():
            state=self._read();protocol=state['protocol']
            if state['baseline'] is None or state['final_selection'] is not None:raise ValueError('search is not open')
            if any(r['attempt_id']==attempt_id for r in state['attempts']):raise ValueError('duplicate attempt id')
            if any(r['dataset_hash']==dataset_hash for r in state['attempts']):raise ValueError('reuse the cached candidate for an identical dataset')
            if len(state['attempts'])>=protocol['max_attempts']:raise ValueError('attempt budget exhausted')
            if type(training_tokens) is not int or training_tokens<=0 or state['used_training_tokens']+training_tokens>protocol['training_token_budget']:raise ValueError('training budget exceeded')
            reserved=state['reservations'].get(attempt_id)
            if not historical_import:
                if reserved is None or reserved['dataset_hash']!=dataset_hash:raise ValueError('pre-execution reservation required')
                if training_tokens>reserved['token_bound']:raise ValueError('training exceeded reserved tokens')
            elif reserved is not None:raise ValueError('historical import cannot replace a live reservation')
            other_pending=sum(v['token_bound'] for k,v in state['reservations'].items() if k!=attempt_id)
            if state['used_training_tokens']+other_pending+training_tokens>protocol['training_token_budget']:raise ValueError('pending reservations would exceed budget')
            scores=valid_scores(summary,protocol['selection_tasks']);incumbent=state['baseline'] if state['selected']=='base' else next(r['evaluation'] for r in state['attempts'] if r['attempt_id']==state['selected'])
            prior=valid_scores(incumbent,protocol['selection_tasks'])
            no_regression=scores is not None and all(scores[t]>=prior[t] for t in prior)
            improved=scores is not None and summary['score']>state['best_score']
            admitted=improved and (no_regression or protocol.get('promotion')=='strict_score')
            record={'attempt_id':attempt_id,'dataset_hash':dataset_hash,'training_manifest':str(training_manifest),'training_tokens':training_tokens,
                    'evaluation':copy.deepcopy(summary),'promoted':admitted,'no_regression':no_regression,'registered_at':time.time(),'accounting':'historical import' if historical_import else 'pre-execution reservation'}
            if evaluation_path is not None:record['evaluation_path']=str(evaluation_path)
            if operational_version is not None:record['operational_version']=str(operational_version)
            state['reservations'].pop(attempt_id,None)
            state['attempts'].append(record);state['used_training_tokens']+=training_tokens
            if admitted:state['selected']=attempt_id;state['best_score']=summary['score']
            self._save(state);return copy.deepcopy(record)

    def recover_evaluation(self,attempt_id,summary,evaluation_path,original_path,plan_path):
        """Resolve the latest invalid execution once, retaining its original evidence."""
        with self._lock():
            state=self._read()
            if state['final_selection'] is not None or state['reservations']:raise ValueError('recovery requires an open search without pending training')
            if not state['attempts'] or state['attempts'][-1]['attempt_id']!=attempt_id:raise ValueError('only the latest candidate can be recovered before continuing search')
            record=state['attempts'][-1]
            if not record['training_manifest'] or record['evaluation']['status']=='scored' or record.get('recovery'):raise ValueError('only one retry of an infrastructure-invalid trained candidate is allowed')
            incumbent=state['baseline'] if state['selected']=='base' else next(r['evaluation'] for r in state['attempts'] if r['attempt_id']==state['selected'])
            scores=valid_scores(summary,state['protocol']['selection_tasks']);prior=valid_scores(incumbent,state['protocol']['selection_tasks'])
            no_regression=scores is not None and all(scores[k]>=prior[k] for k in prior)
            admitted=no_regression and summary['score']>state['best_score']
            record['original_evaluation']=copy.deepcopy(record['evaluation'])
            record['evaluation']=copy.deepcopy(summary);record['evaluation_path']=str(evaluation_path)
            record['recovery']={'original_path':str(original_path),'plan_path':str(plan_path),'registered_at':time.time(),'valid':scores is not None}
            record['promoted']=admitted;record['no_regression']=no_regression
            if admitted:state['selected']=attempt_id;state['best_score']=summary['score']
            self._save(state);return copy.deepcopy(record)

    def freeze_selection(self,reason):
        with self._lock():
            state=self._read()
            if state['final_selection'] is not None:return copy.deepcopy(state['final_selection'])
            if state['reservations']:raise ValueError('resolve pending training reservations before final selection')
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
