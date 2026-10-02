"""Reference-only visible native control selection; ambiguous visible nodes fail."""
from hashlib import sha256
from pathlib import Path
from types import ModuleType,FunctionType,MethodType
from . import native_reference_bulk_price_v4 as parent

PARENT_SHA='f27a45ca9ed38f242ac7082dac8e2459402164e54f4190127d975c638f61cfb1'
if sha256(Path(parent.__file__).read_bytes()).hexdigest()!=PARENT_SHA:raise ValueError('Frozen V4 reference source changed')
before=" if not await loc.is_visible():return wait()\n require(await loc.count()==1,'reference_bulk_target_ambiguous')"
after=" loc=loc.filter(visible=True)\n count=await loc.count()\n if count==0:return wait()\n require(count==1,'reference_bulk_target_ambiguous')"
if parent.text.count(before)!=1:raise ValueError('Frozen reference visibility boundary changed')
_impl=ModuleType('magento_catalog_factory._native_reference_bulk_price_v5');_impl.__package__='magento_catalog_factory';_impl.__file__=str(Path(__file__).resolve())
exec(compile(parent.text.replace(before,after),'magento-reference-current-visible-native-control-v5','exec'),_impl.__dict__)
control_sample=FunctionType(parent.control_sample.__code__,{**parent.control_sample.__globals__,'_original_control_sample':_impl.control_sample},parent.control_sample.__name__)

def sampler(case,mode):
 from .native_surface_facade_v1 import ReferenceSampler
 value=ReferenceSampler(case,mode)
 async def current(self,observation):return await control_sample(self,observation)
 value.control_sample=MethodType(current,value)
 return value
