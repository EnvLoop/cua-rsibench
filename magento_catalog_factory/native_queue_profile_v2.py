"""One owned native Magento attribute consumer; actor tools remain GUI-only."""
from __future__ import annotations
import json,re
from hashlib import sha256
TOPIC='product_action_attribute.update'
PROFILE='magento-native-single-attribute-consumer-v2'
APP='/var/www/magento2'
MAX_MESSAGES=10000
PACKAGE_PINS={
 'vendor/magento/module-message-queue/Console/StartConsumerCommand.php':'df44f00aa598f68c1a2d2ac18d219ed98ed7496fcd3fd267e3d9a3a1d5bdf99b',
 'vendor/magento/module-catalog/Controller/Adminhtml/Product/Action/Attribute/Save.php':'5613846622a2996bff0d435174435c2b4b2d5f4e7569997921738837cb3f2d7d',
 'vendor/magento/module-catalog/Model/Attribute/Backend/Consumer.php':'62e4a4c772de7f762995f810814ad7f055f8ce20700572a01108844ea8908223',
}
ARGV=['php',APP+'/bin/magento','queue:consumers:start',TOPIC,'--max-messages=10000','--single-thread']
CMDLINE_SHA256=sha256(('\0'.join(ARGV)+'\0').encode()).hexdigest()

def require(value,code):
 if not value:raise ValueError(code)

def token(value):
 require(type(value) is str and re.fullmatch('[0-9a-f]{24}',value),'Owned queue token malformed');return value

def directory(value):return '/tmp/envloop-magento-native-queue-'+token(value)

# All database credentials stay inside Magento's owned app. Only channel state
# and content hashes leave the read-only native inspector.
QUEUE_READ_PHP=r'''$cfg=include '/var/www/magento2/app/etc/env.php';$c=$cfg['db']['connection']['default'];
$db=new PDO('mysql:host='.$c['host'].';dbname='.$c['dbname'],$c['username'],$c['password'],[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]);
$p=$cfg['db']['table_prefix']??'';if(!preg_match('/^[a-zA-Z0-9_]*$/',$p))throw new Exception('prefix');
$topic='product_action_attribute.update';
$messages=$db->query("SELECT id AS message_id,topic_name,body FROM `{$p}queue_message` WHERE topic_name='product_action_attribute.update' ORDER BY id")->fetchAll(PDO::FETCH_ASSOC);
$states=$db->query("SELECT s.message_id,s.queue_id,s.status,s.updated_at FROM `{$p}queue_message_status` s JOIN `{$p}queue_message` m ON m.id=s.message_id WHERE m.topic_name='product_action_attribute.update' ORDER BY s.message_id,s.queue_id")->fetchAll(PDO::FETCH_ASSOC);
$operations=$db->query("SELECT id,bulk_uuid,topic_name,status,error_code,result_message,serialized_data FROM `{$p}magento_operation` WHERE topic_name='product_action_attribute.update' ORDER BY id")->fetchAll(PDO::FETCH_ASSOC);
foreach($messages as &$m){$m['body_sha256']=hash('sha256',$m['body']);unset($m['body']);}unset($m);
foreach($operations as &$o){$o['serialized_data_sha256']=hash('sha256',$o['serialized_data']);unset($o['serialized_data']);}unset($o);
$pending=0;$failed=0;foreach($states as $s){$v=(int)$s['status'];if(!in_array($v,[2,3,4,5,6,7],true))throw new Exception('queue_status');if(in_array($v,[2,3,5],true))$pending++;if($v===6)$failed++;}
foreach($operations as $o){$v=(int)$o['status'];if(!in_array($v,[1,2,3,4,5],true))throw new Exception('operation_status');if(in_array($v,[2,4],true))$pending++;if(in_array($v,[3,5],true))$failed++;}
echo json_encode(['schema'=>'magento-owned-native-queue-state-v2','topic'=>$topic,'messages'=>$messages,'states'=>$states,'operations'=>$operations,'pending'=>$pending,'failed'=>$failed,'consumers_wait_for_messages'=>$cfg['queue']['consumers_wait_for_messages']??1],JSON_UNESCAPED_SLASHES);'''

