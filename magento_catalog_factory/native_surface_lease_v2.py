"""Original exact lease/origin/window checks plus the rendered header witness."""
from .native_surface_lease_v1 import LeaseBoundary as OriginalLeaseBoundary,OwnedOperation
from .native_principal_header_v2 import valid_witness
from urllib.parse import urlsplit
import re

class LeaseBoundary(OriginalLeaseBoundary):
    async def owns(self,page,meta):
        path=urlsplit(meta.get('physical_url','')).path
        return bool(not re.search(r'/(?:logout|system_account)(?:/|$)',path) and
            await super().owns(page,meta) and valid_witness(meta,self.username))
