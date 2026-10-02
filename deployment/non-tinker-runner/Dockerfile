FROM docker@sha256:018edbc908e08fcc9dbf029c812c34251e9b4719e6f71ca0e5eae2a987d014ca AS docker_cli
FROM python@sha256:8d9d0b8bcf6506481eae4907c18f5e3e7902e629f5f6d684f9e7c32e85e3ddf0
WORKDIR /opt/envloop
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PYTHONPATH=/opt/envloop:/opt/envloop/src \
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright
COPY deployment/non-tinker-runner/requirements.txt /tmp/envloop-requirements.txt
RUN pip install --no-cache-dir -r /tmp/envloop-requirements.txt \
    && python -m playwright install --with-deps chromium \
    && apt-get update && apt-get install -y --no-install-recommends poppler-utils \
    && rm -rf /var/lib/apt/lists/*
COPY . /opt/envloop/
COPY --from=docker_cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker_cli /usr/local/libexec/docker/cli-plugins/ /usr/local/libexec/docker/cli-plugins/
RUN python tools/build_non_tinker_source_bundle_v1.py verify --root /opt/envloop \
    && python -c "import ast,pathlib; [ast.parse(p.read_text(), filename=str(p)) for p in pathlib.Path('.').rglob('*.py')]"
CMD ["python", "tools/non_tinker_runner_smoke_v1.py"]
