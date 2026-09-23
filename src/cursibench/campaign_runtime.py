"""Host-owned browser runner, budgeted model transport and tamper-evident ledger."""
import copy
import hashlib
import json
import threading
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from .agentrouter import response_receipt, ProviderFailure
from .workbench_data import digest, verify_case

BASE_PROMPT='Complete the user task using the browser. Follow the visible application instructions.'
ACTION_CONTRACT='''Return only JSON {"actions": [...]}. Allowed actions: {"type":"click","control":"visible-control-id"}, {"type":"fill","control":"visible-control-id","value":"text"}, {"type":"select","control":"visible-control-id","value":"option"}, {"type":"done"}. At most 4 actions per response, each on a currently visible control. No code, URLs, file access, network or arbitrary selectors. Do not guess unseen controls. UI observations after each batch will be provided.'''

class BudgetExhausted(RuntimeError):pass

class Ledger:
    def __init__(self,path,max_calls=600,max_input_bytes=2500000,max_wall_seconds=7200):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        if self.path.exists():raise ValueError('new ledger path required; do not overwrite a campaign')
        self.lock=threading.Lock();self.head='0'*64;self.calls=0;self.input_bytes=0
        self.max_calls=max_calls;self.max_input_bytes=max_input_bytes;self.deadline=time.monotonic()+max_wall_seconds
    def append(self,kind,data):
        with self.lock:
            row={'kind':kind,'data':data,'prev':self.head}
            row['hash']=digest(row)
            with self.path.open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
            self.head=row['hash']
    def reserve(self,prompt):
        n=len(prompt.encode())
        with self.lock:
            if self.calls>=self.max_calls or self.input_bytes+n>self.max_input_bytes or time.monotonic()>self.deadline:
                raise BudgetExhausted('campaign request/byte/time cap reached')
            self.calls+=1;self.input_bytes+=n
    def call(self,prompt,model,kind,timeout=60):
        self.reserve(prompt)
        start=time.monotonic()
        # Persist outgoing content for leakage audits; no keys or raw provider envelopes.
        self.append('request',{'purpose':kind,'model':model,'prompt':prompt,'input_sha256':hashlib.sha256(prompt.encode()).hexdigest()})
        try:
            text,receipt=response_receipt(prompt,model,900,timeout)
            self.append('response',{'purpose':kind,'text':text,'receipt':receipt})
            return text,receipt
        except ProviderFailure as exc:
            self.append('provider_failure',{'purpose':kind,'receipt':exc.receipt})
            raise


def verify_ledger(path):
    previous='0'*64
    for line in Path(path).read_text().splitlines():
        row=json.loads(line);hash_=row.pop('hash')
        if row['prev']!=previous or digest(row)!=hash_:return False
        previous=hash_
    return True


def json_object(text):
    clean=text.strip()
    if clean.startswith('```'): clean='\n'.join(clean.splitlines()[1:-1])
    result=json.loads(clean)
    if not isinstance(result,dict):raise ValueError('object required')
    return result


def observe(page):
    # Browser-visible controls only; ignore source-code state, hidden tabs and localStorage.
    controls=[]
    dialog_open=page.locator('dialog[open]').count()>0
    root=page.locator('dialog[open]') if dialog_open else page
    for el in root.locator('[data-control]').all():
        if not el.is_visible() or not el.is_enabled():continue
        tag=el.evaluate('(e)=>e.tagName.toLowerCase()')
        row={'id':el.get_attribute('data-control'),'tag':tag,'label':el.get_attribute('aria-label') or el.inner_text()}
        if tag in ('input','select'):row['value']=el.input_value()
        if tag=='select':row['options']=el.locator('option').all_text_contents()
        controls.append(row)
    return {'text':root.locator('body').inner_text() if not dialog_open else root.inner_text(),'controls':controls}


