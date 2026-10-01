"""Actual owned clone/process lock/native username witness for Magento."""
from __future__ import annotations
from hashlib import sha256
import asyncio
import fcntl
import json
import os
from pathlib import Path
import time
from urllib.parse import urlsplit
from cursibench import native_surface_guard_policy_v1 as policy


class OwnedOperation:
    def __init__(self,path):self.path=Path(path);self.fd=None;self.row=None
    def __enter__(self):
        self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        if self.path.is_symlink():raise policy.GuardError('owned_magento_lock_unsafe')
        self.fd=os.open(self.path,os.O_RDWR|os.O_CREAT,0o600)
        try:fcntl.flock(self.fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BaseException:os.close(self.fd);self.fd=None;raise
        self.row={'schema':'magento-owned-operation-v1','pid':os.getpid(),'started_monotonic':time.monotonic()}
        raw=policy.canonical(self.row);os.ftruncate(self.fd,0);os.write(self.fd,raw);os.fsync(self.fd)
        self.raw=raw;return self
    def active(self):
        return self.fd is not None and self.row['pid']==os.getpid() and self.path.read_bytes()==self.raw
    def __exit__(self,*_):
        if self.fd is not None:fcntl.flock(self.fd,fcntl.LOCK_UN);os.close(self.fd);self.fd=None


class LeaseBoundary:
    def __init__(self,*,session,operation,username,page,store,started,deadline,prepared):
        self.session=session;self.operation=operation;self.username=username;self.page=page;self.store=store
        self.prepared=prepared;self.origin=f'http://127.0.0.1:{session.spec.http_port}';self.count=0
        if not operation.active() or not username or not prepared['no_host_mounts']:
            raise policy.GuardError('owned_magento_native_lease_missing')
        proof=store.json('guard/held-lease.private.json',{'schema':'magento-actual-held-lease-v1',
            'owned_operation':operation.row,'owned_operation_sha256':sha256(operation.raw).hexdigest(),
            'lock_path_sha256':policy.digest(str(operation.path.resolve())),
            'app_id_sha256':prepared['app_id_sha256'],'search_id_sha256':prepared['search_id_sha256'],
            'app_image_sha256':prepared['app_image_sha256'],'search_image_sha256':prepared['search_image_sha256'],
            'origin':self.origin,'native_username_sha256':sha256(username.encode()).hexdigest(),
            'trusted_login_and_native_rendered_username_required':True,'no_host_mounts':True},'lease_evidence')
        self.lease={'schema':'native-surface-lease-v1','lease_id':policy.digest([prepared['app_id_sha256'],operation.row]),
            'cell_id':'magento-admin','account_sha256':sha256(username.encode()).hexdigest(),
            'workspace_sha256':policy.digest([self.origin,prepared['app_id_sha256']]),
            'window_sha256':policy.digest({'pid':os.getpid(),'page_object':id(page)}),
            'owner_sha256':policy.digest(operation.row),'issued_at':started,'expires_at':deadline,'evidence':proof}

    async def owns(self,page,meta):
        parsed=urlsplit(meta['physical_url']);origin=parsed.scheme+'://'+parsed.netloc
        witness=meta.get('account_witness',{})
        return bool(page is self.page and origin==self.origin and (parsed.path=='/admin' or parsed.path.startswith('/admin/')) and
            meta['top_window'] and meta['visible'] and meta['app_shell'] and
            meta['native_username']==self.username and witness.get('visible_count')==1 and
            witness.get('username')==self.username and
            meta['native_window_sha256']==self.lease['window_sha256'] and self.operation.active())

    async def check(self,store):
        spec=self.session.spec;manager=self.session.manager;index=self.count;self.count+=1
        app=await asyncio.to_thread(manager._inspect,f'guard-app-{index:04d}',spec.app)
        search=await asyncio.to_thread(manager._inspect,f'guard-search-{index:04d}',spec.search)
        active=bool(self.operation.active() and app and search and
            app['State']['Running'] and search['State']['Running'] and
            sha256(app['Id'].encode()).hexdigest()==self.prepared['app_id_sha256'] and
            sha256(search['Id'].encode()).hexdigest()==self.prepared['search_id_sha256'] and
            app['Image']==self.prepared['app_image_sha256'] and search['Image']==self.prepared['search_image_sha256'] and
            app['Mounts']==[] and search['Mounts']==[])
        reference=store.json(f'guard/lease-check-{index:04d}.private.json',{
            'schema':'magento-native-clone-lease-check-v1','app':app,'search':search,
            'held_operation':self.operation.row,'active':active,'no_account_or_task_api_query':True},'lease_check')
        return {'schema':'native-surface-lease-check-v1','lease_sha256':policy.digest(self.lease),
            'status':'active' if active else 'inactive','checked_at':time.monotonic(),
            'expires_at':self.lease['expires_at'],'evidence':reference}
