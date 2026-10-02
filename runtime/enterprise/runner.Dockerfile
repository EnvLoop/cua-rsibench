FROM python@sha256:8d9d0b8bcf6506481eae4907c18f5e3e7902e629f5f6d684f9e7c32e85e3ddf0
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/workspace:/workspace/src:/workspace/tests
WORKDIR /workspace
RUN apt-get update && apt-get install --no-install-recommends -y docker.io ca-certificates git \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir '.[browser,cloud]' pillow==11.3.0 \
    && python -m playwright install --with-deps chromium
COPY . ./
RUN apt-get update && apt-get install --no-install-recommends -y docker-cli \
    && rm -rf /var/lib/apt/lists/*
# The default verifies the real browser navigation repair using only a local
# synthetic HTTP fixture. It needs no provider key or evaluator fixture data.
CMD ["python", "-m", "unittest", "tests.test_magento_quote_navigation_v2"]
