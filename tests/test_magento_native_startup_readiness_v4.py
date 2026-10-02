"""Intentionally stopped peers never cause critical-readiness false failure."""
import json,unittest
from types import SimpleNamespace
from unittest.mock import Mock
from magento_catalog_factory import native_startup_readiness_v4 as startup
from magento_catalog_factory import native_surface_workers_v8 as workers,native_queue_runtime_v8 as runtime
from magento_catalog_factory import native_surface_facade_v8 as facade,native_surface_teacher_v6 as teacher
from magento_catalog_factory import native_surface_shared_base_v6 as shared,native_surface_budget_performance_v8 as audit

class ReadinessTests(unittest.TestCase):
    def test_only_individual_running_critical_services_are_probed(self):
        manager=object.__new__(startup.CloneManager);manager.journal=Mock();manager.journal.run.return_value='{"database_ready":true}'
        seen=[]
        def execute(label,container,*args,**kwargs):
            seen.append(args)
            if args[0]=='curl':return '{"status":"yellow","number_of_nodes":1,"timed_out":false}'
            self.assertEqual(args[:2],('supervisorctl','status'));self.assertEqual(len(args),3)
            return args[-1]+' RUNNING pid 1'
        manager._exec=execute;manager._wait_services(SimpleNamespace(index=0,app='owned',search='owned-search'))
        names=[args[-1] for args in seen if args[0]=='supervisorctl']
        self.assertEqual(names,['mysqld','php-fpm','nginx','redis-server'])
        self.assertFalse(any('/admin' in value for args in seen for value in args))

    def test_prepared_witness_patch_targets_current_manager_not_ancestor(self):
        function=startup.Runtime.open_case.__wrapped__
        self.assertIs(function.__globals__['CloneManager'],startup.CloneManager)
        self.assertIn('CloneManager',function.__code__.co_names)
        self.assertIs(startup.CloneManager.cleanup,startup.original.DedicatedCloneManager.cleanup)
        self.assertIs(startup.CloneManager.seed_case,startup.original.DedicatedCloneManager.seed_case)

    def test_fresh_startup_profile_has_all_current_roles_and_no_old_baseline_bridge(self):
        self.assertIs(workers.Inputs.__init__.__globals__['Runtime'],runtime.Runtime)
        self.assertIs(teacher._impl.run_task,runtime.run_task)
        self.assertIs(shared._impl.audit_episode,audit.audit_episode)
        self.assertIs(facade.run_controls.__globals__['audit_episode'],audit.audit_episode)
        self.assertFalse(workers.public_binding()['saved_baseline_from_different_startup_profile_allowed'])
        with self.assertRaises(AttributeError):getattr(facade,'complete_saved_baseline_trio')

if __name__=='__main__':unittest.main()
