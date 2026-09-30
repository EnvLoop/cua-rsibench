"""Finite current-native search-corner identity; all other RGB pixels exact."""
from __future__ import annotations
from hashlib import sha256
from io import BytesIO
import json
import math
from PIL import Image
from . import odoo_native_geometry_material_v3 as rfq
from . import odoo_native_geometry_material_v2 as shape

SEARCH_STATES = (((249,250,250),(238,240,242),(251,252,252)),
                 ((250,250,251),(239,241,243),(252,252,253)))
SEARCH_GEOMETRY_JS = r"""
 const searchContainers=Array.from(document.querySelectorAll('button.o_searchview_dropdown_toggler')).filter(visible);
 const nativeSearchGeometry={count:searchContainers.length,
  element:searchContainers.length===1?geometryIdentity(searchContainers[0]):null};
"""


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def valid_search_geometry(value):
    if type(value) is not dict or set(value)!={'count','element'}:
        return False
    count,element=value['count'],value['element']
    if type(count) is not int or count<0 or ((count==1)!=(element is not None)):
        return False
    if element is None:
        return True
    return (type(element) is dict and set(element)==shape.ELEMENT_FIELDS and
            all(type(element[key]) is str for key in shape.ELEMENT_FIELDS-{'bounds','style'}) and
            shape._bounds(element['bounds']) and type(element['style']) is dict and
            set(element['style'])==set(shape.STYLE_FIELDS) and
            all(type(v) is str for v in element['style'].values()))


def search_points(context):
    witness=context.get('native_search_geometry')
    if not valid_search_geometry(witness) or witness['count']!=1:
        return None
    viewport=context['native_geometry']['viewport']
    if viewport!={'width':1440,'height':1000,'device_pixel_ratio':1,'scroll_x':0,'scroll_y':0,
                  'visual_scale':1,'visual_offset_left':0,'visual_offset_top':0}:
        return None
    element=witness['element'];style=element['style']
    if (element['tag']!='button' or 'o_searchview_dropdown_toggler' not in element['class_name'].split() or
            style['opacity']!='1' or style['transform']!='none' or style['boxShadow']!='none'):
        return None
    if any(style['border'+side+'Width']!='1px' or style['border'+side+'Style']!='solid'
           for side in ('Top','Right','Bottom','Left')):
        return None
    if any(style['border'+corner+'Radius']!=('0px' if corner.endswith('Left') else '4px')
           for corner in ('TopLeft','TopRight','BottomLeft','BottomRight')):
        return None
    left,top,right,bottom=element['bounds']
    if (any(v*64!=int(v*64) or v-math.floor(v)==.5 for v in element['bounds']) or
            not (0<=left<right<=1440 and 0<=top<bottom<=1000) or right-left<24 or bottom-top<12):
        return None
    # Exact native 1/64px CSS bounds remain in the context and identity.
    # Half-pixel ties are refused; only the three device coordinates snap.
    r,b=math.floor(right+.5),math.floor(bottom+.5)
    return [[r-4,b-2],[r-3,b-2],[r-2,b-1]]


def near_border(point,context):
    if rfq.near_border(point,context['native_geometry']):
        return True
    points=search_points(context)
    return points is not None and any(abs(point['x']-x)<=8 and abs(point['y']-y)<=8
                                     for x,y in points)


def border_material(raw,context):
    """Canonicalize only complete finite vectors at their current native edges."""
    geometry=context['native_geometry']
    rfq_material=rfq.border_material(raw,geometry) if context['rfq_form'] else None
    points=search_points(context)
    try:
        with Image.open(BytesIO(raw)) as source:
            if source.format!='PNG' or source.mode!='RGB' or source.size!=(1440,1000):
                return None
            image=source.copy()
        vector=tuple(image.getpixel(tuple(p)) for p in points) if points is not None else None
        search_class=SEARCH_STATES.index(vector) if vector in SEARCH_STATES else None
        if rfq_material is None and search_class is None:
            return None
        if rfq_material is not None:
            for name,state in (('top',shape.TOP_STATES[0]),('bottom',shape.BOTTOM_STATES[0]),
                               ('selected_tab',shape.TAB_STATES[0])):
                for p,rgb in zip(rfq_material['projected_points'][name],state):
                    image.putpixel(tuple(p),rgb)
        if search_class is not None:
            for p,rgb in zip(points,SEARCH_STATES[0]):
                image.putpixel(tuple(p),rgb)
        identity={'rfq_geometry':geometry,'search_geometry':context['native_search_geometry'],
                  'rfq_projected':rfq_material is not None,'search_projected':search_class is not None}
        return {'rfq_material':rfq_material,'search_state_class':search_class,
                'search_points':points if search_class is not None else None,
                'search_rgb_vector':[list(rgb) for rgb in vector] if search_class is not None else None,
                'native_geometry_sha256':sha256(canonical(identity)).hexdigest(),
                'canonical_material_sha256':sha256(b'RGB-1440x1000-native-finite-v4\0'+
                    canonical(identity)+b'\0'+image.tobytes()).hexdigest()}
    except (OSError,ValueError):
        return None