SUPERVISOR_PHP=r'''$token=$argv[1];$deadline=(float)$argv[2];
if(!preg_match('/^[a-f0-9]{24}$/',$token)||$deadline<=microtime(true)||$deadline>microtime(true)+1200)throw new Exception('bounded_owner');
$root='/tmp/envloop-magento-native-queue-'.$token;umask(0077);if(!mkdir($root,0700))throw new Exception('owner_collision');
function retain($path,$v){$f=fopen($path,'x');if(!$f)throw new Exception('one_use_receipt');fwrite($f,json_encode($v,JSON_UNESCAPED_SLASHES));fflush($f);if(function_exists('fsync'))fsync($f);fclose($f);}
function identity($pid){$p='/proc/'.$pid;$s=file_get_contents($p.'/stat');$a=explode(' ',substr($s,strrpos($s,')')+2));$cmd=file_get_contents($p.'/cmdline');$status=file_get_contents($p.'/status');if(!preg_match('/^Uid:\s+(\d+)/m',$status,$u))throw new Exception('uid');return ['pid'=>(int)$pid,'ppid'=>(int)$a[1],'start_ticks'=>$a[19],'uid'=>(int)$u[1],'cmdline_sha256'=>hash('sha256',$cmd),'exe'=>readlink($p.'/exe')];}
$pins=json_decode('PINS',true);foreach($pins as $relative=>$expected){if(hash_file('sha256','/var/www/magento2/'.$relative)!==$expected)throw new Exception('pinned_package_source');}
$args=json_decode('ARGS',true);retain($root.'/launch-intent.private.json',['schema'=>'magento-native-consumer-launch-v2','token'=>$token,'argv'=>$args,'deadline_wall'=>$deadline,'one_new_process'=>true,'replay_authorized'=>false]);
$out=$root.'/consumer.stdout.private.log';$err=$root.'/consumer.stderr.private.log';
$proc=proc_open($args,[0=>['file','/dev/null','r'],1=>['file',$out,'a'],2=>['file',$err,'a']],$pipes,'/var/www/magento2');
if(!is_resource($proc))throw new Exception('consumer_launch_unavailable');$status=proc_get_status($proc);$id=null;$readyUntil=min($deadline,microtime(true)+5);
while(microtime(true)<$readyUntil){$status=proc_get_status($proc);if(!$status['running'])throw new Exception('consumer_exited_before_owner');$candidate=identity($status['pid']);if($candidate['ppid']===getmypid()&&$candidate['uid']===0&&$candidate['cmdline_sha256']==='CMDHASH'){$id=$candidate;break;}usleep(10000);}
if($id===null)throw new Exception('consumer_native_identity');
$owner=['schema'=>'magento-native-consumer-owner-v2','token'=>$token,'supervisor'=>identity(getmypid()),'child'=>$id,'argv'=>$args,'topic'=>'product_action_attribute.update','max_messages'=>10000,'deadline_wall'=>$deadline,'package_sha256s'=>$pins];retain($root.'/owner.private.json',$owner);
$reason=null;$term=false;
while(true){$status=proc_get_status($proc);if(!$status['running'])break;
 if(!$term&&(file_exists($root.'/close-request.private.json')||microtime(true)>=$deadline)){$current=identity($id['pid']);if($current!==$id)throw new Exception('consumer_identity_changed_before_close');
  $reason=microtime(true)>=$deadline?'absolute_owned_deadline':'owned_close_request';
  if($reason==='owned_close_request'){$request=json_decode(file_get_contents($root.'/close-request.private.json'),true);if($request['token']!==$token)throw new Exception('foreign_close_request');}
  retain($root.'/stop-intent.private.json',['reason'=>$reason,'child'=>$id,'before_signal'=>true,'replay_authorized'=>false]);
  $term=proc_terminate($proc,15);if(!$term)throw new Exception('owned_stop_unavailable');
 }
 usleep(100000);
}
$code=$status['exitcode'];$closed=proc_close($proc);$absent=!file_exists('/proc/'.$id['pid']);
retain($root.'/exit.private.json',['schema'=>'magento-native-consumer-exit-v2','token'=>$token,'child'=>$id,'reason'=>$reason??'unexpected_process_exit','first_observed_exitcode'=>$code,'signaled'=>$status['signaled'],'termsig'=>$status['termsig'],'proc_close_returncode'=>$closed,'child_pid_absent'=>$absent,'stop_signal_returned'=>$term,'stdout_sha256'=>hash_file('sha256',$out),'stderr_sha256'=>hash_file('sha256',$err),'closed_wall'=>microtime(true)]);'''.replace('PINS',json.dumps(PACKAGE_PINS,separators=(',',':'))).replace('ARGS',json.dumps(ARGV,separators=(',',':'))).replace('CMDHASH',CMDLINE_SHA256)

