import unittest
from gitlab_world.v066_prospective_v5_terminal_forensic import classify_boot

class BootClassification(unittest.TestCase):
    def setUp(self):
        self.state={'Status':'exited','Running':False,'ExitCode':1,'OOMKilled':False}
        self.logs=(b'gitlab-ctl reconfigure runit_service[postgresql] restart_log_service '
            b'/opt/gitlab/embedded/bin/sv restart /opt/gitlab/service/postgresql/log '
            b'timeout: down: /opt/gitlab/service/postgresql/log')
    def test_specific_observed_failure_retains_unknown_lower_cause(self):
        value=classify_boot(self.state,self.logs,b'')
        self.assertIsNone(value['low_level_logger_restart_cause'])
        self.assertFalse(value['uniform_svwait_60_empirically_validated'])
    def test_oom_or_success_cannot_be_labeled_this_failure(self):
        for change in [{'OOMKilled':True},{'ExitCode':0},{'Running':True}]:
            with self.assertRaises(ValueError):classify_boot({**self.state,**change},self.logs,b'')
    def test_other_boot_failure_cannot_be_labeled_logger_timeout(self):
        with self.assertRaises(ValueError):classify_boot(self.state,b'Permission denied',b'')
    def test_other_service_timeout_is_not_this_failure(self):
        with self.assertRaises(ValueError):classify_boot(self.state,self.logs.replace(b'postgresql/log',b'redis/log'),b'')

if __name__=='__main__':unittest.main()
