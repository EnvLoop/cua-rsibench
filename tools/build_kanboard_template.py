from pathlib import Path
from e2b import Template
import json
root=Path(__file__).resolve().parents[1]
import hashlib,urllib.request
asset=root/'work/kanboard-1.2.54.tar.gz'
asset.parent.mkdir(exist_ok=True)
if not asset.exists():
    req=urllib.request.Request('https://github.com/kanboard/kanboard/archive/refs/tags/v1.2.54.tar.gz',headers={'User-Agent':'cua-rsibench/0.3'})
    with urllib.request.urlopen(req,timeout=90) as response:asset.write_bytes(response.read())
expected='6548946b406bc8640dfe20a884dd9cdf708d8d6c25eeacdabd374a36d5e98237'
if hashlib.sha256(asset.read_bytes()).hexdigest()!=expected:raise RuntimeError('Kanboard archive checksum mismatch')
t=Template(file_context_path=str(root/'work')).from_image('python:3.12-slim')
t=t.run_cmd('apt-get update && apt-get install -y --no-install-recommends chromium curl fonts-dejavu',user='root')
t=t.run_cmd('pip install --no-cache-dir playwright==1.63.0',user='root')
t=t.run_cmd('apt-get update && apt-get install -y --no-install-recommends php-cli php-sqlite3 php-mbstring php-xml php-gd php-curl php-zip',user='root')
t=t.copy('kanboard-1.2.54.tar.gz','/tmp/kanboard.tar.gz',user='root')
t=t.run_cmd('mkdir -p /opt/kanboard /app && chmod a+rwx /app && tar -xzf /tmp/kanboard.tar.gz -C /opt/kanboard --strip-components=1 && chmod -R a+rwX /opt/kanboard/data',user='root')
result=Template.build(t,alias='cua-kanboard-1-2-54',cpu_count=2,memory_mb=2048)
(root/'work/kanboard-template.json').write_text(json.dumps(result.model_dump() if hasattr(result,'model_dump') else {'build':str(result)},indent=2))
print('template build complete')
