"""A failed disposable search startup must not kill unrelated processes."""

from __future__ import annotations

from unittest.mock import patch
import unittest

from tools import start_magento_original_clone_v1 as clone


class MagentoCloneRecoveryTests(unittest.TestCase):
    def test_only_stuck_elasticsearch_startup_helpers_are_killed(self):
        commands = []
        def fake_docker(*args, **kwargs):
            commands.append(args)
            if args[0:3] == ('exec', 'envloop-magento-original-control', 'ps'):
                return ('PID COMMAND\n'
                        '298 /usr/bin/java org.elasticsearch.tools.java_version_checker.JavaVersionChecker\n'
                        '1058 /usr/bin/java org.elasticsearch.tools.launchers.JvmOptionsParser\n'
                        '1700 /usr/bin/java unrelated.application.Main\n')
            return ''
        with patch.object(clone, 'docker', side_effect=fake_docker):
            clone.restart_stuck_search('envloop-magento-original-control')
        self.assertEqual(commands, [
            ('exec', 'envloop-magento-original-control', 'supervisorctl',
             'stop', 'elasticsearch'),
            ('exec', 'envloop-magento-original-control', 'ps', '-eo', 'pid,args'),
            ('exec', 'envloop-magento-original-control', 'kill', '-KILL', '298', '1058'),
            ('exec', 'envloop-magento-original-control', 'supervisorctl',
             'start', 'elasticsearch'),
        ])


if __name__ == '__main__':
    unittest.main()
