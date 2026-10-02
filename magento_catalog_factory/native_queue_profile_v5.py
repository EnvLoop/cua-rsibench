"""Bounded same-PID observation of QEMU fork/exec transition, no relaunch.

An empty /proc argv is never accepted as ownership. Only that typed startup
transition is reread while the single launched child is still running. All
nonempty foreign executables/prefixes retain V4 refusal semantics.
"""
from pathlib import Path
from hashlib import sha256
from types import FunctionType
import base64,json
from . import native_queue_profile_v4 as previous
if sha256(Path(previous.__file__).read_bytes()).hexdigest()!='0651b6cb004d5a1558434ba31dfd04e22ee80e5a7e15e68c27a99e351d1403d5':
    raise ValueError('Frozen V4 dual process proof changed')
for name in ('TOPIC','APP','MAX_MESSAGES','PACKAGE_PINS','ARGV','CMDLINE_SHA256','GUEST_PHP','QEMU',
    'require','token','directory','validate_identity','QUEUE_READ_PHP','validate_queue','close_request_php','exit_read_php'):
    globals()[name]=getattr(previous,name)
PROFILE='magento-native-single-attribute-consumer-v5-bounded-native-exec-transition'
IDENTITY_PHP=previous.IDENTITY_PHP
needle="$cmd=file_get_contents($p.'/cmdline');"
if IDENTITY_PHP.count(needle)!=1:raise ValueError('Checked native command read changed')
IDENTITY_PHP=IDENTITY_PHP.replace(needle,needle+"if($cmd==='')throw new Exception('native_empty_argv_transient');")
SUPERVISOR_PHP=previous.SUPERVISOR_PHP.replace(previous.IDENTITY_PHP,IDENTITY_PHP)
old_reader=base64.b64encode((previous.IDENTITY_PHP+'echo json_encode(identity((int)$argv[1]));').encode()).decode()
new_reader=base64.b64encode((IDENTITY_PHP+'echo json_encode(identity((int)$argv[1]));').encode()).decode()
if SUPERVISOR_PHP.count(old_reader)!=1:raise ValueError('Checked external supervisor reader changed')
SUPERVISOR_PHP=SUPERVISOR_PHP.replace(old_reader,new_reader)
needle="$candidate=identity($status['pid']);"
if SUPERVISOR_PHP.count(needle)!=1:raise ValueError('Checked one-consumer readiness observation changed')
SUPERVISOR_PHP=SUPERVISOR_PHP.replace(needle,
    "try{$candidate=identity($status['pid']);}catch(Exception $e){if($e->getMessage()!=='native_empty_argv_transient')throw $e;usleep(10000);continue;}")
SUPERVISOR_PHP=SUPERVISOR_PHP.replace('magento-native-consumer-launch-v4','magento-native-consumer-launch-v5').replace(
    'magento-native-consumer-owner-v4','magento-native-consumer-owner-v5').replace(
    'magento-native-consumer-exit-v4','magento-native-consumer-exit-v5')
# Keep actual fatal startup diagnostics in the uniquely claimed owner directory.
needle="$root='/tmp/envloop-magento-native-queue-'.$token;umask(0077);if(!mkdir($root,0700))throw new Exception('owner_collision');"
if SUPERVISOR_PHP.count(needle)!=1:raise ValueError('Checked one-use owner namespace changed')
SUPERVISOR_PHP=SUPERVISOR_PHP.replace(needle,needle+r'''register_shutdown_function(function()use($root){$error=error_get_last();if($error!==null&&in_array($error['type'],[E_ERROR,E_PARSE,E_CORE_ERROR,E_COMPILE_ERROR,E_USER_ERROR],true)){$f=fopen($root.'/startup-failure.private.json','x');if($f){fwrite($f,json_encode(['schema'=>'magento-native-consumer-startup-failure-v5','error'=>$error,'recorded_after_actual_failure'=>true]));fflush($f);fclose($f);}}});''')

def owner_read_php(value):
    root=directory(value)
    return IDENTITY_PHP+"$root="+json.dumps(root)+r''';$file=$root.'/owner.private.json';if(!is_file($file)){if(is_file($root.'/startup-failure.private.json')){echo json_encode(['owner_available'=>false,'startup_failure'=>json_decode(file_get_contents($root.'/startup-failure.private.json'),true)]);exit;}echo json_encode(['owner_available'=>false]);exit;}if(is_link($file))throw new Exception('unsafe_owner');$owner=json_decode(file_get_contents($file),true);$actual=identity($owner['child']['pid']);$parent=identity($owner['supervisor']['pid']);
if($actual!==$owner['child'])throw new Exception('owned_consumer_not_current');echo json_encode(['owner'=>$owner,'actual_child'=>$actual,'actual_supervisor'=>$parent,'running'=>true],JSON_UNESCAPED_SLASHES);'''

def _counterpart(method,before,after):
    import inspect,textwrap
    source=textwrap.dedent(inspect.getsource(method))
    if source.count(before)!=1:raise ValueError('Checked typed owner/exit counterpart changed')
    namespace={**method.__globals__,'SUPERVISOR_PHP':SUPERVISOR_PHP}
    exec(compile(source.replace(before,after),'magento-same-native-proof-startup-transition-v5','exec'),namespace)
    return namespace[method.__name__]
validate_owner=_counterpart(previous.validate_owner,'magento-native-consumer-owner-v4','magento-native-consumer-owner-v5')
validate_exit=_counterpart(previous.validate_exit,'magento-native-consumer-exit-v4','magento-native-consumer-exit-v5')
