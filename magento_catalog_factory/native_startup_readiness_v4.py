"""Critical service probes return0 individually despite intentional stopped peers."""
import inspect,json,textwrap,time
from types import FunctionType
from contextlib import asynccontextmanager
from . import native_startup_readiness_v3 as previous
from . import native_quote_navigation_v2 as quote
original=previous.original
DATABASE_READY_PHP=previous.DATABASE_READY_PHP

class CloneManager(previous.CloneManager):
    def _wait_services(self,spec):
        deadline=time.monotonic()+240;attempt=0
        while time.monotonic()<deadline:
            try:
                health=json.loads(self._exec(f'p{spec.index}_search_health_native_{attempt:03d}',spec.search,
                    'curl','-fsS','--max-time','5','http://127.0.0.1:9200/_cluster/health',timeout=10))
                states=[]
                for name in ('mysqld','php-fpm','nginx','redis-server'):
                    status=self._exec(f'p{spec.index}_native_service_{name}_{attempt:03d}',spec.app,
                        'supervisorctl','status',name,timeout=15)
                    parts=status.split();states.append(len(parts)>=2 and parts[0]==name and parts[1]=='RUNNING')
                database=json.loads(self.journal.run(f'p{spec.index}_database_ready_{attempt:03d}',
                    ('exec',spec.app,'php','-r',DATABASE_READY_PHP),mutating=False,timeout=10))
                if health.get('status') in ('yellow','green') and health.get('number_of_nodes')==1 and not health.get('timed_out') and database.get('database_ready') is True and all(states):
                    self.journal._append({'event':'native_dependency_readiness','index':spec.index,
                        'database_select_one':True,'four_individual_critical_processes_running':True,'http_requests_sent':0})
                    return
            except (original.DedicatedLaneError,ValueError,KeyError,json.JSONDecodeError):pass
            attempt+=1;time.sleep(2)
        raise original.DedicatedLaneError('native_database_fpm_search_readiness_failed')

method=quote.dedicated_open.__wrapped__
scoped=FunctionType(method.__code__,{**method.__globals__,'DedicatedCloneManager':CloneManager},
    method.__name__,method.__defaults__,method.__closure__)
scoped.__kwdefaults__=method.__kwdefaults__
dedicated_open=asynccontextmanager(scoped)
source=textwrap.dedent(inspect.getsource(quote.actor.Runtime.open_case.__wrapped__))
for before,after,count in [('async with super().open_case(case,out_dir) as active:',
    'async with dedicated_open(self,case,out_dir) as active:',1),('original.DedicatedCloneManager','CloneManager',2)]:
    if source.count(before)!=count:raise ValueError('Checked prepared native identity bridge changed')
    source=source.replace(before,after)
namespace={**quote.actor.Runtime.open_case.__wrapped__.__globals__,'CloneManager':CloneManager,'dedicated_open':dedicated_open}
exec(compile(source,'magento-native-critical-services-current-prepared-witness-v4','exec'),namespace)
class Runtime(quote.actor.Runtime):
    open_case=namespace['open_case']
