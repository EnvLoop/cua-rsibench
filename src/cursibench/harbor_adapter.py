"""Real external Harbor agent. Provider stays on host; sandbox exposes only fixed GUI RPC."""
import asyncio
import base64
import json
from pathlib import Path
from harbor.agents.base import BaseAgent
from .agentrouter import response_receipt

CONTRACT='Return JSON {"actions":[...]}, maximum 4 actions. Allowed: {"type":"click","control":"visible id"}, {"type":"fill","control":"visible id","value":"text"}, {"type":"select","control":"visible id","value":"visible option"}, {"type":"done"}. Use only current visible controls; visit tabs to read sources and policy. Save and confirm changes. No code.'

class BrowserAgent(BaseAgent):
    @staticmethod
    def name():return 'cua-browser'
    def version(self):return '0.3.0'
    async def call_model(self,prompt,model):
        return await asyncio.to_thread(response_receipt,prompt,model,900,90)
    async def setup(self,environment):
        result=await environment.exec(command='nohup python /app/browser_rpc.py > /app/browser.log 2>&1 < /dev/null &',timeout_sec=15)
        for _ in range(30):
            r=await environment.exec(command='curl -sf http://127.0.0.1:4318/observe',timeout_sec=10)
            if r.return_code==0:return
            await asyncio.sleep(1)
        raise RuntimeError('browser RPC not ready')
    async def run(self,instruction,environment,context):
        history=[];receipts=[];model=self.model_name or 'gpt-5.6-sol'
        for step in range(12):
            r=await environment.exec(command='curl -sf http://127.0.0.1:4318/observe',timeout_sec=15)
            if r.return_code!=0:raise RuntimeError('observation transport failed')
            observation=json.loads(r.stdout)
            prompt=CONTRACT+'\n'+json.dumps({'instruction':instruction,'observation':observation,'history':history[-5:]})
            text,receipt=await self.call_model(prompt,model)
            receipts.append(receipt)
            clean=text.strip()
            if clean.startswith('```'):clean='\n'.join(clean.splitlines()[1:-1])
            try:
                action=json.loads(clean);payload=base64.b64encode(json.dumps(action).encode()).decode()
                result=await environment.exec(command=f"printf %s '{payload}' | base64 -d | curl -sf -X POST -H 'Content-Type: application/json' --data-binary @- http://127.0.0.1:4318/act",timeout_sec=30)
                outcome=json.loads(result.stdout)
            except (ValueError,KeyError):outcome={'error':'invalid action JSON'}
            history.append({'observation':observation,'model_output':text,'outcome':outcome})
            self.logs_dir.mkdir(parents=True,exist_ok=True)
            (self.logs_dir/'browser-trace.json').write_text(json.dumps(history,indent=2))
            (self.logs_dir/'provider-receipts.json').write_text(json.dumps(receipts,indent=2))
            if outcome.get('done'):break
        done=await environment.exec(command='curl -sf http://127.0.0.1:4318/finalize',timeout_sec=15)
        if done.return_code!=0:raise RuntimeError('final artifact readback failed')
        context.n_input_tokens=sum(r['usage'].get('input_tokens',0) for r in receipts if r.get('usage'))
        context.n_output_tokens=sum(r['usage'].get('output_tokens',0) for r in receipts if r.get('usage'))


class TinkerBrowserAgent(BrowserAgent):
    @staticmethod
    def name():return 'cua-tinker-browser'
    async def call_model(self,prompt,model):
        import os
        from .http_transport import post_json
        import uuid,time,httpx
        request_id=uuid.uuid4().hex
        def call():
            for attempt in range(3):
                try:
                    body=post_json(os.environ['CUA_TINKER_PROXY_URL']+'/sample',{'prompt':prompt,'request_id':request_id},
                                   {'Authorization':'Bearer '+os.environ['CUA_PROXY_TOKEN'],'Content-Type':'application/json'},150)
                    break
                except (httpx.TransportError,httpx.HTTPStatusError) as exc:
                    retryable=not isinstance(exc,httpx.HTTPStatusError) or exc.response.status_code in (500,502,503,504)
                    if attempt==2 or not retryable:raise
                    time.sleep(2**attempt)
            if body.get('error'):raise RuntimeError('Tinker proxy sampling failed')
            return body['text'],{'requested_model':model,'usage':body['usage'],'elapsed_seconds':body['elapsed_seconds'],'cost_usd':None}
        return await asyncio.to_thread(call)
