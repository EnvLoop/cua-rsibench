"""Offline application date repair and epoch scope; no Docker, task data or provider needed."""
import json,os,subprocess,unittest
from types import SimpleNamespace
from contextlib import contextmanager
from unittest.mock import Mock,patch
from tools import build_gitlab_member_date_only_image as b
from gitlab_world import member_date_application_epoch as e
class PublicRepairTests(unittest.TestCase):
 def receipt(self):return {'schema':'gitlab-member-date-only-application-build-v1','base_image':b.BASE,'repaired_image':'owned-date-fix','repaired_image_id':'sha256:'+'a'*64,'asset':b.ASSET,'original_asset_sha256':b.ORIGINAL_SHA,'repaired_asset_sha256':b.FIXED_SHA,'date_offset_timezone_or_oracle_changes':False}
 def test_real_payload_rule_preserves_calendar_date_across_utc_positive_negative_zones(self):
  expression=b.REPLACEMENT.decode().split('expires_at:',1)[1].rsplit(',access_level:e',1)[0]
  script='const fix=t=>'+expression+';for(const [y,m,d] of [[2026,9,22],[2026,0,1],[2026,11,31]]){const date=new Date(y,m,d);process.stdout.write(JSON.stringify({fixed:JSON.stringify({expires_at:fix(date)}),old:JSON.stringify({expires_at:date})})+"\\n");}process.stdout.write(JSON.stringify({none:fix(null),raw:fix("2026-10-22"),invalid:JSON.stringify({expires_at:fix(new Date(NaN))})}));'
  for zone in ('UTC','Asia/Shanghai','America/Los_Angeles'):
   result=subprocess.run(['node','-e',script],env={**os.environ,'TZ':zone},capture_output=True,check=True);rows=[json.loads(line) for line in result.stdout.decode().splitlines()]
   self.assertEqual([json.loads(x['fixed'])['expires_at'] for x in rows[:3]],['2026-10-22','2026-01-01','2026-12-31']);self.assertIsNone(rows[3]['none']);self.assertEqual(rows[3]['raw'],'2026-10-22');self.assertIsNone(json.loads(rows[3]['invalid'])['expires_at'])
   if zone=='Asia/Shanghai':self.assertEqual(json.loads(rows[0]['old'])['expires_at'],'2026-10-21T16:00:00.000Z')
 def test_original_exact_asset_digest_is_required_no_blind_bundle_patch(self):
  with self.assertRaises(ValueError):b.patch_asset(b'unknown frontend '+b.NEEDLE)
 def test_copy_assets_have_original_service_readable_mode(self):
  source=__import__('pathlib').Path(b.__file__).read_text();self.assertIn('COPY --chmod=0644 fixed.js ',source);self.assertIn('COPY --chmod=0644 fixed.js.gz ',source);self.assertIn('--network=none',source)
 def test_wrong_epoch_asset_or_oracle_change_refused(self):
  for key,value in (('base_image','foreign'),('repaired_asset_sha256','unknown'),('date_offset_timezone_or_oracle_changes',True)):
   receipt=self.receipt();receipt[key]=value
   with self.assertRaises(ValueError):e.validate_epoch(receipt)
 def test_original_image_check_is_restored_and_owned_cycles_use_new_build(self):
  class Native:
   @contextmanager
   def scope(self,*args,**kwargs):yield
   def boot(self,*args):return {'fixture':True}
  class World:
   def __init__(self,*args,backend_factory=None,**kwargs):self.backend_factory=backend_factory
   @contextmanager
   def _scope(self,*args,**kwargs):yield
  fake=SimpleNamespace(cold=SimpleNamespace(NativeBackend=Native),TaskWorld=World);runtime=SimpleNamespace(IMAGE='original',IMAGE_ID='original-id',inspect=lambda _: {'Image':'sha256:'+'a'*64})
  with patch.object(e,'world',fake),patch.object(e,'runtime',runtime):
   with e.application_epoch_scope(self.receipt()):
    task=fake.TaskWorld();backend=task.backend_factory();backend.doc={'container_prefix':'owned'}
    with backend.scope('preserved-original',None,None,None):self.assertEqual(runtime.IMAGE_ID,'original-id')
    with backend.scope('owned-0',None,None,None):self.assertEqual(runtime.IMAGE_ID,'sha256:'+'a'*64)
    backend.docker=Mock(return_value=b.FIXED_SHA+'  '+b.ASSET);backend.record=Mock();backend.boot(0);self.assertEqual(backend.docker.call_args.args[:3],('exec','--user','gitlab-www'));self.assertEqual(backend.record.call_args.args[1]['actual_asset_sha256'],b.FIXED_SHA)
   self.assertIs(fake.TaskWorld,World);self.assertEqual(runtime.IMAGE_ID,'original-id')
 def test_wrong_owned_image_and_unreadable_or_wrong_asset_refuse(self):
  class Native:
   def boot(self,index):return {}
  class World:
   def __init__(self,*args,backend_factory=None,**kwargs):self.backend_factory=backend_factory
  fake=SimpleNamespace(cold=SimpleNamespace(NativeBackend=Native),TaskWorld=World);runtime=SimpleNamespace(inspect=lambda _: {'Image':'wrong'})
  with patch.object(e,'world',fake),patch.object(e,'runtime',runtime),e.application_epoch_scope(self.receipt()):
   n=fake.TaskWorld().backend_factory();n.doc={'container_prefix':'owned'};n.docker=Mock(return_value='wrongdigest');n.record=Mock()
   with self.assertRaises(ValueError):n.boot(0)
   runtime.inspect=lambda _:{'Image':'sha256:'+'a'*64}
   with self.assertRaises(ValueError):n.boot(0)
 def test_public_evidence_scalar_only_and_no_completed20_claim(self):
  from pathlib import Path
  value=json.loads((Path(__file__).resolve().parents[1]/'docs/evidence/gitlab-member-date-only-repair.json').read_text());self.assertEqual(value['scores'],[0,1,0]);self.assertEqual(value['raw_git_refs_rehashed'],594);self.assertFalse(value['private_payloads_included']);self.assertFalse(value['full_selection20_completed']);self.assertEqual(value['model_tinker_calls'],0)
if __name__=='__main__':unittest.main()
