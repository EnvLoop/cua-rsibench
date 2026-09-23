"""Browser integration checks for stale IDs, modal isolation, and batch performance."""
import time
from playwright.sync_api import sync_playwright
from cursibench.stable_observer import capture,act
with sync_playwright() as p:
 b=p.chromium.launch(channel='chrome',headless=True);page=b.new_page()
 page.set_content('<button onclick="window.chosen=\'original\'">Original</button>')
 frame=capture(page)
 page.evaluate("""() => {const b=document.createElement('button');b.textContent='New';b.onclick=()=>window.chosen='new';document.body.prepend(b)}""")
 act(page,frame,{'type':'click','control':'0'})
 assert page.evaluate('window.chosen')=='original','stale numeric ID clicked the wrong object'
 frame.dispose()
 page.set_content('<button>Remove me</button>')
 frame=capture(page);page.locator('button').evaluate('(e)=>e.remove()')
 try:act(page,frame,{'type':'click','control':'0'})
 except ValueError:pass
 else:raise AssertionError('detached element was accepted')
 frame.dispose()
 page.set_content('<button>Background</button>')
 frame=capture(page)
 page.evaluate("() => {const m=document.createElement('div');m.id='modal-box';m.textContent='Modal';document.body.append(m)}")
 try:act(page,frame,{'type':'click','control':'0'})
 except ValueError:pass
 else:raise AssertionError('background control accepted after a modal opened')
 frame.dispose()
 page.set_content('<button>Background</button><div id="modal-box"><button>Save</button><input aria-label="Title"></div>')
 frame=capture(page)
 assert frame.observation['modal_open']
 assert [r['label'] for r in frame.observation['controls']]==['Save','Title']
 frame.dispose()
 page.set_content('<details><summary>Comments</summary><input aria-label="Hidden comment"><button>Hidden save</button></details><button>Visible</button>')
 frame=capture(page)
 assert [r['label'] for r in frame.observation['controls']]==['Visible'],'closed details leaked hidden controls'
 frame.dispose()
 page.set_content(''.join(f'<button>B{i}</button>' for i in range(500)))
 started=time.monotonic();frame=capture(page);elapsed=time.monotonic()-started
 assert len(frame.observation['controls'])==500
 frame.dispose();b.close()
 print('stable node binding, modal isolation passed; 500 controls snapshot seconds:',round(elapsed,4))
