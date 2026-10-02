"""Evaluator-only native price attribute path; all mutations use common guard."""
import re,time
from decimal import Decimal,InvalidOperation
from .native_surface_workers_v1 import require

async def control_sample(controller,observation):
 page=controller.adapter.page
 if controller.index>=len(controller.edits):return {'type':'finish','memory':''}
 row=controller.edits[controller.index];sku=row['sku'];stage=controller.stage
 def wait():return {'type':'wait','duration_ms':250}
 if stage==0:
  loc=page.locator('[data-ui-id="menu-magento-catalog-catalog-products"] > a')
  if not await loc.is_visible():loc=page.locator('#menu-magento-catalog-catalog > a');next_stage=0
  else:next_stage=1
  action={'type':'click'}
 elif stage==1:loc=page.locator('input#fulltext:visible').first;next_stage=2;action={'type':'type','mode':'fill','text':sku}
 elif stage==2:loc=page.locator('input#fulltext:visible').first;next_stage=3;action={'type':'key','key':'Enter'}
 elif stage==3:
  product=page.locator('table.data-grid tbody tr').filter(has_text=sku)
  if await product.count()!=1:return wait()
  cells=[x.strip() for x in await product.locator('td').all_text_contents()]
  require(cells.count(sku)==1,'reference_bulk_exact_native_sku_required')
  checkbox=product.locator('.data-grid-checkbox-cell input[type="checkbox"]')
  require(await checkbox.count()==1,'reference_one_product_checkbox_required')
  if await checkbox.is_checked():controller.stage=4;return wait()
  # A native rendered label is the checkbox's current physical UI target.
  loc=product.locator('.data-grid-checkbox-cell label');next_stage=4;action={'type':'click'}
 elif stage==4:loc=page.locator('.data-grid-dropdown .action-select').filter(has_text=re.compile(r'^\s*Actions\s*$'));next_stage=5;action={'type':'click'}
 elif stage==5:loc=page.get_by_text('Update attributes',exact=True);next_stage=6;action={'type':'click'}
 elif stage==6:
  toggle=page.locator('#toggle_price');loc=page.locator('label[for="toggle_price"]')
  if not await toggle.is_visible():return wait()
  if await toggle.is_checked():controller.stage=7;return wait()
  next_stage=7;action={'type':'click'}
 elif stage==7:
  loc=page.locator('input[name="attributes[price]"]');next_stage=8;action={'type':'type','mode':'fill','text':row['target_price']}
 elif stage==8:
  form=page.locator('body')
  state=await form.evaluate("""form=>({enabled:Array.from(form.querySelectorAll('[name^="attributes["]')).filter(e=>!e.disabled).map(e=>e.name),changed:Array.from(form.querySelectorAll('input[name^="toggle_"]')).filter(e=>e.checked).map(e=>e.name)})""")
  # Do not submit weight/defaults/inventory/website fields. This is native
  # readback of the form, never a DOM mutation or request manipulation.
  require(state['enabled']==['attributes[price]'] and state['changed']==['toggle_price'],'reference_bulk_only_price_may_be_enabled')
  loc=page.get_by_role('button',name='Save',exact=True);next_stage=9;action={'type':'click'}
 else:
  # A queue notification alone is not save authority. Require the actual
  # owned native grid to display the new price before completing this edit.
  product=page.locator('table.data-grid tbody tr').filter(has_text=sku)
  if await product.count()!=1:return wait()
  cells=[x.strip() for x in await product.locator('td').all_text_contents()]
  if cells.count(sku)!=1:return wait()
  prices=[]
  for value in cells:
   if re.fullmatch(r'\$\s*[0-9,]+(?:\.[0-9]+)?',value):
    try:prices.append(Decimal(value.replace('$','').replace(',','').strip()))
    except InvalidOperation:pass
  if Decimal(row['target_price']) not in prices:
   loc=page.locator('input#fulltext:visible').first
   if not await loc.is_visible():return wait()
   box=await loc.bounding_box(timeout=1000)
   if not box:return wait()
   return {'type':'key','key':'Enter','target':{'x':round(box['x']+box['width']/2),'y':round(box['y']+box['height']/2)}}
  controller.index+=1;controller.stage=0;return wait()
 if not await loc.is_visible():return wait()
 require(await loc.count()==1,'reference_bulk_target_ambiguous')
 box=await loc.bounding_box(timeout=min(1000,max(1,int((controller.adapter.actor.deadline-time.monotonic())*1000))))
 if not box:return wait()
 x=round(box['x']+box['width']/2);y=round(box['y']+box['height']/2)
 if not (0<=x<observation.screenshot['width'] and 0<=y<observation.screenshot['height']):
  return {'type':'scroll','target':{'x':1200,'y':900},'dx':0,'dy':600 if y>=observation.screenshot['height'] else -600}
 controller.stage=next_stage
 return {**action,'target':{'x':x,'y':y}}
