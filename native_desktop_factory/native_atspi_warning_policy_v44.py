"""Source-bound Table getter warning; original stderr validation is reused."""
import re
from types import FunctionType
from . import native_atspi_warning_policy_v32 as base
FILES=base.FILES|{'native_window_current_reader.py','native_editor_reader_v44.py','native_editor_evidence_v44.py','native_virtual_cell_identity_v44.py'}
GETTERS=base.GETTERS|{'get_table_iface'}
HEADER=re.compile(r'(?P<path>/tmp/[A-Za-z0-9_./-]+):(?P<line>[1-9][0-9]*): DeprecationWarning: Atspi\.Accessible\.(?P<method>get_collection_iface|get_component_iface|get_table_iface) is deprecated\n\Z')
original=base.classify
classify=FunctionType(original.__code__,{**original.__globals__,'FILES':FILES,'GETTERS':GETTERS,'HEADER':HEADER},original.__name__,original.__defaults__,original.__closure__)
