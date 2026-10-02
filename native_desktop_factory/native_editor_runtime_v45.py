"""Uniform V45 guest with trusted local metadata-only medium evidence."""
import argparse,hashlib,inspect,json,shlex,time
from pathlib import Path
from types import SimpleNamespace
from . import native_atspi_warning_policy_v44 as warning44
from . import native_window_current_runtime as base
from . import native_editor_reader_v45 as reader
from . import native_editor_capability_v42 as capability
from . import native_editor_evidence_v45 as evidence

BASE_SHA='49902ed749c462c27e1789e5a7dce10366a7feefea0dcbd3ec1f72bc35889d74'
EXTRA=('native_desktop_factory/native_editor_evidence_v44.py','native_desktop_factory/native_editor_reader_v44.py','native_desktop_factory/native_editor_runtime_v44.py','tests/test_native_desktop_mode_path_v45.py','native_desktop_factory/native_editor_evidence_v43.py','native_desktop_factory/native_editor_reader_v43.py','native_desktop_factory/native_editor_runtime_v43.py','native_desktop_factory/native_virtual_cell_identity_v44.py','native_desktop_factory/native_atspi_warning_policy_v44.py','native_desktop_factory/native_editor_evidence_v42.py','native_desktop_factory/native_editor_reader_v42.py','native_desktop_factory/native_editor_runtime_v42.py','native_desktop_factory/native_editor_capability_v42.py','native_desktop_factory/native_editor_evidence_v45.py',
 'native_desktop_factory/native_editor_reader_v45.py','native_desktop_factory/native_editor_runtime_v45.py','tests/test_native_desktop_capability_v42.py',
 'tests/test_native_desktop_capability_refresh_v43.py','tests/test_native_desktop_virtual_cell_identity_v44.py')
if hashlib.sha256(Path(base.__file__).read_bytes()).hexdigest()!=BASE_SHA:raise ValueError('Frozen V41 runtime changed')
parent=base.base.current.base.parent

def source_manifest(root=None):
 root=Path(root or Path(__file__).resolve().parents[1]);old=base.source_manifest(root)
 return {**old,'schema':'cua-native-editor-capability-runtime-source-v45','native_reader_schema':reader.SCHEMA,
  'source_sha256s':{**old['source_sha256s'],**{name:parent.digest((root/name).read_bytes()) for name in EXTRA}},
  'raw_native_flags_preserved':True,'capability_build':capability.BUILD,'evaluator_medium_query':'XStorable.isReadonly_metadata_only_local_owned_pipe',
  'actor_office_api_available':False,'virtual_cell_identity':'same_current_owned_Table_native_index_row_column_roundtrip','owned_pipe_listener_and_connections_distinguished':True,'edit_mode_current_path':'bootstrap_owned_forward_edges_reopened_twice_current_state_and_medium_each_use','native_qualification_passed':False,'old_results_reclassified':False}

