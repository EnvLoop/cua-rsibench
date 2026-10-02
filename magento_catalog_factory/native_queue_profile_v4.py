"""Retain both QEMU self-view and independently read supervisor /proc identity.

QEMU rewrites /proc/self into guest PHP while another process observes its
native launcher. Compare exact stable guest identity and retain both raw views;
never infer parent ownership from the child PPID alone.
"""
import base64
from pathlib import Path
from hashlib import sha256
import json
from . import native_queue_profile_v3 as previous
if sha256(Path(previous.__file__).read_bytes()).hexdigest()!='a48ad303a4ad6f5e06dd8aa0a302984029f76fe7525fbefd693dd422bf9c9b74':
    raise ValueError('Frozen V3 process proof changed')
TOPIC,APP,MAX_MESSAGES,PACKAGE_PINS,ARGV,CMDLINE_SHA256,GUEST_PHP,QEMU=(getattr(previous,k) for k in
    ('TOPIC','APP','MAX_MESSAGES','PACKAGE_PINS','ARGV','CMDLINE_SHA256','GUEST_PHP','QEMU'))
require,token,directory,validate_identity=previous.require,previous.token,previous.directory,previous.validate_identity
IDENTITY_PHP=previous.IDENTITY_PHP
PROFILE='magento-native-single-attribute-consumer-v4-dual-proc-view'
SUPERVISOR_PHP=previous.SUPERVISOR_PHP.replace('magento-native-consumer-launch-v3','magento-native-consumer-launch-v4').replace(
    'magento-native-consumer-owner-v3','magento-native-consumer-owner-v4').replace(
    'magento-native-consumer-exit-v3','magento-native-consumer-exit-v4')
_reader=base64.b64encode((IDENTITY_PHP+'echo json_encode(identity((int)$argv[1]));').encode()).decode()
_native_parent=r'''$parentSelf=identity(getmypid());$reader=['php','-r',base64_decode('READER'),'--',(string)getmypid()];
$readProc=proc_open($reader,[0=>['file','/dev/null','r'],1=>['pipe','w'],2=>['pipe','w']],$readPipes,'/var/www/magento2');if(!is_resource($readProc))throw new Exception('native_parent_reader_unavailable');
$parentRaw=stream_get_contents($readPipes[1]);$parentErr=stream_get_contents($readPipes[2]);fclose($readPipes[1]);fclose($readPipes[2]);$readerCode=proc_close($readProc);
if($readerCode!==0||$parentErr!==''||strlen($parentRaw)>65536)throw new Exception('native_parent_readback_unknown');$parentNative=json_decode($parentRaw,true);
foreach(['pid','ppid','uid','guest_argv','guest_cmdline_sha256'] as $key){if($parentNative[$key]!==$parentSelf[$key])throw new Exception('native_parent_guest_identity_changed');}
'''.replace('READER',_reader)
_before="$out=$root.'/consumer.stdout.private.log';"
if SUPERVISOR_PHP.count(_before)!=1:raise ValueError('Checked parent native read boundary changed')
SUPERVISOR_PHP=SUPERVISOR_PHP.replace(_before,_native_parent+_before)
_before="'supervisor'=>identity(getmypid()),'child'=>$id"
if SUPERVISOR_PHP.count(_before)!=1:raise ValueError('Checked parent owner proof boundary changed')
SUPERVISOR_PHP=SUPERVISOR_PHP.replace(_before,"'supervisor'=>$parentNative,'supervisor_self_view'=>$parentSelf,'child'=>$id")
QUEUE_READ_PHP=previous.QUEUE_READ_PHP
validate_queue=previous.validate_queue
close_request_php=previous.close_request_php
exit_read_php=previous.exit_read_php

def owner_read_php(value):
    root=directory(value)
    return IDENTITY_PHP+"$root="+json.dumps(root)+r''';$file=$root.'/owner.private.json';if(!is_file($file)){echo json_encode(['owner_available'=>false]);exit;}if(is_link($file))throw new Exception('unsafe_owner');$owner=json_decode(file_get_contents($file),true);$actual=identity($owner['child']['pid']);$parent=identity($owner['supervisor']['pid']);
if($actual!==$owner['child'])throw new Exception('owned_consumer_not_current');echo json_encode(['owner'=>$owner,'actual_child'=>$actual,'actual_supervisor'=>$parent,'running'=>true],JSON_UNESCAPED_SLASHES);'''

def validate_owner(value,scope_token):
    owner=value.get('owner',{});child=validate_identity(owner.get('child',{}))
    parent=validate_identity(owner.get('supervisor',{}));current_parent=validate_identity(value.get('actual_supervisor',{}))
    self_view=validate_identity(owner.get('supervisor_self_view',{}))
    stable=('pid','ppid','start_ticks','uid','guest_argv','guest_cmdline_sha256')
    parent_args=parent['guest_argv']
    require(len(parent_args)==6 and parent_args[:4]==['php','-r',SUPERVISOR_PHP,'--'] and
        parent_args[4]==token(scope_token) and float(parent_args[5])==owner.get('deadline_wall'),
        'Exact owned supervisor program/token/deadline required')
    require(parent==current_parent and all(parent[key]==self_view[key] for key in
            ('pid','ppid','uid','guest_argv','guest_cmdline_sha256')) and
        (self_view['execution_transport'],parent['execution_transport']) in {
            ('native_php','native_php'),('native_php','qemu_x86_64_php'),('qemu_x86_64_php','qemu_x86_64_php')},
        'Owned supervisor exact external start/parent/UID/guest identity changed')
    require(value.get('running') is True and owner.get('schema')=='magento-native-consumer-owner-v4' and
        owner.get('token')==token(scope_token) and owner.get('topic')==TOPIC and owner.get('argv')==ARGV and
        owner.get('max_messages')==MAX_MESSAGES and owner.get('package_sha256s')==PACKAGE_PINS and
        child==value.get('actual_child') and child['guest_argv']==ARGV and child['guest_cmdline_sha256']==CMDLINE_SHA256 and
        child['ppid']==current_parent['pid'] and child['execution_transport']==current_parent['execution_transport'],
        'Actual owned native consumer identity/source changed')
    return owner

def validate_exit(value,owner):
    require(value.get('exit_available') is True and value.get('supervisor_pid_absent') is True,
        'Owned consumer supervisor close unknown')
    exit=value['exit']
    require(exit.get('schema')=='magento-native-consumer-exit-v4' and exit.get('token')==owner['token'] and
        exit.get('child')==owner['child'] and exit.get('reason')=='owned_close_request' and
        exit.get('child_pid_absent') is True and exit.get('stop_signal_returned') is True and
        type(exit.get('first_observed_exitcode')) is int and (exit['first_observed_exitcode'] in {0,143} or
        exit['first_observed_exitcode']==-1 and exit.get('signaled') is True and exit.get('termsig')==15),
        'Owned native consumer exit/ack unknown')
    return exit
