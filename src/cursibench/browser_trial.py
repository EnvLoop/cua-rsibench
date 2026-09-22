"""Real Chrome execution against a synthetic expense app; not an enterprise benchmark.

Only visible page controls/text enter the provider request. Expected state remains in
this trusted runner and is never included in model messages. This is an API exposure
boundary, not an OS sandbox for arbitrary agent code.
"""
import argparse
import copy
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from .agentrouter import responses_call

INITIAL = [
    {'id':'EXP-104','owner':'Lin','amount':1200,'currency':'CNY','status':'Pending'},
    {'id':'EXP-140','owner':'Lin','amount':1200,'currency':'USD','status':'Pending'},
    {'id':'EXP-109','owner':'Mei','amount':350,'currency':'CNY','status':'Approved'},
]
HTML = '''<!doctype html><html><meta charset="utf-8"><title>Expense review</title>
<style>body{font:18px system-ui;background:#eef2f7;color:#15253e;padding:48px}main{background:white;padding:32px;border-radius:16px;max-width:900px}table{border-collapse:collapse;width:100%;margin:24px 0}td,th{text-align:left;padding:14px;border-bottom:1px solid #ddd}button,select{font:inherit;padding:8px}button{background:#154c91;color:white;border:0;border-radius:6px}</style>
<main><small>CUA-RSIBENCH / SYNTHETIC BROWSER ENVIRONMENT</small><h1>Expense review</h1>
<p>Update the status and select Save changes. Changes persist only after saving.</p>
<table><thead><tr><th>ID</th><th>Owner</th><th>Amount</th><th>Currency</th><th>Status</th></tr></thead><tbody id="rows"></tbody></table>
<button data-action="save">Save changes</button><p id="notice"></p></main>
<script>
const initial=INITIAL_DATA;
const saved=JSON.parse(localStorage.getItem('expenses')||JSON.stringify(initial));
localStorage.setItem('expenses',JSON.stringify(saved));
for(const row of saved){let tr=document.createElement('tr');tr.innerHTML=`<td>${row.id}</td><td>${row.owner}</td><td>${row.amount}</td><td>${row.currency}</td><td><select data-id="${row.id}" aria-label="${row.id} status">${['Pending','Approved','Rejected'].map(x=>`<option ${x===row.status?'selected':''}>${x}</option>`).join('')}</select></td>`;document.querySelector('#rows').appendChild(tr)}
document.querySelector('button').onclick=()=>{for(const row of saved)row.status=document.querySelector(`[data-id="${row.id}"]`).value;localStorage.setItem('expenses',JSON.stringify(saved));document.querySelector('#notice').textContent='Changes saved';};
</script></html>'''

def grade(initial, final, target, status):
    expected=copy.deepcopy(initial)
    for row in expected:
        if row['id']==target: row['status']=status
    return {'success': final==expected, 'evidence_kind':'browser_persisted_state',
            'side_effect_free': all(row==next((r for r in final if r.get('id')==row['id']),None) for row in initial if row['id']!=target)}


def run(out, model, max_steps=8):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    instruction='Reject expense EXP-140 (Lin, USD 1200). Leave every other expense unchanged. Save changes.'
    events=[];started=time.monotonic();provider_error=None
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome',headless=True)
        context=browser.new_context(viewport={'width':1200,'height':800})
        context.route('https://cua-bench.test/**',lambda route:route.fulfill(content_type='text/html',body=HTML.replace('INITIAL_DATA',json.dumps(INITIAL))))
        page=context.new_page();page.goto('https://cua-bench.test/')
        before=page.evaluate("JSON.parse(localStorage.getItem('expenses'))")
        assert before==INITIAL,'reset failed'
        for step in range(max_steps):
            shot=f'{step:02d}.png';page.screenshot(path=str(out/shot))
            controls=page.locator('select').evaluate_all('(els)=>els.map(e=>({selector:`select[data-id="${e.dataset.id}"]`,value:e.value,options:[...e.options].map(o=>o.value)}))')
            observation={'visible_text':page.locator('body').inner_text(),'selects':controls,'buttons':[{'selector':'button[data-action="save"]','text':'Save changes'}]}
            prompt='You operate a browser through allowed actions. Return exactly one JSON object: {"action":"select","selector":"...","value":"..."}, {"action":"click","selector":"..."}, or {"action":"done"}. Use only supplied visible selectors. Verify saved state via visible feedback before done.\n'+json.dumps({'instruction':instruction,'observation':observation,'history':events})
            event={'step':step,'screenshot':shot,'observation':observation}
            try:
                raw=responses_call(prompt,model=model,max_output_tokens=350)
                event['model_output']=raw
                action=json.loads(raw.strip().removeprefix('```json').removesuffix('```').strip())
                if action.get('action')=='done':
                    event['result']='done';events.append(event);break
                if action.get('action')=='select' and action.get('selector') in [c['selector'] for c in controls] and action.get('value') in ['Pending','Approved','Rejected']:
                    page.locator(action['selector']).select_option(label=action['value'])
                elif action.get('action')=='click' and action.get('selector')=='button[data-action="save"]':
                    page.locator(action['selector']).click()
                else: raise ValueError('action outside allowlist')
                event['result']='executed'
            except (ValueError,KeyError) as exc:
                event['result']='invalid_action:'+str(exc)
            except Exception as exc:
                provider_error=type(exc).__name__;event['result']='infrastructure_error:'+provider_error;events.append(event);break
            events.append(event)
        page.reload()
        final=page.evaluate("JSON.parse(localStorage.getItem('expenses'))")
        page.screenshot(path=str(out/'final.png'))
        browser.close()
    result={'model':model,'environment':'synthetic expense app in real Chrome','action_space':'DOM selectors, not pixel-only','events':events,'initial':before,'final':final,'verification':grade(INITIAL,final,'EXP-140','Rejected'),'infrastructure_error':provider_error,'elapsed_seconds':time.monotonic()-started,'official_benchmark':False}
    (out/'result.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k not in ['events','initial','final']}))
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);parser.add_argument('--model',default='gpt-5.6-sol');args=parser.parse_args();run(args.out,args.model)
