"""Versioned browser observer prototype; does not modify the frozen v2 experiments.

One DOM snapshot avoids hundreds of protocol round trips. Actions bind to the
observed element object, so later insertion/reordering cannot retarget a click.
"""
from dataclasses import dataclass

SELECTOR='a,button,input:not([type=hidden]),select,textarea'
SNAPSHOT='''els => {
 const visible=e=>e.checkVisibility({visibilityProperty:true})&&[...e.getClientRects()].some(r=>r.width>0&&r.height>0);
 const modal=document.getElementById('modal-box');const root=modal&&visible(modal)?modal:document.body;
 const controls=[];
 els.forEach((e,i)=>{if(!visible(e)||e.matches(':disabled')||e.closest('[aria-disabled="true"]')||!root.contains(e))return;
 const tag=e.tagName.toLowerCase();const label=e.getAttribute('aria-label')||(e.labels?[...e.labels].map(l=>l.innerText).join(' '):'')||e.innerText||e.getAttribute('title')||e.getAttribute('placeholder')||e.getAttribute('name')||e.getAttribute('value')||e.id||'';
 const c={id:String(i),tag,type:e.getAttribute('type')||'',label:String(label).slice(0,500)};
 if(tag==='a')c.href=e.getAttribute('href');
 if(['input','select','textarea'].includes(tag))c.value=e.value;
 if(tag==='select')c.options=[...e.options].map(o=>({label:o.textContent,value:o.value}));
 controls.push(c);});
 return {text:root.innerText,controls,modal_open:root!==document.body};
}'''

@dataclass
class Frame:
    ref: object
    observation: dict
    def dispose(self):self.ref.dispose()


def capture(page):
    ref=page.evaluate_handle('(selector)=>Array.from(document.querySelectorAll(selector))',SELECTOR)
    try:
        observation=ref.evaluate(SNAPSHOT);observation['url']=page.url
        return Frame(ref,observation)
    except Exception:
        ref.dispose();raise


def act(page,frame,action):
    kind=action.get('type')
    if kind=='done':return {'done':True}
    if kind=='back':page.go_back();return {'executed':'back'}
    control=str(action.get('control',''));rows={r['id']:r for r in frame.observation['controls']}
    if control not in rows:raise ValueError('control not in observed frame')
    handle=frame.ref.get_property(control);element=handle.as_element()
    try:
        if element is None or not element.is_visible() or not element.is_enabled():raise ValueError('observed element is no longer actionable')
        allowed=element.evaluate('''e => {const m=document.getElementById('modal-box');
          return e.isConnected && !e.closest('[aria-disabled="true"]') &&
            (!m || !m.getClientRects().length || getComputedStyle(m).visibility==='hidden' || m.contains(e));}''')
        if not allowed:raise ValueError('observed element is outside the current active surface')
        value=action.get('value','');tag=rows[control]['tag']
        if kind=='click' and tag in ('a','button','input'):element.click()
        elif kind=='fill' and tag in ('input','textarea') and isinstance(value,str) and len(value)<=4000:element.fill(value)
        elif kind=='select' and tag=='select' and value in [o['label'] for o in rows[control]['options']]:element.select_option(label=value)
        elif kind=='press' and value in ('Enter','Tab','Escape'):element.press(value)
        else:raise ValueError('action outside allowed schema')
        return {'executed':kind}
    finally:handle.dispose()
