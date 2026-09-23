"""Controller-only append ledger with idempotent resource reservations."""
import fcntl
import hashlib
import json
import os
from pathlib import Path


def checksum(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()


class Budget:
    def __init__(self,path,limits):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        if any(type(v) is not int or v<0 for v in limits.values()):raise ValueError('nonnegative integer limits required')
        self.limits=dict(limits)
        with self._lock():
            if not self.path.exists():self._append({'type':'limits','limits':self.limits,'previous':None})
            self._events()

    def _lock(self):
        class Lock:
            def __enter__(lock):
                lock.file=self.path.with_suffix('.lock').open('a');fcntl.flock(lock.file,fcntl.LOCK_EX)
            def __exit__(lock,*args):lock.file.close()
        return Lock()

    def _events(self):
        rows=[json.loads(x) for x in self.path.read_text().splitlines()];previous=None
        if not rows or rows[0].get('limits')!=self.limits:raise ValueError('budget configuration mismatch')
        for row in rows:
            content={k:v for k,v in row.items() if k!='hash'}
            if row.get('previous')!=previous or row.get('hash')!=checksum(content):raise ValueError('budget ledger integrity error')
            previous=row['hash']
        return rows

    def _append(self,event):
        row=dict(event,hash=checksum(event))
        with self.path.open('a') as f:f.write(json.dumps(row)+'\n');f.flush();os.fsync(f.fileno())
        os.chmod(self.path,0o600)

    def reserve(self,resource,amount,request_id):
        if resource not in self.limits or type(amount) is not int or amount<0 or not isinstance(request_id,str) or not request_id:raise ValueError('invalid reservation')
        with self._lock():
            rows=self._events()
            existing=[x for x in rows[1:] if x['request_id']==request_id]
            if existing:
                if existing[0]['resource']!=resource or existing[0]['amount']!=amount:raise ValueError('reservation id collision')
                return
            used=sum(x['amount'] for x in rows[1:] if x['resource']==resource)
            if used+amount>self.limits[resource]:raise ValueError(f'{resource} budget exhausted')
            self._append({'type':'reservation','resource':resource,'amount':amount,'request_id':request_id,'previous':rows[-1]['hash']})

    def snapshot(self):
        with self._lock():rows=self._events()
        used={k:sum(r['amount'] for r in rows[1:] if r['resource']==k) for k in self.limits}
        return {'limits':self.limits,'reserved':used,'remaining':{k:self.limits[k]-v for k,v in used.items()}}

    def next_research_turn(self):
        with self._lock():rows=self._events()
        turns=[int(r['request_id'].split(':')[1]) for r in rows[1:]
               if r['resource']=='researcher_calls' and r['request_id'].startswith('researcher:')]
        return max(turns,default=-1)+1
