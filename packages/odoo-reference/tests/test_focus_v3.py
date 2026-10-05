"""Actual v3 helper + Journal on fake native controls, real O_EXCL files."""
import unittest,tempfile,time,json,copy,hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from odoo_reference.control import Journal
from odoo_reference.focus import restore_owned_focus,TAB_SELECTOR
from test_public_package import SCOPE  # activates the package runtime before probe imports
from probe_fixture import png

def fact(page):
 return {'role':'tab','active_tab':page.active,'disabled':False,'aria_disabled':None,'connected':page.connected,'same_document':True,'inside_current_form':page.inside,'native_V5_chain_visible':page.visible,'native_path':[{'tag':'BUTTON','index':0,'id':'synthetic-tab'}],'element_ref':page.native_ref,'focused_same_element':page.focused,'document_url':page.url,'rect':{'x':1,'y':1,'width':8,'height':8}}
class Handle:
 def __init__(self,page):self.page=page
 def evaluate(self,script):
  assert 'document.activeElement===el' in script
  return fact(self.page)
 def bounding_box(self):return {'x':1,'y':1,'width':8,'height':8}
 def dispose(self):pass
class Locator:
 def __init__(self,page):self.page=page
 def filter(self,visible):assert visible;return self
 def element_handles(self):return [Handle(self.page) for _ in range(self.page.count)]
class Page:
 def __init__(self):self.url='http://127.0.0.1/odoo/purchase/1';self.count=1;self.connected=True;self.active=True;self.visible=True;self.inside=True;self.focused=False;self.native_ref="c-tab";self.focus_effect=True;self.context=object()
 def locator(self,selector):assert selector==TAB_SELECTOR;return Locator(self)
class Adapter:
 def __init__(self,page,root):
  self.page=page;self.calls=0;self.status="applied";self.window="a"*64;self.mutate_window=False;self.principal="res.users:2";self.mutate_lease=False;self.mutate_principal=False;self.started=time.monotonic();self.actor_clock=SimpleNamespace(deadline=self.started+720,check=lambda _:None);lock_path=root/'held.lock';lock_path.write_bytes(b'public-fake-lock');lock_path.chmod(0o600);credential=root/'held.creds';credential.write_bytes(b'public-fake-credential');credential.chmod(0o600);self.boundary=SimpleNamespace(private=root,module=SimpleNamespace(require_worker_lease=lambda **_:None),lock_path=lock_path,lock=b'public-fake-lock',credentials_path=credential,credentials_sha=hashlib.sha256(credential.read_bytes()).hexdigest(),window_sha='a'*64,lease={'expires_at':self.started+1200},owns=lambda p,m:p is page and m['physical_url']==page.url and m['app_shell'] is True and m['account_principal']=='res.users:2')
 def _meta(self):
  if self.page.focused:self.page.native_ref='nf-tab'
  return {'visible':True,'top_window':True,'app_shell':True,'physical_url':self.page.url,'native_window_sha256':self.window,'native_capture_monotonic':time.monotonic(),'account_principal':self.principal,'focus_owned_app':self.page.focused,'focus':{'tag':'button' if self.page.focused else 'body','ref':'nf-tab' if self.page.focused else 'body'}}
 def observe_for_model(self,**_):return SimpleNamespace(screenshot={'width':20,'height':20},screenshot_bytes=png(),controls=[SimpleNamespace(ref='c-tab')]),{}
 def parse_current_action(self,raw):return json.loads(raw)
 def dispatch(self,action):
  assert action['type']=='click';self.calls+=1;self.page.focused=self.page.focus_effect

  if self.mutate_lease:self.boundary.lease['expires_at']+=1
  if self.mutate_principal:self.principal='res.users:3'
  if self.mutate_window:self.window='b'*64
  return {'status':self.status,'public_contract_receipt':{'synthetic':True}}
