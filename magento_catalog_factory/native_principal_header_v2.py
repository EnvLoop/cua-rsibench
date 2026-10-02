"""Current-document rendered account header, independent of viewport clipping.

Only principal proof changes. Every control, hit-test, keyboard focus, unsafe
link and modal predicate remains the exact original viewport implementation.
"""
from hashlib import sha256
import math
from .native_surface_adapter_v2 import NATIVE_JS as ORIGINAL_JS

SELECTOR='.admin-user .admin-user-account-text'
_old=" const account=Array.from(document.querySelectorAll('.admin-user .admin-user-account-text')).filter(visible);"
_new=r''' const accountNodes=Array.from(document.querySelectorAll('.admin-user .admin-user-account-text'));
 const renderedAccount=e=>{if(!e.isConnected||e.ownerDocument!==document)return false;const r=e.getBoundingClientRect();if(!(r.width>0&&r.height>0))return false;
  for(let n=e;n&&n.nodeType===1;n=n.parentElement){const s=getComputedStyle(n);if(n.hidden||n.hasAttribute('inert')||n.getAttribute('aria-hidden')==='true'||s.display==='none'||s.visibility==='hidden'||s.visibility==='collapse'||Number(s.opacity)===0||s.contentVisibility==='hidden')return false;}
  return true;};
 const renderedAccounts=accountNodes.filter(renderedAccount);
 const account=accountNodes.length===1&&renderedAccounts.length===1?renderedAccounts:[];
 const accountBounds=account.length?(()=>{const r=account[0].getBoundingClientRect();return [r.left,r.top,r.width,r.height];})():null;'''
if ORIGINAL_JS.count(_old)!=1:raise ValueError('Frozen original account selector changed')
NATIVE_JS=ORIGINAL_JS.replace(_old,_new)
_old="account_witness:{selector:'.admin-user .admin-user-account-text',visible_count:account.length,username:account.length===1?account[0].textContent.trim():null}"
_new="account_witness:{schema:'magento-current-document-rendered-principal-v2',selector:'.admin-user .admin-user-account-text',visible_count:account.length,rendered_count:renderedAccounts.length,total_match_count:accountNodes.length,username:account.length===1?account[0].textContent.trim():null,connected_current_document:account.length===1,rendered_css_visible:account.length===1,header_bounds:accountBounds,in_viewport:account.length===1?visible(account[0]):false,viewport_excluded_from_principal_predicate:true}"
if NATIVE_JS.count(_old)!=1:raise ValueError('Frozen original account witness fields changed')
NATIVE_JS=NATIVE_JS.replace(_old,_new)

def valid_witness(meta,username):
    witness=meta.get('account_witness',{});bounds=witness.get('header_bounds')
    return bool(type(username) is str and username and meta.get('native_username')==username and
        witness.get('schema')=='magento-current-document-rendered-principal-v2' and witness.get('selector')==SELECTOR and
        witness.get('visible_count')==witness.get('rendered_count')==witness.get('total_match_count')==1 and
        witness.get('username')==username and witness.get('connected_current_document') is True and
        witness.get('rendered_css_visible') is True and witness.get('viewport_excluded_from_principal_predicate') is True and
        type(witness.get('in_viewport')) is bool and type(bounds) is list and len(bounds)==4 and
        all(type(value) in (float,int) and math.isfinite(value) for value in bounds) and bounds[2]>0 and bounds[3]>0)
