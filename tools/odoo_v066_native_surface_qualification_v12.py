"""Fresh v12 principal-correct TRAIN and unchanged all-family 20/100 controls."""
from enterprise_fallback.odoo18.native_compat_source_loader_v1 import load_source

_impl=load_source('tools/odoo_v066_native_surface_qualification_v6.py',
 'tools._odoo_native_surface_qualification_v12_wrapper',
 '7c9906b883552885dd0a483c731d948d935a4744674d5b0134d4871c9738baaa',(('v6','v12',7),))


def __getattr__(name):return getattr(_impl,name)


if __name__=='__main__':_impl._impl.main()
