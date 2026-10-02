"""One actual public-TRAIN base-model episode, outside official study results.

Root source review plus a fresh one-use permit precedes every paid callback.
The model receives only the current full screenshot and actor instruction.
Saved-state evaluation and an independent fresh guest reset use the same
concrete episode implementation as future base/checkpoint study workers.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path

from . import admit, factory as base
from . import model_transport_integration_v11 as integration
from . import prospective_model_worker_v11 as worker
from . import uniform_model_transport_v11 as transport

SCHEMA = 'cua-native-public-train-weak-base-pilot-freeze-v11'
PERMIT = 'cua-native-public-train-weak-base-pilot-one-use-permit-v11'


def prepare(*, control_freeze, task_id, output_root, freeze_path):
    value = integration.controls.validate(control_freeze)
    root = Path(value['candidate_root'])
    inventory = json.loads(integration.controls.private(root / 'candidate-inventory.json'))
    matches = [r for r in inventory['tasks'] if r['task_id'] == task_id]
    integration.require(len(matches) == 1 and matches[0]['split'] == 'train',
                        'Pilot preparation permits public TRAIN only')
    row = matches[0]
    admit._package(root, row)  # This one already-visible TRAIN package only.
    integration.require(not output_root.exists() and not output_root.is_symlink(), 'Pilot root is already consumed')
    integration.require(not any(output_root.resolve().is_relative_to(Path(p).resolve()) for p in value['accounting_roots']),
                        'Pilot artifacts must be outside every frozen historical accounting root')
    result = {'schema': SCHEMA, 'status': 'source_frozen_no_provider_or_model_calls',
              'control_freeze': str(control_freeze.resolve()), 'control_freeze_sha256': base.digest(control_freeze.read_bytes()),
              'source_sha256s': integration.proposal()['source_sha256s'], 'task_row': row,
              'candidate_root': str(root), 'output_root': str(output_root.resolve()),
              'guest_public': value['guest_public'], 'scoped_reference': value['scoped_reference'],
              'private_map': value['private_map'], 'model': transport.MODEL,
              'checkpoint_path': None, 'checkpoint_sha256': integration.proposal()['base_checkpoint_sha256'],
              'seed': 23, 'max_output_tokens': 4096, 'max_actor_actions': 90,
              'max_actor_wall_seconds': 720, 'lease_seconds_each': 1200,
              'maximum_environment_creates': 2, 'maximum_sample_requests': 90,
              'same_intent_replay_authorized': False, 'official_final_admissions': 0,
              'official_model_results': 0}
    integration.controls.accounting._write_new(freeze_path, result)
    return {'status': result['status'], 'pilot_freeze_sha256': base.digest(freeze_path.read_bytes())}


def validate(freeze_path):
    value = json.loads(integration.controls.private(freeze_path))
    integration.require(value.get('schema') == SCHEMA and value.get('model') == transport.MODEL and
                        value.get('checkpoint_path') is None and value.get('source_sha256s') == integration.proposal()['source_sha256s'] and
                        value.get('task_row', {}).get('split') == 'train' and value.get('same_intent_replay_authorized') is False and
                        value.get('max_actor_actions') == 90 and value.get('max_actor_wall_seconds') == 720 and
                        value.get('lease_seconds_each') == 1200 and value.get('max_output_tokens') == 4096,
                        'Pilot source, split or common model policy changed')
    control = integration.controls.validate(Path(value['control_freeze']))
    integration.require(base.digest(Path(value['control_freeze']).read_bytes()) == value['control_freeze_sha256'] and
                        control['candidate_root'] == value['candidate_root'], 'Pilot current source epoch changed')
    return value


def review(*, freeze_path, permit_path):
    from .reconcile_interrupted_sweep import active_hashes
    value = validate(freeze_path)
    integration.require(not Path(value['output_root']).exists(), 'Consumed pilot cannot receive another permit')
    active, count = active_hashes()
    integration.require(not active and count == 0, 'Pilot review requires provider active zero')
    permit = {'schema': PERMIT, 'freeze_sha256': base.digest(freeze_path.read_bytes()),
              'source_sha256s': value['source_sha256s'], 'task_id': value['task_row']['task_id'],
              'package_sha256': value['task_row']['package_sha256'], 'root_source_reviewed': True,
              'provider_active_zero_at_review': True, 'same_intent_replay_authorized': False}
    integration.controls.accounting._write_new(permit_path, permit)
    return {'status': 'one_train_pilot_permit_written_no_create', 'official_model_results': 0}


class PilotPaidCalls:
    def __init__(self, freeze, output, sampler):
        self.freeze = freeze; self.root = output; self.sampler = sampler
        self.attempt_id = 'public-train-weak-base'; self.ids = []; self.calls = []
        self.root.mkdir(mode=0o700)

    def invoke(self, *, suffix, category, request, provider, identity=None):
        identifier = self.attempt_id + '-' + suffix
        path = self.root / (identifier + '.intent.private.json')
        integration.require(not path.exists() and len(self.ids) < 93 and
                            self.freeze['source_sha256s'] == integration.proposal()['source_sha256s'],
                            'Paid pilot source changed or request consumed; no resubmit')
        worker.write(path, {'category': category, 'request_sha256': base.digest(integration.canonical(request)),
                           'task_identity': identity, 'same_intent_replay_authorized': False,
                           'lease_seconds': 1200 if category == 'e2b' else None})
        self.ids.append(identifier)
        if category == 'tinker':
            self.sampler.process.call('gate', {})
        worker.write(self.root / (identifier + '.dispatched.private.json'), {'intent_sha256': base.digest(path.read_bytes())})
        result = provider(request)
        ref = worker.write(self.root / (identifier + '.result.private.json'), result)
        self.calls.append({'attempt_id': identifier, 'category': category, 'result_sha256': ref['sha256']})
        return result, ref['sha256'], identifier


def run(*, freeze_path, permit_path, enable_paid_pilot=False):
    integration.require(enable_paid_pilot is True, 'Paid TRAIN pilot is disabled before private reads')
    value = validate(freeze_path)
    permit = json.loads(integration.controls.private(permit_path))
    row = value['task_row']; output = Path(value['output_root'])
    integration.require(permit.get('schema') == PERMIT and permit.get('freeze_sha256') == base.digest(freeze_path.read_bytes()) and
                        permit.get('source_sha256s') == value['source_sha256s'] and permit.get('task_id') == row['task_id'] and
                        permit.get('package_sha256') == row['package_sha256'] and permit.get('root_source_reviewed') is True and
                        permit.get('provider_active_zero_at_review') is True and permit.get('same_intent_replay_authorized') is False and
                        not output.exists() and not output.is_symlink(), 'Fresh source-reviewed TRAIN permit is required')
    pins = {'e2b-desktop': '2.2.0', 'e2b': '2.51.0', 'Pillow': '11.3.0'}
    integration.require({k: importlib.metadata.version(k) for k in pins} == pins, 'Pinned native SDK host is required')
    directory, source, oracle = admit._package(Path(value['candidate_root']), row)
    filename = next(p.name for p in directory.iterdir() if p.suffix in ('.xlsx', '.pptx', '.docx'))
    package = {'identity': {k: row[k] for k in ('task_id', 'package_sha256')}, 'source': source,
               'oracle': oracle, 'filename': filename, 'instruction': (directory / 'actor_task.txt').read_text(),
               'guest_reference_path':value['guest_public']}
    output.mkdir(parents=True, mode=0o700)
    worker.write(output / 'started.private.json', {'pilot_freeze_sha256': base.digest(freeze_path.read_bytes()),
                 'permit_sha256': base.digest(permit_path.read_bytes()), 'same_intent_replay_authorized': False})
    sampler = transport.ModelSampler(repo_root=integration.ROOT, journal_root=output / 'sampler-process',
                                     plan_sha256=base.digest(freeze_path.read_bytes()))
    paid = PilotPaidCalls(value, output / 'paid', sampler)
    model_worker = worker.DesktopProspectiveModelWorker(study=None, admissions_path=Path('/unused'), proposal_path=Path('/unused'))
    success = False
    try:
        paid.invoke(suffix='sampler-setup', category='tinker', request={'sampling_kind': 'base'},
                    provider=lambda request: sampler.start(checkpoint_path=None, checkpoint_sha256=value['checkpoint_sha256'],
                        seed=23, max_output_tokens=4096, attempt_id=paid.attempt_id))
        result, _out, trace, elapsed, outcome = model_worker._episode(
            admitted=value, package=package, ordinal=0, batch=output, paid=paid, sampler=sampler)
        receipt = {'schema': 'cua-native-public-train-weak-base-pilot-result-v11', 'status': 'train_pilot_saved_state_scored_and_reset',
                   'model': transport.MODEL, 'score': result['score'], 'model_outcome': outcome,
                   'actor_elapsed_seconds': elapsed, 'observed_model_turns': len(trace), 'paid_attempt_ids': paid.ids,
                   'result': result, 'native_actor_source': 'model_sampler_responses_only',
                   'actual_provider_billed_usd': None, 'official_final_admissions': 0, 'official_model_results': 0}
        worker.write(output / 'result.private.json', receipt); success = True
        return {k: receipt[k] for k in ('status', 'model', 'score', 'model_outcome', 'observed_model_turns', 'official_model_results')}
    except Exception as exc:
        worker.write(output / 'invalid.private.json', {'status': 'train_pilot_infrastructure_or_provider_invalid',
             'exception_type': type(exc).__name__, 'paid_attempt_ids': paid.ids,
             'same_intent_replay_authorized': False, 'failed_task_score_inferred': False, 'official_model_results': 0})
        raise
    finally:
        sampler.close(success)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=('prepare', 'review', 'run'))
    p.add_argument('--freeze', type=Path, required=True)
    for name in ('control-freeze', 'output-root', 'permit'):
        p.add_argument('--' + name, type=Path)
    p.add_argument('--task-id'); p.add_argument('--enable-paid-pilot', action='store_true')
    a = p.parse_args()
    if a.mode == 'prepare':
        result = prepare(control_freeze=a.control_freeze, task_id=a.task_id, output_root=a.output_root, freeze_path=a.freeze)
    elif a.mode == 'review':
        result = review(freeze_path=a.freeze, permit_path=a.permit)
    else:
        result = run(freeze_path=a.freeze, permit_path=a.permit, enable_paid_pilot=a.enable_paid_pilot)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
