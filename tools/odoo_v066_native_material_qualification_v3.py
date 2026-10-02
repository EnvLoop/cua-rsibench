"""Fresh v3 qualification API using exact preserved v2 protocol mechanics."""
from enterprise_fallback.odoo18.native_compat_source_loader_v1 import load_source

_impl = load_source('tools/odoo_v066_native_material_qualification_v2.py',
    'tools._odoo_native_material_qualification_v3',
    '391656e5aad08f9eee8975c5eb94d10970e74e44849d06383bdc8aa59e40bafb', (
        ('native_material_workers_v2', 'native_material_workers_v3', 1),
        ('-v2"', '-v3"', 6),
        ('native-v2-', 'native-v3-', 2),
        ('v066_native_material_controls_v2', 'v066_native_material_controls_v3', 2),
    ))


def __getattr__(name):
    return getattr(_impl, name)


if __name__ == '__main__':
    _impl.main()
