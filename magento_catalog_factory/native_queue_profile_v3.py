"""Exact native PHP ownership on native AMD64 or the pinned QEMU launcher.

Raw /proc identity remains authoritative. Only the known two-element QEMU
launcher prefix is decoded; all original CLI arguments, parent, UID and start
ticks are retained and rechecked. Queue rows and package source pins stay V2.
"""
from hashlib import sha256
from pathlib import Path
import json
from . import native_queue_profile_v2 as original

ROOT=Path(__file__).resolve().parents[1]
if sha256(Path(original.__file__).read_bytes()).hexdigest()!='174276f962e515f6090e569bae8bff7cfb2db543462a6b93546ed64ac0dbd312':
    raise ValueError('Frozen queue profile source changed')
TOPIC,APP,MAX_MESSAGES,PACKAGE_PINS,ARGV,CMDLINE_SHA256=(getattr(original,k) for k in
    ('TOPIC','APP','MAX_MESSAGES','PACKAGE_PINS','ARGV','CMDLINE_SHA256'))
PROFILE='magento-native-single-attribute-consumer-v3-exact-qemu-or-native'
require,token,directory=original.require,original.token,original.directory
QUEUE_READ_PHP=original.QUEUE_READ_PHP
GUEST_PHP='/usr/local/bin/php'
QEMU='/usr/bin/qemu-x86_64'
IDENTITY_PHP=r'''function identity($pid){$p='/proc/'.$pid;$s=file_get_contents($p.'/stat');$a=explode(' ',substr($s,strrpos($s,')')+2));$cmd=file_get_contents($p.'/cmdline');$status=file_get_contents($p.'/status');if(!preg_match('/^Uid:\s+(\d+)/m',$status,$u))throw new Exception('uid');
$native=explode(chr(0),$cmd);if(array_pop($native)!=='')throw new Exception('native_argv_not_nul_terminated');$exe=readlink($p.'/exe');$guest=$native;$transport='native_php';
if($exe==='/usr/bin/qemu-x86_64'){if(count($native)<3||$native[0]!=='/usr/bin/qemu-x86_64'||$native[1]!=='/usr/local/bin/php')throw new Exception('foreign_emulator_prefix');$guest=array_slice($native,2);$transport='qemu_x86_64_php';}
elseif($exe!=='/usr/local/bin/php')throw new Exception('foreign_native_executable');
return ['pid'=>(int)$pid,'ppid'=>(int)$a[1],'start_ticks'=>$a[19],'uid'=>(int)$u[1],'cmdline_sha256'=>hash('sha256',$cmd),'exe'=>$exe,'native_argv'=>$native,'guest_argv'=>$guest,'guest_cmdline_sha256'=>hash('sha256',implode(chr(0),$guest).chr(0)),'execution_transport'=>$transport];}'''
source=original.SUPERVISOR_PHP
start=source.index('function identity($pid)');end=source.index('\n$pins=',start)
source=source[:start]+IDENTITY_PHP+source[end:]
if source.count("$candidate['cmdline_sha256']===")!=1:raise ValueError('Frozen owner readiness predicate changed')
source=source.replace("$candidate['cmdline_sha256']===","$candidate['guest_cmdline_sha256']===")
SUPERVISOR_PHP=source.replace('magento-native-consumer-launch-v2','magento-native-consumer-launch-v3').replace(
    'magento-native-consumer-owner-v2','magento-native-consumer-owner-v3').replace(
    'magento-native-consumer-exit-v2','magento-native-consumer-exit-v3')

def normalize_native_argv(exe,native):
    require(type(native) is list and bool(native) and all(type(v) is str and '\0' not in v for v in native),
        'Native process argument bytes unavailable')
    if exe==QEMU:
        require(len(native)>=3 and native[:2]==[QEMU,GUEST_PHP],'Foreign emulator prefix refused')
        return native[2:],'qemu_x86_64_php'
    require(exe==GUEST_PHP,'Foreign native executable refused')
    return native,'native_php'

def validate_identity(value):
    fields={'pid','ppid','start_ticks','uid','cmdline_sha256','exe','native_argv','guest_argv',
        'guest_cmdline_sha256','execution_transport'}
    require(type(value) is dict and set(value)==fields,'Exact native process identity required')
    guest,transport=normalize_native_argv(value['exe'],value['native_argv'])
    encode=lambda values: ('\0'.join(values)+'\0').encode()
    require(value['guest_argv']==guest and value['execution_transport']==transport and
        value['cmdline_sha256']==sha256(encode(value['native_argv'])).hexdigest() and
        value['guest_cmdline_sha256']==sha256(encode(guest)).hexdigest() and
        type(value['pid']) is int and value['pid']>0 and type(value['ppid']) is int and value['ppid']>=0 and
        type(value['start_ticks']) is str and value['start_ticks'].isdigit() and type(value['uid']) is int and value['uid']==0,
        'Native argv/hash/parent/start identity changed')
    return value

def owner_read_php(value):
    root=directory(value)
    return IDENTITY_PHP+"$root="+json.dumps(root)+r''';$file=$root.'/owner.private.json';if(!is_file($file)){echo json_encode(['owner_available'=>false]);exit;}if(is_link($file))throw new Exception('unsafe_owner');$owner=json_decode(file_get_contents($file),true);$actual=identity($owner['child']['pid']);
if($actual!==$owner['child'])throw new Exception('owned_consumer_not_current');echo json_encode(['owner'=>$owner,'actual_child'=>$actual,'running'=>true],JSON_UNESCAPED_SLASHES);'''

close_request_php=original.close_request_php
exit_read_php=original.exit_read_php
validate_queue=original.validate_queue

def validate_owner(value,scope_token):
    owner=value.get('owner',{});child=validate_identity(owner.get('child',{}));parent=validate_identity(owner.get('supervisor',{}))
    require(value.get('running') is True and owner.get('schema')=='magento-native-consumer-owner-v3' and
        owner.get('token')==token(scope_token) and owner.get('topic')==TOPIC and owner.get('argv')==ARGV and
        owner.get('max_messages')==MAX_MESSAGES and owner.get('package_sha256s')==PACKAGE_PINS and
        child==value.get('actual_child') and child['guest_argv']==ARGV and child['guest_cmdline_sha256']==CMDLINE_SHA256 and
        child['ppid']==parent['pid'] and child['execution_transport']==parent['execution_transport'],
        'Actual owned native consumer identity/source changed')
    return owner

def validate_exit(value,owner):
    require(value.get('exit_available') is True and value.get('supervisor_pid_absent') is True,
        'Owned consumer supervisor close unknown')
    exit=value['exit']
    require(exit.get('schema')=='magento-native-consumer-exit-v3' and exit.get('token')==owner['token'] and
        exit.get('child')==owner['child'] and exit.get('reason')=='owned_close_request' and
        exit.get('child_pid_absent') is True and exit.get('stop_signal_returned') is True and
        type(exit.get('first_observed_exitcode')) is int and (exit['first_observed_exitcode'] in {0,143} or
        exit['first_observed_exitcode']==-1 and exit.get('signaled') is True and exit.get('termsig')==15),
        'Owned native consumer exit/ack unknown')
    return exit
