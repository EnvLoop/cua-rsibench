"""Native dependency readiness then one real HTTP warmup, no request storm.

Cron and unused embedded x86 search never autostart in the disposable app.
The original native ARM search sidecar and SQL/scorer/reset remain unchanged.
An unresponsive application is never accepted as ready.
"""
import asyncio,inspect,json,textwrap,time
from types import FunctionType
from tools import magento_dedicated_train_lane_v066 as original
from . import native_quote_navigation_v2 as quote

DATABASE_READY_PHP=r'''try{$cfg=include '/var/www/magento2/app/etc/env.php';$c=$cfg['db']['connection']['default'];$db=new PDO('mysql:host='.$c['host'].';dbname='.$c['dbname'],$c['username'],$c['password'],[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_TIMEOUT=>2]);echo json_encode(['database_ready'=>$db->query('SELECT 1')->fetchColumn()==1]);}catch(Throwable $e){echo json_encode(['database_ready'=>false]);}'''

class CloneManager(original.DedicatedCloneManager):
    def _wait_services(self,spec):
        deadline=time.monotonic()+240;attempt=0
        while time.monotonic()<deadline:
            try:
                health=json.loads(self._exec(f'p{spec.index}_search_health_native_{attempt:03d}',spec.search,
                    'curl','-fsS','--max-time','5','http://127.0.0.1:9200/_cluster/health',timeout=10))
                services=self._exec(f'p{spec.index}_native_services_{attempt:03d}',spec.app,'supervisorctl','status',timeout=15)
                database=json.loads(self.journal.run(f'p{spec.index}_database_ready_{attempt:03d}',
                    ('exec',spec.app,'php','-r',DATABASE_READY_PHP),mutating=False,timeout=10))
                ready_services=all(any(line.split()[0]==name and 'RUNNING' in line for line in services.splitlines())
                    for name in ('mysqld','php-fpm','nginx','redis-server'))
                if health.get('status') in ('yellow','green') and health.get('number_of_nodes')==1 and not health.get('timed_out') and database.get('database_ready') is True and ready_services:
                    self.journal._append({'event':'native_dependency_readiness','index':spec.index,
                        'database_select_one':True,'critical_processes_running':True,'http_requests_sent':0})
                    return
            except (original.DedicatedLaneError,ValueError,KeyError,json.JSONDecodeError):pass
            attempt+=1;time.sleep(2)
        raise original.DedicatedLaneError('native_database_fpm_search_readiness_failed')

    def _single_http_warmup(self,spec):
        status=self._exec(f'p{spec.index}_single_http_warmup',spec.app,'curl','-sS','-o','/dev/null','-w',
            '%{http_code}','--max-time','90','http://127.0.0.1/admin',timeout=100)
        if status.strip() not in ('200','301','302'):raise original.DedicatedLaneError('single_bounded_real_http_warmup_failed')
        self.journal._append({'event':'single_native_http_readiness_verified','index':spec.index,
            'http_status':status.strip(),'after_database_and_search_config':True,'aborted_requests_replayed':False})

source=textwrap.dedent(inspect.getsource(original.DedicatedCloneManager.prepare))
old='"/etc/supervisor.d/cron.ini && "'
new='"/etc/supervisor.d/cron.ini /etc/supervisor.d/elasticsearch.ini && "'
if source.count(old)!=1:raise ValueError('Checked original pre-supervisor profile changed')
source=source.replace(old,new)
old='"grep -q \'^autostart=false$\' /etc/supervisor.d/cron.ini && "'
new='"grep -q \'^autostart=false$\' /etc/supervisor.d/cron.ini && grep -q \'^autostart=false$\' /etc/supervisor.d/elasticsearch.ini && "'
if source.count(old)!=1:raise ValueError('Checked pre-supervisor profile verification changed')
source=source.replace(old,new)
old='''self._exec(f"p{spec.index}_embedded_search_stop", spec.app,
               "supervisorctl", "stop", "elasticsearch", timeout=30)'''
if source.count(old)!=1:raise ValueError('Checked original embedded search stop boundary changed')
source=source.replace(old,'''embedded=self._exec(f"p{spec.index}_embedded_search_never_started",spec.app,
               "cat","/etc/supervisor.d/elasticsearch.ini",timeout=30)
    if "autostart=false" not in embedded or "autostart=true" in embedded:
        raise DedicatedLaneError("embedded_search_autostart_profile_unproved")''')
old='''self.prepared[spec.index] = proof'''
if source.count(old)!=1:raise ValueError('Checked original prepared evidence boundary changed')
source=source.replace(old,'self._single_http_warmup(spec)\n    '+old)
namespace=dict(original.DedicatedCloneManager.prepare.__globals__)
exec(compile(source,'magento-dependency-readiness-before-single-http-v3','exec'),namespace)
CloneManager.prepare=namespace['prepare']

method=quote.dedicated_open.__wrapped__
scoped=FunctionType(method.__code__,{**method.__globals__,'DedicatedCloneManager':CloneManager},
    method.__name__,method.__defaults__,method.__closure__)
scoped.__kwdefaults__=method.__kwdefaults__
dedicated_open=__import__('contextlib').asynccontextmanager(scoped)
method=quote.Runtime.open_case.__wrapped__
scoped=FunctionType(method.__code__,{**method.__globals__,'dedicated_open':dedicated_open},
    method.__name__,method.__defaults__,method.__closure__)
scoped.__kwdefaults__=method.__kwdefaults__
class Runtime(quote.Runtime):
    open_case=__import__('contextlib').asynccontextmanager(scoped)
