"""Raw process proof retained; only the actual pinned launcher is decoded."""
import copy,json,subprocess,unittest
from hashlib import sha256
from magento_catalog_factory import native_queue_profile_v3 as profile,seed

def identity(argv,exe,pid=11,parent=9):
    guest,transport=profile.normalize_native_argv(exe,argv)
    digest=lambda args:sha256(('\0'.join(args)+'\0').encode()).hexdigest()
    return {'pid':pid,'ppid':parent,'start_ticks':'123','uid':0,'exe':exe,'native_argv':argv,
        'guest_argv':guest,'cmdline_sha256':digest(argv),'guest_cmdline_sha256':digest(guest),'execution_transport':transport}

class NativeGuestIdentityTests(unittest.TestCase):
    def test_native_and_exact_qemu_keep_raw_bytes_and_identical_guest_cli(self):
        for exe,argv in [(profile.GUEST_PHP,profile.ARGV),
            (profile.QEMU,[profile.QEMU,profile.GUEST_PHP,*profile.ARGV])]:
            value=identity(argv,exe)
            self.assertEqual(profile.validate_identity(value),value)
            self.assertEqual(value['guest_cmdline_sha256'],profile.CMDLINE_SHA256)
            self.assertEqual(value['guest_argv'],profile.ARGV)
            if exe==profile.QEMU:self.assertNotEqual(value['cmdline_sha256'],profile.CMDLINE_SHA256)

    def test_unknown_prefix_executable_extra_args_and_tampered_hashes_refuse(self):
        for exe,argv in [('/tmp/qemu',profile.ARGV),(profile.QEMU,['/tmp/qemu',profile.GUEST_PHP,*profile.ARGV]),
            (profile.QEMU,[profile.QEMU,'/tmp/foreign-php',*profile.ARGV])]:
            with self.subTest(exe=exe,argv=argv),self.assertRaises(ValueError):profile.normalize_native_argv(exe,argv)
        valid=identity([profile.QEMU,profile.GUEST_PHP,*profile.ARGV],profile.QEMU)
        for change in [{'guest_argv':profile.ARGV+['--unexpected']},{'cmdline_sha256':'0'*64},
            {'guest_cmdline_sha256':'0'*64},{'execution_transport':'native_php'},{'uid':1},{'start_ticks':''}]:
            with self.subTest(change=change),self.assertRaises(ValueError):profile.validate_identity({**valid,**change})

    def test_owner_checks_exact_args_parent_source_uid_and_live_identity(self):
        child=identity([profile.QEMU,profile.GUEST_PHP,*profile.ARGV],profile.QEMU)
        parent=identity([profile.QEMU,profile.GUEST_PHP,'php','-r','synthetic-supervisor'],profile.QEMU,pid=9,parent=1)
        owner={'schema':'magento-native-consumer-owner-v3','token':'a'*24,'child':child,'supervisor':parent,
            'topic':profile.TOPIC,'argv':profile.ARGV,'max_messages':profile.MAX_MESSAGES,'package_sha256s':profile.PACKAGE_PINS}
        value={'owner':owner,'actual_child':copy.deepcopy(child),'running':True}
        self.assertEqual(profile.validate_owner(value,'a'*24),owner)
        for defect in ['parent','args','source','actual','uid']:
            bad=copy.deepcopy(value)
            if defect=='parent':bad['owner']['child']['ppid']=18
            if defect=='args':bad['owner']['argv']=profile.ARGV+['--foreign']
            if defect=='source':bad['owner']['package_sha256s']={}
            if defect=='actual':bad['actual_child']['start_ticks']='999'
            if defect=='uid':bad['owner']['child']['uid']=1
            with self.subTest(defect=defect),self.assertRaises(ValueError):profile.validate_owner(bad,'a'*24)

    def test_actual_pinned_php_proc_open_returns_guest_and_retains_raw_qemu_vector(self):
        check=subprocess.run(['docker','--context','colima-cua-scale','image','inspect',seed.IMAGE],capture_output=True)
        if check.returncode:self.skipTest('Pinned original Magento image unavailable')
        code=profile.IDENTITY_PHP+r'''$args=['php','-r','usleep(500000);'];$p=proc_open($args,[0=>['file','/dev/null','r'],1=>['file','/dev/null','a'],2=>['file','/dev/null','a']],$pipes);$s=proc_get_status($p);usleep(50000);echo json_encode(identity($s['pid']));proc_close($p);'''
        result=subprocess.run(['docker','--context','colima-cua-scale','run','--rm','--platform','linux/amd64',
            '--entrypoint','php',seed.IMAGE,'-r',code],capture_output=True,text=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stderr)
        observed=json.loads(result.stdout)
        self.assertEqual(profile.validate_identity(observed),observed)
        self.assertEqual(observed['guest_argv'],['php','-r','usleep(500000);'])
        self.assertIn(observed['execution_transport'],['qemu_x86_64_php','native_php'])
        lint=subprocess.run(['docker','--context','colima-cua-scale','run','--rm','-i','--platform','linux/amd64',
            '--entrypoint','php',seed.IMAGE,'-l'],input='<?php\n'+profile.SUPERVISOR_PHP,capture_output=True,text=True,timeout=60)
        self.assertEqual(lint.returncode,0,lint.stderr)

if __name__=='__main__':unittest.main()