def apply_actions(page,actions):
    if not isinstance(actions,list) or not 1<=len(actions)<=4:raise ValueError('1..4 actions required')
    outcomes=[]
    for action in actions:
        if not isinstance(action,dict):raise ValueError('invalid action')
        kind=action.get('type')
        if kind=='done':return outcomes+['done'],True
        available={r['id']:r for r in observe(page)['controls']}
        control=action.get('control')
        if control not in available:raise ValueError('control is not currently visible')
        element=page.locator('[data-control]') # exact ID matched without model-supplied CSS
        element=next(el for el in element.all() if el.get_attribute('data-control')==control)
        row=available[control]
        if kind=='click' and row['tag']=='button':element.click()
        elif kind=='fill' and row['tag']=='input' and isinstance(action.get('value'),str) and len(action['value'])<=120:
            element.fill(action['value']);element.press('Tab')
        elif kind=='select' and row['tag']=='select' and action.get('value') in row['options']:element.select_option(label=action['value'])
        else:raise ValueError('unsupported action or value')
        outcomes.append({'control':control,'type':kind,'result':'executed'})
    return outcomes,False


def trial(case,prompt,model,out,ledger,max_steps=12,wall_seconds=240):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    trace=[];started=time.monotonic();error=None;termination='step_limit';receipts=[]
    html=Path(__file__).with_name('web').joinpath('workbench.html').read_text()
    html=html.replace('VISIBLE_TASK',json.dumps(case.visible()).replace('</','<\\/'))
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel='chrome',headless=True)
        try:
            context=browser.new_context(viewport={'width':1440,'height':1050})
            context.route('**/*',lambda route:route.fulfill(content_type='text/html',body=html) if route.request.url=='https://cua-bench.test/' else route.abort())
            page=context.new_page();page.set_default_timeout(5000);page.goto('https://cua-bench.test/')
            initial=page.evaluate("JSON.parse(localStorage.getItem('state'))")
            if initial!={'records':case.records,'source':case.source,'policy':case.policy}:raise RuntimeError('reset_failed')
            for step in range(max_steps):
                remaining=wall_seconds-(time.monotonic()-started)
                if remaining<=1:termination='wall_limit';break
                obs=observe(page);page.screenshot(path=str(out/f'{step:02}.png'))
                # History contains visible observations, actions and execution feedback only.
                message=ACTION_CONTRACT+'\nStanding strategy:\n'+prompt+'\n'+json.dumps({'task':case.instruction,'observation':obs,'history':trace[-5:]})
                raw=None
                for attempt in range(2):
                    remaining=wall_seconds-(time.monotonic()-started)
                    if remaining<=1:termination='wall_limit';break
                    try:
                        raw,receipt=ledger.call(message,model,f'trial:{out.name}:{step}:attempt{attempt}',min(60,remaining))
                        receipts.append(receipt);break
                    except ProviderFailure as exc:
                        receipts.append(exc.receipt)
                        if attempt==0 and exc.receipt['error'] in ('URLError','TimeoutError','http_502','http_503','http_504'):
                            continue
                        error=exc.receipt['error'];termination='infrastructure_error';break
                    except BudgetExhausted:
                        error='campaign_budget';termination='budget_exhausted';break
                if raw is None:break
                event={'step':step,'observation':obs,'model_output':raw}
                try:
                    actions=json_object(raw).get('actions')
                    outcome,done=apply_actions(page,actions)
                    event['outcome']=outcome;trace.append(event)
                    if done:termination='done';break
                except (ValueError,KeyError,json.JSONDecodeError) as exc:
                    event['outcome']={'invalid_action':str(exc)};trace.append(event)
                (out/'trace.json').write_text(json.dumps(trace,indent=2))
            page.reload()
            final=page.evaluate("JSON.parse(localStorage.getItem('state'))")
            page.screenshot(path=str(out/'final.png'))
            verification=verify_case(case,final)
            if error:verification['success']=None
            result={'task_id':case.id,'family':case.family,'model':model,'prompt_hash':digest(prompt),
                    'initial_hash':digest(initial),'final':final,'verification':verification,'infrastructure_error':error,
                    'termination':termination,'steps':len(trace),'elapsed_seconds':time.monotonic()-started,
                    'usage':{'input_tokens':sum(r['usage'].get('input_tokens',0) for r in receipts if r.get('usage')),
                             'output_tokens':sum(r['usage'].get('output_tokens',0) for r in receipts if r.get('usage')),
                             'unknown_calls':sum(not r.get('usage') for r in receipts),'cost_usd':None},
                    'trace':trace,'browser_version':browser.version}
            (out/'result.json').write_text(json.dumps(result,indent=2))
            ledger.append('trial_finished',{'path':str(out),'result_hash':digest(result),'success':verification['success']})
            return result
        finally:browser.close()
