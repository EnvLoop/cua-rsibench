"""Same paid/invoice/coverage verifier bound to the v21 episode and clock audit."""
from .pinned_model_load_v21 import load
from . import model_transport_integration_v21 as integration
from . import prospective_model_worker_v21 as worker

_bound=load('shared_base_model_execution_v11.py','native_desktop_factory._v21_bound_shared_base')
_bound.integration=integration;_bound.model=worker
_bound.SCHEMA='cua-native-desktop-v21-shared-base-selection'
verify_receipt=_bound.verify_receipt
execute=_bound.execute
