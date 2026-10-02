"""Full editing sequence uses one material rule without accepting body/caret edits."""
from __future__ import annotations
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from PIL import Image
from cursibench.scale_action_contract import ContractError
from enterprise_fallback.odoo18.odoo_native_adapter import VISIBLE_CONTROLS_JS
from enterprise_fallback.odoo18.odoo_v066_train_route_router_v2 import PRICE_EDITOR_OWNING_ROW_JS
from enterprise_fallback.odoo18.odoo_v066_train_route_router_v5 import OdooV066TrainRouteRouterV5,FLOW_CONTEXT_JS
from tests.test_odoo_v066_train_price_passive_stability_v11 import PassivePricePage
from tests.test_odoo_v066_train_route_router_v1 import PriceLocator,TARGETS
from tests.test_odoo_v066_train_border_material_v12 import png
from tools import record_odoo_v066_train_gui_v1 as recorder
from tools.odoo_v066_train_route_journal_v1 import RouteAwareHoldoutJournal
from tools.odoo_v066_train_rfq_flow_audit_v13 import flow_guard
from tools.audit_odoo_v066_train_attachment_calibration_v12 import _route_binding


class Keyboard:
 def __init__(self,page):self.page=page
 def press(self,key):
  self.page.keys.append(key)
  if key in ('Control+A','Meta+A'):self.page.selected=True
  elif key in ('Enter','Tab'):self.page.editing=False
 def insert_text(self,text):
  self.page.value=text if self.page.selected else self.page.value+text


