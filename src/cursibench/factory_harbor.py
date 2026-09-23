"""Student/teacher Harbor adapters sharing the generated-data prompt contract."""
import asyncio,base64,json
from harbor.agents.base import BaseAgent
from .agentrouter import response_receipt,ProviderFailure
from .gui_contract import json_object
from .gui_contract import prompt,MAX_OUTPUT_TOKENS,MAX_MEMORY_CHARS,VERSION


class FactoryKanboardAgent(BaseAgent):
    @staticmethod
    def name():return 'cua-factory-frontier'
    def version(self):return VERSION

    async def call_model(self,text,model):
        failures=[]
        for retry in range(3):
            try:
                answer,receipt=await asyncio.to_thread(response_receipt,text,model,MAX_OUTPUT_TOKENS,180)
                receipt['prior_transport_failures']=failures
                return answer,receipt
            except ProviderFailure as exc:
                failures.append(exc.receipt)
                if retry==2 or exc.receipt['error'] not in ('URLError','TimeoutError','http_502','http_503','http_504'):raise
                await asyncio.sleep(retry+1)

    async def setup(self,environment):
        r=await environment.exec(command='bash /app/start.sh',timeout_sec=150)
        if r.return_code:raise RuntimeError('native task setup failed')

    async def run(self,instruction,environment,context):
        self.logs_dir.mkdir(exist_ok=True,parents=True)
        history=[];receipts=[];memory='';model=self.model_name or 'gpt-5.6-sol'
        for step in range(90):
            r=await environment.exec(command='curl -sf http://127.0.0.1:4318/observe',timeout_sec=20)
            if r.return_code:raise RuntimeError('native observation failed')
            observation=json.loads(r.stdout)
            request=prompt(instruction,observation,memory,history[-1]['outcome'] if history else None)
            response,receipt=await self.call_model(request,model);receipts.append(receipt)
            try:
                parsed=json_object(response);action=parsed['action'];memory=str(parsed.get('memory',memory))[:MAX_MEMORY_CHARS]
                encoded=base64.b64encode(json.dumps(action).encode()).decode()
                r=await environment.exec(command=f"printf %s '{encoded}' | base64 -d | curl -sf -X POST --data-binary @- http://127.0.0.1:4318/act",timeout_sec=20)
                if r.return_code:raise RuntimeError('native action transport failed')
                outcome=json.loads(r.stdout)
            except (ValueError,KeyError):outcome={'error':'invalid response'}
            history.append({'step':step,'prompt':request,'observation':observation,'response':response,'outcome':outcome})
            (self.logs_dir/'trace.json').write_text(json.dumps(history,indent=2));(self.logs_dir/'receipts.json').write_text(json.dumps(receipts,indent=2))
            if outcome.get('done'):break
        r=await environment.exec(command='python /app/kanboard_seed.py /app/final-db.json',timeout_sec=20,user='root')
        if r.return_code:raise RuntimeError('independent state snapshot failed')
        context.n_input_tokens=sum(x['usage'].get('input_tokens',0) for x in receipts if x.get('usage'))
        context.n_output_tokens=sum(x['usage'].get('output_tokens',0) for x in receipts if x.get('usage'))


class FactoryTinkerAgent(FactoryKanboardAgent):
    @staticmethod
    def name():return 'cua-factory-student'
    async def call_model(self,text,model):
        from .harbor_adapter import TinkerBrowserAgent
        return await TinkerBrowserAgent.call_model(self,text,model)
