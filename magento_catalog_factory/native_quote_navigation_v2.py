"""One CMS navigation click, followed by explicit bounded editor readiness.

Only evaluator setup navigation changes. Exact quote bytes, original screenshot
readback, native actor budget, saved scorer and physical clone reset stay frozen.
"""
from hashlib import sha256
import inspect
from pathlib import Path
from types import FunctionType, SimpleNamespace
from contextlib import asynccontextmanager
import textwrap
from tools import qualify_magento_original_catalog_v1 as quote
from tools import magento_dedicated_train_lane_v066 as dedicated
from . import native_surface_actor_v1 as actor

ROOT=Path(__file__).resolve().parents[1]
PINS={'tools/qualify_magento_original_catalog_v1.py':'573fa5b29f7d9e6d991734ddc05a14f1e8046313ae17e3942c5f4b17a231cdd8',
 'tools/magento_dedicated_train_lane_v066.py':'e0f69e87c1f9197ca4ee4564dc6d74b04a9d28d84159e0e4c1952568781a4242',
 'magento_catalog_factory/native_surface_actor_v1.py':'e50def6066e7883f8a0423119f47ff6e9d56d579c6a3d444daa7fe0876f6ffaf'}
for name,expected in PINS.items():
    if sha256((ROOT/name).read_bytes()).hexdigest()!=expected:raise ValueError('Frozen Magento setup source changed')

source=inspect.getsource(quote.read_quote_in_gui)
for before,after in [("await pages_menu.click()","await pages_menu.click(no_wait_after=True)"),
 ("await row.get_by_text('Edit', exact=True).click()","await row.get_by_text('Edit', exact=True).click(no_wait_after=True)")]:
    if source.count(before)!=1:raise ValueError('Checked Magento quote navigation branch changed')
    source=source.replace(before,after)
namespace=dict(quote.read_quote_in_gui.__globals__)
exec(compile(source,'magento-cms-explicit-editor-readiness-v2','exec'),namespace)
read_quote_in_gui=namespace['read_quote_in_gui']

# Isolate the original runtime's dependency; never patch the V1 module globals.
method=dedicated.DedicatedMagentoTrainRuntime.open_case.__wrapped__
gui=SimpleNamespace(**{**vars(quote),'read_quote_in_gui':read_quote_in_gui})
scoped=FunctionType(method.__code__,{**method.__globals__,'original_gui':gui,
    'CommandJournal':actor.NativeCommandJournal},method.__name__,method.__defaults__,method.__closure__)
scoped.__kwdefaults__=method.__kwdefaults__
dedicated_open=asynccontextmanager(scoped)

source=textwrap.dedent(inspect.getsource(actor.Runtime.open_case.__wrapped__))
before='async with super().open_case(case,out_dir) as active:'
if source.count(before)!=1:raise ValueError('Checked Magento original setup bridge changed')
source=source.replace(before,'async with dedicated_open(self,case,out_dir) as active:')
namespace={**actor.Runtime.open_case.__wrapped__.__globals__,'dedicated_open':dedicated_open}
exec(compile(source,'magento-original-setup-quote-navigation-v2','exec'),namespace)

class Runtime(actor.Runtime):
    open_case=namespace['open_case']
