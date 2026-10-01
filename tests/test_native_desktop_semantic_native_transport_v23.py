"""Source-only native policy call paths. Synthetic IO is not qualification."""
import io
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from PIL import Image
from cursibench import native_surface_guard_policy_v1 as guard
from native_desktop_factory import semantic_native_transport_v23 as transport
from native_desktop_factory.factory import digest


def png(color):
 out=io.BytesIO();Image.new('RGB',(1280,800),color).save(out,format='PNG');return out.getvalue()

class SemanticTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.root.chmod(0o700);self.out=self.root/'fixture'/'actor';self.out.mkdir(mode=0o700,parents=True)
  self.meta={'schema':transport.PROBE_SCHEMA,'status':'observed','probe_source_sha256':digest(transport.PROBE_SOURCE.read_bytes()),'native_api':'x11-and-gi-atspi','window_id_sha256':'a'*64,'native_pid':123,'native_uid':1000,
   'account_sha256':'b'*64,'owned_document_window':True,'owned_native_application':True,'viewport':[1280,800],'view_id':'calc','context_id':'native-current-window','modal_id':'none','focus_id':'field',
   'focus_editable':True,'focus_fill_scope_verified':True,'targets':[{'ref':'field','bounds':[20,30,200,40],'visible':True,'enabled':True,'obscured':False,'keyboard':True,'actions':['click','double_click','type','key','scroll','drag']}],
   'native_mutations':0,'raster_equality_used':False}
  self.native_calls=[];self.images=0
  def screenshot():self.images+=1;return png('white' if self.images==1 else 'blue')
  self.sandbox=SimpleNamespace(sandbox_id='synthetic-owned',commands=SimpleNamespace(run=lambda *a,**k:SimpleNamespace(exit_code=0,stdout=json.dumps(self.meta),stderr='')),screenshot=screenshot,is_running=lambda **kwargs:True)
  self.proxy=SimpleNamespace(left_click=lambda *a,**k:self.native_calls.append(('click',a or (k['x'],k['y']))),double_click=lambda *a:self.native_calls.append(('double',a)),press=lambda *a:self.native_calls.append(('key',a)),write=lambda *a:self.native_calls.append(('text',a)),current_actor_step=None)
  self.actor=object.__new__(transport.SemanticModelGuest);self.actor.sandbox=self.sandbox;self.actor.proxy=self.proxy;self.actor.root=self.root;self.actor.out=self.out;self.actor.filename='fixture.xlsx';self.actor.killed=False;self.actor.quarantined=False;self.actor.last_envelope=None;self.actor.last_observation=None;self.actor.pending=False;self.actor.native_sequence=0;self.actor.consumed=set()
  now=time.monotonic();ref=transport.json_put(self.root,self.out/'lease.private.json',{'owned':True});ref['kind']='lease_evidence'
  self.actor.lease={'schema':'native-surface-lease-v1','lease_id':'synthetic-owned','cell_id':'desktop-native','account_sha256':'b'*64,'workspace_sha256':'c'*64,'window_sha256':'a'*64,'owner_sha256':'d'*64,'issued_at':now-1,'expires_at':now+1200,'evidence':ref}
 def tearDown(self):self.temp.cleanup()
 def observation(self):return self.actor.observe(identity={'task_id':'fixture','package_sha256':'e'*64},instruction='Visible task only',step=0)
 def test_changed_pixels_are_not_retried_and_safe_wrong_target_is_applied_once(self):
  obs=self.observation();action,evidence=self.actor.dispatch_model('{"type":"click","target":{"x":40,"y":40}}',obs,actor_deadline=time.monotonic()+720)
  self.assertEqual(evidence['native_status'],'applied');self.assertEqual(self.native_calls,[('click',(40,40))]);self.assertEqual(self.images,2);self.assertEqual(evidence['caret_resamples'],[])
 def test_actual_current_disabled_target_rejects_without_driver_or_retarget(self):
  obs=self.observation();self.meta['targets'][0]['enabled']=False;action,evidence=self.actor.dispatch_model('{"type":"click","target":{"x":40,"y":40}}',obs,actor_deadline=time.monotonic()+720)
  self.assertEqual(evidence['native_status'],'rejected');self.assertEqual(self.native_calls,[]);self.assertIn(obs.frame_id,self.actor.consumed)
 def test_owned_window_loss_hard_stops_before_native_io(self):
  obs=self.observation();self.meta['window_id_sha256']='f'*64
  with self.assertRaises(guard.GuardError):self.actor.dispatch_model('{"type":"click","target":{"x":40,"y":40}}',obs,actor_deadline=time.monotonic()+720)
  self.assertEqual(self.native_calls,[])
 def test_keyboard_reopens_actual_native_focus_after_pointer_before_text(self):
  obs=self.observation();_,evidence=self.actor.dispatch_model('{"type":"type","target":{"x":40,"y":40},"text":"wrong safe value","mode":"fill"}',obs,actor_deadline=time.monotonic()+720)
  self.assertEqual(evidence['native_status'],'applied');self.assertEqual([c[0] for c in self.native_calls],['click','key','text']);self.assertTrue(any(json.loads(p.read_bytes())['phase']=='verified-keyboard-focus' for p in self.out.glob('native-probe-*.private.json')))
 def test_unknown_native_probe_never_becomes_safe_canvas(self):
  self.meta['status']='unavailable_or_unsafe'
  with self.assertRaises(ValueError):self.observation()
  self.assertEqual(self.native_calls,[])

if __name__=='__main__':unittest.main()
