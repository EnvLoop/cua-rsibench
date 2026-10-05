"""Build a provenance-pinned GitLab18.5 member date-only serialization repair.

The upstream member invite payload sends a Date, causing JSON UTC conversion to
move a selected local calendar date in positive-offset timezones. This patch
formats that date as YYYY-MM-DD before transport. No scoring/data/date offsets.
"""
import argparse,gzip,hashlib,json,subprocess,tempfile
from pathlib import Path
BASE='gitlab/gitlab-ce@sha256:f7e992491db0c80a9a3f066c2c26e69b444307b5a8834e1bdde7929c4a74e97e'
ASSET='/opt/gitlab/embedded/service/gitlab-rails/public/assets/webpack/initInviteMembersModal.24fa6f95.chunk.js'
ORIGINAL_SHA='e3f273c6e01b415cce27b131a0f6a9738ac7a3a338ea342ff9bcc6b2aa59088f'
FIXED_SHA='d0c614124283127abf791f4bfdde1db0e20e1da0d676e8fbd63999bba64535ac'
NEEDLE=b'format:"json",expires_at:t,access_level:e'
REPLACEMENT=b'format:"json",expires_at:t instanceof Date&&!Number.isNaN(t.getTime())?String(t.getFullYear()).padStart(4,"0")+"-"+String(t.getMonth()+1).padStart(2,"0")+"-"+String(t.getDate()).padStart(2,"0"):t,access_level:e'

def patch_asset(raw):
    if hashlib.sha256(raw).hexdigest()!=ORIGINAL_SHA or raw.count(NEEDLE)!=1:raise ValueError('Exact original GitLab18.5 frontend asset required')
    fixed=raw.replace(NEEDLE,REPLACEMENT)
    if hashlib.sha256(fixed).hexdigest()!=FIXED_SHA:raise ValueError('Repaired member-date asset digest mismatch')
    return fixed

def build(context,image,output):
    def docker(*args,**kwargs):return subprocess.run(['docker','--context',context,*args],check=True,**kwargs)
    raw=docker('run','--rm','--entrypoint','cat',BASE,ASSET,capture_output=True).stdout;fixed=patch_asset(raw)
    with tempfile.TemporaryDirectory(prefix='gitlab-date-only-build-') as temporary:
        directory=Path(temporary);(directory/'fixed.js').write_bytes(fixed);(directory/'fixed.js.gz').write_bytes(gzip.compress(fixed,mtime=0));(directory/'Dockerfile').write_text('FROM '+BASE+'\nCOPY --chmod=0644 fixed.js '+ASSET+'\nCOPY --chmod=0644 fixed.js.gz '+ASSET+'.gz\n');docker('build','--network=none','--pull=false','-t',image,str(directory))
    inspected=json.loads(docker('image','inspect',image,capture_output=True).stdout)[0]
    value={'schema':'gitlab-member-date-only-application-build-v1','base_image':BASE,'repaired_image':image,'repaired_image_id':inspected['Id'],'asset':ASSET,'original_asset_sha256':ORIGINAL_SHA,'repaired_asset_sha256':FIXED_SHA,'frontend_fix':'Local calendar Date -> YYYY-MM-DD before member invite JSON','date_offset_timezone_or_oracle_changes':False}
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as stream:json.dump(value,stream,indent=2,sort_keys=True);stream.write('\n')
    return value
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--docker-context',default='colima-cua-gitlab');parser.add_argument('--image',default='envloop/gitlab-ce-date-only:18.5.0-fix2');parser.add_argument('--output',required=True);args=parser.parse_args();print(json.dumps(build(args.docker_context,args.image,args.output),sort_keys=True))
