"""Opt-in repaired application build for owned GitLab worlds, without changing gold or data seeds."""
from contextlib import contextmanager
from unittest.mock import patch
runtime=world=None  # Native dependencies are loaded only for an actual owned run.
from tools.build_gitlab_member_date_only_image import ASSET,ORIGINAL_SHA,FIXED_SHA,BASE


def validate_epoch(value):
    expected={'schema':'gitlab-member-date-only-application-build-v1','base_image':BASE,'asset':ASSET,'original_asset_sha256':ORIGINAL_SHA,'repaired_asset_sha256':FIXED_SHA,'date_offset_timezone_or_oracle_changes':False}
    if any(value.get(k)!=v for k,v in expected.items()):raise ValueError('Exact member date-only application build receipt required')
    if not value.get('repaired_image') or not value.get('repaired_image_id','').startswith('sha256:'):raise ValueError('Repaired application image identity required')
    return value


@contextmanager
def application_epoch_scope(value):
    """Use a pinned repaired image only for owned resets; restore original runtime afterwards.

    Callers must record this application epoch alongside native results. The
    original SQL/Git reset seed and evaluator remain unchanged. Historical
    application results do not become results of the new build.
    """
    global runtime,world
    if runtime is None:
        from . import runtime as native_runtime
        runtime=native_runtime
    if world is None:
        from . import v066_uniform_task_runtime_v15 as native_world
        world=native_world
    value=validate_epoch(value);image=value['repaired_image'];image_id=value['repaired_image_id'];BaseNative=world.cold.NativeBackend;BaseTaskWorld=world.TaskWorld
    class RepairedNative(BaseNative):
        @contextmanager
        def scope(self,*args,**kwargs):
            name=args[0] if args else kwargs.get('name');owned=isinstance(name,str) and name.startswith(self.doc['container_prefix']+'-')
            with super().scope(*args,**kwargs):
                if owned:
                    with patch.object(runtime,'IMAGE',image),patch.object(runtime,'IMAGE_ID',image_id):yield
                else:yield
        def boot(self,index):
            result=super().boot(index);name=self.doc['container_prefix']+'-'+str(index);actual=runtime.inspect(name)
            if actual['Image']!=image_id:raise ValueError('Owned application image differs from epoch receipt')
            digest=self.docker('exec','--user','gitlab-www',name,'sha256sum',ASSET,timeout=30).split()[0]
            if digest!=FIXED_SHA:raise ValueError('Owned served frontend asset differs from repaired epoch')
            self.record(f'cycle-{index}-application-epoch.private.json',{**value,'actual_image_id':actual['Image'],'actual_asset_sha256':digest,'same_original_sql_git_seed':True,'old_application_credit':False})
            return result
    class RepairedTaskWorld(BaseTaskWorld):
        def __init__(self,*args,**kwargs):
            if 'backend_factory' in kwargs:raise ValueError('Repaired epoch owns its backend factory')
            super().__init__(*args,backend_factory=RepairedNative,**kwargs)
        @contextmanager
        def _scope(self,*args,**kwargs):
            with super()._scope(*args,**kwargs),patch.object(runtime,'IMAGE',image),patch.object(runtime,'IMAGE_ID',image_id):yield
    with patch.object(world,'TaskWorld',RepairedTaskWorld):yield
