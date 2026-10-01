"""Source registration only; native qualification is an independent epoch."""
from pathlib import Path
import hashlib
from . import full_study_policy_amendment_v2 as policy
from . import full_study_matrix_v1 as matrix

ODOO_SUPPLEMENT_COMMIT='06b18ef7ded4e284defa24c101937483552c5854'
ODOO_REQUIRED_FILES=('enterprise_fallback/odoo18/native_surface_final_worker_v1.py',
    'enterprise_fallback/odoo18/native_surface_shared_base_v1.py','tools/odoo_native_surface_final_v1.py')


def register(root,*,cell_id,native_source_sha256s,actor_clock_source_sha256,native_epoch_sha256,qualified=False):
    if cell_id not in matrix.CELLS or not isinstance(native_source_sha256s,dict) or not native_source_sha256s:
        raise ValueError('explicit_cell_source_registration_required')
    if qualified is not False:raise ValueError('source_registration_cannot_assert_native_qualification')
    root=Path(root).resolve()
    for name,digest in native_source_sha256s.items():
        path=root/name
        if Path(name).is_absolute() or '..' in Path(name).parts or path.is_symlink() or not path.resolve().is_relative_to(root) or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise ValueError('registered_native_source_bytes_changed')
    if not all(isinstance(v,str) and len(v)==64 and all(c in '0123456789abcdef' for c in v) for v in (actor_clock_source_sha256,native_epoch_sha256)):
        raise ValueError('fresh_native_clock_epoch_required')
    if actor_clock_source_sha256 not in native_source_sha256s.values():raise ValueError('actor_clock_source_not_in_reviewed_closure')
    if cell_id=='odoo-community' and not set(ODOO_REQUIRED_FILES)<=set(native_source_sha256s):raise ValueError('odoo_supplemental_final_and_shared_base_source_required')
    return {'schema':'cua-full-study-native-counterpart-registration-v22','cell_id':cell_id,
        'native_source_sha256s':native_source_sha256s,'actor_clock_source_sha256':actor_clock_source_sha256,
        'native_epoch_sha256':native_epoch_sha256,'all_five_slots_same_source':True,
        'task_policy':{'max_actions':90,'actor_seconds':720,'lease_seconds':1200},
        'separate_actor_and_lifecycle_clocks':True,'qualified_native_epoch':qualified,
        'old_epoch_reclassified':False,'provider_calls':0,'official_model_results':0,
        'teacher_counterpart_status':'requires_same_native_actor_engine_and_authentic_teacher_paid_callback',
        'legacy_desktop_teacher_lease_seconds':600,'legacy_desktop_teacher_wall_seconds':1350,
        'legacy_desktop_teacher_qualified_under_v22':False,'all_seven_actor_paths_qualified':False}


def require_activation(registration):
    if registration.get('schema')!='cua-full-study-native-counterpart-registration-v22' or registration.get('qualified_native_epoch') is not True:
        raise ValueError('fresh_native_actor_clock_qualification_required')
    return registration