class FocusTests(unittest.TestCase):
 def setup_case(self):
  root=Path(tempfile.mkdtemp(prefix='public-v3-focus-files-'));root.chmod(0o700);page=Page();adapter=Adapter(page,root);journal=Journal(adapter,page,root);journal.trace=[{'step':0}];manual={'phase':'positive','status':'saved_native_indicator','ended_monotonic':time.monotonic(),'samples':[{'native':{'url':page.url}}]};return root,page,adapter,journal,manual
 def test_actual_helper_one_current_guarded_click_and_files(self):
  root,page,adapter,journal,manual=self.setup_case()
  with patch('subprocess.Popen',side_effect=AssertionError('native_ctor_forbidden')),patch('playwright.sync_api.sync_playwright',side_effect=AssertionError('native_ctor_forbidden')):
   proof=restore_owned_focus(page,journal,'positive',manual)
  self.assertEqual(adapter.calls,1);self.assertEqual(len(journal.trace),2);self.assertTrue(proof['after_selection']['focused_same_element']);self.assertTrue(proof['native_after']['focus_owned_app'])
  intent=json.loads((root/'actions/step-001-intent.private.json').read_bytes());self.assertEqual(intent['selected_native_control']['element_ref'],'c-tab');self.assertEqual(intent['normalized_action']['type'],'click')
  self.assertTrue((root/'post-save-focus-attempt.private.json').exists());self.assertTrue((root/'post-save-focus-proof.private.json').exists())
  with self.assertRaises(FileExistsError):restore_owned_focus(page,journal,'positive',manual)
  self.assertEqual(adapter.calls,1)
 def test_ambiguous_hidden_inactive_or_outside_form_refuse_before_input(self):
  for key,value in [('count',2),('visible',False),('active',False),('inside',False),('connected',False)]:
   root,page,adapter,journal,manual=self.setup_case();setattr(page,key,value)
   with self.assertRaises(RuntimeError):restore_owned_focus(page,journal,'positive',manual)
   self.assertEqual(adapter.calls,0);self.assertTrue((root/'post-save-focus-attempt.private.json').exists())
 def test_remaining_BODY_focus_stops_without_retry(self):
  root,page,adapter,journal,manual=self.setup_case();page.focus_effect=False
  with self.assertRaises(RuntimeError):restore_owned_focus(page,journal,'positive',manual)
  self.assertEqual(adapter.calls,1);self.assertFalse(json.loads((root/'post-save-focus-proof.private.json').read_bytes())['native_after']['focus_owned_app'])
 def test_wrong_document_before_click_has_no_fallback(self):
  root,page,adapter,journal,manual=self.setup_case();page.url+='/wrong'
  with self.assertRaises(RuntimeError):restore_owned_focus(page,journal,'positive',manual)
  self.assertEqual(adapter.calls,0)
 def test_unapplied_click_changed_principal_or_lease_stops_without_retry(self):
  for setting,value in [('status','rejected'),('mutate_principal',True),('mutate_lease',True)]:
   root,page,adapter,journal,manual=self.setup_case();setattr(adapter,setting,value)
   with self.assertRaises(RuntimeError):restore_owned_focus(page,journal,'positive',manual)
   self.assertEqual(adapter.calls,1)
 def test_saved_focus_actual_file_replay_and_tamper(self):
  from odoo_reference.audit import audit_post_save_focus
  from odoo_reference.control import write
  from odoo_reference.observer_audit import ImmutableSavedReader
  root,page,adapter,journal,manual=self.setup_case();proof=restore_owned_focus(page,journal,'positive',manual)
  write(root/'surface-guard/turn-001/observation-native.private.json',{'targets':[{'ref':'c-tab'}]})
  write(root/'actor-clock/start.private.json',{'actor_deadline_monotonic':adapter.actor_clock.deadline})
  write(root/'surface-guard/lease-boundary.private.json',{'native_avatar_principal':'res.users:2','window_sha256':'a'*64,'lock_sha256':hashlib.sha256(adapter.boundary.lock).hexdigest(),'credential_file_sha256':adapter.boundary.credentials_sha})
  write(root/'surface-guard/turn-001/observation-envelope.private.json',{'lease':adapter.boundary.lease})
  write(root/'reference-priority-autosave-test-intent.private.json',{'started_monotonic':time.monotonic(),'actor_action_count_before':2})
  result=audit_post_save_focus(ImmutableSavedReader(),root,'positive',manual);self.assertTrue(result['eligible_owned_focus_proven'])
  file=root/'post-save-focus-proof.private.json';original=file.read_bytes()
  for field,value in [('actor_action_count_after',3),('original_Save_proof_sha256','x'),('ended_monotonic',adapter.actor_clock.deadline+1)]:
   bad=json.loads(original);bad[field]=value;file.write_bytes(json.dumps(bad).encode())
   with self.assertRaises(RuntimeError):audit_post_save_focus(ImmutableSavedReader(),root,'positive',manual)
  file.write_bytes(original);bad=json.loads(original);bad['native_after']['focus_owned_app']=False;file.write_bytes(json.dumps(bad).encode())
  with self.assertRaises(RuntimeError):audit_post_save_focus(ImmutableSavedReader(),root,'positive',manual)
  file.write_bytes(original);dispatch=root/'actions/step-001-result.private.json';old=dispatch.read_bytes();bad=json.loads(old);bad['dispatch']['status']='rejected';dispatch.write_bytes(json.dumps(bad).encode())
  with self.assertRaises(RuntimeError):audit_post_save_focus(ImmutableSavedReader(),root,'positive',manual)
 def test_changed_after_click_native_window_refused_no_retry(self):
  root,page,adapter,journal,manual=self.setup_case();adapter.mutate_window=True
  with self.assertRaisesRegex(RuntimeError,'public_v3_native_eligible_owned_focus_not_proven'):restore_owned_focus(page,journal,'positive',manual)
  self.assertEqual(adapter.calls,1);self.assertEqual(len(journal.trace),2)
  proof=json.loads((root/'post-save-focus-proof.private.json').read_bytes());self.assertNotEqual(proof['native_after']['native_window_sha256'],adapter.boundary.window_sha)
 def test_original_metadata_assigns_ref_before_current_DOM_reread(self):
  root,page,adapter,journal,manual=self.setup_case();proof=restore_owned_focus(page,journal,'positive',manual)
  self.assertEqual(adapter.calls,1)
  self.assertEqual(proof['after_selection_before_native_metadata']['element_ref'],'c-tab')
  self.assertEqual(proof['after_selection']['element_ref'],'nf-tab')
  self.assertEqual(proof['native_after']['focus']['ref'],proof['after_selection']['element_ref'])
  self.assertEqual(proof['after_selection_before_native_metadata']['native_path'],proof['after_selection']['native_path'])
if __name__=='__main__':unittest.main()
