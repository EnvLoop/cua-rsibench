"""Bounded real Tinker LoRA SFT, sampler checkpoint and sampling smoke.

Consumes verified training demonstrations; no synthetic success scores. Training
and sampling usage are recorded separately from browser task accuracy.
"""
import argparse
import hashlib
import json
import time
from pathlib import Path


def validate_records(records):
    if not records:raise ValueError('empty training data')
    for row in records:
        messages=row.get('messages')
        if not isinstance(messages,list) or len(messages)<2:raise ValueError('invalid messages')
        if messages[-1].get('role')!='assistant' or not messages[-1].get('content') or messages[-1].get('loss') is False:raise ValueError('final assistant target required')
        if not any(m.get('role')=='user' for m in messages):raise ValueError('user observation required')
        if any(m.get('role') not in ('system','user','assistant','tool') for m in messages):raise ValueError('unknown role')
        if row.get('source_split')!='train':raise ValueError('only training-split demonstrations are allowed')


def train(data_path,out,model='Qwen/Qwen3.5-4B',steps=1):
    if not 1<=steps<=4:raise ValueError('smoke training allows 1..4 steps')
    import tinker
    from tinker import types
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    records=[json.loads(l) for l in Path(data_path).read_text().splitlines() if l.strip()]
    validate_records(records)
    if len(records)>32:raise ValueError('smoke record limit 32')
    service=tinker.ServiceClient(user_metadata={'purpose':'cua-rsibench-training-smoke'})
    status='errored';started=time.monotonic();report={'model':model,'steps_requested':steps,'record_count':len(records),'data_sha256':hashlib.sha256(Path(data_path).read_bytes()).hexdigest(),'cost_usd':None}
    def save():out.joinpath('training.json').write_text(json.dumps(report,indent=2,default=str))
    save()
    try:
        client=service.create_lora_training_client(base_model=model,rank=8,seed=23)
        tokenizer=client.get_tokenizer();examples=[];prompts=[]
        for row in records:
            messages=[{'role':m['role'],'content':m['content']} for m in row['messages']]
            prefix_text=tokenizer.apply_chat_template(messages[:-1],tokenize=False,add_generation_prompt=True,enable_thinking=False)
            prefix=tokenizer.encode(prefix_text,add_special_tokens=False)
            target=tokenizer.encode(messages[-1]['content'],add_special_tokens=False)
            if tokenizer.eos_token_id is not None:target.append(tokenizer.eos_token_id)
            tokens=prefix+target
            if len(tokens)>8192:raise ValueError('training record exceeds 8192 token smoke limit')
            examples.append(types.Datum(model_input=types.ModelInput.from_ints(tokens[:-1]),loss_fn_inputs={'target_tokens':tokens[1:],'weights':[0.0]*(len(prefix)-1)+[1.0]*len(target)}))
            prompts.append(prefix)
        report['scheduled_tokens']=sum(len(ex.model_input.to_ints()) for ex in examples[:2])*steps
        report['events']=[];save()
        for step in range(steps):
            batch=examples[(step*2)%len(examples):][:2]
            fw=client.forward_backward(batch,'cross_entropy').result(timeout=180)
            opt=client.optim_step(types.AdamParams(learning_rate=1e-4)).result(timeout=180)
            report['events'].append({'step':step+1,'metrics':getattr(fw,'metrics',{}),'optimizer_metrics':getattr(opt,'metrics',{})});save()
        checkpoint=client.save_weights_for_sampler('cua-smoke').result(timeout=180)
        report['checkpoint']=checkpoint.path;save()
        sampling=service.create_sampling_client(model_path=checkpoint.path)
        sampled=sampling.sample(prompt=types.ModelInput.from_ints(prompts[0]),num_samples=1,sampling_params=types.SamplingParams(max_tokens=128,temperature=0,seed=23)).result(timeout=180)
        report['sample_text']=tokenizer.decode(sampled.sequences[0].tokens)
        report['sample_tokens']=len(sampled.sequences[0].tokens)
        report['verified_training_and_sampling']=True
        report['benchmark_improvement_claim']=False
        status='success';return report
    finally:
        report['elapsed_seconds']=time.monotonic()-started;save()
        service.close(status).result(timeout=30)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data',required=True);p.add_argument('--out',required=True);p.add_argument('--model',default='Qwen/Qwen3.5-4B');a=p.parse_args();print(json.dumps(train(a.data,a.out,a.model),default=str))
