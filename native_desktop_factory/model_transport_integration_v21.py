"""Additive source ratifier; old control and eligibility receipts stay intact."""
from pathlib import Path
from contextlib import contextmanager
from unittest.mock import patch
from .pinned_model_load_v21 import load
from . import deadline_model_transport_v21 as transport
from . import qwen_sampler_process_v21 as rpc

_bound=load('model_transport_integration_v11.py','native_desktop_factory._v21_bound_integration')
_bound.transport=transport
_bound.SCHEMA='cua-native-desktop-uniform-model-transport-proposal-v21'
_bound.ADMISSIONS_SCHEMA='cua-native-desktop-prospective120-model-admissions-private-v21'
ADDITIVE_SOURCES=(
 'native_desktop_factory/actor_deadline_future_v21.py',
 'native_desktop_factory/pinned_model_load_v21.py',
 'native_desktop_factory/deadline_model_transport_v21.py',
 'native_desktop_factory/qwen_sampler_process_v21.py',
 'native_desktop_factory/model_transport_integration_v21.py',
 'native_desktop_factory/prospective_model_worker_v21.py',
 'native_desktop_factory/train_weak_base_pilot_v21.py',
 'native_desktop_factory/shared_base_model_execution_v21.py',
 'tests/test_native_desktop_actor_deadline_future_v21.py',
 'tests/test_native_desktop_deadline_runtime_v21.py',
)
_bound.SOURCE_PATHS=tuple(dict.fromkeys((*_bound.SOURCE_PATHS,*ADDITIVE_SOURCES)))
_original_proposal=_bound.proposal


def proposal(root=None):
    value=_original_proposal(Path(root) if root is not None else _bound.ROOT)
    value.update(adapter_source_sha256=value['source_sha256s']['native_desktop_factory/deadline_model_transport_v21.py'],
        deadline_policy='absolute-monotonic-exact-float-v21',actor_clock_end='deadline-before-ack-and-evaluation',
        no_late_gui=True,no_actor_budget_minimum_cutoff=True,provider_ack_grace_seconds=5,
        provider_shutdown_wait_seconds=45,uncertain_sample_coverage_relaxed=False)
    return value


_bound.proposal=proposal


@contextmanager
def runtime_context():
    from cursibench import full_study_qwen_runtime_gate_v1 as gate
    # Other admission/ratification validators remain in the exact legacy body.
    from cursibench import full_study_shared_base_selection_v1 as shared
    from . import v066_final_freeze as freeze
    from . import shared_base_model_execution_v21 as base_bridge
    with patch.object(freeze,'validate_ratification',_bound.validate_ratification),\
         patch.object(gate,'pre_dispatch',rpc.delegated_pre_dispatch),\
         patch.object(shared,'verify_receipt',base_bridge.verify_receipt):
        yield


_bound.runtime_context=runtime_context
for _name,_value in vars(_bound).copy().items():
    if not _name.startswith('_') and _name not in {'proposal','runtime_context','transport'}:
        globals()[_name]=_value


if __name__=='__main__':_bound.main()
