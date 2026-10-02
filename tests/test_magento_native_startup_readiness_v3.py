"""Readiness cannot multiply aborted HTTP requests or accept an offline app."""
import inspect,json,unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
from magento_catalog_factory import native_startup_readiness_v3 as startup

class ReadinessTests(unittest.TestCase):
    def manager(self):
        manager=object.__new__(startup.CloneManager);manager.journal=Mock()
        manager.journal.run.return_value=json.dumps({'database_ready':True})
        return manager

    def test_native_dependencies_are_read_before_any_http_request(self):
        manager=self.manager();spec=SimpleNamespace(index=0,app='owned-app',search='owned-search')
        seen=[]
        def execute(label,container,*args,**kwargs):
            seen.append(args)
            if args[0]=='curl':return json.dumps({'status':'yellow','number_of_nodes':1,'timed_out':False})
            return '\n'.join(name+' RUNNING pid 1' for name in ['mysqld','php-fpm','nginx','redis-server'])
        manager._exec=execute;manager._wait_services(spec)
        self.assertFalse(any('http://127.0.0.1/admin' in args for args in seen))
        self.assertEqual(manager.journal.run.call_count,1)
        self.assertFalse(manager.journal.run.call_args.kwargs['mutating'])

    def test_single_bounded_http_warmup_never_replays_or_accepts_missing_response(self):
        manager=self.manager();spec=SimpleNamespace(index=0,app='owned-app')
        manager._exec=Mock(return_value='302');manager._single_http_warmup(spec)
        manager._exec.assert_called_once()
        self.assertIn('90',manager._exec.call_args.args)
        self.assertEqual(manager._exec.call_args.kwargs['timeout'],100)
        manager._exec=Mock(return_value='000')
        with self.assertRaisesRegex(startup.original.DedicatedLaneError,'single_bounded_real_http'):manager._single_http_warmup(spec)
        manager._exec.assert_called_once()

    def test_pre_supervisor_disables_unused_embedded_search_without_changing_scorer(self):
        code=startup.CloneManager.prepare.__code__
        literals='\n'.join(value for value in code.co_consts if isinstance(value,str))
        self.assertIn('/etc/supervisor.d/elasticsearch.ini',literals)
        self.assertIn('autostart=false',literals)
        self.assertIn('_single_http_warmup',code.co_names)
        self.assertIs(startup.CloneManager.seed_case,startup.original.DedicatedCloneManager.seed_case)
        self.assertIs(startup.CloneManager.cleanup,startup.original.DedicatedCloneManager.cleanup)

if __name__=='__main__':unittest.main()
