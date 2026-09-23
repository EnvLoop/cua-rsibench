"""Explicit entry points: fixture checks never masquerade as a live benchmark."""
import argparse,json

def main():
    p=argparse.ArgumentParser(description='CUA-RSIBench: real-application computer-use experiments')
    sub=p.add_subparsers(dest='command')
    f=sub.add_parser('fixture',help='Run deterministic unit fixtures (not RSI evidence)');f.add_argument('--rounds',type=int,default=5)
    n=sub.add_parser('native',help='Run actual Kanboard in E2B');n.add_argument('--out',required=True);n.add_argument('--model',default='gpt-5.6-sol');n.add_argument('--kind',default='public',choices=['basic','public','public-allocation','triage','allocation']);n.add_argument('--seed',type=int,default=51);n.add_argument('--max-steps',type=int,default=90)
    t=sub.add_parser('train',help='Bounded real Tinker SFT');t.add_argument('--data',required=True);t.add_argument('--out',required=True);t.add_argument('--model',default='Qwen/Qwen3.5-4B');t.add_argument('--steps',type=int,default=1)
    h=sub.add_parser('export-harbor',help='Export real Kanboard Harbor task');h.add_argument('--out',required=True);h.add_argument('--kind',default='public')
    args=p.parse_args()
    if args.command=='fixture':
        from .benchmark import run_benchmark
        print(json.dumps(run_benchmark(args.rounds),indent=2));return 0
    if args.command=='native':
        from .kanboard_runner import run
        r=run(args.out,args.model,args.kind,args.seed,max_steps=args.max_steps)
        print(json.dumps({k:r.get(k) for k in ['case','verification','infrastructure_error']}));return 2 if r.get('infrastructure_error') else 0
    if args.command=='train':
        from .tinker_backend import train
        r=train(args.data,args.out,args.model,args.steps);print(json.dumps({'verified_training_and_sampling':r.get('verified_training_and_sampling'),'benchmark_improvement_claim':False}));return 0
    if args.command=='export-harbor':
        from .kanboard_harbor_export import export
        print(export(args.out,args.kind));return 0
    p.print_help();return 0

if __name__=='__main__':raise SystemExit(main())
