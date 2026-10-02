"""Preserved v6 evidence mechanics with a typed native principal resource."""
from .native_compat_source_loader_v1 import load_source
import re

_impl=load_source('enterprise_fallback/odoo18/odoo_native_surface_evidence_v6.py',
 'enterprise_fallback.odoo18._native_surface_evidence_v8',
 'fe0069f58c7936ffbb55717e1f89792e8abe1070048404b7ad3be5876a4c1b40',(
 ('account_uid','account_principal',9),('native_avatar_uid','native_avatar_principal',2),
 ('odoo-native-held-lease-evidence-v6','odoo-native-held-lease-evidence-v8',1),
 ('odoo-native-lease-check-evidence-v6','odoo-native-lease-check-evidence-v8',1),
 ('account_principal.isdigit()',"re.fullmatch(r'res\\.(?:partner|users):[1-9][0-9]*',account_principal) is not None",1),
 ))
_impl.re=re
EvidenceStore=_impl.EvidenceStore
OdooLeaseEvidence=_impl.OdooLeaseEvidence
require,private_bytes,read_ref=_impl.require,_impl.private_bytes,_impl.read_ref


def __getattr__(name):return getattr(_impl,name)
