"""Real Magento CLI pre-exec empty argv is observed, never accepted/relaunched."""
import base64,json,subprocess,unittest
from magento_catalog_factory import native_queue_profile_v5 as profile,seed
from magento_catalog_factory import native_surface_workers_v5 as worker,native_surface_facade_v5 as controls
from magento_catalog_factory import native_surface_teacher_v3 as teacher,native_surface_shared_base_v3 as shared
from magento_catalog_factory import native_queue_runtime_v5 as runtime,native_surface_budget_performance_v5 as audit

class ExecTransitionTests(unittest.TestCase):
    def test_only_typed_empty_argv_is_boundedly_reread_without_second_launch(self):
        code=profile.SUPERVISOR_PHP
        self.assertEqual(code.count('$proc=proc_open($args,'),1)
        self.assertIn("if($e->getMessage()!=='native_empty_argv_transient')throw $e",code)
        self.assertIn("$readyUntil=min($deadline,microtime(true)+5)",code)
        self.assertIn("if(!$status['running'])throw new Exception('consumer_exited_before_owner')",code)
        with self.assertRaises(ValueError):profile.validate_identity({})

    def test_all_current_slots_and_lazy_auditors_use_same_runtime(self):
        self.assertIs(worker.Inputs.__init__.__globals__['Runtime'],runtime.Runtime)
        self.assertIs(worker.execute_owned.__globals__['run_task'],runtime.run_task)
        self.assertIs(teacher._impl.run_task,runtime.run_task)
        self.assertIs(teacher._impl.audit_episode,audit.audit_episode)
        self.assertIs(shared._impl.Inputs,worker.Inputs)
        self.assertIs(shared._impl.audit_episode,audit.audit_episode)
        self.assertIs(controls.run_controls.__globals__['run_task'],runtime.run_task)
        self.assertIs(controls.run_controls.__globals__['audit_episode'],audit.audit_episode)

    def test_current_owner_decoder_binds_v5_exact_program_not_ancestor(self):
        import copy
        from tests.test_magento_native_queue_dual_proc_view_v4 import DualViewTests
        from tests.test_magento_native_queue_guest_identity_v3 import identity
        value=DualViewTests().fixture();owner=value['owner'];owner['schema']='magento-native-consumer-owner-v5'
        args=['php','-r',profile.SUPERVISOR_PHP,'--','a'*24,str(owner['deadline_wall'])]
        owner['supervisor_self_view']=identity(args,profile.GUEST_PHP,pid=9,parent=1)
        owner['supervisor']=identity([profile.QEMU,profile.GUEST_PHP,*args],profile.QEMU,pid=9,parent=1)
        value['actual_supervisor']=copy.deepcopy(owner['supervisor'])
        self.assertEqual(profile.validate_owner(value,'a'*24),owner)
        owner['schema']='magento-native-consumer-owner-v4'
        with self.assertRaises(ValueError):profile.validate_owner(value,'a'*24)

    def test_actual_pinned_magento_cli_now_reaches_owner_without_database_services(self):
        probe=subprocess.run(['docker','--context','colima-cua-scale','image','inspect',seed.IMAGE],capture_output=True)
        if probe.returncode:self.skipTest('Pinned Magento image unavailable')
        encoded=base64.b64encode(profile.SUPERVISOR_PHP.encode()).decode()
        code=r'''$p=proc_open(['php','-r',base64_decode('CODE'),'--','ffffffffffffffffffffffff',(string)(microtime(true)+20)],[0=>['file','/dev/null','r'],1=>['pipe','w'],2=>['pipe','w']],$pipes);$out=stream_get_contents($pipes[1]);$err=stream_get_contents($pipes[2]);fclose($pipes[1]);fclose($pipes[2]);$status=proc_close($p);$root='/tmp/envloop-magento-native-queue-ffffffffffffffffffffffff';echo json_encode(['status'=>$status,'stdout'=>$out,'stderr'=>$err,'owner_created'=>is_file($root.'/owner.private.json'),'fatal_record'=>is_file($root.'/startup-failure.private.json')]);'''.replace('CODE',encoded)
        result=subprocess.run(['docker','--context','colima-cua-scale','run','--rm','--platform','linux/amd64',
            '--entrypoint','php',seed.IMAGE,'-r',code],capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        actual=json.loads(result.stdout)
        self.assertEqual(actual,{'status':0,'stdout':'','stderr':'','owner_created':True,'fatal_record':False})
        # This is startup mechanism evidence only. No SQL/database/GUI task is
        # evaluated, and an unexpected empty-environment consumer exit is not
        # accepted as owned-close or benchmark qualification.

if __name__=='__main__':unittest.main()
