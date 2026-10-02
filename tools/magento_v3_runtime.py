"""Fail-closed project-Python and headless Playwright preflight for Magento v3.

This runs a local about:blank browser smoke before any disposable clone can be
created. It makes no Docker, application, model, or provider call.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import platform
import sys

from magento_catalog_factory.plan import ROOT


SCHEMA = 'envloop-magento-v3-python-playwright-runtime-private-v1'
PUBLIC_SCHEMA = 'envloop-magento-v3-python-playwright-runtime-public-v1'
PINNED_PYTHON = Path('/Users/xiaoyong/Documents/Codex/2026-09-22/ya/.venv/bin/python')
PRIVATE_RECEIPT = ROOT / 'work/magento-original/v3-python-playwright-runtime.private.json'
PUBLIC_RECEIPT = ROOT / 'docs/evidence/magento-v3-python-playwright-runtime-2026-09-28.json'


def require(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError(code)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def headless_shell_path(browser_manifest: Path) -> tuple[Path, str]:
    browsers = json.loads(browser_manifest.read_bytes())['browsers']
    matches = [row for row in browsers if row.get('name') == 'chromium-headless-shell']
    require(len(matches) == 1 and type(matches[0].get('revision')) is str and
            platform.system() == 'Darwin' and platform.machine() == 'arm64' and
            'PLAYWRIGHT_BROWSERS_PATH' not in os.environ,
            'pinned_macos_arm64_playwright_headless_registry_required')
    revision = matches[0]['revision']
    binary = (Path.home() / 'Library/Caches/ms-playwright' /
              ('chromium_headless_shell-' + revision) /
              'chrome-headless-shell-mac-arm64/chrome-headless-shell')
    require(binary.is_file() and not binary.is_symlink() and
            os.access(binary, os.X_OK),
            'matching_headless_chromium_binary_missing')
    return binary, revision


async def _launch_headless() -> str:
    from playwright.async_api import async_playwright
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, timeout=30000)
        try:
            page = await browser.new_page()
            await page.goto('about:blank', timeout=10000)
            require(page.url == 'about:blank', 'headless_browser_smoke_did_not_open_blank_page')
            return browser.version
        finally:
            await browser.close()


def check_current(*, launch_browser: bool = True) -> dict:
    require(PINNED_PYTHON.is_file() and
            Path(sys.executable) == PINNED_PYTHON and
            Path(sys.prefix) == PINNED_PYTHON.parent.parent and
            sys.prefix != sys.base_prefix,
            'wrong_operator_python_before_clone_create')
    require(importlib.util.find_spec('playwright.async_api') is not None,
            'playwright_async_api_not_importable_before_clone_create')
    module = importlib.import_module('playwright.async_api')
    package = importlib.import_module('playwright')
    package_path = Path(package.__file__).parent
    manifest = package_path / 'driver/package/browsers.json'
    binary, revision = headless_shell_path(manifest)
    browser_version = asyncio.run(_launch_headless()) if launch_browser else None
    require(not launch_browser or
            (type(browser_version) is str and browser_version),
            'headless_chromium_launch_failed_before_clone_create')
    return {
        'schema': SCHEMA,
        'python_path': str(PINNED_PYTHON),
        'python_version': sys.version.split()[0],
        'python_binary_sha256': sha(PINNED_PYTHON.read_bytes()),
        'venv_prefix': str(Path(sys.prefix)),
        'playwright_version': importlib.metadata.version('playwright'),
        'playwright_async_api_sha256': sha(Path(module.__file__).read_bytes()),
        'browsers_manifest_sha256': sha(manifest.read_bytes()),
        'headless_revision': revision,
        'headless_binary_sha256': sha(binary.read_bytes()),
        'headless_browser_version': browser_version,
        'headless_launch_passed': launch_browser,
        'runtime_source_sha256': sha(Path(__file__).read_bytes()),
        'docker_calls': 0, 'model_calls': 0, 'official_final_admitted': 0,
    }


def validate_receipt() -> tuple[dict, str]:
    require(PRIVATE_RECEIPT.is_file() and PUBLIC_RECEIPT.is_file(),
            'source_bound_runtime_receipts_required_before_freeze')
    raw = PRIVATE_RECEIPT.read_bytes()
    value = json.loads(raw)
    current = check_current(launch_browser=True)
    require(value == current and value['headless_launch_passed'] is True,
            'pinned_python_playwright_or_headless_binary_changed')
    public = json.loads(PUBLIC_RECEIPT.read_bytes())
    require(public.get('schema') == PUBLIC_SCHEMA and
            public.get('private_runtime_sha256') == sha(raw) and
            public.get('python_path') == value['python_path'] and
            public.get('playwright_version') == value['playwright_version'] and
            public.get('headless_revision') == value['headless_revision'] and
            public.get('headless_binary_sha256') == value['headless_binary_sha256'] and
            public.get('headless_launch_passed') is True and
            public.get('docker_calls') == public.get('model_calls') ==
            public.get('official_final_admitted') == 0,
            'published_python_playwright_runtime_receipt_changed')
    return value, sha(raw)


def _write_new(path: Path, value: dict, mode: int) -> str:
    raw = (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return sha(raw)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('preflight', 'verify'))
    args = parser.parse_args()
    if args.action == 'preflight':
        require(not PRIVATE_RECEIPT.exists() and not PUBLIC_RECEIPT.exists(),
                'new_runtime_receipt_paths_required')
        value = check_current(launch_browser=True)
        PRIVATE_RECEIPT.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        private_sha = _write_new(PRIVATE_RECEIPT, value, 0o600)
        public = {'schema': PUBLIC_SCHEMA,
                  'status': 'local_runtime_only_no_application_clone_created',
                  'private_runtime_sha256': private_sha,
                  'python_path': value['python_path'],
                  'python_version': value['python_version'],
                  'playwright_version': value['playwright_version'],
                  'headless_revision': value['headless_revision'],
                  'headless_binary_sha256': value['headless_binary_sha256'],
                  'headless_browser_version': value['headless_browser_version'],
                  'headless_launch_passed': True,
                  'docker_calls': 0, 'model_calls': 0,
                  'official_final_admitted': 0}
        _write_new(PUBLIC_RECEIPT, public, 0o644)
        print(json.dumps(public, sort_keys=True))
    else:
        _value, digest = validate_receipt()
        print(json.dumps({'status': 'pinned_python_and_headless_browser_verified',
                          'private_runtime_sha256': digest,
                          'docker_calls': 0, 'model_calls': 0,
                          'official_final_admitted': 0}, sort_keys=True))


if __name__ == '__main__':
    main()
