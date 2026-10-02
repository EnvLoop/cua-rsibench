"""Mandatory current native Odoo worker injection for shared-base selection."""
from pathlib import Path
import json
from cursibench import full_study_shared_base_execution_v1 as execution


def run_odoo_shared_base(study,usage_reconciler,*,native_binding_path:Path,
    native_binding_file_sha256:str,train_control_path:Path,train_control_sha256:str,
    worker_dir:Path,local_cost_authority_path:Path,local_cost_authority_sha256:str,
    native_worker_module=None):
    from .native_surface_final_worker_v1 import _worker_module,module_from_binding,study_source_snapshot,digest,final,private,require
    raw=private(native_binding_path)
    require(digest(raw)==native_binding_file_sha256,'shared_base_native_binding_file_changed')
    raw_binding=json.loads(raw)
    native_worker_module=module_from_binding(raw_binding,native_worker_module)
    workers=_worker_module(native_worker_module)
    binding=workers.validate_binding(workers.private_json(native_binding_path,native_binding_file_sha256))
    workers.validate_train_control(workers.private_json(train_control_path,train_control_sha256),binding)
    cell=next(row for row in study.plan['cells'] if row['cell_id']=='odoo-community')
    workers.require(cell['matched_bindings']['runtime']==binding['binding_sha256'] and
        cell['matched_bindings']['source_snapshot']==digest(final.canonical(study_source_snapshot(native_worker_module))) and
        study.ratification['cell_profiles']['odoo-community']['adapter_sha256']==binding['source_sha256s'][workers.ADAPTER_FILE],
        'shared_base_current_surface_binding_required')
    execution._verify_base_freeze(study,cell)

    def factory(**kwargs):
        # The legacy runner owns budget, frozen base identity and native
        # operation. Its historical keyword names are translated explicitly.
        path=kwargs.pop('ratification_path');digest=kwargs.pop('ratification_sha256')
        return workers.selection_worker(native_binding_path=native_binding_path,
            native_binding_file_sha256=native_binding_file_sha256,
            train_control_path=train_control_path,train_control_sha256=train_control_sha256,
            campaign_ratification_path=path,campaign_ratification_sha256=digest,**kwargs)

    return execution.run_odoo_shared_base(study,usage_reconciler,worker_dir=worker_dir,
        local_cost_authority_path=local_cost_authority_path,
        local_cost_authority_sha256=local_cost_authority_sha256,worker_factory=factory)
