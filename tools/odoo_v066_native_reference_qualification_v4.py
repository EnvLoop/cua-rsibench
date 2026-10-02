"""Fresh Ref4 qualification with unchanged controls under native V14."""
from enterprise_fallback.odoo18.native_compat_source_loader_v1 import load_source


_impl = load_source(
    "tools/odoo_v066_native_reference_qualification_v3.py",
    "tools._odoo_native_reference_qualification_v4",
    "bf23cd7bf9e9d774cd05f88254a2c01a2401f65d882bba8945899998b3fd575a",
    (("v13", "v14", 4), ("v3", "v4", 5)),
)


def __getattr__(name):
    return getattr(_impl, name)


if __name__ == "__main__":
    _impl.main()