# Detached launch acknowledgement is never process-start authority. Probe the
# retained native owner plus current /proc identity in the exact owned app.
def owner_read_php(value):
 root=directory(value)
 return r'''$root='ROOT';$file=$root.'/owner.private.json';if(!is_file($file)){echo json_encode(['owner_available'=>false]);exit;}if(is_link($file))throw new Exception('unsafe_owner');$owner=json_decode(file_get_contents($file),true);$pid=$owner['child']['pid'];
$s=file_get_contents('/proc/'.$pid.'/stat');$a=explode(' ',substr($s,strrpos($s,')')+2));$cmd=file_get_contents('/proc/'.$pid.'/cmdline');$status=file_get_contents('/proc/'.$pid.'/status');preg_match('/^Uid:\s+(\d+)/m',$status,$u);
$actual=['pid'=>(int)$pid,'ppid'=>(int)$a[1],'start_ticks'=>$a[19],'uid'=>(int)$u[1],'cmdline_sha256'=>hash('sha256',$cmd),'exe'=>readlink('/proc/'.$pid.'/exe')];
if($actual!==$owner['child'])throw new Exception('owned_consumer_not_current');echo json_encode(['owner'=>$owner,'actual_child'=>$actual,'running'=>true],JSON_UNESCAPED_SLASHES);'''.replace('ROOT',root)

def close_request_php(value):
 root=directory(value)
 return "$root="+json.dumps(root)+";$f=fopen($root.'/close-request.private.json','x');if(!$f)throw new Exception('close_request_replay');fwrite($f,json_encode(['token'=>'"+token(value)+"']));fflush($f);if(function_exists('fsync'))fsync($f);fclose($f);echo json_encode(['close_request_written'=>true]);"

def exit_read_php(value):
 root=directory(value)
 return "$root="+json.dumps(root)+";$p=$root.'/exit.private.json';if(!is_file($p)||is_link($p)){echo json_encode(['exit_available'=>false]);exit;}$exit=json_decode(file_get_contents($p),true);$owner=json_decode(file_get_contents($root.'/owner.private.json'),true);$parentAbsent=!file_exists('/proc/'.$owner['supervisor']['pid']);echo json_encode(['exit_available'=>true,'exit'=>$exit,'supervisor_pid_absent'=>$parentAbsent,'stdout'=>base64_encode(file_get_contents($root.'/consumer.stdout.private.log')),'stderr'=>base64_encode(file_get_contents($root.'/consumer.stderr.private.log'))],JSON_UNESCAPED_SLASHES);"

def validate_owner(value,scope_token):
 owner=value.get('owner',{});child=owner.get('child',{})
 require(value.get('running') is True and owner.get('schema')=='magento-native-consumer-owner-v2' and owner.get('token')==token(scope_token) and owner.get('topic')==TOPIC and owner.get('argv')==ARGV and owner.get('max_messages')==MAX_MESSAGES and owner.get('package_sha256s')==PACKAGE_PINS and child==value.get('actual_child') and child.get('cmdline_sha256')==CMDLINE_SHA256 and child.get('uid')==0 and child.get('ppid')==owner.get('supervisor',{}).get('pid'),'Actual owned native consumer identity/source changed')
 return owner

def validate_queue(value):
 require(type(value) is dict and value.get('schema')=='magento-owned-native-queue-state-v2' and value.get('topic')==TOPIC and type(value.get('pending')) is int and value['pending']>=0 and type(value.get('failed')) is int and value['failed']>=0 and value.get('consumers_wait_for_messages') in {1,True},'Native queue evidence unavailable/unknown')
 for group in ['messages','states','operations']:require(type(value.get(group)) is list,'Native queue row set missing')
 pending=failed=0
 for row in value['states']:
  status=int(row['status']);require(status in {2,3,4,5,6,7},'Unknown native message status')
  pending+=int(status in {2,3,5});failed+=int(status==6)
 for row in value['operations']:
  status=int(row['status']);require(status in {1,2,3,4,5} and row['topic_name']==TOPIC,'Unknown/foreign native operation')
  pending+=int(status in {2,4});failed+=int(status in {3,5})
 require(value['pending']==pending and value['failed']==failed,'Native queue aggregate does not match raw status rows')
 return value

def validate_exit(value,owner):
 require(value.get('exit_available') is True and value.get('supervisor_pid_absent') is True,'Owned consumer supervisor close unknown')
 exit=value['exit'];require(exit.get('schema')=='magento-native-consumer-exit-v2' and exit.get('token')==owner['token'] and exit.get('child')==owner['child'] and exit.get('reason')=='owned_close_request' and exit.get('child_pid_absent') is True and exit.get('stop_signal_returned') is True and type(exit.get('first_observed_exitcode')) is int and (exit['first_observed_exitcode'] in {0,143} or exit['first_observed_exitcode']==-1 and exit.get('signaled') is True and exit.get('termsig')==15),'Owned native consumer exit/ack unknown')
 return exit
