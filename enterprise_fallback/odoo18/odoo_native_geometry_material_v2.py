"""Neutral geometry projection and finite complete decorative RGB vectors.

The DOM witness is current rendered geometry, never task data or an oracle.
Only nine projected pixels can canonicalize; every other RGB pixel is exact.
"""
from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import json
import math
from itertools import product
from PIL import Image

VIEWPORT = (1440, 1000)
TOP_STATES = (((246, 247, 248), (226, 230, 234), (249, 250, 250)),
              ((246, 247, 249), (226, 229, 234), (250, 250, 251)))
BOTTOM_STATES = (((226, 230, 234), (249, 250, 250), (246, 247, 248), (229, 233, 236)),
                 ((226, 229, 234), (250, 250, 251), (246, 247, 249), (230, 233, 236)))
TAB_STATES = (((235, 237, 240), (235, 237, 240)),
              ((235, 237, 239), (235, 237, 239)))
# Eight explicitly finite complete nine-pixel vectors retain v1's independent
# complete form-corner states and the observed complete selected-tab states.
WHOLE_STATES = tuple(top + bottom + tab for top, bottom, tab in
                     product(TOP_STATES, BOTTOM_STATES, TAB_STATES))
STYLE_FIELDS = ('backgroundColor', 'borderTopColor', 'borderRightColor',
                'borderBottomColor', 'borderLeftColor', 'borderTopWidth',
                'borderRightWidth', 'borderBottomWidth', 'borderLeftWidth',
                'borderTopStyle', 'borderRightStyle', 'borderBottomStyle',
                'borderLeftStyle', 'borderTopLeftRadius', 'borderTopRightRadius',
                'borderBottomLeftRadius', 'borderBottomRightRadius', 'opacity',
                'transform', 'boxShadow')
GEOMETRY_FIELDS = {'viewport', 'form_bounds', 'sheet_count', 'sheet',
                   'selected_tab_count', 'selected_tab'}
ELEMENT_FIELDS = {'tag', 'class_name', 'role', 'aria_selected', 'ref', 'bounds', 'style'}

# Inserted into the adapter's current visible-native-context read. It does
# not issue RPC, query hidden records, expose actor tools, or modify the DOM.
NATIVE_GEOMETRY_JS = r"""
 const geometryIdentity=el=>{const s=getComputedStyle(el);return {
  tag:el.tagName.toLowerCase(),class_name:el.className,role:el.getAttribute('role')||'',
  aria_selected:el.getAttribute('aria-selected')||'',ref:el.getAttribute('data-envloop-ref')||'',bounds:bounds(el),
  style:Object.fromEntries(STYLE_FIELDS.map(key=>[key,s[key]]))};};
 const sheets=form?Array.from(form.querySelectorAll('.o_form_sheet')).filter(visible):[];
 const sheet=sheets.length===1?sheets[0]:null;
 const tabs=sheet?Array.from(sheet.querySelectorAll('.o_notebook .nav-link.active')).filter(visible):[];
 const vv=window.visualViewport;
 const nativeGeometry={viewport:{width:innerWidth,height:innerHeight,device_pixel_ratio:devicePixelRatio,
  scroll_x:scrollX,scroll_y:scrollY,visual_scale:vv?vv.scale:null,visual_offset_left:vv?vv.offsetLeft:null,
  visual_offset_top:vv?vv.offsetTop:null},form_bounds:form?bounds(form):null,
  sheet_count:sheets.length,sheet:sheet?geometryIdentity(sheet):null,
  selected_tab_count:tabs.length,selected_tab:tabs.length===1?geometryIdentity(tabs[0]):null};
""".replace('STYLE_FIELDS', json.dumps(STYLE_FIELDS))


def _bounds(value):
    return (type(value) is list and len(value) == 4 and
            all(type(v) in (int, float) and math.isfinite(v) for v in value) and
            value[0] < value[2] and value[1] < value[3])


def valid_geometry(value):
    if type(value) is not dict or set(value) != GEOMETRY_FIELDS:
        return False
    viewport = value['viewport']
    if (type(viewport) is not dict or set(viewport) != {
            'width', 'height', 'device_pixel_ratio', 'scroll_x', 'scroll_y',
            'visual_scale', 'visual_offset_left', 'visual_offset_top'} or
            any(type(v) not in (int, float) or not math.isfinite(v)
                for v in viewport.values()) or
            (value['form_bounds'] is not None and not _bounds(value['form_bounds']))):
        return False
    for count_key, element_key in (('sheet_count', 'sheet'), ('selected_tab_count', 'selected_tab')):
        count, element = value[count_key], value[element_key]
        if type(count) is not int or count < 0 or ((count == 1) != (element is not None)):
            return False
        if element is not None and (type(element) is not dict or set(element) != ELEMENT_FIELDS or
                any(type(element[key]) is not str for key in ELEMENT_FIELDS - {'bounds', 'style'}) or
                not _bounds(element['bounds']) or type(element['style']) is not dict or
                set(element['style']) != set(STYLE_FIELDS) or
                any(type(s) is not str for s in element['style'].values())):
            return False
    return True


