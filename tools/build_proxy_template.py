"""Build the reusable sampling-proxy runtime from public dependencies only."""
import dataclasses,json,tempfile,shutil
from pathlib import Path
from e2b import Template
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(dir=root/'work') as folder:
    context=Path(folder);shutil.copyfile(root/'src/cursibench/tinker_proxy.py',context/'tinker_proxy.py')
    template=Template(file_context_path=str(context)).from_image('python:3.12-slim')
    template=template.run_cmd('pip install --no-cache-dir tinker==0.30.0 jinja2',user='root')
    template=template.run_cmd('mkdir -p /app',user='root').copy('tinker_proxy.py','/app/tinker_proxy.py',user='root')
    result=Template.build(template,alias='cua-tinker-proxy-v1',cpu_count=2,memory_mb=2048)
    (root/'work/proxy-template.json').write_text(json.dumps(dataclasses.asdict(result) if dataclasses.is_dataclass(result) else {'build':str(result)},indent=2))
print('portable proxy runtime built')
