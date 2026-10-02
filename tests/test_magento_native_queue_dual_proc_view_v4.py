"""QEMU self-view differs genuinely; independently read parent retains proof."""
import base64,copy,json,subprocess,unittest
from hashlib import sha256
from magento_catalog_factory import native_queue_profile_v4 as profile,seed
from tests.test_magento_native_queue_guest_identity_v3 import identity

class DualViewTests(unittest.TestCase):
    def fixture(self):
        token='a'*24;deadline=12345.25
        args=['php','-r',profile.SUPERVISOR_PHP,'--',token,str(deadline)]
        self_parent=identity(args,profile.GUEST_PHP,pid=9,parent=1)
        outside_parent=identity([profile.QEMU,profile.GUEST_PHP,*args],profile.QEMU,pid=9,parent=1)
        child=identity([profile.QEMU,profile.GUEST_PHP,*profile.ARGV],profile.QEMU,pid=11,parent=9)
        owner={'schema':'magento-native-consumer-owner-v4','token':token,'deadline_wall':deadline,
            'child':child,'supervisor':outside_parent,'supervisor_self_view':self_parent,'argv':profile.ARGV,'topic':profile.TOPIC,
            'max_messages':profile.MAX_MESSAGES,'package_sha256s':profile.PACKAGE_PINS}
        return {'owner':owner,'actual_child':copy.deepcopy(child),'actual_supervisor':outside_parent,'running':True}

    def test_exact_guest_self_and_native_other_view_are_both_retained(self):
        value=self.fixture();self.assertEqual(profile.validate_owner(value,'a'*24),value['owner'])
        self.assertNotEqual(value['owner']['supervisor_self_view']['cmdline_sha256'],value['actual_supervisor']['cmdline_sha256'])
        self.assertEqual(value['owner']['supervisor_self_view']['guest_cmdline_sha256'],value['actual_supervisor']['guest_cmdline_sha256'])

    def test_parent_absence_replacement_program_token_deadline_and_uid_fail_closed(self):
        for defect in ['missing','start','pid','parent','uid','program','token','deadline']:
            value=self.fixture()
            if defect=='missing':value.pop('actual_supervisor')
            elif defect=='program':value['owner']['supervisor']['guest_argv'][2]='foreign program'
            elif defect=='token':value['owner']['token']='b'*24
            elif defect=='deadline':value['owner']['deadline_wall']=12346
            else:value['actual_supervisor'][{'start':'start_ticks','pid':'pid','parent':'ppid','uid':'uid'}[defect]]=999
            with self.subTest(defect=defect),self.assertRaises(ValueError):profile.validate_owner(value,'a'*24)

    def test_actual_php_observes_different_self_and_outside_raw_views(self):
        probe=subprocess.run(['docker','--context','colima-cua-scale','image','inspect',seed.IMAGE],capture_output=True)
        if probe.returncode:self.skipTest('Pinned image unavailable')
        # A temporary reader process inspects its owning parent while that
        # parent reads itself. This calls no Magento consumer or model API.
        reader=profile.IDENTITY_PHP+'echo json_encode(identity((int)$argv[1]));'
        encoded=base64.b64encode(reader.encode()).decode()
        code=profile.IDENTITY_PHP+'$self=identity(getmypid());$args=["php","-r",base64_decode("'+encoded+'"),"--",(string)getmypid()];$p=proc_open($args,[0=>["file","/dev/null","r"],1=>["pipe","w"],2=>["pipe","w"]],$pipes);$outside=json_decode(stream_get_contents($pipes[1]),true);fclose($pipes[1]);fclose($pipes[2]);proc_close($p);echo json_encode(["self"=>$self,"outside"=>$outside]);'
        result=subprocess.run(['docker','--context','colima-cua-scale','run','--rm','--platform','linux/amd64',
            '--entrypoint','php',seed.IMAGE,'-r',code],capture_output=True,text=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stderr)
        observed=json.loads(result.stdout)
        for value in observed.values():profile.validate_identity(value)
        for key in ['pid','ppid','uid','guest_argv','guest_cmdline_sha256']:
            self.assertEqual(observed['self'][key],observed['outside'][key])

if __name__=='__main__':unittest.main()
