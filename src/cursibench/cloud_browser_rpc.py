"""Fixed browser control process for Harbor/E2B. No model credentials inside sandbox."""
import json
from http.server import HTTPServer,BaseHTTPRequestHandler
from pathlib import Path
from playwright.sync_api import sync_playwright


def observe(page):
    controls=[];modal=page.locator('dialog[open]').count()>0
    root=page.locator('dialog[open]') if modal else page.locator('body')
    for el in root.locator('[data-control]').all():
        if not el.is_visible() or not el.is_enabled():continue
        tag=el.evaluate('(e)=>e.tagName.toLowerCase()')
        row={'id':el.get_attribute('data-control'),'tag':tag,'label':el.get_attribute('aria-label') or el.inner_text()}
        if tag in ['select','input']:row['value']=el.input_value()
        if tag=='select':row['options']=el.locator('option').all_text_contents()
        controls.append(row)
    return {'text':root.inner_text(),'controls':controls}


def apply(page,actions):
    if not isinstance(actions,list) or not 1<=len(actions)<=4:raise ValueError('1..4 actions required')
    outcomes=[]
    for a in actions:
        if a.get('type')=='done':return {'done':True,'outcomes':outcomes}
        controls={x['id']:x for x in observe(page)['controls']};id=a.get('control');value=a.get('value')
        if id not in controls:raise ValueError('non-visible control')
        el=next(e for e in page.locator('[data-control]').all() if e.get_attribute('data-control')==id)
        tag=controls[id]['tag'];kind=a.get('type')
        if kind=='click' and tag=='button':el.click()
        elif kind=='fill' and tag=='input' and isinstance(value,str) and len(value)<=120:el.fill(value);el.press('Tab')
        elif kind=='select' and tag=='select' and value in controls[id]['options']:el.select_option(label=value)
        else:raise ValueError('invalid action')
        outcomes.append({'type':kind,'control':id,'result':'executed'})
    return {'done':False,'outcomes':outcomes}


def main():
    html=Path('/app/app.html').read_text();Path('/app/screenshots').mkdir(exist_ok=True)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        context=browser.new_context(viewport={'width':1440,'height':1050})
        context.route('**/*',lambda r:r.fulfill(content_type='text/html',body=html) if r.request.url=='https://cua-bench.test/' else r.abort())
        page=context.new_page();page.set_default_timeout(5000);page.goto('https://cua-bench.test/')
        count=0
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                nonlocal count
                if self.path=='/observe':
                    data=observe(page);page.screenshot(path=f'/app/screenshots/{count:03}.png');count+=1
                elif self.path=='/finalize':
                    page.reload();data=page.evaluate("JSON.parse(localStorage.getItem('state'))")
                    Path('/app/final.json').write_text(json.dumps(data));page.screenshot(path='/app/screenshots/final.png')
                else:self.send_error(404);return
                self.reply(data)
            def do_POST(self):
                try:
                    size=int(self.headers.get('Content-Length','0'))
                    if not 0<size<20000:raise ValueError('request too large')
                    data=json.loads(self.rfile.read(size));result=apply(page,data['actions']);self.reply(result)
                except Exception as e:self.reply({'error':type(e).__name__})
            def reply(self,data):
                body=json.dumps(data).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        try:HTTPServer(('127.0.0.1',4318),Handler).serve_forever()
        finally:browser.close()

if __name__=='__main__':main()
