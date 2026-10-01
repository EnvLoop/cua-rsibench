"""Original WDI/SEC package with setup errors kept distinct from task scores."""
import json
from tools import office_owned_folder_runtime_v2 as original

class Package(original.Package):
 def __init__(self,*args,**kwargs):
  super().__init__(*args,**kwargs)
  if self.actor.cell_id=='excel-web':self._checked_sec(super().strict_score(self.paths['baseline']))
 def _checked_sec(self,result):
  raw=result['raw_strict'];errors=raw['errors']
  from sec_excel_factory.verify_integrated_candidate import target_addresses
  cases=json.loads(original.private(self.paths['case_manifest']));case=next(r for r in cases if r['case_id']==self.value['case_id'])
  original.require(raw['checked_targets']==len(target_addresses(case['split'])) and not any(e.startswith('oracle_setup:') for e in errors),'Original SEC source/oracle setup failure remains infrastructure-invalid')
  return result
 def strict_score(self,candidate):
  result=super().strict_score(candidate)
  return self._checked_sec(result) if self.actor.cell_id=='excel-web' else result
