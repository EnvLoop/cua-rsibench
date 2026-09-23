"""Validate and register the predeclared Sol round-five setup-error recovery."""
import json
from pathlib import Path
from cursibench.factory_campaign import CampaignRegistry,digest
from cursibench.factory_final import validate_study,verify_execution,sha
from cursibench.factory_results import summarize
ROOT=Path(__file__).resolve().parents[1];study=ROOT/'work/factory-study-02';registry=CampaignRegistry(study/'sol-campaign.json');state=registry.snapshot()
plan_path=study/'round-5/sol-recovery-plan.json';plan=json.loads(plan_path.read_text());attempt=next(r for r in state['attempts'] if r['attempt_id']==plan['candidate']);training=json.loads(Path(attempt['training_manifest']).read_text())
assert sha(attempt['training_manifest'])==plan['training_manifest_sha256'] and digest(training['checkpoint'])==plan['checkpoint_sha256']
assert sha(study/'manifest.json')==plan['selection_manifest_sha256']
validate_study(ROOT,study,state)
out=study/plan['recovery_evaluation'];original=study/plan['original_evaluation']
assert json.loads((out/'process.json').read_text())['started']>=plan['created_at']
binding={'binding':{'checkpoint_sha256':plan['checkpoint_sha256'],'model':training['model'],'candidate':plan['candidate']}}
valid=verify_execution(out,binding);summary=summarize(out,state['protocol']['selection_tasks'])
if summary['status'] in ('not_started','running'):raise ValueError('recovery has not finished')
if not valid:summary.update(status='infrastructure_error',score=None)
(out/'summary.json').write_text(json.dumps(summary,indent=2))
record=registry.recover_evaluation(plan['candidate'],summary,out,original,plan_path)
print(json.dumps({'status':summary['status'],'score':summary['score'],'promoted':record['promoted']}))
