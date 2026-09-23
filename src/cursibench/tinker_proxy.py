"""E2B-hosted, bearer-authenticated Tinker sampling proxy (no evaluator access)."""
import hmac,json,os,time
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
import tinker
from tinker import types
from transformers import AutoTokenizer
from sample_cache import SamplingCache,request_capacity


def main():
    service=tinker.ServiceClient();checkpoint=os.environ['TINKER_MODEL_PATH'];base=os.environ['TINKER_BASE_MODEL']
    sampling=service.create_sampling_client(model_path=checkpoint) if checkpoint.startswith('tinker://') else service.create_sampling_client(base_model=base)
    tokenizer=AutoTokenizer.from_pretrained(base)
    token=os.environ['CUA_PROXY_TOKEN'];capacity=request_capacity(int(os.environ.get('CUA_TASK_COUNT','1')));cache=SamplingCache(limit=capacity);finished={}
    class H(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            if self.path=='/health':self.respond({'ready':True,'request_capacity':capacity})
            else:self.send_error(404)
        def do_POST(self):
            if not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+token):self.send_error(401);return
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=200000:self.send_error(413);return
            try:
                request=json.loads(self.rfile.read(size));prompt=request['prompt'];request_id=request['request_id']
                text=tokenizer.apply_chat_template([{'role':'user','content':prompt}],tokenize=False,add_generation_prompt=True,enable_thinking=False)
                ids=tokenizer.encode(text,add_special_tokens=False)
                if len(ids)>15000:raise ValueError('prompt exceeds fixed proxy budget')
                started=time.monotonic()
                future,reused=cache.get(request_id,prompt,lambda:sampling.sample(prompt=types.ModelInput.from_ints(ids),num_samples=1,sampling_params=types.SamplingParams(max_tokens=512,temperature=0,seed=23)))
                if request_id in finished:self.respond(finished[request_id]);return
                output=future.result(timeout=120)
                tokens=output.sequences[0].tokens
                result={'request_id':request_id,'text':tokenizer.decode(tokens,skip_special_tokens=True),'usage':{'input_tokens':len(ids),'output_tokens':len(tokens)},'elapsed_seconds':time.monotonic()-started}
                finished[request_id]=result
                # Accounting only; never log credentials or private provider envelopes.
                with Path('/app/proxy-usage.jsonl').open('a') as f:f.write(json.dumps(result)+'\n')
                self.respond(result)
            except Exception as exc:self.respond({'error':type(exc).__name__},500)
        def respond(self,data,code=200):
            b=json.dumps(data).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
    try:HTTPServer(('0.0.0.0',8088),H).serve_forever()
    finally:service.close('success').result(timeout=30)

if __name__=='__main__':main()
