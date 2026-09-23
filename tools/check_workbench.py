"""Exercise UI save, reload, reset and side-effect verification for every case."""
import copy
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from cursibench.workbench_data import suite,verify_case
from cursibench.campaign_runtime import apply_actions,observe
html=Path('src/cursibench/web/workbench.html').read_text()
with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=True)
    for case in suite():
        context=browser.new_context()
        context.route('**/*',lambda route: route.fulfill(content_type='text/html',body=html.replace('VISIBLE_TASK',json.dumps(case.visible()))))
        page=context.new_page();page.goto('https://cua-bench.test/')
        assert 'expected' not in page.content()
        state=lambda:page.evaluate("JSON.parse(localStorage.getItem('state'))")
        assert state()['records']==case.records
        for row in case.expected:
            for field,kind in case.fields.items():
                apply_actions(page,[{'type':'select' if isinstance(kind,list) else 'fill','control':row['id']+':'+field,'value':row[field]}])
        assert not verify_case(case,state())['success'],'unsaved edits must not count'
        apply_actions(page,[{'type':'click','control':'save'}]);assert {c['id'] for c in observe(page)['controls']}=={'confirm','cancel'}
        apply_actions(page,[{'type':'click','control':'confirm'}]);page.reload()
        assert verify_case(case,state())['success']
        context.close()
        print(case.id,'UI reset, edit, confirm, reload passed')
    browser.close()