def _style_known(style, *, tab):
    white, border = 'rgb(255, 255, 255)', 'rgb(222, 226, 230)'
    expected = {'backgroundColor': white, 'opacity': '1', 'transform': 'none', 'boxShadow': 'none'}
    for side in ('Top', 'Right', 'Bottom', 'Left'):
        expected['border' + side + 'Color'] = white if tab and side == 'Bottom' else border
        expected['border' + side + 'Width'] = '1px'
        expected['border' + side + 'Style'] = 'solid'
    for corner in ('TopLeft', 'TopRight', 'BottomLeft', 'BottomRight'):
        expected['border' + corner + 'Radius'] = '0px' if tab and corner.startswith('Bottom') else '4px'
    return style == expected


def projected_points(geometry):
    """Project a single unambiguous, fully visible native sheet/tab witness."""
    if not valid_geometry(geometry):
        return None
    if geometry['viewport'] != {'width': 1440, 'height': 1000, 'device_pixel_ratio': 1,
            'scroll_x': 0, 'scroll_y': 0, 'visual_scale': 1,
            'visual_offset_left': 0, 'visual_offset_top': 0}:
        return None
    if geometry['sheet_count'] != 1 or geometry['selected_tab_count'] != 1:
        return None
    sheet, tab = geometry['sheet'], geometry['selected_tab']
    form = geometry['form_bounds']
    if (form is None or sheet['tag'] != 'div' or 'o_form_sheet' not in sheet['class_name'].split() or
            tab['tag'] not in ('a', 'button') or not {'nav-link', 'active'} <= set(tab['class_name'].split()) or
            tab['role'] not in ('', 'tab') or tab['aria_selected'] not in ('', 'true') or
            not _style_known(sheet['style'], tab=False) or not _style_known(tab['style'], tab=True)):
        return None
    left, top, right, bottom = sheet['bounds']
    tl, tt, tr, tb = tab['bounds']
    # Native CSS coordinates may have an exact 1/64px fraction. Bind those
    # values unchanged; clipping, arbitrary precision and overlap are refused.
    if (any(v * 64 != int(v * 64) for v in (*form, *sheet['bounds'], *tab['bounds'])) or
            not (0 <= left < right <= VIEWPORT[0] and 0 <= top < bottom <= VIEWPORT[1]) or
            not (form[0] <= left and form[1] <= top and right <= form[2] and bottom <= form[3]) or
            right - left < 16 or bottom - top < 16 or tr - tl < 16 or tb - tt < 12 or
            not (left + 4 <= tl < tr <= right - 4 and top + 4 <= tt < tb <= bottom - 4)):
        return None
    x, y, end = math.floor(left), math.floor(top), math.ceil(bottom)
    points = {'top': [[x, y + 1], [x, y + 3], [x + 1, y + 3]],
              'bottom': [[x, end - 4], [x + 1, end - 4], [x, end - 2], [x + 1, end - 2]],
              'selected_tab': [[math.floor(tl), math.ceil(tb) - 1],
                               [math.ceil(tr) - 1, math.ceil(tb) - 1]]}
    flat = [tuple(p) for values in points.values() for p in values]
    if len(set(flat)) != 9 or any(not (0 <= px < 1440 and 0 <= py < 1000) for px, py in flat):
        return None
    return points


def near_border(point, geometry):
    points = projected_points(geometry)
    return points is not None and any(abs(point['x'] - x) <= 8 and abs(point['y'] - y) <= 8
                                     for values in points.values() for x, y in values)


def border_material(raw: bytes, geometry: dict) -> dict | None:
    """Accept complete finite vectors, canonicalize only their nine pixels."""
    points = projected_points(geometry)
    if points is None:
        return None
    try:
        with Image.open(BytesIO(raw)) as source:
            if source.format != 'PNG' or source.mode != 'RGB' or source.size != VIEWPORT:
                return None
            image = source.copy()
        states = {'top': TOP_STATES, 'bottom': BOTTOM_STATES, 'selected_tab': TAB_STATES}
        vectors = {name: tuple(image.getpixel(tuple(p)) for p in values) for name, values in points.items()}
        whole = vectors['top'] + vectors['bottom'] + vectors['selected_tab']
        if whole not in WHOLE_STATES:
            return None
        classes = {name: states[name].index(vectors[name]) for name in states}
        for name, values in points.items():
            for p, rgb in zip(values, states[name][0]):
                image.putpixel(tuple(p), rgb)
        geometry_raw = json.dumps(geometry, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        return {'state_class': classes, 'whole_state_index': WHOLE_STATES.index(whole), 'projected_points': points,
                'rgb_vectors': {name: [list(rgb) for rgb in vector] for name, vector in vectors.items()},
                'native_geometry_sha256': sha256(geometry_raw).hexdigest(),
                'canonical_material_sha256': sha256(b'RGB-1440x1000-native-geometry-nine-v2\0' +
                    geometry_raw + b'\0' + image.tobytes()).hexdigest()}
    except (OSError, ValueError):
        return None
