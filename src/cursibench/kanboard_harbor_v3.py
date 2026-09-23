"""Opt-in frontier actor with bounded, logged inference transport recovery."""
import asyncio,json
from .kanboard_harbor import KanboardAgent
from .agentrouter import ProviderFailure


class ResilientKanboardAgent(KanboardAgent):
    @staticmethod
    def name():return 'cua-kanboard-v3'
    def version(self):return '0.4.0'
    async def call_model(self,prompt,model):
        failures=[]
        for attempt in range(3):
            try:
                text,receipt=await super().call_model(prompt,model)
                receipt['prior_transport_failures']=failures
                return text,receipt
            except ProviderFailure as exc:
                failures.append(exc.receipt)
                with (self.logs_dir/'inference-failures.jsonl').open('a') as f:
                    f.write(json.dumps(exc.receipt)+'\n')
                if attempt==2 or exc.receipt.get('error') not in ('TimeoutError','URLError','http_502','http_503','http_504'):raise
                # Inference can be billed before response loss; usage remains unknown.
                # There is no GUI effect until a successful response is acted upon.
                await asyncio.sleep(1+attempt)
