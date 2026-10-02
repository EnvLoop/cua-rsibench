"""Fresh source-reviewed v21 TRAIN pilot; legacy output namespaces are refused."""
import json
from pathlib import Path
from .pinned_model_load_v21 import load
from . import model_transport_integration_v21 as integration
from . import prospective_model_worker_v21 as worker
from . import deadline_model_transport_v21 as transport
from .factory import digest

_bound=load('train_weak_base_pilot_v11.py','native_desktop_factory._v21_bound_train_pilot',[
 ("self.attempt_id = 'public-train-weak-base'", "self.attempt_id = 'public-train-weak-base-v21'"),
 ("'schema': 'cua-native-public-train-weak-base-pilot-result-v11'",
  "'schema': 'cua-native-public-train-weak-base-pilot-result-v21'"),
])
_bound.integration=integration;_bound.worker=worker;_bound.transport=transport
_bound.SCHEMA='cua-native-public-train-weak-base-pilot-freeze-v21'
_bound.PERMIT='cua-native-public-train-weak-base-pilot-one-use-permit-v21'
prepare=_bound.prepare;validate=_bound.validate;review=_bound.review;PilotPaidCalls=_bound.PilotPaidCalls
_native_run=_bound.run


def run(*,freeze_path,permit_path,enable_paid_pilot=False):
    result=_native_run(freeze_path=freeze_path,permit_path=permit_path,enable_paid_pilot=enable_paid_pilot)
    value=validate(freeze_path);output=Path(value['output_root'])
    terminal=output/'sampler-process/child-terminal.private.json'
    raw=integration.controls.private(terminal);closed=json.loads(raw)
    worker.write(output/'shutdown-link.private.json',{
        'schema':'cua-native-train-pilot-shutdown-link-v21','child_terminal_sha256':digest(raw),
        'provider_shutdown_acknowledged':closed['provider_shutdown_acknowledged'],
        'command_poisoned':closed['command_poisoned'],'model_completion_uncertain':closed['model_completion_uncertain'],
        'model_result_resubmitted':False,'provider_invoice_verified':False,'cost_usd':None,
        'official_final_admissions':0,'official_model_results':0})
    return {**result,'provider_shutdown_acknowledged':closed['provider_shutdown_acknowledged'],
            'model_completion_uncertain':closed['model_completion_uncertain']}


def main():
    _bound.run=run
    _bound.main()


if __name__=='__main__':main()
