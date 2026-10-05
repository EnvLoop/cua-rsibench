"""Public package-local successor loader. No private history/authority imports."""
from pathlib import Path
import hashlib,json,os,sys,importlib
RUNTIME=Path(__file__).resolve().parent/'runtime'
def source_binding():
 lock=json.loads((RUNTIME/'source-lock.json').read_text())
 if set(lock)!={str(p.relative_to(RUNTIME)) for p in RUNTIME.rglob('*.py')}:raise RuntimeError('bundled public source closure changed')
 for name,expected in lock.items():
  path=RUNTIME/name
  if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise RuntimeError('bundled public source hash changed')
 own={str(p.relative_to(Path(__file__).parent)):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')}
 return {'schema':'public-odoo-reference-source-v5','public_guard_source_lock':lock,'public_successor_sources':own,
   'compose_sha256':hashlib.sha256((Path(__file__).parent/'compose.yaml').read_bytes()).hexdigest(),'personal_paths_or_historical_receipts_required':False,'models':0,'training':False,'reference_extension':{'one_guarded_current_active_form_tab_click_after_original_Save':True,'same_native_DOM_control_and_eligible_owned_focus_required':True,'strict_observer_unmodified':True,'native_window_equality_before_and_after_focus_click':True,'original_native_focus_ref_registration_followed_by_current_DOM_reread':True,'extra_Save_or_retry':False,'native_guard_relaxed':False}}
def activate(workspace):
 worker=Path(workspace).resolve();os.environ['ENVLOOP_ODOO_WORKER_DIR']=str(worker)
 paths=[RUNTIME,RUNTIME/'src',RUNTIME/'enterprise_fallback/odoo18']
 for path in reversed(paths):
  if str(path) not in sys.path:sys.path.insert(0,str(path))
 source_binding()
 for name,loaded in list(sys.modules.items()):
  if name.split('.')[0] not in ('cursibench','enterprise_fallback','native_desktop_factory'):continue
  locations=list(getattr(loaded,'__path__',[]))
  if getattr(loaded,'__file__',None):locations.append(loaded.__file__)
  if not locations or any(not Path(location).resolve().is_relative_to(RUNTIME.resolve()) for location in locations):raise RuntimeError('foreign_runtime_namespace_loaded')
 for name in ('factory','worker_lease','verify','reset'):
  loaded=sys.modules.get(name)
  expected=RUNTIME/'enterprise_fallback/odoo18'/f'{name}.py'
  if loaded and Path(loaded.__file__).resolve()!=expected.resolve():raise RuntimeError('fresh process required; stale runtime module detected')
 modules=[importlib.import_module(name) for name in ('factory','worker_lease','verify','reset')]
 if any(m.PRIVATE!=worker/'private' for m in modules):raise RuntimeError('public worker scope mismatch')
 from enterprise_fallback.odoo18.odoo_v066_native_surface_adapter_v14 import OdooV066NativeSurfaceAdapter
 return (*modules,OdooV066NativeSurfaceAdapter)
