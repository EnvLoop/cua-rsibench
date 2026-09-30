"""Four native families, complete edit flow and adversarial physical guards."""
from __future__ import annotations
import copy,json,unittest
from io import BytesIO
from types import SimpleNamespace
from PIL import Image
from cursibench.scale_action_contract import ContractError
from enterprise_fallback.odoo18.odoo_v066_native_material_adapter_v2 import (
 OdooV066NativeMaterialAdapter,PROFILE,VISIBLE_CONTROLS_JS,NATIVE_CONTEXT_JS,audit_guard,public_binding)
from enterprise_fallback.odoo18.odoo_native_geometry_material_v2 import (TOP_STATES,BOTTOM_STATES,TAB_STATES,projected_points,border_material,STYLE_FIELDS)


def geometry(bottom=865, tab_bounds=None):
 style={key:"none" if key in ("transform","boxShadow") else "1" if key=="opacity" else "1px" if key.endswith("Width") else "solid" if key.endswith("Style") else "4px" if key.endswith("Radius") else "rgb(255, 255, 255)" if key=="backgroundColor" else "rgb(222, 226, 230)" for key in STYLE_FIELDS}
 sheet={"tag":"div","class_name":"o_form_sheet position-relative","role":"","aria_selected":"","ref":"","bounds":[16,154,1424,bottom],"style":style}
 tab_style={**style,"borderBottomColor":"rgb(255, 255, 255)","borderBottomLeftRadius":"0px","borderBottomRightRadius":"0px"}
 tab={"tag":"a","class_name":"nav-link active","role":"tab","aria_selected":"true","ref":"tab","bounds":tab_bounds or [41,381,133,420],"style":tab_style}
 return {"viewport":{"width":1440,"height":1000,"device_pixel_ratio":1,"scroll_x":0,"scroll_y":0,"visual_scale":1,"visual_offset_left":0,"visual_offset_top":0},"form_bounds":[0,104,1440,1000],"sheet_count":1,"sheet":sheet,"selected_tab_count":1,"selected_tab":tab}


POINTS=projected_points(geometry())
TOP_POINTS=tuple(map(tuple,POINTS["top"]))
BOTTOM_POINTS=tuple(map(tuple,POINTS["bottom"]))


def png(top=0,bottom=0,value='10',bad=None,geo=None,tab=0):
 image=Image.new('RGB',(1440,1000),'white')
 points=projected_points(geo or geometry())
 for name,states,state in [('top',TOP_STATES,top),('bottom',BOTTOM_STATES,bottom),('selected_tab',TAB_STATES,tab)]:
  for xy,rgb in zip(points[name],states[state]):image.putpixel(tuple(xy),rgb)
 image.putpixel((700,300),(int(float(value))%255,50,70))
 if bad=='body':image.putpixel((702,300),(1,2,3))
 if bad=='caret':
  for y in range(420,440):image.putpixel((810,y),(0,0,0))
 if bad=='franken':image.putpixel(TOP_POINTS[0],TOP_STATES[1][0])
 if bad=='mode':image=image.convert('RGBA')
 out=BytesIO();image.save(out,'PNG');return out.getvalue()


def identity(tag='body',ref='',name='',value=None):
 return {'tag':tag,'type':'text' if tag=='input' else 'button' if tag=='button' else '',
  'name':name,'ref':ref,'label':'price_unit' if tag=='input' else 'Save' if tag=='button' else '',
  'value':value,'disabled':False,'readonly':False,
  'bounds':[780,400,840,440] if tag=='input' else [100,20,160,50] if tag=='button' else [0,0,1440,1000]}


