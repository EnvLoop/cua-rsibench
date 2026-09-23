"""Start a fresh bounded study without the author's private execution directories.

Use --prepare-only to export tasks and freeze contracts without cloud model calls.
The full mode uses the configured provider accounts and requires built E2B templates.
"""
import argparse,json,subprocess,sys
from pathlib import Path
from cursibench.factory_campaign import CampaignRegistry
from cursibench.factory_results import summarize
from run_factory_round import run as run_round,child,ROOT
from prepare_factory_comparison import prepare
from run_factory_final import run as run_final
from audit_factory_study import audit


def run(out,prepare_only=False):
    study=Path(out).resolve()
    if study.exists():raise ValueError('fresh study requires a new output directory; preserve existing runs')
    for command in (
        [sys.executable,'tools/prepare_factory_study.py','--out',str(study),'--skip-initial-data'],
        [sys.executable,'tools/prepare_factory_final.py','--study',str(study),'--seal-only']):
        subprocess.run(command,cwd=ROOT,check=True)
    if prepare_only:
        print(json.dumps({'prepared':True,'cloud_calls':0,'study':str(study)}));return
    # Download only public tokenizer files on the trusted host, never in generated-code sandboxes.
    from transformers import AutoTokenizer
    AutoTokenizer.from_pretrained('Qwen/Qwen3.5-4B')
    child([sys.executable,str(ROOT/'tools/run_cloud_chain.py'),'--out',str(study/'baseline'),
        '--base','--model','Qwen/Qwen3.5-4B','--task',str(study/'selection'),
        '--factory','--environment','journal','--concurrency','3','--job-timeout','2700'],study,'baseline-execution')
    registries={name:CampaignRegistry(study/(name+'-campaign.json')) for name in ('astra','sol')}
    baseline=summarize(study/'baseline',registries['astra'].snapshot()['protocol']['selection_tasks'])
    for r in registries.values():r.set_baseline(baseline)
    for number in range(1,6):
        for name,r in registries.items():
            s=r.snapshot()
            if s['best_score']==1 or s['used_training_tokens']+262144>s['protocol']['training_token_budget']:continue
            run_round(study,name,number)
    prepare(study)
    comparison=json.loads((study/'final-comparison.json').read_text())
    for execution in comparison['executions']:
        run_final(study,execution['researcher'],execution['role'],execution['repetition'])
    report=audit(study);(study/'public-evidence.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({'completed':True,'audit_pass':report['audit_pass']}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--prepare-only',action='store_true');a=p.parse_args();run(a.out,a.prepare_only)
