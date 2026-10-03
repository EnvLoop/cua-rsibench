"""Reference7 save correction in an isolated original all-family recipe."""
from enterprise_fallback.odoo18.native_compat_source_loader_v1 import load_source
from enterprise_fallback.odoo18.native_reference_save_v7 import save_original_form
from tools.odoo_v066_scale_recipes_v5 import clear_current_search_facets

_OLD_FACET='''    facet = page.locator("button.o_facet_remove").first
    if facet.count() and facet.is_visible():
        _act(journal, "click", phase, locator=facet)'''
_impl=load_source('tools/odoo_v066_scale_recipes_v1.py','tools._odoo_reference_recipes_v8',
    'ba51d22415dd2f84c6f083ee80b129d377ebd74c136ae39458fcd1c8282427d6',(
        (_OLD_FACET,'    clear_current_search_facets(page,journal,phase)',2),
        ('    page.goto(f"http://127.0.0.1:{port}/odoo/purchase")',
         '    page.goto(f"http://127.0.0.1:{port}/odoo/purchase")\n    clear_current_search_facets(page,journal,phase)',1),
        ('    page.wait_for_url("**/odoo/replenishment")',
         '    page.wait_for_url("**/odoo/replenishment")\n    clear_current_search_facets(page,journal,phase)',1),
        ('        page.goto(f"http://127.0.0.1:{port}/odoo/action-430")',
         '        page.goto(f"http://127.0.0.1:{port}/odoo/action-430")\n        clear_current_search_facets(page,journal,"positive")',1),
    ))
_impl.clear_current_search_facets=clear_current_search_facets
_impl._save=save_original_form

def __getattr__(name):return getattr(_impl,name)
