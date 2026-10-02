"""Production queue closure/clock code with synthetic native process transport."""
import asyncio,copy,json,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
from cursibench import native_surface_guard_policy_v1 as policy
from enterprise_fallback.odoo18.odoo_native_surface_evidence_v6 import EvidenceStore
from magento_catalog_factory import native_queue_profile_v2 as p,native_queue_runtime_v2 as rt

TOKEN='a'*24

def queue(pending=False):
 return {'schema':'magento-owned-native-queue-state-v2','topic':p.TOPIC,'messages':[],'states':[{'message_id':'1','status':'2' if pending else '4'}] if pending else [],'operations':[],'pending':int(pending),'failed':0,'consumers_wait_for_messages':1}

def owner():
 child={'pid':33,'ppid':32,'uid':0,'start_ticks':'998','cmdline_sha256':p.CMDLINE_SHA256,'exe':'/usr/local/bin/php'}
 return {'schema':'magento-native-consumer-owner-v2','token':TOKEN,'topic':p.TOPIC,'argv':p.ARGV,'max_messages':p.MAX_MESSAGES,'package_sha256s':p.PACKAGE_PINS,'supervisor':{'pid':32},'child':child}

def process():
 value=owner();return {'running':True,'owner':value,'actual_child':copy.deepcopy(value['child'])}

class ProfileTests(unittest.TestCase):
 def test_native_command_has_only_topic_and_bounded_options_no_task_body(self):
  self.assertEqual(p.ARGV,['php','/var/www/magento2/bin/magento','queue:consumers:start','product_action_attribute.update','--max-messages=10000','--single-thread'])
  self.assertNotIn('sku',p.SUPERVISOR_PHP.lower());self.assertNotIn('target_price',p.SUPERVISOR_PHP)
 def test_owner_checks_source_argv_actual_identity_and_foreign_scope(self):
  self.assertEqual(p.validate_owner(process(),TOKEN),owner())
  for mutate in [lambda x:x['actual_child'].update(start_ticks='foreign'),lambda x:x.update(running=False),lambda x:x['owner'].update(token='b'*24),lambda x:x['owner'].update(argv=['php','arbitrary']),lambda x:x['owner'].update(package_sha256s={})]:
   value=copy.deepcopy(process());mutate(value)
   with self.assertRaises(ValueError):p.validate_owner(value,TOKEN)
 def test_native_aggregate_rederived_and_unknown_or_foreign_status_refuses(self):
  self.assertEqual(p.validate_queue(queue(True))['pending'],1)
  for value in [queue(True)|{'pending':0},queue()|{'states':[{'status':99}]},queue()|{'operations':[{'status':1,'topic_name':'foreign'}]}]:
   with self.assertRaises(ValueError):p.validate_queue(value)
 def test_exit_requires_actual_owned_signal_and_parent_absence(self):
  value={'exit_available':True,'supervisor_pid_absent':True,'exit':{'schema':'magento-native-consumer-exit-v2','token':TOKEN,'child':owner()['child'],'reason':'owned_close_request','child_pid_absent':True,'stop_signal_returned':True,'first_observed_exitcode':-1,'signaled':True,'termsig':15}}
  p.validate_exit(value,owner())
  for mutate in [lambda x:x.update(supervisor_pid_absent=False),lambda x:x['exit'].update(reason='absolute_owned_deadline'),lambda x:x['exit'].update(termsig=9),lambda x:x['exit'].update(child_pid_absent=False)]:
   changed=copy.deepcopy(value);mutate(changed)
   with self.assertRaises(ValueError):p.validate_exit(changed,owner())

class ClockTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.root.chmod(0o700);self.store=EvidenceStore(self.root)
 def retained(self,*,pending=False,probe_time=9,end=10,context={'schema':'synthetic'}):
  self.store.json('actor-clock/end.private.json',{'actor_ended_monotonic':end,'native_io':[]},'native_observation_envelope')
  row={'observed_monotonic':probe_time,'native_context_sha256':policy.digest(context),'native_process':process(),'queue':queue(pending)}
  ref=self.store.json('queue/probe-0000.private.json',row,'native_observation_envelope')
  self.store.json('queue/probes.private.json',{'probes':[{'reference':ref,'observed_monotonic':probe_time}]},'native_observation_envelope')
  meta=self.store.json('native.private.json',context|{'native_window_sha256':'a'*64},'native_observation_envelope')
  capsule=self.store.json('capsule.private.json',{'current':{'raw_envelope':meta}},'dispatch_receipt')
  self.store.json('actions.private.json',{'actions':[{'action':{'type':'finish'},'contract':{'native_surface_guard':capsule}}]},'native_observation_envelope')
 def test_known_pending_before_finish_stays_task_zero(self):
  self.retained(pending=True)
  self.assertEqual(rt.queue_verdict(self.root)['score'],0)
 def test_acknowledged_before_actor_end_with_same_native_predispatch_can_succeed(self):
  self.retained()
  self.assertEqual(rt.queue_verdict(self.root)['score'],1)
 def test_late_probe_cannot_rescue_early_finish(self):
  self.retained(probe_time=11)
  with self.assertRaises(ValueError):rt.queue_verdict(self.root)
 def test_mismatched_context_cannot_use_a_different_native_queue_read(self):
  self.retained();path=self.root/'native.private.json';path.write_text(json.dumps({'schema':'foreign'}));path.chmod(0o600)
  with self.assertRaises(ValueError):rt.queue_verdict(self.root)
 def test_changed_raw_probe_hash_refuses(self):
  self.retained();path=self.root/'queue/probe-0000.private.json';path.write_text('{}')
  with self.assertRaises(policy.GuardError):rt.queue_verdict(self.root)

