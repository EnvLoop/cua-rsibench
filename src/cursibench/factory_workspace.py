"""E2B workspace boundary for researcher-written code; host secrets stay outside."""
import json
import hashlib
import time
import uuid
from pathlib import Path
from .factory_worker import resolve_path


class FactoryWorkspace:
    def __init__(self,artifact_dir,budget,resume=False):
        self.root=Path(artifact_dir);self.root.mkdir(parents=True,exist_ok=resume)
        self.budget=budget;self.sandbox=None

    def start(self,inputs):
        from e2b import Sandbox
        self.sandbox=Sandbox.create(timeout=3600,allow_internet_access=False,envs={},
                                    metadata={'project':'cua-data-factory','role':'research-workspace'})
        (self.root/'sandbox.json').write_text(json.dumps({'id':self.sandbox.sandbox_id,'network':'no outbound internet','provider_credentials_injected':False}))
        self.sandbox.files.write('/tmp/factory_worker.py',Path(__file__).with_name('factory_worker.py').read_text(),user='root')
        result=self.sandbox.commands.run('python /tmp/factory_worker.py --initialize',timeout=30,user='root')
        (self.root/'initialization.json').write_text(result.stdout)
        for name,content in inputs.items():
            if '/' in name or not name or '..' in name:raise ValueError('flat controller input names required')
            self.sandbox.files.write('/inputs/'+name,content,user='root')
        return json.loads(result.stdout)

    def reconnect(self):
        from e2b import Sandbox
        record=json.loads((self.root/'sandbox.json').read_text())
        self.sandbox=Sandbox.connect(record['id'],timeout=1800)
        before=self.sandbox.files.read('/service/factory_worker.py',user='root')
        current=Path(__file__).with_name('factory_worker.py').read_text()
        if before!=current:
            self.sandbox.files.write('/service/factory_worker.py',current,user='root')
            (self.root/'supervisor-upgrade.json').write_text(json.dumps({
                'reason':'controller recovery and bounded workspace preservation',
                'old_sha256':hashlib.sha256(before.encode()).hexdigest(),
                'new_sha256':hashlib.sha256(current.encode()).hexdigest()},indent=2))
        return {'connected_existing':True}

    def snapshot(self):
        result=self.call('snapshot','factory.py')
        if 'files' not in result:raise RuntimeError('workspace preservation failed: '+str(result))
        (self.root/'final-files.json').write_text(json.dumps(result,indent=2))
        return {'files':len(result['files']),'bytes':result['bytes']}

    def add_input(self,name,content):
        if '/' in name or not name or '..' in name:raise ValueError('flat input name required')
        self.sandbox.files.write('/inputs/'+name,content,user='root')

    def call(self,operation,path,**kwargs):
        resolve_path(path,writing=operation=='write')
        request_id=uuid.uuid4().hex
        if operation=='run':self.budget.reserve('program_runs',1,request_id)
        packet={'op':operation,'path':path,**kwargs}
        local=self.root/(request_id+'.request.json');local.write_text(json.dumps(packet))
        remote='/service/requests/'+request_id+'.json'
        self.sandbox.files.write(remote,json.dumps(packet),user='root')
        for attempt in range(3):
            try:
                reply=self.sandbox.commands.run('python /service/factory_worker.py --request '+request_id,
                    timeout=(kwargs.get('seconds',30)+15 if operation=='run' else 15),user='root')
                result=json.loads(reply.stdout);break
            except Exception:
                # The root-owned request journal prevents repeat execution after response loss.
                try:result=json.loads(self.sandbox.files.read('/service/results/'+request_id+'.json',user='root'));break
                except Exception:
                    if attempt==2:raise
                    time.sleep(attempt+1)
        (self.root/(request_id+'.result.json')).write_text(json.dumps(result,indent=2))
        return result

    def write(self,path,content):return self.call('write',path,content=content)
    def read(self,path):return self.call('read',path)
    def run(self,path,args=None,seconds=30):return self.call('run',path,args=args or [],seconds=seconds)

    def close(self):
        if self.sandbox:
            try:self.sandbox.kill();destroyed=True
            except Exception:destroyed=False
            (self.root/'cleanup.json').write_text(json.dumps({'sandbox_destroyed':destroyed}))
            self.sandbox=None
