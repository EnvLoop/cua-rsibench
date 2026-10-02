"""Fresh reference epoch: clear all current native facets through journal GUI."""
from enterprise_fallback.odoo18.native_compat_source_loader_v1 import load_source


def clear_current_search_facets(page,journal,phase):
    # Hydration is a generic visible searchbox wait, never an answer lookup or
    # an enabled-target wait. Each removal uses the same current-frame journal.
    page.get_by_role('searchbox').first.wait_for(state='visible')
    for _index in range(16):
        facets=page.locator('.o_searchview .o_facet_remove')
        visible=[facets.nth(index) for index in range(facets.count()) if facets.nth(index).is_visible()]
        if not visible:return
        journal.act('click',phase=phase,locator=visible[0])
    raise RuntimeError('native_search_facet_clear_bound_exhausted')


_OLD_FACET='''    facet = page.locator("button.o_facet_remove").first
    if facet.count() and facet.is_visible():
        _act(journal, "click", phase, locator=facet)'''
_impl=load_source('tools/odoo_v066_scale_recipes_v1.py','tools._odoo_reference_recipes_v2',
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


def __getattr__(name):return getattr(_impl,name)
