"""Load an exact frozen source in an isolated namespace without global patches."""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path
import json
import sys
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]


def load_source(relative, name, expected_sha256, substitutions=()):
    path = ROOT / relative
    if path.is_symlink() or not path.is_file():
        raise ValueError('native_compat_source_unsafe')
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('native_compat_frozen_source_changed')
    source = raw.decode('utf-8')
    for before, after, count in substitutions:
        if source.count(before) != count:
            raise ValueError('native_compat_substitution_interface_changed')
        source = source.replace(before, after)
    identity = sha256(source.encode()).hexdigest()
    loaded = sys.modules.get(name)
    if loaded is not None:
        if loaded._native_compat_source_sha256 != identity:
            raise ValueError('native_compat_namespace_conflict')
        return loaded
    module = ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = name.rsplit('.', 1)[0]
    module._native_compat_source_sha256 = identity
    sys.modules[name] = module
    try:
        exec(compile(source, str(path), 'exec'), module.__dict__)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


V2_SOURCE_PINS = {
    'enterprise_fallback/odoo18/odoo_native_geometry_material_v2.py': 'a4936949ccdd8774486b0691342cb271b34efae39184b3db620e564988e61f68',
    'enterprise_fallback/odoo18/odoo_v066_native_material_adapter_v2.py': 'df736235bdc584677a6762d9c65134d3a4177372bf4c35cada30cdf306fda3c3',
    'enterprise_fallback/odoo18/native_material_workers_v2.py': 'f989273c67f57bcf11101f26395168d33e45f93f7c1f7fc418c102fdbec3c453',
    'tools/odoo_v066_native_material_qualification_v2.py': '391656e5aad08f9eee8975c5eb94d10970e74e44849d06383bdc8aa59e40bafb',
}


def assert_frozen_v2_sources():
    for name, expected in V2_SOURCE_PINS.items():
        path = ROOT / name
        if path.is_symlink() or not path.is_file() or sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('native_compat_frozen_v2_source_changed')
