"""Evaluate a frozen checkpoint on sealed final chunks, with durable phase records."""
import argparse
import json
import time
import sys
from pathlib import Path
from cursibench.factory_campaign import CampaignRegistry
from cursibench.factory_final import make_plan, combine, verify_execution, read
from cursibench.factory_results import summarize
from run_factory_round import child, write, ROOT


def run(study, name, role, repetition):
    study = Path(study).resolve()
    registry = CampaignRegistry(study / (name + '-campaign.json'))
    # Both searches close before either researcher could receive final-test evidence.
    for researcher in ('astra', 'sol'):
        if CampaignRegistry(study / (researcher + '-campaign.json')).snapshot()['final_selection'] is None:
            raise ValueError('both research campaigns must be frozen before final testing')
    state = registry.snapshot()
    plan = make_plan(ROOT, study, state, role, repetition)
    label = f'{name}-{role}-repeat-{repetition}'
    out = study / 'final-executions' / label
    out.mkdir(parents=True, exist_ok=True)
    if (out / 'plan.json').exists():
        if read(out / 'plan.json') != plan:
            raise ValueError('final execution plan changed')
    else:
        write(out / 'plan.json', plan)
        write(out / 'started.json', {'started_at': time.time(), 'label': label})
    started_at = read(out / 'started.json')['started_at']
    if started_at < plan['selection']['frozen_at']:
        raise ValueError('execution predates frozen selection')
    summaries = []
    for chunk, tasks in sorted(plan['chunks'].items()):
        if make_plan(ROOT, study, registry.snapshot(), role, repetition) != plan:
            raise ValueError('inputs changed during final execution')
        destination = out / chunk
        if not (destination / 'result.json').exists():
            # child refuses a second execution if a previous phase log exists.
            command = [sys.executable, str(ROOT / 'tools/run_cloud_chain.py'),
                       '--out', str(destination), '--task', str(study / 'sealed-final' / chunk),
                       '--factory', '--environment', 'journal', '--concurrency', '3', '--job-timeout', '2700']
            training = plan['binding']['training_manifest']
            command += ['--training', training] if training else ['--base', '--model', plan['binding']['model']]
            child(command, out, chunk + '-execution')
        infrastructure_ok = verify_execution(destination, plan)
        summary = summarize(destination, tasks)
        if not infrastructure_ok:
            summary.update(status='infrastructure_error', score=None)
        summaries.append(summary)
    result = combine(summaries, state['protocol']['final_tasks'])
    write(out / 'summary.json', result)
    existing = [r for r in registry.snapshot()['final_results'] if r['label'] == label]
    if existing:
        if existing[0]['evaluation'] != result:
            raise ValueError('registered final result differs from evidence')
    else:
        registry.record_final(label, result, started_at)
    print(json.dumps({'label': label, 'candidate': plan['binding']['candidate'],
                      'status': result['status'], 'score': result['score']}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--study', default='work/factory-study-02')
    parser.add_argument('--researcher', choices=['astra', 'sol'], required=True)
    parser.add_argument('--role', choices=['selected', 'base'], required=True)
    parser.add_argument('--repetition', type=int, default=1)
    args = parser.parse_args()
    run(args.study, args.researcher, args.role, args.repetition)
