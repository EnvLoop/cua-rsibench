from pathlib import Path
from e2b import Template
import json
root=Path(__file__).resolve().parents[1]
t=Template(file_context_path=str(root/'work')).from_template('support-train__272943137319')
t=t.run_cmd('apt-get update && apt-get install -y --no-install-recommends php-cli php-sqlite3 php-mbstring php-xml php-gd php-curl php-zip',user='root')
t=t.copy('kanboard-1.2.54.tar.gz','/tmp/kanboard.tar.gz',user='root')
t=t.run_cmd('mkdir -p /opt/kanboard && tar -xzf /tmp/kanboard.tar.gz -C /opt/kanboard --strip-components=1 && chmod -R a+rwX /opt/kanboard/data',user='root')
result=Template.build(t,alias='cua-kanboard-1-2-54',cpu_count=2,memory_mb=2048)
(root/'work/kanboard-template.json').write_text(json.dumps(result.model_dump() if hasattr(result,'model_dump') else {'build':str(result)},indent=2))
print('template build complete')