class FlowPage(PassivePricePage):
 def __init__(self,phase):
  super().__init__(phase);target=next(t for t in TARGETS if t['phase']==phase)
  self.value=target['initial_price'];self.editing=True;self.selected=False;self.saved_value=None
  self.keys=[];self.keyboard=Keyboard(self);self.capture_count=0;self.bad=None
  self.mouse.click=lambda x,y:setattr(self,'saved_value',self.value)
 def screenshot(self,*,type):
  state=0 if self.capture_count<2 else self.capture_count%4
  raw=png(state//2,state%2);image=Image.open(BytesIO(raw)).copy()
  # A changed typed value creates a new legitimate observed body in the next
  # step. Guard captures must keep that whole body exact within this step.
  image.putpixel((700,300),(int(float(self.value))%255,50,70))
  if self.bad=='body' and self.capture_count>=2:image.putpixel((701,300),(0,0,0))
  if self.bad=='caret' and self.capture_count>=2:
   for y in range(470,485):image.putpixel((810,y),(0,0,0))
  if self.bad=='mode' and self.capture_count>=2:image=image.convert('RGBA')
  self.capture_count+=1;out=BytesIO();image.save(out,'PNG');return out.getvalue()
 def evaluate(self,script,args=None):
  if script==VISIBLE_CONTROLS_JS:
   self.capture_count=0
   return [{'ref':'save','role':'button','label':'Save','visible':True,'enabled':True}]
  if script==PRICE_EDITOR_OWNING_ROW_JS and self.value!=args['price']:
   return {'status':'nonclaim','reason_code':'initial_price_mismatch','visible_price_input_count':1}
  if script==FLOW_CONTEXT_JS:
   if self.bad in ('modal','identity'):return None
   focus={'tag':'input' if self.editing else 'body','type':'text' if self.editing else '',
          'name':'price_unit' if self.editing else '', 'ref':'price' if self.editing else '',
          'value':self.value if self.editing else None,'disabled':False,'readonly':False,
          'bounds':[782,465,836,493] if self.editing else [0,0,1440,1000]}
   target=None if args['target'] is None else {'tag':'button','type':'button','name':'','ref':'save',
       'value':None,'disabled':False,'readonly':False,'bounds':[100,20,160,50]}
   return {'rfq_id':args['rfq_id'],'route_path':args['route_path'],'modal_absent':True,'viewer_absent':True,
           'focus':focus,'focus_in_form':self.editing,'focus_is_body':not self.editing,'target':target}
  return super().evaluate(script,args)


class SaveLocator:
 def bounding_box(self):return {'x':100,'y':20,'width':60,'height':30}


class CompleteFlowTests(unittest.TestCase):
 def setup_flow(self,phase='positive'):
  temp=tempfile.TemporaryDirectory();out=Path(temp.name)/'attempt';out.mkdir(mode=0o700)
  page=FlowPage(phase);page.attempt_dir=out
  adapter=OdooV066TrainRouteRouterV5(page,task_id='ELPO-TRN-0001',task_binding_sha256='a'*64,instruction='train-only',
    expected_attachment_label='ELPO-TRN-0001-source.pdf',expected_price_targets=TARGETS)
  journal=RouteAwareHoldoutJournal(adapter,page,out);routes=out/'routes';routes.mkdir(mode=0o700)
  def sink(prefix):
   def save(serial,value):
    ref=recorder._artifact(routes,f'{prefix}-{serial:04d}.json',value);ref['path']='routes/'+ref['path'];return ref
   return save
  adapter.route_probe_sink=sink('probe');adapter.route_decision_sink=sink('decision')
  def guard(index,raw):
   ref=recorder._artifact(out/'frames',f'guard-{index:04d}.png',raw);ref['path']='frames/'+ref['path'];return ref
  adapter.frame_guard_sink=guard
  return temp,out,page,adapter,journal

 def test_complete_doubleclick_select_type_commit_save_both_train_phases(self):
  for phase in ('positive','negative'):
   for commit in ('Tab','Enter'):
    with self.subTest(phase=phase,commit=commit):
     temp,out,page,adapter,journal=self.setup_flow(phase)
     with temp:
      journal.act('double_click',phase=phase,locator=PriceLocator())
      journal.act('key',phase=phase,key='Control+A')
      journal.act('type',phase=phase,text='100.0',mode='insert')
      journal.act('key',phase=phase,key=commit)
      journal.act('click',phase=phase,locator=SaveLocator())
      self.assertEqual(page.saved_value,'100.0');self.assertEqual(len(journal.trace),5)
      self.assertEqual(journal.pre_intent_rejections,[])
      case={'id':TARGETS[0]['rfq_id']};wrong={'id':TARGETS[1]['rfq_id']}
      baseline={'orders':[{'name':r['rfq_id'],'id':int(r['route_path'].rsplit('/',1)[1])} for r in TARGETS]}
      for step in range(1,5):
       intent=json.loads((out/f'actions/step-{step:03d}-intent.private.json').read_bytes())
       result=json.loads((out/f'actions/step-{step:03d}-result.private.json').read_bytes())
       kind,_refs=_route_binding(out,journal.trace[step],intent,result);self.assertEqual(kind,'generic_rfq')
       refs,count=flow_guard(out,journal.trace[step],intent,result,case,wrong,baseline,adapter.frame_guard_samples)
       self.assertEqual(count,1);self.assertEqual(len(refs),6)

 def test_body_and_caret_change_fail_before_keyboard_dispatch(self):
  for bad in ('body','caret','mode'):
   temp,out,page,adapter,journal=self.setup_flow()
   with temp:
    journal.act('double_click',phase='positive',locator=PriceLocator());page.bad=bad
    with self.assertRaises(ContractError):journal.act('key',phase='positive',key='Control+A')
    self.assertEqual(page.keys,[]);self.assertFalse(any((out/'actions').glob('step-001*-intent.private.json')))

 def test_focus_identity_loss_after_parse_refuses_dispatch(self):
  temp,out,page,adapter,_journal=self.setup_flow()
  with temp:
   adapter.observe_for_model();action=adapter.parse_current_action(json.dumps({'type':'key','key':'Control+A'}))
   token=adapter.parsed_route_claim['route_token'];page.bad='identity'
   with self.assertRaises(ContractError):adapter.dispatch(action,route_token=token)
   self.assertEqual(page.keys,[])


if __name__=='__main__':unittest.main()
