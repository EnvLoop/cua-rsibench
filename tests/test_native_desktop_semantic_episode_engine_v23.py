"""The actual current episode loop continues after one semantic rejection."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from native_desktop_factory import semantic_episode_engine_v23 as engine
from native_desktop_factory.factory import digest
from tests.test_native_desktop_uniform_model_transport_v11 import FakeModelGuest,FakeSampler
from tests.test_native_desktop_selection_worker_v066 import source_case

class EpisodeTests(unittest.TestCase):
 def test_current_loop_never_labels_rejection_applied_and_all_slots_use_semantic_factory(self):
  self.assertIs(engine.DesktopSemanticModelWorker._create.__globals__['transport'],engine.transport)
  source,_,positive,oracle,ext=source_case('calc-growth')
  for owner in ['shared-base','astra','sol56','sol6','luna6']:
   with self.subTest(owner=owner),tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);root.chmod(0o700);guest=root/'guest.json';guest.write_text('{}');mapping=root/'map.json';engine.write(mapping,{'variant_salt':'offline-only-'*4})
    identity={'task_id':'fixture','package_sha256':'a'*64};package={'identity':identity,'source':source,'oracle':oracle,'filename':'train'+ext,'instruction':'Visible fixture task','guest_reference_path':str(guest)}
    admitted={'guest_public':str(guest),'scoped_reference':str(root/'profile'),'private_map':str(mapping)}
    made=[]
    class Model(engine.DesktopSemanticModelWorker):
     def _create(self,**kwargs):
      out=kwargs['gui_root']/identity['task_id']/kwargs['phase'];out.mkdir(parents=True,mode=0o700)
      native=FakeModelGuest(kwargs['gui_root'],out,package['filename'],source,positive,kwargs['phase'],identity)
      original=native.dispatch_model
      def dispatch(raw,obs,**args):
       action,evidence=original(raw,obs,**args)
       if obs.step==0:native.clicked=False;evidence['native_status']='rejected'
       else:evidence['native_status']='applied'
       return action,evidence
      native.dispatch_model=dispatch;made.append(native);return native
     def _audit_episode(self,**kwargs):
      # Native policy is separately tested; this fixture isolates actual loop
      # bookkeeping without manufacturing a native AX qualification.
      trace=json.loads((kwargs['out']/'actions.private.json').read_bytes());self.test_trace=trace
    class Sampler(FakeSampler):
     def sample(self,**kwargs):
      result=super().sample(**kwargs);step=kwargs['observation'].step
      result['text']='{"type":"click","target":{"x":500,"y":400}}' if step<2 else '{"type":"finish"}'
      return result
    class Paid:
     attempt_id='synthetic-'+owner
     def invoke(self,**kwargs):
      result=kwargs['provider'](kwargs['request']);return result,digest(engine.integration.canonical(result)),'actual-fixture-'+kwargs['suffix']
    model=Model(study=None,admissions_path=Path('/unused'),proposal_path=Path('/unused'));result,out,trace,_,outcome=model._episode(admitted=admitted,package=package,ordinal=0,batch=root,paid=Paid(),sampler=Sampler())
    self.assertEqual([r['status'] for r in trace],['rejected','applied','applied']);self.assertEqual(outcome,'finished');self.assertEqual(result['score'],1);self.assertTrue(all(g.killed for g in made))
    self.assertEqual(len(made),2);self.assertNotEqual(made[0].sandbox.sandbox_id,made[1].sandbox.sandbox_id)

if __name__=='__main__':unittest.main()
