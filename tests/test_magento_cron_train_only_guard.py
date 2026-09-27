import subprocess
import sys
import unittest


class MagentoCronTrainOnlyGuardTest(unittest.TestCase):
    def test_final_split_refused_before_files_or_containers(self):
        result = subprocess.run([
            sys.executable, 'tools/sweep_magento_original_gui_controls_v1.py',
            '--plan', '/does-not-exist', '--plan-sha256', '0' * 64,
            '--split', 'official_candidate', '--source', '/does-not-exist',
            '--out-dir', '/does-not-exist', '--limit', '1',
            '--train-cron-never-autostart',
        ], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('cron startup probe is train-only', result.stderr)


if __name__ == '__main__':
    unittest.main()
