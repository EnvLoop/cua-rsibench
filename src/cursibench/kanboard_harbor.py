"""Harbor external agent for the real Kanboard application; all edits through GUI RPC."""
import asyncio,base64,json
from harbor.agents.base import BaseAgent
from .agentrouter import response_receipt,ProviderFailure

CONTRACT='Return JSON {"action":{"type":"click/fill/select/press/back/done","control":"CURRENT visible id","value":"text or option label"},"memory":"working notes"}. One action. Never invent control IDs. IDs change after navigation. Preserve source facts and completed steps in memory. The native Kanboard session is already logged in. No shell, SQL, APIs, URLs or file edits.'

class KanboardAgent(BaseAgent):
    @staticmethod
    def name():return 'cua-kanboard'
    def version(self):return '0.3.0'
    async def call_model(self,prompt,model):
        return await asyncio.to_thread(response_receipt,prompt,model,1200,180)
    async def setup(self,environment):
        r=await environment.exec(command='bash /app/start.sh',timeout_sec=150)
        if r.return_code:raise RuntimeError('Kanboard setup failed')
    async def run(self,instruction,environment,context):
        model=self.model_name or 'gpt-5.6-sol';memory='';history=[];receipts=[]
        self.logs_dir.mkdir(exist_ok=True,parents=True)
        for step in range(90):
            r=await environment.exec(command='curl -sf http://127.0.0.1:4318/observe',timeout_sec=20)
            if r.return_code:raise RuntimeError('GUI observation failed')
            obs=json.loads(r.stdout)
            prompt=CONTRACT+'\n'+json.dumps({'task':instruction,'observation':obs,'memory':memory,'last_action':history[-1]['outcome'] if history else None})
            text,receipt=await self.call_model(prompt,model);receipts.append(receipt)
            try:
                clean=text.strip()
                if clean.startswith('```'):clean='\n'.join(clean.splitlines()[1:-1])
                data=json.loads(clean);memory=str(data.get('memory',memory))[:6000]
                encoded=base64.b64encode(json.dumps(data['action']).encode()).decode()
                r=await environment.exec(command=f"printf %s '{encoded}' | base64 -d | curl -sf -X POST --data-binary @- http://127.0.0.1:4318/act",timeout_sec=20)
                outcome=json.loads(r.stdout)
            except (ValueError,KeyError):outcome={'error':'invalid action'}
            history.append({'step':step,'observation':obs,'response':text,'outcome':outcome})
            (self.logs_dir/'trace.json').write_text(json.dumps(history,indent=2))
            (self.logs_dir/'receipts.json').write_text(json.dumps(receipts,indent=2))
            if outcome.get('done'):break
        r=await environment.exec(command='python /app/kanboard_seed.py /app/final-db.json',timeout_sec=20,user='root')
        if r.return_code:raise RuntimeError('independent snapshot failed')
        context.n_input_tokens=sum(x['usage'].get('input_tokens',0) for x in receipts if x.get('usage'))
        context.n_output_tokens=sum(x['usage'].get('output_tokens',0) for x in receipts if x.get('usage'))


class TinkerKanboardAgent(KanboardAgent):
    @staticmethod
    def name():return 'cua-tinker-kanboard'
    async def call_model(self,prompt,model):
        from .harbor_adapter import TinkerBrowserAgent
        return await TinkerBrowserAgent.call_model(self,prompt,model)
