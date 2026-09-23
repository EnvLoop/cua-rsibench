"""Browser-only RPC for unmodified Kanboard. No SQL/API/code tools are exposed to models."""
import json
from http.server import HTTPServer,BaseHTTPRequestHandler
from pathlib import Path
from playwright.sync_api import sync_playwright

ELEMENTS='a,button,input:not([type=hidden]),select,textarea'

def controls(page):
    rows=[];locators={}
    for i,el in enumerate(page.locator(ELEMENTS).all()):
        if not el.is_visible() or not el.is_enabled():continue
        tag=el.evaluate('(e)=>e.tagName.toLowerCase()')
        typ=el.get_attribute('type') or ''
        label=el.evaluate("(e)=>e.getAttribute('aria-label') || (e.labels ? [...e.labels].map(l=>l.innerText).join(' ') : '') || e.innerText || e.getAttribute('title') || e.getAttribute('placeholder') || e.getAttribute('name') || e.getAttribute('value') || e.id")
        row={'id':str(i),'tag':tag,'type':typ,'label':label[:500]}
        if tag=='a':row['href']=el.get_attribute('href')
        if tag in ('input','select','textarea'):row['value']=el.input_value()
        if tag=='select':row['options']=el.locator('option').evaluate_all('(xs)=>xs.map(x=>({label:x.textContent,value:x.value}))')
        rows.append(row);locators[str(i)]=el
    return rows,locators


def main():
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
        context=browser.new_context(viewport={'width':1440,'height':1050})
        context.route('**/*',lambda r:r.continue_() if r.request.url.startswith('http://127.0.0.1:8080/') else r.abort())
        page=context.new_page();page.set_default_timeout(8000);page.goto('http://127.0.0.1:8080/')
        page.locator('input[name=username]').fill('admin');page.locator('input[name=password]').fill('admin');page.locator('button[type=submit]').click()
        cache={};counter=0;Path('/app/screenshots').mkdir(exist_ok=True)
        class H(BaseHTTPRequestHandler):
            def log_message(self,*a):pass
            def do_GET(self):
                nonlocal cache,counter
                if self.path!='/observe':self.send_error(404);return
                rows,cache=controls(page)
                captured=False
                for retry in range(2):
                    try:
                        page.screenshot(path=f'/app/screenshots/{counter:03}.png');captured=True;break
                    except Exception:
                        page.wait_for_timeout(250)
                if not captured:
                    with Path('/app/capture-errors.jsonl').open('a') as f:f.write(json.dumps({'index':counter,'error':'screenshot_unavailable'})+'\n')
                counter+=1
                self.reply({'url':page.url,'text':page.locator('body').inner_text(),'controls':rows})
            def do_POST(self):
                nonlocal cache
                try:
                    n=int(self.headers.get('Content-Length','0'))
                    if not 0<n<18000:raise ValueError('bad length')
                    a=json.loads(self.rfile.read(n));kind=a.get('type')
                    if kind=='done':self.reply({'done':True});return
                    if kind=='back':page.go_back();cache={};self.reply({'executed':'back'});return
                    el=cache.get(str(a.get('control')))
                    if el is None or not el.is_visible() or not el.is_enabled():raise ValueError('unknown or stale visible control')
                    value=a.get('value','');tag=el.evaluate('(e)=>e.tagName.toLowerCase()')
                    if kind=='click' and tag in ('a','button','input'):
                        el.click();cache={}
                    elif kind=='fill' and tag in ('input','textarea') and isinstance(value,str) and len(value)<=4000:el.fill(value)
                    elif kind=='select' and tag=='select':el.select_option(label=value)
                    elif kind=='press' and value in ('Enter','Tab','Escape'):el.press(value);cache={}
                    else:raise ValueError('action denied')
                    self.reply({'executed':kind})
                except Exception as exc:self.reply({'error':type(exc).__name__})
            def reply(self,d):
                b=json.dumps(d).encode();self.send_response(200);self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
        try:HTTPServer(('127.0.0.1',4318),H).serve_forever()
        finally:browser.close()

if __name__=='__main__':main()
