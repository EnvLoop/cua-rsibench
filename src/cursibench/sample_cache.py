"""Per-proxy idempotency for sampling retries; duplicate requests share a future."""
import hashlib

class SamplingCache:
    def __init__(self,limit=256):self.entries={};self.limit=limit
    def get(self,request_id,prompt,start):
        if not isinstance(request_id,str) or not 8<=len(request_id)<=100:raise ValueError('request id required')
        digest=hashlib.sha256(prompt.encode()).hexdigest()
        if request_id in self.entries:
            old,future=self.entries[request_id]
            if old!=digest:raise ValueError('request id reused for different prompt')
            return future,True
        if len(self.entries)>=self.limit:raise ValueError('request cache cap reached')
        future=start();self.entries[request_id]=(digest,future)
        return future,False
