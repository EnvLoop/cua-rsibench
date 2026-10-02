"""Reference-only native Actions toolbar selector matching the pinned template."""
from pathlib import Path
from hashlib import sha256
from types import ModuleType,MethodType
import time
from . import native_reference_bulk_price_v3 as previous

source=previous._impl.control_sample
from . import native_reference_bulk_price_v2 as original
text=Path(original.__file__).read_text()
before="loc=product.locator('.data-grid-checkbox-cell label');next_stage=4;action={'type':'click'}"
after="""identifier=await checkbox.get_attribute('id')
  require(type(identifier) is str and re.fullmatch(r'[a-zA-Z0-9_-]+',identifier),'reference_exact_checkbox_native_id_required')
  loc=product.locator('.data-grid-checkbox-cell label[for="'+identifier+'"]');next_stage=4;action={'type':'click'}"""
if text.count(before)!=1:raise ValueError('Frozen original checkbox reference changed')
text=text.replace(before,after)
before="page.locator('.data-grid-dropdown .action-select')"
if text.count(before)!=1:raise ValueError('Frozen original Actions toolbar reference changed')
text=text.replace(before,"page.locator('.action-select-wrap > button.action-select')")
_impl=ModuleType('magento_catalog_factory._native_reference_bulk_price_v4')
_impl.__package__='magento_catalog_factory';_impl.__file__=str(Path(__file__).resolve())
exec(compile(text,'magento-reference-native-associated-label-and-toolbar-v4','exec'),_impl.__dict__)
_original_control_sample=_impl.control_sample

async def control_sample(controller,observation):
    action=await _original_control_sample(controller,observation)
    key=(controller.index,controller.stage)
    if action['type']=='wait':
        if getattr(controller,'_current_native_wait_key',None)!=key:
            controller._current_native_wait_key=key;controller._current_native_wait_started=time.monotonic()
        elif time.monotonic()-controller._current_native_wait_started>=30:
            raise ValueError('reference_native_target_or_save_not_ready_within_30_seconds')
    else:
        controller._current_native_wait_key=None;controller._current_native_wait_started=None
    return action

def sampler(case,mode):
    from .native_surface_facade_v1 import ReferenceSampler
    value=ReferenceSampler(case,mode)
    async def current(self,observation):return await control_sample(self,observation)
    value.control_sample=MethodType(current,value)
    return value
