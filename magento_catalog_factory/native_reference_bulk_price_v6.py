"""Reference-only scroll point selection from genuine current native metadata."""
from pathlib import Path
from hashlib import sha256
from types import MethodType
from . import native_reference_bulk_price_v5 as parent

PARENT_SHA='279b1b7dc155b7093b52cd945670c2c11cac2042b39186696031066650a645c9'
if sha256(Path(parent.__file__).read_bytes()).hexdigest()!=PARENT_SHA:raise ValueError('Frozen V5 reference source changed')

async def control_sample(controller,observation):
 action=await parent.control_sample(controller,observation)
 if action['type']!='scroll':return action
 width,height=observation.screenshot['width'],observation.screenshot['height']
 points=[{'x':int(width*f),'y':int(height*g)} for f,g in ((.8,.3),(.8,.5),(.7,.3),(.9,.3),(.7,.6))]
 metadata=await controller.adapter.meta(points)
 controller.adapter.actor.check('reference_current_scroll_target_readback')
 sequence=getattr(controller,'_native_scroll_query_sequence',0);controller._native_scroll_query_sequence=sequence+1
 if hasattr(controller.adapter,'store'):controller.adapter.store.json(f'reference/scroll-target-{sequence:03d}.private.json',{'schema':'magento-reference-native-scroll-target-v6','points':points,'current_native_metadata':metadata,'gui_driver_called':False},'native_observation_envelope')
 for point,hit in zip(points,metadata['hits']):
  if hit['visible'] and hit['enabled'] and not hit['obscured'] and 'scroll' in hit['actions']:
   return {**action,'target':point}
 raise ValueError('reference_no_current_safe_scroll_surface')

def sampler(case,mode):
 from .native_surface_facade_v1 import ReferenceSampler
 value=ReferenceSampler(case,mode)
 async def current(self,observation):return await control_sample(self,observation)
 value.control_sample=MethodType(current,value)
 return value
