"""Trusted sandbox supervisor. Untrusted programs execute as a dedicated OS user."""
import argparse
import ctypes
import fcntl
import hashlib
import json
import os
import platform
import pwd
import re
import resource
import signal
import subprocess
import sys
from pathlib import Path

SERVICE=Path('/service');WORKSPACE=Path('/workspace');INPUTS=Path('/inputs')
MAX_BYTES=2_000_000


def resolve_path(name,writing=False,workspace=WORKSPACE,inputs=INPUTS):
    if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9_./-]{1,180}',name):raise ValueError('invalid artifact path')
    parts=Path(name).parts
    if not parts or Path(name).is_absolute() or '..' in parts or '.' in parts:raise ValueError('relative artifact path required')
    root=inputs if parts[0]=='inputs' else workspace
    if writing and root==inputs:raise ValueError('inputs are read-only')
    suffix=Path(*parts[1:]) if root==inputs else Path(name)
    if not suffix.parts:raise ValueError('file path required')
    candidate=(root/suffix).resolve()
    if not candidate.is_relative_to(root.resolve()) or candidate==root.resolve():raise ValueError('artifact path escapes its root')
    return candidate


def initialize():
    try:user=pwd.getpwnam('factory')
    except KeyError:
        subprocess.run(['useradd','--create-home','--shell','/bin/bash','factory'],check=True)
        user=pwd.getpwnam('factory')
    for path in (SERVICE,SERVICE/'requests',SERVICE/'results',INPUTS,WORKSPACE):path.mkdir(exist_ok=True)
    os.chmod(SERVICE/'requests',0o700);os.chmod(SERVICE/'results',0o700)
    os.chmod(INPUTS,0o755);os.chown(WORKSPACE,user.pw_uid,user.pw_gid)
    (SERVICE/'factory_worker.py').write_text(Path(__file__).read_text())
    os.chmod(SERVICE/'factory_worker.py',0o644)
    return {'initialized':True,'program_uid':user.pw_uid}


def cleanup(uid):
    # The dedicated account has no service processes; only generated-code children.
    for entry in Path('/proc').iterdir():
        try:
            if entry.name.isdigit() and entry.stat().st_uid==uid:os.kill(int(entry.name),signal.SIGKILL)
        except (FileNotFoundError,ProcessLookupError,PermissionError):pass


def execute_program(packet,request_id):
    path=resolve_path(packet['path'])
    if path.suffix!='.py' or not path.is_file():raise ValueError('Python entrypoint required')
    args=packet.get('args',[])
    if not isinstance(args,list) or len(args)>20 or any(not isinstance(x,str) or len(x)>2000 for x in args):raise ValueError('invalid program arguments')
    seconds=packet.get('seconds',30)
    if type(seconds) is not int or not 1<=seconds<=60:raise ValueError('invalid execution limit')
    user=pwd.getpwnam('factory');cleanup(user.pw_uid)
    code_hash=hashlib.sha256(path.read_bytes()).hexdigest()
    def limits():
        libc=ctypes.CDLL(None,use_errno=True)
        # Empty network namespace: no inherited interfaces or routes. Fail closed.
        if libc.unshare(0x40000000)!=0:raise OSError(ctypes.get_errno(),'network namespace isolation unavailable')
        if libc.prctl(38,1,0,0,0)!=0:raise OSError(ctypes.get_errno(),'no-new-privileges unavailable')
        resource.setrlimit(resource.RLIMIT_CPU,(seconds,seconds+1))
        resource.setrlimit(resource.RLIMIT_AS,(1024**3,1024**3))
        resource.setrlimit(resource.RLIMIT_FSIZE,(8_000_000,8_000_000))
        resource.setrlimit(resource.RLIMIT_NOFILE,(128,128))
        resource.setrlimit(resource.RLIMIT_NPROC,(64,64))
        os.setgroups([]);os.setgid(user.pw_gid);os.setuid(user.pw_uid)
    stdout=SERVICE/'results'/f'{request_id}.stdout';stderr=SERVICE/'results'/f'{request_id}.stderr'
    timed_out=False
    try:
        with stdout.open('w') as out,stderr.open('w') as err:
            child=subprocess.Popen([sys.executable,str(path),*args],cwd=WORKSPACE,
                env={'PATH':'/usr/local/bin:/usr/bin:/bin','HOME':user.pw_dir,'LANG':'C.UTF-8'},
                stdout=out,stderr=err,preexec_fn=limits,start_new_session=True)
            try:child.wait(timeout=seconds+2)
            except subprocess.TimeoutExpired:
                timed_out=True;cleanup(user.pw_uid);child.wait(timeout=5)
        return {'exit_code':child.returncode,'timed_out':timed_out,'entrypoint_sha256':code_hash,'supervisor_netns':os.stat('/proc/self/ns/net').st_ino,
                'stdout':stdout.read_text(errors='replace')[-16000:],'stderr':stderr.read_text(errors='replace')[-16000:]}
    finally:cleanup(user.pw_uid)


