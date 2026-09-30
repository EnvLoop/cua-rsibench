"""Exact finite geometry compatibility for retained native CSS edge phases.

No RGB states, styles, viewport, actor or task rules change. Raw DOM bounds
remain exact. Only proven native fractional edges and v2 integer edges project;
unknown phases and half-pixel ties retain strict screenshot equality.
"""
from __future__ import annotations
import math
from types import FunctionType
from .native_compat_source_loader_v1 import load_source, assert_frozen_v2_sources

_base = load_source('enterprise_fallback/odoo18/odoo_native_geometry_material_v2.py',
                    'enterprise_fallback.odoo18._native_geometry_frozen_v2',
                    'a4936949ccdd8774486b0691342cb271b34efae39184b3db620e564988e61f68')
valid_geometry = _base.valid_geometry
NATIVE_GEOMETRY_JS = _base.NATIVE_GEOMETRY_JS
TOP_STATES, BOTTOM_STATES, TAB_STATES = _base.TOP_STATES, _base.BOTTOM_STATES, _base.TAB_STATES
WHOLE_STATES, STYLE_FIELDS = _base.WHOLE_STATES, _base.STYLE_FIELDS
VIEWPORT = _base.VIEWPORT
NATIVE_PHASES = (0, 0.75, 0, 0.03125, 0, 0.9375, 0.109375, 0.9375)
INTEGER_PHASES = (0,) * 8


def phase_profile(geometry):
    if _base.projected_points(geometry) is None:
        return None
    bounds = (*geometry['sheet']['bounds'], *geometry['selected_tab']['bounds'])
    phases = tuple(v - math.floor(v) for v in bounds)
    if phases == NATIVE_PHASES:
        return 'retained_native_css_edge_phases'
    if phases == INTEGER_PHASES:
        return 'unchanged_v2_integer_edge_compatibility'
    return None


def projected_points(geometry):
    if phase_profile(geometry) is None:
        return None
    # These two finite phase profiles have no .5 tie. Retain the exact DOM
    # witness and snap only the projected device-pixel coordinates.
    edges = [math.floor(v + 0.5) for v in (*geometry['sheet']['bounds'], *geometry['selected_tab']['bounds'])]
    x, y, _right, bottom, tl, _tt, tr, tb = edges
    points = {'top': [[x, y + 1], [x, y + 3], [x + 1, y + 3]],
              'bottom': [[x, bottom - 4], [x + 1, bottom - 4], [x, bottom - 2], [x + 1, bottom - 2]],
              'selected_tab': [[tl, tb - 1], [tr - 1, tb - 1]]}
    flat = [tuple(p) for values in points.values() for p in values]
    if len(set(flat)) != 9 or any(not (0 <= px < 1440 and 0 <= py < 1000) for px, py in flat):
        return None
    return points


def near_border(point, geometry):
    points = projected_points(geometry)
    return points is not None and any(abs(point['x'] - x) <= 8 and abs(point['y'] - y) <= 8
                                     for values in points.values() for x, y in values)


_scope = dict(_base.__dict__)
_scope['projected_points'] = projected_points
_material = FunctionType(_base.border_material.__code__, _scope, 'border_material',
                         _base.border_material.__defaults__, _base.border_material.__closure__)


def border_material(raw, geometry):
    assert_frozen_v2_sources()
    result = _material(raw, geometry)
    if result is not None:
        result['geometry_phase_profile'] = phase_profile(geometry)
    return result
