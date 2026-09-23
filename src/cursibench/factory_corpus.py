"""Controller-owned proof registry for data emitted by researcher programs."""
import copy
import json
from .factory_cases import digest
from .factory_rollout import examples


class VerifiedCorpus:
    def __init__(self):self.records={};self.episodes={}

    def add(self,case,result,episode_id):
        if episode_id in self.episodes:raise ValueError('episode id already used')
        records=examples(case,result,episode_id)
        self.episodes[episode_id]={'case_hash':digest(case),'result_hash':digest(result)}
        for row in records:self.records[row['record_id']]=copy.deepcopy(row)
        return records

    def export(self):return copy.deepcopy(list(self.records.values()))

    def validate_submission(self,text,max_records=256):
        if not isinstance(text,str) or len(text.encode())>2_000_000:raise ValueError('submission too large')
        try:rows=[json.loads(line) for line in text.splitlines() if line.strip()]
        except ValueError as exc:raise ValueError('messages JSONL required') from exc
        if not 1<=len(rows)<=max_records:raise ValueError('submission record count outside contract')
        verified=[]
        for row in rows:
            if not isinstance(row,dict):raise ValueError('record must be an object')
            expected=self.records.get(row.get('record_id'))
            if expected is None or digest(row)!=digest(expected):raise ValueError('record lacks matching controller-verified provenance')
            verified.append(copy.deepcopy(expected))
        return verified
