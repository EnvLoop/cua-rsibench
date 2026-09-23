"""Opt-in v3 observer: batched DOM, stable element handles and bounded screenshots."""
import contextlib
import json
import time
from http.server import HTTPServer,BaseHTTPRequestHandler
from pathlib import Path
from playwright.sync_api import sync_playwright
try:
    from .stable_observer import capture,act
except ImportError:
    from stable_observer import capture,act


def main():
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
        context=browser.new_context(viewport={'width':1440,'height':1050})
        context.route('**/*',lambda r:r.continue_() if r.request.url.startswith('http://127.0.0.1:8080/') else r.abort())
        page=context.new_page();page.set_default_timeout(8000);page.goto('http://127.0.0.1:8080/')
        page.locator('input[name=username]').fill('admin');page.locator('input[name=password]').fill('admin');page.locator('button[type=submit]').click()
        frame=None;counter=0;Path('/app/screenshots').mkdir(exist_ok=True)
        Path('/app/observer-errors.jsonl').touch()
        def clear():
            nonlocal frame
            if frame:
                with contextlib.suppress(Exception):frame.dispose()
            frame=None
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def reply(self,data,status=200):
                payload=json.dumps(data).encode();self.send_response(status)
                self.send_header('Content-Length',str(len(payload)));self.end_headers()
                # A timed-out read may disconnect; the server must still accept the retry.
                with contextlib.suppress(BrokenPipeError,ConnectionResetError):self.wfile.write(payload)
            def do_GET(self):
                nonlocal frame,counter
                if self.path!='/observe':self.send_error(404);return
                started=time.monotonic();clear()
                try:
                    for attempt in range(3):
                        try:
                            page.wait_for_load_state('domcontentloaded',timeout=3000)
                            frame=capture(page);break
                        except Exception as exc:
                            with Path('/app/observer-errors.jsonl').open('a') as f:
                                f.write(json.dumps({'index':counter,'attempt':attempt,'error':type(exc).__name__,'message':str(exc)[:1000]})+'\n')
                            if attempt==2:raise
                            page.wait_for_timeout(150)
                    captured=False
                    try:page.screenshot(path=f'/app/screenshots/{counter:03}.png',timeout=2000);captured=True
                    except Exception:
                        with Path('/app/capture-errors.jsonl').open('a') as f:f.write(json.dumps({'index':counter,'error':'screenshot_unavailable'})+'\n')
                    with Path('/app/observer-metrics.jsonl').open('a') as f:
                        f.write(json.dumps({'index':counter,'seconds':time.monotonic()-started,'screenshot':captured,'controls':len(frame.observation['controls'])})+'\n')
                    counter+=1;self.reply(frame.observation)
                except Exception as exc:self.reply({'error':type(exc).__name__},500)
            def do_POST(self):
                if self.path!='/act':self.send_error(404);return
                try:
                    size=int(self.headers.get('Content-Length','0'))
                    if not 0<size<18000:raise ValueError('bad length')
                    action=json.loads(self.rfile.read(size))
                    if frame is None and action.get('type') not in ('back','done'):raise ValueError('observe before action')
                    outcome=act(page,frame,action)
                    clear();self.reply(outcome)
                except Exception as exc:clear();self.reply({'error':type(exc).__name__})
        try:HTTPServer(('127.0.0.1',4318),Handler).serve_forever()
        finally:clear();browser.close()

if __name__=='__main__':main()
