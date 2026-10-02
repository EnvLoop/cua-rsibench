"""Durable Odoo guard evidence and checks of the actual cooperative lease."""
from __future__ import annotations
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import time
from urllib.parse import urlsplit
from cursibench import native_surface_guard_policy_v1 as policy

ROOT=Path(__file__).resolve().parents[2]


def require(condition,code):
    if not condition:raise policy.GuardError(code)


class EvidenceStore:
    def __init__(self,root):
        self.root=Path(root).absolute()
        require(self.root.is_dir() and not self.root.is_symlink() and
                self.root.stat().st_mode&0o077==0,'guard_private_root_unsafe')

    def write(self,name,raw,kind):
        require(type(raw) is bytes and 0<len(raw)<=8_000_000,'guard_artifact_bytes_invalid')
        path=self.root/name
        require(not Path(name).is_absolute() and '..' not in Path(name).parts,'guard_artifact_path_unsafe')
        current=self.root
        for part in Path(name).parts[:-1]:
            current=current/part
            if not current.exists():current.mkdir(mode=0o700)
            require(current.is_dir() and not current.is_symlink() and current.stat().st_mode&0o077==0,
                    'guard_artifact_parent_unsafe')
        require(not path.exists() and not path.is_symlink(),'guard_artifact_consumed')
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as handle:handle.write(raw);handle.flush();os.fsync(handle.fileno())
        directory=os.open(path.parent,os.O_RDONLY)
        try:os.fsync(directory)
        finally:os.close(directory)
        return {'schema':'native-guard-artifact-ref-v1','path':name,'sha256':sha256(raw).hexdigest(),
                'size':len(raw),'kind':kind}

    def json(self,name,value,kind):return self.write(name,policy.canonical(value),kind)


def private_bytes(path):
    path=Path(path)
    require(path.is_file() and not path.is_symlink() and path.stat().st_mode&0o077==0,
            'guard_private_lease_file_unsafe')
    return path.read_bytes()


class OdooLeaseEvidence:
    def __init__(self,*,store,worker_private,page,account_uid,started,expires,clock=time.monotonic):
        self.store=store;self.private=Path(worker_private).resolve();self.page=page;self.clock=clock;self.count=0
        module=sys.modules.get('worker_lease');factory=sys.modules.get('factory')
        require(module is not None and factory is not None and
            Path(module.__file__).resolve()==ROOT/'enterprise_fallback/odoo18/worker_lease.py' and
            Path(factory.__file__).resolve()==ROOT/'enterprise_fallback/odoo18/factory.py' and
            module.PRIVATE.resolve()==self.private and factory.PRIVATE.resolve()==self.private,
            'guard_pinned_worker_lease_required')
        self.module=module;self.factory=factory
        module.require_worker_lease(root=self.private)
        self.lock_path=self.private/'worker-operation.lock';self.lock=private_bytes(self.lock_path)
        row=json.loads(self.lock)
        require(type(row) is dict and row.get('pid')==os.getpid() and type(row.get('operation')) is str,
                'guard_worker_lease_owner_changed')
        self.credentials_path=self.private/'actor_credentials.json'
        credentials=private_bytes(self.credentials_path);self.credentials_sha=sha256(credentials).hexdigest()
        login=json.loads(credentials).get('login')
        require(type(login) is str and login and type(account_uid) is str and account_uid.isdigit(),
                'guard_native_account_binding_missing')
        config=factory.local_config();port=config.get('ODOO_PORT');project=config.get('ODOO_PROJECT')
        require(str(port).isdigit() and type(project) is str and project,'guard_worker_workspace_missing')
        self.origin='http://127.0.0.1:'+str(port);self.account_uid=account_uid
        self.window_sha=policy.digest({'pid':os.getpid(),'page_object':id(page),'origin':self.origin})
        self.account_sha=policy.digest({'login_sha256':sha256(login.encode()).hexdigest(),'native_avatar_uid':account_uid})
        proof=store.json('surface-guard/lease-boundary.private.json',{
            'schema':'odoo-native-held-lease-evidence-v6','lock_sha256':sha256(self.lock).hexdigest(),
            'lock_owner':row,'credential_file_sha256':self.credentials_sha,'window_sha256':self.window_sha,
            'worker_private_sha256':policy.digest(str(self.private)),'origin':self.origin,
            'native_account_sha256':self.account_sha,'native_avatar_uid':account_uid,
            'login_sha256':sha256(login.encode()).hexdigest(),
            'bound_after_trusted_browser_login':True},'lease_evidence')
        self.lease={'schema':'native-surface-lease-v1','lease_id':sha256(self.lock+self.window_sha.encode()).hexdigest(),
            'cell_id':'odoo-community','account_sha256':self.account_sha,
            'workspace_sha256':policy.digest({'worker':str(self.private),'origin':self.origin,'project':project}),
            'window_sha256':self.window_sha,'owner_sha256':policy.digest({'pid':os.getpid(),'uid':os.getuid()}),
            'issued_at':started,'expires_at':expires,'evidence':proof}
        policy.validate_lease(self.lease)

    def check(self,bound):
        index=self.count;self.count+=1;status='active';reason='held_native_worker_lease'
        try:
            self.module.require_worker_lease(root=self.private)
            require(private_bytes(self.lock_path)==self.lock,'guard_worker_lock_changed')
            require(sha256(private_bytes(self.credentials_path)).hexdigest()==self.credentials_sha,
                    'guard_actor_credentials_changed')
            require(policy.digest(bound)==policy.digest(self.lease),'guard_lease_descriptor_changed')
        except Exception as error:status='inactive';reason=getattr(error,'code','native_worker_lease_not_held')
        tick=self.clock()
        ref=self.store.json(f'surface-guard/lease-check-{index:04d}.private.json',{
            'schema':'odoo-native-lease-check-evidence-v6','status':status,'reason':reason,
            'lock_sha256':sha256(self.lock).hexdigest(),'checked_at':tick},'lease_check')
        return {'schema':'native-surface-lease-check-v1','lease_sha256':policy.digest(bound),'status':status,
                'checked_at':tick,'expires_at':self.lease['expires_at'],'evidence':ref}

    def owns(self,page,metadata):
        parsed=urlsplit(page.url);origin=parsed.scheme+'://'+parsed.netloc
        return (page is self.page and origin==self.origin and
            (parsed.path=='/odoo' or parsed.path.startswith('/odoo/')) and
            metadata.get('visible') is True and metadata.get('top_window') is True and
            metadata.get('app_shell') is True and metadata.get('account_uid')==self.account_uid)


def read_ref(root,reference):
    policy.verify_artifact(root,reference)
    return private_bytes(Path(root)/reference['path'])