class RuntimeTests(unittest.IsolatedAsyncioTestCase):
 async def test_passive_page_does_not_modify_actor_metadata_or_replay_evaluate(self):
  native=SimpleNamespace(evaluate=AsyncMock(return_value={'schema':'actual-current'}));service=SimpleNamespace(observe=AsyncMock());page=rt.PassivePage(native,service)
  value=await page.evaluate(rt.CURRENT_JS,[])
  self.assertEqual(value,{'schema':'actual-current'});native.evaluate.assert_awaited_once_with(rt.CURRENT_JS,[]);service.observe.assert_awaited_once_with(value)
 async def test_non_native_read_does_not_receive_queue_probe(self):
  native=SimpleNamespace(evaluate=AsyncMock(return_value=True));service=SimpleNamespace(observe=AsyncMock());page=rt.PassivePage(native,service)
  self.assertTrue(await page.evaluate('element=>element.disabled'));service.observe.assert_not_called()
 async def test_service_failure_refuses_observation_without_native_gui_call(self):
  native=SimpleNamespace(evaluate=AsyncMock(return_value={'schema':'actual'}));service=SimpleNamespace(observe=AsyncMock(side_effect=ValueError('Native process unknown')));page=rt.PassivePage(native,service)
  with self.assertRaises(ValueError):await page.evaluate(rt.CURRENT_JS,[])
  native.evaluate.assert_awaited_once()
 async def test_detached_launch_is_one_call_readiness_can_only_resample_missing_owner(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);root.chmod(0o700);active=SimpleNamespace(spec=SimpleNamespace(app='owned'))
   service=rt.NativeQueue(active,root,time.monotonic());service.scope=TOKEN
   with patch.object(service,'state',return_value=queue()),patch.object(service,'command',return_value='detached-accepted') as launch,patch.object(service,'php',side_effect=[{'owner_available':False},process()]) as reader:
    await service.start()
   launch.assert_called_once();self.assertEqual(reader.call_count,2);self.assertEqual(service.owner,owner())
 async def test_foreign_owner_is_terminal_not_read_retry_or_new_launch(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);root.chmod(0o700);active=SimpleNamespace(spec=SimpleNamespace(app='owned'))
   service=rt.NativeQueue(active,root,time.monotonic());service.scope=TOKEN;bad=copy.deepcopy(process());bad['owner']['token']='b'*24
   with patch.object(service,'state',return_value=queue()),patch.object(service,'command',return_value='accepted') as launch,patch.object(service,'php',return_value=bad) as reader:
    with self.assertRaises(ValueError):await service.start()
   launch.assert_called_once();reader.assert_called_once()


class CloseTests(unittest.IsolatedAsyncioTestCase):
 async def test_actual_empty_streams_retained_without_padding_and_one_close_request(self):
  from hashlib import sha256
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);root.chmod(0o700);service=rt.NativeQueue(SimpleNamespace(spec=SimpleNamespace(app='owned')),root,time.monotonic());service.scope=TOKEN;service.owner=owner()
   digest=sha256(b'').hexdigest();ack={'exit_available':True,'supervisor_pid_absent':True,'stdout':'','stderr':'','exit':{'schema':'magento-native-consumer-exit-v2','token':TOKEN,'child':owner()['child'],'reason':'owned_close_request','child_pid_absent':True,'stop_signal_returned':True,'first_observed_exitcode':-1,'signaled':True,'termsig':15,'stdout_sha256':digest,'stderr_sha256':digest}}
   with patch.object(service,'php',side_effect=[process(),{'close_request_written':True},ack]) as read:await service.close()
   self.assertEqual(read.call_count,3);self.assertEqual((root/'queue/consumer.stdout.private.bin').read_bytes(),b'');self.assertEqual((root/'queue/consumer.stderr.private.bin').read_bytes(),b'')
 async def test_foreign_or_unknown_live_identity_refuses_before_close_request(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);root.chmod(0o700);service=rt.NativeQueue(SimpleNamespace(spec=SimpleNamespace(app='owned')),root,time.monotonic());service.scope=TOKEN;service.owner=owner();bad=process();bad['actual_child']['start_ticks']='wrong'
   with patch.object(service,'php',return_value=bad) as read:
    with self.assertRaises(ValueError):await service.close()
   read.assert_called_once();self.assertFalse((root/'queue/close-intent.private.json').exists())

if __name__=='__main__':unittest.main()
