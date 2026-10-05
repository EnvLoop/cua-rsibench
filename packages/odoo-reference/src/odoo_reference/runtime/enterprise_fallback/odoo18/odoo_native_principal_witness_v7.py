"""Typed native avatar principal resource; no account API or inferred user UID."""
from __future__ import annotations
from urllib.parse import urlsplit,parse_qs
import re

SELECTOR='.o_main_navbar .o_user_menu img.o_user_avatar'
READINESS_DELAYS_MS=(0,120,160,200,240,280,320,360)
_PATH=re.compile(r'/web/image/(res\.partner|res\.users)/([1-9][0-9]*)/avatar_128\Z')


def parse_resource(raw,origin):
    if type(raw) is not str or type(origin) is not str:return None
    try:
        url=urlsplit(raw);base=urlsplit(origin)
        if url.scheme not in ('http','https') or url.scheme!=base.scheme or url.netloc!=base.netloc or url.username or url.password or url.fragment:return None
        match=_PATH.fullmatch(url.path)
        if match:return match[1]+':'+match[2]
        if url.path!='/web/image':return None
        args=parse_qs(url.query,keep_blank_values=True)
        if any(len(args.get(key,[]))!=1 for key in ('model','id','field')):return None
        model,identity,field=(args[key][0] for key in ('model','id','field'))
        if model not in ('res.partner','res.users') or field!='avatar_128' or re.fullmatch(r'[1-9][0-9]*',identity) is None:return None
        return model+':'+identity
    except (ValueError,TypeError):return None


def principal_from_witness(value,origin):
    if (type(value) is not dict or set(value)!={'selector','total','visible_count','nodes'} or
        value['selector']!=SELECTOR or type(value['total']) is not int or value['total']<1 or
        type(value['visible_count']) is not int or value['visible_count']!=1 or type(value['nodes']) is not list or len(value['nodes'])!=1):return None
    row=value['nodes'][0]
    if (type(row) is not dict or row.get('visible') is not True or row.get('complete') is not True or
        type(row.get('natural_width')) is not int or row['natural_width']<1):return None
    source=parse_resource(row.get('src'),origin);current=parse_resource(row.get('current_src'),origin)
    return source if source is not None and source==current else None


PRINCIPAL_JS=r"""
 const avatarSelector='.o_main_navbar .o_user_menu img.o_user_avatar';
 const allAvatars=Array.from(document.querySelectorAll(avatarSelector));
 const nativeAvatars=allAvatars.filter(visible);
 const principalResource=raw=>{try{const u=new URL(raw,location.href);if(u.origin!==location.origin||u.username||u.password||u.hash)return '';const m=u.pathname.match(/^\/web\/image\/(res\.partner|res\.users)\/([1-9][0-9]*)\/avatar_128$/);if(m)return m[1]+':'+m[2];if(u.pathname!=='/web/image')return '';for(const k of ['model','id','field'])if(u.searchParams.getAll(k).length!==1)return '';const model=u.searchParams.get('model'),id=u.searchParams.get('id');return ['res.partner','res.users'].includes(model)&&/^[1-9][0-9]*$/.test(id)&&u.searchParams.get('field')==='avatar_128'?model+':'+id:'';}catch{return '';}};
 const principalWitness={selector:avatarSelector,total:allAvatars.length,visible_count:nativeAvatars.length,nodes:nativeAvatars.map(el=>({src:el.src,current_src:el.currentSrc,visible:true,complete:el.complete,natural_width:el.naturalWidth}))};
 let principal='';if(nativeAvatars.length===1&&nativeAvatars[0].complete&&nativeAvatars[0].naturalWidth>0){const s=principalResource(nativeAvatars[0].src),c=principalResource(nativeAvatars[0].currentSrc);if(s&&s===c)principal=s;}
"""