def handle(packet,request_id):
    operation=packet['op']
    if operation=='run':return execute_program(packet,request_id)
    if operation=='snapshot':
        user=pwd.getpwnam('factory');cleanup(user.pw_uid)
        files=[];size=0;visited=0
        for item in WORKSPACE.rglob('*'):
            visited+=1
            if visited>512:raise ValueError('workspace snapshot entry limit exceeded')
            if item.is_symlink():raise ValueError('workspace snapshot contains a symlink')
            if not item.is_file() or '__pycache__' in item.parts:continue
            if item.suffix not in ('.py','.json','.jsonl','.md','.txt'):continue
            path=resolve_path(item.relative_to(WORKSPACE).as_posix())
            if path.stat().st_size>MAX_BYTES:raise ValueError('workspace file too large to preserve')
            text=path.read_text();size+=len(text.encode())
            if size>8_000_000 or len(files)>=128:raise ValueError('workspace snapshot limit exceeded')
            files.append({'path':item.relative_to(WORKSPACE).as_posix(),'content':text,
                          'sha256':hashlib.sha256(text.encode()).hexdigest()})
        return {'files':files,'bytes':size}

    path=resolve_path(packet['path'],writing=operation=='write')
    if operation=='read':
        if not path.is_file() or path.stat().st_size>MAX_BYTES:raise ValueError('artifact missing or too large')
        content=path.read_text();return {'content':content,'sha256':hashlib.sha256(content.encode()).hexdigest()}
    if operation=='write':
        content=packet['content']
        if not isinstance(content,str) or len(content.encode())>100_000:raise ValueError('source file too large')
        path.parent.mkdir(parents=True,exist_ok=True)
        user=pwd.getpwnam('factory')
        for parent in [path.parent,*path.parent.parents]:
            if parent==WORKSPACE or not parent.is_relative_to(WORKSPACE):break
            os.chown(parent,user.pw_uid,user.pw_gid)
        path.write_text(content);os.chown(path,user.pw_uid,user.pw_gid)
        return {'written':packet['path'],'sha256':hashlib.sha256(content.encode()).hexdigest()}
    raise ValueError('unknown worker operation')


def request(request_id):
    if not re.fullmatch(r'[a-f0-9]{32}',request_id):raise ValueError('invalid request id')
    result=SERVICE/'results'/f'{request_id}.json';intent=result.with_suffix('.intent')
    packet_path=SERVICE/'requests'/f'{request_id}.json'
    if packet_path.stat().st_size>300_000:raise ValueError('request too large')
    raw=packet_path.read_bytes();fingerprint=hashlib.sha256(raw).hexdigest()
    with result.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if intent.exists() and intent.read_text()!=fingerprint:raise ValueError('request collision')
        if result.exists():return json.loads(result.read_text())
        if intent.exists():raise RuntimeError('uncertain prior execution; not replayed')
        with intent.open('x') as f:f.write(fingerprint);f.flush();os.fsync(f.fileno())
        try:value=handle(json.loads(raw),request_id)
        except Exception as exc:value={'error':type(exc).__name__,'message':str(exc)[:1000]}
        temporary=result.with_suffix('.tmp')
        with temporary.open('w') as f:json.dump(value,f);f.flush();os.fsync(f.fileno())
        temporary.replace(result);return value


if __name__=='__main__':
    if platform.system()!='Linux' or os.geteuid()!=0:raise SystemExit('supervisor runs only as root inside the disposable Linux sandbox')
    p=argparse.ArgumentParser();p.add_argument('--initialize',action='store_true');p.add_argument('--request');a=p.parse_args()
    print(json.dumps(initialize() if a.initialize else request(a.request)))
