"""Evaluator chooses GUI actions only; no locator mutation or queue-success shortcut."""
import json,time,unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from magento_catalog_factory import native_reference_bulk_price_v2 as ref
from magento_catalog_factory.native_surface_facade_v1 import ReferenceSampler

class Locator:
 def __init__(self,*,count=1,texts=None,checked=False,visible=True,state=None):
  self.n=count;self.texts=texts or ['MP07-36-Purple','$68.00'];self.checked=checked;self.visible=visible;self.state=state;self.children={};self.first=self
 async def count(self):return self.n
 async def is_visible(self):return self.visible
 async def is_checked(self):return self.checked
 async def all_text_contents(self):return self.texts
 async def bounding_box(self,**kw):return {'x':120,'y':200,'width':100,'height':30}
 def filter(self,**kw):return self
 def locator(self,selector):return self.children.get(selector,self)
 async def evaluate(self,script):return self.state
 async def click(self,*a,**kw):raise AssertionError('Reference must not dispatch locator.click')
 async def fill(self,*a,**kw):raise AssertionError('Reference must not dispatch locator.fill')

class Page:
 def __init__(self):self.items={};self.default=Locator()
 def locator(self,selector):return self.items.get(selector,self.default)
 def get_by_role(self,*a,**kw):return self.default
 def get_by_text(self,*a,**kw):return self.default

class ReferenceTests(unittest.IsolatedAsyncioTestCase):
 def controller(self,stage):
  page=Page();control=SimpleNamespace(adapter=SimpleNamespace(page=page,actor=SimpleNamespace(deadline=time.monotonic()+720)),index=0,edits=[{'sku':'MP07-36-Purple','target_price':'59.85'}],stage=stage)
  return control,page,SimpleNamespace(screenshot={'width':1440,'height':1000})
 async def test_checkbox_selection_needs_exact_native_sku(self):
  c,p,o=self.controller(3);p.default.texts=['MP07-36-Purple-other','$68.00']
  with self.assertRaises(ValueError):await ref.control_sample(c,o)
 async def test_only_price_change_checkbox_target(self):
  c,p,o=self.controller(6);action=await ref.control_sample(c,o)
  self.assertEqual(action['type'],'click');self.assertEqual(c.stage,7)
 async def test_price_fill_uses_one_guard_action_no_direct_mutation(self):
  c,p,o=self.controller(7);action=await ref.control_sample(c,o)
  self.assertEqual(action['type'],'type');self.assertEqual(action['text'],'59.85');self.assertEqual(c.stage,8)
 async def test_any_extra_enabled_attribute_refuses_before_save(self):
  c,p,o=self.controller(8);p.items['body']=Locator(state={'enabled':['attributes[price]','attributes[has_weight]'],'changed':['toggle_price']})
  with self.assertRaises(ValueError):await ref.control_sample(c,o)
  self.assertEqual(c.stage,8)
 async def test_only_price_form_can_propose_save(self):
  c,p,o=self.controller(8);p.items['body']=Locator(state={'enabled':['attributes[price]'],'changed':['toggle_price']})
  action=await ref.control_sample(c,o);self.assertEqual(action['type'],'click');self.assertEqual(c.stage,9)
 async def test_queued_or_stale_grid_price_is_not_finish(self):
  c,p,o=self.controller(9);action=await ref.control_sample(c,o)
  self.assertEqual(action['type'],'key');self.assertEqual(action['key'],'Enter');self.assertEqual(c.index,0)
 async def test_actual_grid_price_advances_then_next_frame_finish(self):
  c,p,o=self.controller(9);p.default.texts=['MP07-36-Purple','$59.85']
  self.assertEqual((await ref.control_sample(c,o))['type'],'wait');self.assertEqual(c.index,1)
  self.assertEqual((await ref.control_sample(c,o))['type'],'finish')
 async def test_facade_keeps_exact_trusted_controller_module_and_delegates_source(self):
  case={'target_variants':[{'sku':'MP07-36-Purple','target_price':'59.85'}]}
  c=ReferenceSampler(case,'positive');c.adapter=SimpleNamespace(page=Page(),actor=SimpleNamespace(deadline=time.monotonic()+720));c.stage=7
  self.assertEqual(type(c).__module__,'magento_catalog_factory.native_surface_facade_v1')
  self.assertEqual((await c.control_sample(SimpleNamespace(screenshot={'width':1440,'height':1000})))['text'],'59.85')

if __name__=='__main__':unittest.main()
