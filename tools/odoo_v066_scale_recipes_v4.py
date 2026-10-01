"""All-family reference facet clearing with post-observation optional choice."""
from enterprise_fallback.odoo18.native_compat_source_loader_v1 import load_source


def clear_current_search_facets(page,journal,phase):
    page.get_by_role('searchbox').first.wait_for(state='visible')
    for _index in range(16):
        facets=page.locator('.o_searchview .o_facet_remove')
        if not any(facets.nth(index).is_visible() for index in range(facets.count())):return
        # No locator/coordinate is selected here. The journal first observes,
        # then resolves its current unique first native facet, before intent.
        journal.act('click',phase=phase,optional_facet=True)
    raise RuntimeError('native_search_facet_clear_bound_exhausted')


_impl=load_source('tools/odoo_v066_scale_recipes_v2.py','tools._odoo_reference_recipes_v4',
 '1243254ee91d3af790797a3b9551afd26834fbbe972e0b16b4d4b861b666ad1b',(('tools._odoo_reference_recipes_v2','tools._odoo_reference_recipes_v4_body',1),))
_impl._impl.clear_current_search_facets=clear_current_search_facets


def __getattr__(name):return getattr(_impl,name)
