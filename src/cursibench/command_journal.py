"""Sandbox-side command journal; uncertain completed effects are never replayed.

Trusted host infrastructure only. The GUI model has no file/shell access.
"""
import argparse,base64,fcntl,hashlib,json,os,re,subprocess,sys
from pathlib import Path


def execute(root,request_id,command,timeout):
    if not re.fullmatch(r'[a-f0-9]{32}',request_id):raise ValueError('invalid request id')
    root=Path(root);root.mkdir(exist_ok=True,parents=True)
    base=root/request_id;identity=hashlib.sha256(command.encode()).hexdigest()
    with base.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        intent=base.with_suffix('.intent');result=base.with_suffix('.json')
        if intent.exists() and intent.read_text()!=identity:raise ValueError('request id collision')
        if result.exists():return json.loads(result.read_text())
        if intent.exists():raise RuntimeError('uncertain prior execution; refusing to replay')
        with intent.open('x') as f:f.write(identity);f.flush();os.fsync(f.fileno())
        try:
            process=subprocess.run(command,shell=True,capture_output=True,text=True,timeout=timeout)
            data={'stdout':process.stdout,'stderr':process.stderr,'return_code':process.returncode}
        except subprocess.TimeoutExpired:
            # Keep the intent. A child may already have produced a GUI effect.
            raise RuntimeError('command timeout with uncertain effects; refusing to replay') from None
        temporary=base.with_suffix('.tmp')
        with temporary.open('w') as f:json.dump(data,f);f.flush();os.fsync(f.fileno())
        temporary.replace(result)
        return data


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--request-id',required=True);p.add_argument('--command-b64',required=True);p.add_argument('--timeout',type=int,default=20);p.add_argument('--root',default='/app/command-journal');a=p.parse_args()
    try:
        result=execute(a.root,a.request_id,base64.b64decode(a.command_b64,validate=True).decode(),a.timeout)
        sys.stdout.write(result['stdout']);sys.stderr.write(result['stderr']);sys.exit(result['return_code'])
    except (RuntimeError,ValueError) as exc:
        sys.stderr.write(str(exc)+'\n');sys.exit(75)
