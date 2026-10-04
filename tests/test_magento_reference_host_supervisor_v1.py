"""No process, sleep, model, Tinker, or application launch in these tests."""
import copy
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from magento_catalog_factory import native_reference_host_supervisor_v1 as m


class HostSupervisorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        (self.root / 'work').mkdir()
        for name in (m.SUPERVISOR_SOURCE, m.WORKER_SOURCE):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('# frozen offline fixture\n')
        self.patches = [patch.object(m, 'ROOT', self.root),
                        patch.object(m, 'AUTHORITY_ROOT', self.root / 'work/authority.private')]
        for item in self.patches:
            item.start()
        self.output = self.root / 'work/supervisor.private'
        self.argv = [str(Path(sys.executable)), '-m', m.WORKER_MODULE, 'run',
                     '--output', str(self.root / 'work/continuation.private'), '--execute']
        self.spec = m.review_spec(worker_argv=self.argv, cwd=self.root, output=self.output)
        self.review = self.root / 'work/root-reviewed.private.json'
        self.review_ref = m._write(self.review, self.spec)

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temporary.cleanup()

    def launch(self, process=None):
        process = process or Mock(pid=1001)
        with patch.object(m.subprocess, 'Popen', return_value=process) as popen:
            receipt = m.launch(spec_path=self.review, spec_sha256=self.review_ref['sha256'], execute=True)
        return receipt, popen

    def supervise(self, process):
        claim_sha = m._sha(m._claim_path(self.review_ref['sha256']))
        with patch.object(m.subprocess, 'Popen', return_value=process) as popen, \
             patch.object(m.os, 'killpg') as signal_owned:
            value = m.supervise(spec_path=self.review, spec_sha256=self.review_ref['sha256'],
                                claim_sha256=claim_sha, execute=True)
        return value, popen, signal_owned

    def test_review_is_metadata_only_and_keeps_native_budgets(self):
        with patch.object(m.subprocess, 'Popen', side_effect=AssertionError('no process')):
            value = m.review_spec(worker_argv=self.argv, cwd=self.root, output=self.output)
        self.assertEqual(value, self.spec)
        self.assertFalse(self.output.exists())
        self.assertEqual((value['seconds_limit'], value['native_actor_seconds'],
                          value['native_max_actions'], value['native_owned_lifecycle_seconds']),
                         (36000, 720, 90, 1200))
        self.assertFalse(value['automatic_restart_authorized'])

    def test_launch_consumes_global_authority_and_detaches_exact_supervisor(self):
        receipt, popen = self.launch()
        args, kwargs = popen.call_args
        self.assertEqual(args[0][:4], [self.argv[0], '-m', m.MODULE, 'supervise'])
        self.assertTrue(kwargs['start_new_session'])
        self.assertEqual(kwargs['cwd'], str(self.root))
        self.assertEqual({key: kwargs['env'][key] for key in m.ENVIRONMENT_OVERLAY}, m.ENVIRONMENT_OVERLAY)
        self.assertEqual(receipt['status'], 'launch_requested')
        self.assertTrue(m._claim_path(self.review_ref['sha256']).exists())
        self.assertEqual(self.output.stat().st_mode & 0o077, 0)
        self.assertEqual((self.output / 'supervisor.stdout.private.bin').stat().st_mode & 0o077, 0)

    def test_no_explicit_execute_or_changed_review_never_starts_process(self):
        with patch.object(m.subprocess, 'Popen') as popen:
            with self.assertRaises(m.SupervisionError):
                m.launch(spec_path=self.review, spec_sha256=self.review_ref['sha256'])
            with self.assertRaises(m.SupervisionError):
                m.launch(spec_path=self.review, spec_sha256='0' * 64, execute=True)
            popen.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_source_drift_refuses_before_authority_or_launch(self):
        (self.root / m.WORKER_SOURCE).write_text('# source drift\n')
        with patch.object(m.subprocess, 'Popen') as popen:
            with self.assertRaises(m.SupervisionError):
                m.launch(spec_path=self.review, spec_sha256=self.review_ref['sha256'], execute=True)
            popen.assert_not_called()
        self.assertFalse(m._claim_path(self.review_ref['sha256']).exists())

    def test_review_refuses_nonreference_command_cwd_alias_or_existing_output(self):
        for argv in ([self.argv[0], '-c', 'print(1)', 'run'],
                     [self.argv[0], '-m', 'other.model.worker', 'run']):
            with self.assertRaises(m.SupervisionError):
                m.review_spec(worker_argv=argv, cwd=self.root, output=self.output)
        alias = self.root / 'alias'
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(m.SupervisionError):
            m.review_spec(worker_argv=self.argv, cwd=alias, output=self.output)
        self.output.mkdir(mode=0o700)
        with self.assertRaises(m.SupervisionError):
            m.review_spec(worker_argv=self.argv, cwd=self.root, output=self.output)

    def test_changed_limits_or_added_review_fields_fail(self):
        for key, value in [('seconds_limit', 36001), ('native_actor_seconds', 721),
                           ('worker_launch_count', 2), ('automatic_restart_authorized', True),
                           ('native_qualification_credit', False), ('unreviewed', True)]:
            changed = copy.deepcopy(self.spec)
            changed[key] = value
            path = self.root / 'work' / (key + '.private.json')
            ref = m._write(path, changed)
            with patch.object(m.subprocess, 'Popen') as popen:
                with self.assertRaises(m.SupervisionError):
                    m.launch(spec_path=path, spec_sha256=ref['sha256'], execute=True)
                popen.assert_not_called()

    def test_uncertain_launch_is_consumed_failed_and_cannot_replay_after_output_loss(self):
        with patch.object(m.subprocess, 'Popen', side_effect=OSError('launch outcome unknown')) as popen:
            with self.assertRaises(OSError):
                m.launch(spec_path=self.review, spec_sha256=self.review_ref['sha256'], execute=True)
            self.assertEqual(popen.call_count, 1)
        failure = m._private(self.output / 'launch-failure.private.json')
        self.assertEqual(failure['status'], 'launch_uncertain')
        self.assertFalse(failure['automatic_replay_authorized'])
        shutil.rmtree(self.output)
        with patch.object(m.subprocess, 'Popen') as popen:
            with self.assertRaises(FileExistsError):
                m.launch(spec_path=self.review, spec_sha256=self.review_ref['sha256'], execute=True)
            popen.assert_not_called()

    def test_worker_zero_exit_one_call_and_saved_status_without_process_check(self):
        self.launch()
        process = Mock(pid=2002)
        process.wait.return_value = 0
        value, popen, signal_owned = self.supervise(process)
        self.assertEqual(value['status'], 'worker_exit_zero')
        self.assertTrue(value['worker_exit_acknowledged'])
        self.assertEqual(value['native_qualification_credit'], 0)
        self.assertEqual(popen.call_count, 1)
        self.assertEqual(popen.call_args.args[0], self.argv)
        self.assertTrue(popen.call_args.kwargs['start_new_session'])
        self.assertEqual({key: popen.call_args.kwargs['env'][key] for key in m.ENVIRONMENT_OVERLAY},
                         m.ENVIRONMENT_OVERLAY)
        signal_owned.assert_not_called()
        with patch.object(m.subprocess, 'Popen', side_effect=AssertionError('no launch')), \
             patch.object(m.os, 'killpg', side_effect=AssertionError('no signal')):
            status = m.saved_status(spec_path=self.review, spec_sha256=self.review_ref['sha256'])
        self.assertEqual(status['status'], 'worker_exit_zero')
        self.assertIn('exit.private.json', status)

    def test_nonzero_worker_exit_is_failure_and_bootstrap_cannot_restart(self):
        self.launch()
        process = Mock(pid=2002)
        process.wait.return_value = 7
        value, popen, _ = self.supervise(process)
        self.assertEqual(value['status'], 'worker_exit_nonzero')
        with patch.object(m.subprocess, 'Popen') as retry:
            with self.assertRaises(FileExistsError):
                m.supervise(spec_path=self.review, spec_sha256=self.review_ref['sha256'],
                            claim_sha256=m._sha(m._claim_path(self.review_ref['sha256'])), execute=True)
            retry.assert_not_called()
        self.assertEqual(popen.call_count, 1)

    def test_deadline_signals_exact_owned_group_and_does_not_retry_worker(self):
        self.launch()
        process = Mock(pid=2002)
        process.wait.side_effect = [subprocess.TimeoutExpired(self.argv, 36000), -15]
        process.poll.return_value = None
        value, popen, signal_owned = self.supervise(process)
        self.assertEqual(value['status'], 'host_deadline_exceeded')
        self.assertEqual(value['worker_exit_code'], -15)
        signal_owned.assert_called_once_with(2002, m.signal.SIGTERM)
        self.assertEqual(popen.call_count, 1)
        self.assertEqual(process.wait.call_count, 2)
        self.assertLessEqual(process.wait.call_args_list[0].kwargs['timeout'], 36000)

    def test_worker_launch_uncertainty_is_terminal_and_not_retried(self):
        self.launch()
        with patch.object(m.subprocess, 'Popen', side_effect=OSError('unknown')) as popen:
            value = m.supervise(spec_path=self.review, spec_sha256=self.review_ref['sha256'],
                                claim_sha256=m._sha(m._claim_path(self.review_ref['sha256'])), execute=True)
        self.assertEqual(popen.call_count, 1)
        self.assertEqual(value['status'], 'worker_launch_uncertain')
        self.assertIsNone(value['worker_exit_code'])
        self.assertFalse(value['worker_exit_acknowledged'])
        self.assertEqual(value['worker_launch_attempts'], 1)
        self.assertEqual(value['worker_launch_acknowledgments'], 0)

    def test_bootstrap_source_drift_retains_terminal_failure_before_worker(self):
        self.launch()
        (self.root / m.WORKER_SOURCE).write_text('# drift after detached launch\n')
        with patch.object(m.subprocess, 'Popen') as popen:
            value = m.supervise(spec_path=self.review, spec_sha256=self.review_ref['sha256'],
                                claim_sha256=m._sha(m._claim_path(self.review_ref['sha256'])), execute=True)
            popen.assert_not_called()
        self.assertEqual(value['status'], 'worker_launch_uncertain')
        self.assertEqual(value['error_type'], 'SupervisionError')
        self.assertEqual(value['worker_launch_attempts'], 0)
        self.assertTrue((self.output / 'exit.private.json').exists())

    def test_output_stream_tampering_fails_saved_readback(self):
        self.launch()
        process = Mock(pid=2002)
        process.wait.return_value = 0
        self.supervise(process)
        (self.output / 'worker.stdout.private.bin').write_bytes(b'changed')
        with self.assertRaises(m.SupervisionError):
            m.saved_status(spec_path=self.review, spec_sha256=self.review_ref['sha256'])

    def test_exit_code_cannot_be_relabelled_success(self):
        self.launch()
        process = Mock(pid=2002)
        process.wait.return_value = 7
        self.supervise(process)
        path = self.output / 'exit.private.json'
        value = m._private(path)
        value['status'] = 'worker_exit_zero'
        path.write_bytes(m.canonical(value))
        with self.assertRaises(m.SupervisionError):
            m.saved_status(spec_path=self.review, spec_sha256=self.review_ref['sha256'])

    def test_virtualenv_symlink_launch_path_preserved_for_supervisor_and_worker(self):
        physical = Path(sys.executable).resolve()
        entry = self.root / '.venv/bin/python'
        entry.parent.mkdir(parents=True)
        entry.symlink_to(physical)
        with patch.object(m.sys, 'executable', str(entry)), \
             patch.dict(m.os.environ, {'OFFLINE_SECRET_FIXTURE': 'private-sentinel', 'PYTHONPATH': 'old-path'}):
            self.argv[0] = str(entry)
            spec = m.review_spec(worker_argv=self.argv, cwd=self.root, output=self.output)
            self.assertEqual(spec['interpreter_ref'], {'path': str(entry),
                'resolved_path': str(physical), 'sha256': m._sha(physical)})
            self.assertNotIn('private-sentinel', m.canonical(spec).decode())
            self.review = self.root / 'work/root-reviewed-venv.private.json'
            self.review_ref = m._write(self.review, spec)
            receipt, detached = self.launch()
            self.assertEqual(detached.call_args.args[0][0], str(entry))
            self.assertEqual(detached.call_args.kwargs['env']['PYTHONPATH'], '.:src:tests')
            self.assertEqual(detached.call_args.kwargs['env']['PYTHONUNBUFFERED'], '1')
            self.assertNotIn('private-sentinel', m.canonical(receipt).decode())
            process = Mock(pid=2002)
            process.wait.return_value = 0
            value, worker, _ = self.supervise(process)
            self.assertEqual(worker.call_args.args[0][0], str(entry))
            self.assertEqual(worker.call_args.kwargs['env']['PYTHONPATH'], '.:src:tests')
            self.assertEqual(worker.call_args.kwargs['env']['PYTHONUNBUFFERED'], '1')
            self.assertNotIn('private-sentinel', m.canonical(value).decode())

    def test_unreviewed_environment_overlay_refused_before_launch(self):
        changed = copy.deepcopy(self.spec)
        changed['environment_overlay']['PYTHONPATH'] = '/unreviewed'
        path = self.root / 'work/changed-overlay.private.json'
        ref = m._write(path, changed)
        with patch.object(m.subprocess, 'Popen') as popen:
            with self.assertRaises(m.SupervisionError):
                m.launch(spec_path=path, spec_sha256=ref['sha256'], execute=True)
            popen.assert_not_called()

    def test_host_output_rejects_original_scope_or_continuation_output_overlap(self):
        original_scope = self.root / 'work/original.private'
        original_scope.mkdir(mode=0o700)
        arguments = original_scope / 'prepared-cli-arguments.private.json'
        m._write(arguments, {})
        argv = self.argv + ['--original-arguments-path', str(arguments)]
        worker_output = Path(argv[5])
        for output in (original_scope / 'host.private', worker_output, worker_output / 'host.private'):
            with self.assertRaises(m.SupervisionError):
                m.review_spec(worker_argv=argv, cwd=self.root, output=output)
        value = m.review_spec(worker_argv=argv, cwd=self.root, output=self.output)
        self.assertEqual(value['output_root'], str(self.output))

    def test_worker_argument_paths_must_be_canonical_and_equals_flags_are_checked(self):
        alias = self.root / 'work/alias'
        alias.symlink_to(self.root / 'work', target_is_directory=True)
        for argv in (self.argv + ['--root-review-path', str(alias / 'review.private.json')],
                     self.argv[:4] + ['--output=' + str(self.output)],
                     self.argv + ['--output=' + str(self.output)]):
            with self.assertRaises(m.SupervisionError):
                m.review_spec(worker_argv=argv, cwd=self.root, output=self.output)


if __name__ == '__main__':
    unittest.main()
