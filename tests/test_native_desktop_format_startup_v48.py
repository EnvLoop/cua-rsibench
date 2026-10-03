"""Offline startup ordering and strict preference projection; no native credit."""
import hashlib,json,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from native_desktop_factory import native_format_startup_preset_v48 as preset
from native_desktop_factory import native_editor_runtime_v48 as runtime
from native_desktop_factory import native_editor_runtime_v47 as old
from native_desktop_factory import uniform_model_transport_v11 as legacy
ROOT=Path(__file__).resolve().parents[1]
SCHEMA=b'<oor:component-schema xmlns:oor="http://openoffice.org/2001/registry" oor:name="Common" oor:package="org.openoffice.Office"><component><group oor:name="Save"><group oor:name="Document"><prop oor:name="WarnAlienFormat" oor:type="xs:boolean"><value>true</value></prop></group></group></component></oor:component-schema>'
class Startup(unittest.TestCase):
 def test_primary_schema_boolean_default_mandatory(self):
  self.assertTrue(preset.installed_default(SCHEMA))
  for raw in (SCHEMA.replace(b'true',b'false'),SCHEMA.replace(b'xs:boolean',b'xs:string'),SCHEMA.replace(b'WarnAlienFormat',b'Other'),SCHEMA.replace(b'Common',b'Other')):
   with self.assertRaises(ValueError):preset.installed_default(raw)
 def test_exact_preference_required_and_all_other_xml_bytes_preserved(self):
  extra=b'<item oor:path="/other"><prop oor:name="Other"><value>unchanged</value></prop></item>'
  raw=preset.XML.replace(b'</oor:items>',extra+b'</oor:items>')
  clean=preset.parent_registry_projection(raw)
  self.assertIn(extra,clean);self.assertNotIn(b'WarnAlienFormat',clean)
  for invalid in (raw.replace(b'false',b'true'),raw.replace(b'false',b'unknown'),raw.replace(b'/Save/Document',b'/Security'),raw.replace(b'</oor:items>',preset.XML[preset.XML.index(b'<item'):preset.XML.index(b'</item>')+7]+b'</oor:items>')):
   with self.assertRaises(ValueError):preset.parent_registry_projection(invalid)
 def test_other_property_in_same_item_retained(self):
  raw=preset.XML.replace(b'</item>',b'<prop oor:name="Unrelated" oor:op="fuse"><value>true</value></prop></item>')
  self.assertIn(b'Unrelated',preset.parent_registry_projection(raw))
 def test_preference_setup_precedes_original_stage_and_open_for_all_apps(self):
  fn=runtime.StartupGuest.prepare
  for filename in ('fixture.xlsx','fixture.docx','fixture.pptx'):
   events=[];files={}
   class FakeFiles:
    def write(self,path,data):events.append(('stage',path));files[path]=data
    def read(self,path,**kwargs):return files[path]
   def run(command):events.append(('fresh-check',command));return SimpleNamespace(exit_code=0)
   sandbox=SimpleNamespace(sandbox_id='offline-no-credit',get_info=lambda **k:SimpleNamespace(template_id='offline',envd_version='offline',cpu_count=1,memory_mb=1),files=FakeFiles(),commands=SimpleNamespace(run=run),open=lambda path:events.append(('open',path)),press=lambda key:events.append(('key',key)))
   guest=object.__new__(runtime.StartupGuest);guest.sandbox=sandbox;guest.receipt={};guest.remote='/home/user/'+filename;guest.filename=filename;guest.root=ROOT;guest.out=ROOT;guest.persist=lambda:None
   def apply(guest):events.append(('preset',False))
   def probe(*a,**kw):return None,{'content_tree_sha256':'a'*64},{'identity_kind':'offline','raw_tree_sha256':'a'*64,'raw_tree_equals_legacy_reference':True}
   with patch.dict(fn.__globals__,preset=SimpleNamespace(setup=apply),profile=SimpleNamespace(attest=lambda **k:events.append(('attest',k['app_kind']))),runtime_policy=SimpleNamespace(execute_probe=probe),wait_for_document_ready=lambda *a:None,time=SimpleNamespace(sleep=lambda *a:None)):
    fn(guest,source=b'offline original bytes',guest_reference={'provider_template_id':'offline','provider_envd_version':'offline','provider_shape':{'vcpu':1,'memory_mb':1}},profile_reference=ROOT/'offline.private')
   labels=[x[0] for x in events]
   self.assertLess(labels.index('fresh-check'),labels.index('preset'));self.assertLess(labels.index('preset'),labels.index('stage'));self.assertLess(labels.index('stage'),labels.index('open'));self.assertEqual(files[guest.remote],b'offline original bytes')
 def test_all_roles_same_class_and_guards_old_sources_unchanged(self):
  modules=(old,legacy);before={m:(Path(m.__file__).read_bytes(),dict(vars(m))) for m in modules}
  previous=old.factory(manifest=old.source_manifest(ROOT),source_root=ROOT);factory=runtime.factory(manifest=runtime.source_manifest(ROOT),source_root=ROOT)
  actors=[]
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory)
   for role in factory.manifest['actor_paths']:
    for filename in ('fixture.xlsx','fixture.docx','fixture.pptx'):
     out=root/role/Path(filename).suffix[1:];out.mkdir(mode=0o700,parents=True)
     actor=factory.wrap_owned_guest(SimpleNamespace(sandbox_id='offline-'+role,commands=SimpleNamespace(),files=SimpleNamespace()),root=root,out=out,filename=filename,lease_started_monotonic=time.monotonic());actors.append(actor)
     self.assertIs(type(actor),factory.actor_class);self.assertIn(runtime.StartupGuest,type(actor).__mro__)
  self.assertEqual(len(actors),21)
  for name in ('capture','native_input','envelope','lease_check'):
   self.assertIs(getattr(factory.actor_class,name),getattr(previous.actor_class,name))
  for m,(raw,namespace) in before.items():self.assertEqual(Path(m.__file__).read_bytes(),raw);self.assertEqual(dict(vars(m)),namespace)
  self.assertEqual(factory.manifest['task_policy'],{'max_actions':90,'actor_seconds':720,'lease_seconds':1200});self.assertFalse(runtime.public_binding(ROOT)['native_qualification_passed'])
  with self.assertRaises(ValueError):factory.require_activation()
if __name__=='__main__':unittest.main()