def factory(*,manifest,source_root=None,qualification=None,independent_raw_auditor=None):
 original=base.factory;ns={**original.__globals__,'reader':reader,'source_manifest':source_manifest}
 source=inspect.getsource(original)
 peers="'native_window_current_reader.py','native_client_coordinate_probe.py'),"
 path="parent.REMOTE+'/native_window_current_reader.py'"
 parent.require(source.count(peers)==1 and source.count(path)==1,'Frozen V41 editor integration changed')
 source=source.replace(peers,"'native_window_current_reader.py','native_client_coordinate_probe.py','native_editor_reader_v45.py','native_editor_capability_v42.py','native_editor_evidence_v45.py','native_virtual_cell_identity_v44.py'),")
 source=source.replace(path,"parent.REMOTE+'/native_editor_reader_v45.py'")
 source=source.replace("warning.FILES|{'native_window_current_reader.py'}","warning.FILES|{'native_window_current_reader.py','native_editor_evidence_v45.py','native_editor_reader_v45.py'}")
 exec(compile(source,__file__,'exec'),ns)
 result=ns['factory'](manifest=manifest,source_root=source_root,qualification=qualification,independent_raw_auditor=independent_raw_auditor)
 result.actor_class.native_probe.__globals__['warning_policy']=SimpleNamespace(classify=warning44.classify)
 guest_class=result.actor_class;original_prepare=guest_class.prepare
 def prepare(self,**kwargs):
  original_prepare(self,**kwargs)
  self.editor_pipe='envloop_v45_'+parent.digest(self.sandbox.sandbox_id.encode())[:20]
  command='libreoffice '+shlex.quote('--accept=pipe,name='+self.editor_pipe+';urp;StarOffice.ServiceManager')+' --nodefault --norestore'
  parent.json_put(self.root,self.out/'editor-listener-intent.private.json',{'command_sha256':parent.digest(command.encode()),'local_evaluator_only':True,'metadata_methods':['getURL','getLocation','hasLocation','isReadonly'],'actor_api_exposed':False})
  launch=self.sandbox.commands.run(command,background=True,timeout=0,request_timeout=12)
  parent.json_put(self.root,self.out/'editor-listener-return.private.json',{'process_pid':getattr(launch,'pid',None),'automatic_retries':0})
  self.refresh_editor_bootstrap()
 def refresh(self):
  started=time.monotonic();before=self.read_saved();before_image=bytes(self.sandbox.screenshot())
  parent.put(self.root,self.out/'editor-before-menu.png',before_image)
  parent.json_put(self.root,self.out/'editor-menu-open-intent.private.json',{'keys':['alt','e'],'trusted_ui_probe':True,'business_edit':False,'started_monotonic':started})
  self.sandbox.press(['alt','e'])
  command='GI_TYPELIB_PATH='+shlex.quote(parent.bootstrap.PREFIX)+' python3 '+shlex.quote(parent.REMOTE+'/native_editor_evidence_v45.py')+' --bootstrap --filename '+shlex.quote(self.filename)+' --pipe '+shlex.quote(self.editor_pipe)
  raw=self.sandbox.commands.run(command,timeout=30,request_timeout=40)
  parent.json_put(self.root,self.out/'editor-mode-bootstrap-command.private.json',{'exit_code':raw.exit_code,'stdout':raw.stdout,'stderr':raw.stderr,'command_sha256':parent.digest(command.encode())})
  parent.json_put(self.root,self.out/'editor-menu-close-intent.private.json',{'key':'Escape','trusted_ui_probe':True,'business_edit':False})
  self.sandbox.press('Escape')
  parent.put(self.root,self.out/'editor-after-menu.png',bytes(self.sandbox.screenshot()))
  parent.require(raw.exit_code==0 and not raw.stderr,'Current native editor mode bootstrap failed')
  seed=json.loads(raw.stdout)
  parent.require(seed.get('checked') is True and seed.get('enabled') is True and seed.get('sensitive') is True and seed.get('visible_initial_native_proof') is True,'Native current Edit Mode not positively proved')
  self.sandbox.files.write(str(evidence.SEED),parent.canonical(seed))
  parent.require(self.read_saved()==before,'Trusted menu probe changed saved task artifact')
  self.editor_bootstrap_wall_seconds=time.monotonic()-started
  self.editor_actor_wall_started_monotonic=started
  parent.json_put(self.root,self.out/'editor-bootstrap-state.private.json',{'seed':seed,'elapsed_seconds':self.editor_bootstrap_wall_seconds,'include_in_actor_wall_time':True,'saved_bytes_unchanged':True,'selection_focus_restore':'Escape returns original editor; actual focus is rechecked on every native probe'})
 guest_class.prepare=prepare;guest_class.refresh_editor_bootstrap=refresh
 original_dispatch=guest_class.dispatch_model
 def dispatch(self,raw,observation,*,actor_deadline):
  effective=min(actor_deadline,getattr(self,'editor_actor_wall_started_monotonic',actor_deadline-720)+720)
  return original_dispatch(self,raw,observation,actor_deadline=effective)
 guest_class.dispatch_model=dispatch
 return result

control_driver=base.control_driver

def public_binding(root=None):
 manifest=source_manifest(root)
 return {'schema':'cua-native-editor-capability-public-binding-v45','source_manifest_sha256':parent.digest(parent.canonical(manifest)),
  'native_policy_sha256':manifest['native_policy_sha256'],'native_reader_schema':manifest['native_reader_schema'],'actor_paths':manifest['actor_paths'],
  'native_qualification_passed':False,'raw_native_flags_preserved':True,'model_calls':0,'tinker_calls':0,'old_results_reclassified':False}

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['source','public-binding']);parser.add_argument('--root',type=Path);args=parser.parse_args()
 print(json.dumps(source_manifest(args.root) if args.mode=='source' else public_binding(args.root),sort_keys=True,separators=(',',':')))