class FakePage:
 viewport_size={'width':1440,'height':1000}
 def __init__(self,family):
  self.family=family;self.url='http://127.0.0.1:8069/odoo/'+family+'/42';self.value='10.0';self.editing=True
  self.geometry=geometry();self.capture=0;self.bad=None;self.bad_context=None;self.alt=False;self.canvas=False;self.actions=[];self.selected=False;self.saved=None
  self.mouse=SimpleNamespace(click=self.click,dblclick=self.doubleclick,move=lambda *a,**k:self.actions.append(('move',a)),down=lambda:self.actions.append(('down',)),up=lambda:self.actions.append(('up',)))
  self.keyboard=SimpleNamespace(press=self.press,insert_text=self.insert)
 def evaluate(self,script,args=None):
  if script==VISIBLE_CONTROLS_JS:
   self.capture=0
   return [{'ref':'price','role':'input','label':'price_unit','visible':True,'enabled':True},
           {'ref':'save','role':'button','label':'Save','visible':True,'enabled':True}]
  if script==NATIVE_CONTEXT_JS:
   focus=identity('input','price','price_unit',self.value) if self.editing else identity()
   target=None;row=None
   if args:
    target=identity('input','price','price_unit',self.value) if args['x']>500 else identity('button','save')
    if self.canvas:
     target=identity();target.update(tag='canvas',ref='',bounds=[300,300,1100,900])
    if target['tag']=='input':row={'bounds':[200,380,1000,460],'product':['Native rendered product'],'editor':target,'row_visible':True}
   ctx={'native_geometry':copy.deepcopy(self.geometry),'route_path':self.url.split('8069',1)[1],'document_visible':True,'top_window':True,'form_count':1,
    'form_heading':['Current native record'],'rfq_form':self.family=='purchase','modal_count':0,'viewer_count':0,
    'focus':focus,'focus_in_form':self.editing,'focus_is_body':not self.editing,'target':target,'row':row}
   if self.bad_context=='focus':ctx['focus']['value']='changed'
   if self.bad_context=='modal':ctx['modal_count']=1
   if self.bad_context=='row' and row:ctx['row']['product']=['Different native product']
   if self.bad_context=='window':ctx['top_window']=False
   if self.bad_context=='disabled' and target:ctx['target']['disabled']=True
   if self.bad_context=='global':ctx['focus_in_form']=False;ctx['focus_is_body']=False
   if self.canvas:ctx.update(viewer_count=1,rfq_form=False,form_count=0)
   return ctx
  raise AssertionError('Unexpected JS')
 def screenshot(self,*,type):
  active=self.capture>=2
  state=(self.capture%4) if self.alt and active else 0
  self.capture+=1
  return png(state//2,state%2,self.value,self.bad if active else None,geo=self.geometry,tab=state%2)
 def locator(self,selector):
  ref=selector.split('=')[1].strip('\"]')
  box={'x':780,'y':400,'width':60,'height':40} if ref=='price' else {'x':100,'y':20,'width':60,'height':30}
  return SimpleNamespace(count=lambda:1,is_visible=lambda:True,is_enabled=lambda:True,bounding_box=lambda:box)
 def wait_for_timeout(self,milliseconds):pass
 def doubleclick(self,x,y):self.actions.append(('double_click',x,y));self.editing=True
 def click(self,x,y):
  self.actions.append(('click',x,y))
  if x<500:self.saved=self.value
  else:self.editing=True
 def press(self,key):
  self.actions.append(('key',key))
  if key in ('Control+A','Meta+A'):self.selected=True
  elif key in ('Tab','Enter'):self.editing=False
 def insert(self,text):
  self.actions.append(('type',text));self.value=text if self.selected else self.value+text


def setup(family='purchase'):
 page=FakePage(family);adapter=OdooV066NativeMaterialAdapter(page,task_id='opaque-task',task_binding_sha256='a'*64,instruction='Repair visible business record')
 raw={}
 def sink(index,png):
  path=f'frames/guard-{index}.png';raw[path]=png
  import hashlib
  return {'path':path,'sha256':hashlib.sha256(png).hexdigest()}
 adapter.frame_guard_sink=sink
 return page,adapter,raw


class NativeMaterialTests(unittest.TestCase):
 def run_action(self,adapter,action,raw):
  observation,rendered=adapter.observe_for_model()
  parsed=adapter.parse_current_action(json.dumps(action));result=adapter.dispatch(parsed)
  self.assertNotIn('oracle',str(rendered));receipt=result['public_contract_receipt']
  for field in ('native_material_parse_guard','native_material_dispatch_guard'):
   audited=audit_guard(receipt[field],observation.screenshot_bytes,lambda ref:raw[ref['path']],action=result['action'])
   self.assertEqual(audited['raw_guard_pngs_reopened'],3)
  return receipt
 def test_complete_doubleclick_select_type_enter_save_all_four_families(self):
  for family in ['purchase','inventory','sales','crm']:
   with self.subTest(family=family):
    page,adapter,raw=setup(family);page.alt=family=='purchase'
    for action in [{'type':'double_click','target':{'x':810,'y':420}},{'type':'key','key':'Control+A'},
       {'type':'type','text':'100.0','mode':'insert'},{'type':'key','key':'Enter'},
       {'type':'click','target':{'x':120,'y':35}}]:
     receipt=self.run_action(adapter,action,raw)
     self.assertEqual(receipt['native_material_parse_guard']['mode'],'finite_rfq_material' if family=='purchase' else 'exact_full_png')
    self.assertEqual(page.saved,'100.0');self.assertEqual(len(page.actions),5)
 def test_known_whole_vectors_allowed_only_on_rfq(self):
  for family in ['inventory','sales','crm']:
   page,adapter,_raw=setup(family);page.alt=True;adapter.observe_for_model()
   with self.assertRaises(ContractError):adapter.parse_current_action(json.dumps({'type':'key','key':'Control+A'}))
   self.assertEqual(page.actions,[])
 def test_body_caret_franken_mode_refused_before_action_intent(self):
  for bad in ['body','caret','franken','mode']:
   page,adapter,_raw=setup();page.bad=bad;adapter.observe_for_model()
   with self.assertRaises(ContractError):adapter.parse_current_action(json.dumps({'type':'key','key':'Control+A'}))
   self.assertEqual(page.actions,[])
 def test_native_focus_modal_window_and_row_change_after_parse_refused(self):
  for bad in ['focus','modal','window','row','disabled']:
   page,adapter,_raw=setup();adapter.observe_for_model()
   action=adapter.parse_current_action(json.dumps({'type':'double_click','target':{'x':810,'y':420}}))
   page.bad_context=bad
   with self.assertRaises(ContractError):adapter.dispatch(action)
   self.assertEqual(page.actions,[])
 def test_task_url_frame_and_unequal_action_refused_after_parse(self):
  for change in ['task','url','frame','action']:
   page,adapter,_raw=setup();observation,_=adapter.observe_for_model()
   action=adapter.parse_current_action(json.dumps({'type':'key','key':'Control+A'}))
   if change=='task':adapter.task_id='other-task'
   elif change=='url':page.url='http://127.0.0.1:8069/odoo/purchase/43'
   elif change=='frame':adapter.latest=None
   else:action={**action,'key':'Enter'}
   with self.assertRaises(ContractError):adapter.dispatch(action)
   self.assertEqual(page.actions,[])
 def test_adapter_constructor_rejects_gold_directed_arguments(self):
  for key in ['expected_price_targets','expected_attachment_label','oracle','split']:
   with self.assertRaises(TypeError):OdooV066NativeMaterialAdapter(FakePage('purchase'),task_id='t',task_binding_sha256='a'*64,instruction='visible',**{key:[]})
 def test_auditor_rederives_raw_membership_and_context_rejects_mutations(self):
  page,adapter,raw=setup();page.alt=True;obs,_=adapter.observe_for_model();parsed=adapter.parse_current_action(json.dumps({'type':'key','key':'Control+A'}));result=adapter.dispatch(parsed)
  guard=result['public_contract_receipt']['native_material_parse_guard']
  bad=copy.deepcopy(guard);bad['native_context']['focus']['value']='spoof'
  with self.assertRaises(ValueError):audit_guard(bad,obs.screenshot_bytes,lambda r:raw[r['path']],action=parsed)
  first=guard['sampled_frames'][0]['sampled_frame_ref']['path'];raw[first]=png(bad='body')
  with self.assertRaises(ValueError):audit_guard(guard,obs.screenshot_bytes,lambda r:raw[r['path']],action=parsed)
 def test_reference_and_drag_endpoints_bound_and_audited(self):
  page,adapter,raw=setup();self.run_action(adapter,{'type':'double_click','target':{'ref':'price'}},raw)
  receipt=self.run_action(adapter,{'type':'drag','from':{'ref':'price'},'to':{'x':120,'y':35}},raw)
  guard=receipt['native_material_parse_guard'];self.assertEqual(guard['mode'],'exact_full_png')
  self.assertEqual([r['slot'] for r in guard['native_target_contexts']],['from','to'])
 def test_unenumerated_canvas_target_keeps_strict_coordinate_actions(self):
  page,adapter,raw=setup();page.canvas=True
  receipt=self.run_action(adapter,{'type':'click','target':{'x':700,'y':500}},raw)
  self.assertEqual(receipt['native_material_parse_guard']['mode'],'exact_full_png')
  self.assertEqual(page.actions,[('click',700,500)])
 def test_header_focus_outside_form_has_no_finite_border_allowance(self):
  page,adapter,_raw=setup();page.bad_context='global';page.alt=True;adapter.observe_for_model()
  with self.assertRaises(ContractError):adapter.parse_current_action(json.dumps({'type':'key','key':'Control+A'}))
  self.assertEqual(page.actions,[])
 def test_auditor_refuses_missing_target_records_and_frame_metadata(self):
  page,adapter,raw=setup();obs,_=adapter.observe_for_model()
  action=adapter.parse_current_action(json.dumps({'type':'double_click','target':{'ref':'price'}}));receipt=adapter.dispatch(action)['public_contract_receipt'];guard=receipt['native_material_parse_guard']
  for change in ['empty','point','frame']:
   bad=copy.deepcopy(guard)
   if change=='empty':bad['native_target_contexts']=[];bad['native_context']=bad['observed_native_context']
   elif change=='point':bad['native_target_contexts'][0]['point']['x']+=1
   else:bad['sampled_frames'][0]['observed_frame_sha256']='0'*64
   with self.assertRaises(ValueError):audit_guard(bad,obs.screenshot_bytes,lambda r:raw[r['path']],action=action)
 def test_shared_binding_is_model_and_split_neutral(self):
  binding=public_binding();self.assertEqual(binding['profile'],PROFILE)
  self.assertFalse(binding['gold_directed_adapter_arguments']);self.assertEqual(binding['finite_border_pixels'],9)

if __name__=='__main__':unittest.main()
