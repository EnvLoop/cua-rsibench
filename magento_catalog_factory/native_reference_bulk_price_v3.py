"""Reference-only exact label association; native actions/guard stay identical."""
from pathlib import Path
from hashlib import sha256
from types import ModuleType
from . import native_reference_bulk_price_v2 as original

source=Path(original.__file__).read_bytes()
_PIN='f70d08e60a0845f44ee1b2086b5c04c19b37c367f74bf8a9431c1e3188dec5d4'
if sha256(source).hexdigest()!=_PIN:raise ValueError('Frozen original reference source changed')
text=source.decode();before="loc=product.locator('.data-grid-checkbox-cell label');next_stage=4;action={'type':'click'}"
if text.count(before)!=1:raise ValueError('Checked original native checkbox recipe changed')
after="""identifier=await checkbox.get_attribute('id')
  require(type(identifier) is str and re.fullmatch(r'[a-zA-Z0-9_-]+',identifier),'reference_exact_checkbox_native_id_required')
  loc=product.locator('.data-grid-checkbox-cell label[for="'+identifier+'"]');next_stage=4;action={'type':'click'}"""
_impl=ModuleType('magento_catalog_factory._native_reference_bulk_price_v3')
_impl.__package__='magento_catalog_factory';_impl.__file__=str(Path(__file__).resolve())
exec(compile(text.replace(before,after),'magento-reference-current-checkbox-associated-label-v3','exec'),_impl.__dict__)
control_sample=_impl.control_sample

def sampler(case,mode):
    """Original trusted class, explicit current evaluator callback on instance."""
    from types import MethodType
    from .native_surface_facade_v1 import ReferenceSampler
    value=ReferenceSampler(case,mode)
    async def current(self,observation):return await control_sample(self,observation)
    value.control_sample=MethodType(current,value)
    return value
