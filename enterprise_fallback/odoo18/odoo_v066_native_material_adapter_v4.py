"""Prospective uniform adapter retaining the frozen v2/v3 action mechanics."""
from hashlib import sha256
from pathlib import Path
from .native_compat_source_loader_v1 import load_source,assert_frozen_v2_sources
from . import odoo_native_search_material_v4 as material

_impl=load_source('enterprise_fallback/odoo18/odoo_v066_native_material_adapter_v2.py',
    'enterprise_fallback.odoo18._native_material_adapter_v4',
    'df736235bdc584677a6762d9c65134d3a4177372bf4c35cada30cdf306fda3c3',(
        ('odoo_native_geometry_material_v2','odoo_native_geometry_material_v3',2),
        ('native-observed-context-geometry-finite-material-v2','native-observed-context-geometry-finite-material-v4',1),
        ("border_material(observation.screenshot_bytes,context['native_geometry'])","border_material(observation.screenshot_bytes,context)",1),
        ("border_material(observed_png,context['native_geometry'])","border_material(observed_png,context)",1),
        ("border_material(raw,context['native_geometry'])","border_material(raw,context)",2),
        ("near_border(point,current['native_geometry'])","near_border(point,current)",1),
        ("near_border(point,c['native_geometry'])","near_border(point,c)",1),
        ('finite_rfq_material','finite_native_decorative_material',2),
    ))
_legacy_context=_impl.valid_context
_legacy_eligible=_impl.material_eligible
_impl.NATIVE_CONTEXT_JS=_impl.NATIVE_CONTEXT_JS.replace(
    ' const focused=identity(document.activeElement);',
    material.SEARCH_GEOMETRY_JS+' const focused=identity(document.activeElement);').replace(
    'return {native_geometry:nativeGeometry,','return {native_search_geometry:nativeSearchGeometry,native_geometry:nativeGeometry,')


def valid_context(raw):
    return (type(raw) is dict and 'native_search_geometry' in raw and
            material.valid_search_geometry(raw['native_search_geometry']) and
            _legacy_context({k:v for k,v in raw.items() if k!='native_search_geometry'}))


def material_eligible(context,action):
    return (_legacy_eligible(context,action) or
            (context['modal_count']==0 and context['viewer_count']==0 and
             material.search_points(context) is not None and
             action.get('type') in ('click','double_click','type','key','wait')))


_impl.valid_context=valid_context
_impl.material_eligible=material_eligible
_impl.border_material=material.border_material
_impl.near_border=material.near_border
OdooV066NativeMaterialAdapter=_impl.OdooV066NativeMaterialAdapter
PROFILE,VIEWPORT=_impl.PROFILE,_impl.VIEWPORT
NATIVE_CONTEXT_JS,VISIBLE_CONTROLS_JS=_impl.NATIVE_CONTEXT_JS,_impl.VISIBLE_CONTROLS_JS
audit_guard=_impl.audit_guard


def public_binding():
    assert_frozen_v2_sources()
    value=_impl.public_binding();root=Path(__file__).resolve().parents[2]
    extra=('enterprise_fallback/odoo18/odoo_v066_native_material_adapter_v4.py',
           'enterprise_fallback/odoo18/odoo_native_search_material_v4.py',
           'enterprise_fallback/odoo18/odoo_native_geometry_material_v3.py',
           'enterprise_fallback/odoo18/native_compat_source_loader_v1.py')
    bindings={**value['bindings_sha256'],**{name:sha256((root/name).read_bytes()).hexdigest() for name in extra}}
    return {**value,'schema':'envloop-odoo-native-material-common-binding-v4',
            'finite_border_pixels':12,'search_corner_pixels':3,
            'search_projection':'current_visible_native_64th_css_rectangle_no_half_pixel_ties_complete_rgb_vector',
            'bindings_sha256':bindings,'binding_sha256':sha256(material.canonical(bindings)).hexdigest()}


def __getattr__(name):
    return getattr(_impl,name)
