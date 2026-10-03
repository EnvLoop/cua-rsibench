"""Original selection20 reference controls; no provider or model-lane admission.

The existing Native10 facade already has the exact selection loop. This
additive entrypoint supplies explicit reference-only TRAIN/source prerequisites
and a one-use reviewed authority, without changing that loop or Native10.
"""
import argparse
import json
from hashlib import sha256
from pathlib import Path
from . import native_surface_workers_v10 as workers
from . import native_surface_facade_v10 as facade
from . import native_reference_qualification_v7 as reference
from . import native_surface_budget_performance_v10 as audit
from .native_principal_header_v2 import valid_witness
from cursibench import native_surface_guard_policy_v1 as policy

require, private, write = workers.require, workers.private_json, workers.write
MODES = (('baseline', 0), ('positive', 1), ('wrong_variant', 0))


def _sha(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), 'reference_artifact_unsafe')
    return sha256(path.read_bytes()).hexdigest()


def _ref(path, digest):
    private(path, digest)
    return {'path': str(Path(path).resolve()), 'sha256': digest}


def source_binding():
    root = Path(__file__).resolve().parents[1]
    names = ('magento_catalog_factory/native_selection_reference_controls_v1.py',
             'magento_catalog_factory/native_surface_facade_v10.py',
             'magento_catalog_factory/native_surface_facade_v1.py')
    value = {'schema': 'magento-selection20-reference-source-v1',
             'native_binding_sha256': workers.public_binding()['binding_sha256'],
             'reference_binding_sha256': reference.reference_binding()['binding_sha256'],
             'source_sha256s': {name: _sha(root/name) for name in names},
             'native_actor_sampler_scorer_reset_changed': False, 'model_calls': 0}
    return {**value, 'binding_sha256': workers.digest(workers.final.canonical(value))}


def _trios(inputs, controls_path, controls_sha256, split, count):
    controls = private(controls_path, controls_sha256)
    require(controls.get('schema') == 'magento-native-surface-control-set-v1' and
            controls.get('source_binding_sha256') == inputs.binding['binding_sha256'] and
            controls.get('split') == split and controls.get('task_count') == count and
            len(controls.get('tasks', [])) == count and controls.get('model_calls') == 0 and
            controls.get('formal_registration_performed') is False and
            controls.get('old_development_control_credit') == 0, 'current_whole_controls_required')
    identities = inputs.roster['splits'][split]
    if split == 'train':
        require(controls.get('reference_binding') == reference.reference_binding() and
                controls.get('fresh_three_modes_completed') is True and
                controls.get('old_principal_epoch_qualification_credit') == 0 and
                controls.get('original_baseline_promoted') is False, 'current_train_reference_required')
        require({k: controls['tasks'][0][k] for k in ('task_id', 'package_sha256')} in identities,
                'train_control_identity_changed')
    else:
        require([{k: row[k] for k in ('task_id', 'package_sha256')} for row in controls['tasks']] == identities,
                'original_ordered_selection20_required')
    actions = frames = 0
    for ordinal, task in enumerate(controls['tasks']):
        identity = {k: task[k] for k in ('task_id', 'package_sha256')}
        require(set(task['trio']) == {mode for mode, _ in MODES}, 'whole_three_modes_required')
        for mode, score in MODES:
            proof = task['trio'][mode]
            folder = Path(proof['episode_root'])
            require(folder.resolve() == (Path(controls_path).parent/f'attempt-{ordinal:03d}'/mode).resolve(),
                    'original_episode_path_changed')
            row = private(folder/'native-row.private.json', proof['native_row_sha256'])
            require({k: row[k] for k in identity} == identity and
                    row['native_source_binding_sha256'] == inputs.binding['binding_sha256'] and
                    row['score'] == proof['score'] == score and
                    all(sample.get('paid_attempt_id') is None for sample in row['samples']),
                    'original_identity_or_score_or_paid_path_changed')
            saved = audit.audit_episode(folder, row, provider_close_required=False)
            require(saved['score'] == score, 'independent_original_score_changed')
            actions += len(saved['actions']); frames += len(saved['frames'])
    return {'controls_ref': _ref(controls_path, controls_sha256),
            'task_identities': [{k: row[k] for k in ('task_id', 'package_sha256')} for row in controls['tasks']],
            'actions': actions,
            'frames': frames, 'task_count': count, 'saved_state_reset_rederived': True}


def _source_reading(inputs, inputs_ref, path, digest):
    root = Path(path).parent
    review = private(path, digest)
    require(review.get('schema') == 'root-magento11-native-source-read-close-reset-audit-v1' and
            review.get('actual_exec_exit_code') == 0 and review.get('model_calls') == 0 and
            review.get('tinker_calls') == 0 and review.get('native_full_qualification_claimed') is False,
            'actual_reference_source_review_required')
    flags = ('actual_four_guarded_navigation_receipts', 'consumer_child_supervisor_absent',
             'fresh_distinct_queue_reset_exact', 'native10_source_unchanged', 'owned_app_search_network_removed',
             'process_absent_scale_inventory_empty', 'quote_and_business_baseline_unchanged',
             'source_and_closed_native_images_visually_reviewed')
    require(all(review.get(key) is True for key in flags), 'actual_source_close_reset_review_incomplete')
    required = {'before-native-close.private.png', 'after-native-close.private.png',
                'native-close-ready-state.private.json', 'native.private/queue/close.private.json',
                'native.private/queue/reset.private.json', 'readonly-native-source-ui.private.json',
                'run-source-ui.private.py', 'terminal.private.json'}
    require(set(review['source_hashes']) == required, 'exact_source_review_artifacts_required')
    for name, expected in review['source_hashes'].items():
        require(_sha(root/name) == expected, 'reviewed_source_artifact_changed')
    intent = private(root/'intent.private.json')
    require(intent['inputs_ref'] == inputs_ref and intent['native_binding_sha256'] == inputs.binding['binding_sha256'] and
            _sha(root/'run-source-ui.private.py') == intent['controller_source_sha256'],
            'source_reader_inputs_or_source_changed')
    approved = private(root/'root-controller-review-approved.private.json')
    require(approved['controller_ref']['sha256'] == intent['controller_source_sha256'] and
            approved['intent_ref']['sha256'] == _sha(root/'intent.private.json'), 'source_reader_authority_changed')
    terminal = private(root/'terminal.private.json')
    require(terminal['frozen_native_binding_sha256'] == inputs.binding['binding_sha256'] and
            terminal['fresh_distinct_reset_and_cleanup_verified'] is True and
            terminal['original_source_and_business_baseline_unchanged'] is True, 'source_reader_terminal_changed')
    result = private(root/'readonly-native-source-ui.private.json')
    require(result['guarded_navigation_actions'] == 4 and result['business_edits'] == 0 and
            result['source_input_performed'] is False and result['native_code_modal_cancelled'] is True and
            result['cms_save_called'] is False and result['source_quote_sha256_unchanged'] is True,
            'source_reader_business_or_close_changed')
    native = root/'native.private'
    identities = inputs.roster['splits']['train']
    identity = identities[intent['public_train_ordinal']]
    def reopen(value):
        if isinstance(value, dict):
            if value.get('schema') == 'native-guard-artifact-ref-v1':
                policy.verify_artifact(native, value)
            for item in value.values(): reopen(item)
        elif isinstance(value, list):
            for item in value: reopen(item)
    guard_hashes, nonces = [], set()
    for step in range(4):
        capsule_path = native/f'guard/turn-{step:03d}/receipt.private.json'
        guard_hashes.append(_sha(capsule_path))
        capsule = private(native/f'guard/turn-{step:03d}/receipt.private.json'); reopen(capsule)
        require(capsule['action']['type'] == 'click' and capsule['action']['step'] == step and
                capsule['action']['task_id'] == identity['task_id'] and
                capsule['action']['task_binding_sha256'] == identity['package_sha256'],
                'source_reader_action_changed')
        decided = policy.decision(capsule['observed'], capsule['current'], capsule['action'],
                                  lease_check=lambda _: capsule['lease_check'], now=capsule['audit_clock'])
        receipt = policy.validate_receipt(capsule['receipt'])
        require(capsule['action']['frame_id'] not in nonces and
                receipt['action_sha256'] == policy.digest(capsule['action']) and
                receipt['decision_sha256'] == policy.digest(decided) and
                receipt['frame_id'] == capsule['action']['frame_id'] and receipt['step'] == step,
                'source_reader_action_receipt_or_nonce_changed')
        nonces.add(capsule['action']['frame_id'])
        nonce_ref = capsule['nonce_consumption']
        nonce = private(native/nonce_ref['path'], nonce_ref['sha256'])
        require(nonce == {'action_sha256': policy.digest(capsule['action']),
                         'frame_id': capsule['action']['frame_id'], 'step': step}, 'source_reader_nonce_changed')
        intent_ref = capsule['receipt']['intent']
        io_intent = private(native/intent_ref['path'], intent_ref['sha256'])
        reopen(io_intent)
        decision_ref = io_intent['decision']
        io_decision = private(native/decision_ref['path'], decision_ref['sha256'])
        require(io_intent['action'] == capsule['action'] and io_decision == decided and
                io_intent['driver_not_yet_called'] is True, 'source_reader_io_intent_changed')
        require(decided == capsule['decision'] and decided['status'] == 'accepted' and
                receipt['status'] == 'applied' and receipt['driver_result'] == 'succeeded',
                'source_reader_guard_not_rederived')
        driver_ref = capsule['receipt']['driver_evidence']
        driver = private(native/driver_ref['path'], driver_ref['sha256'])
        require(driver['returned'] is True and len(driver['actual_calls']) == 1, 'source_reader_actual_io_changed')
        for envelope in (capsule['observed'], capsule['current']):
            raw = private(native/envelope['raw_envelope']['path'], envelope['raw_envelope']['sha256'])
            require(valid_witness(raw, raw['native_username']), 'source_reader_principal_changed')
    reset = private(native/'queue/reset.private.json'); close = private(native/'queue/close.private.json')
    require(reset['full_channel_exact'] is True and reset['fresh_app_b_before_original_cleanup'] is True and
            reset['baseline'] == reset['restored'] and close['supervisor_pid_absent'] is True and
            close['exit']['child_pid_absent'] is True, 'source_reader_reset_or_consumer_changed')
    return {'root_review_ref': _ref(path, digest), 'actual_native_source_and_close_reviewed': True,
            'four_guarded_clicks_rederived': True, 'guard_receipts_sha256s': guard_hashes,
            'train_identity': identity, 'model_lane_admission_claimed': False}


def _prepare(*, inputs_path, inputs_sha256, train_controls_path, train_controls_sha256,
             source_review_path, source_review_sha256, output):
    inputs_ref = _ref(inputs_path, inputs_sha256)
    inputs = workers.Inputs(**private(inputs_path, inputs_sha256), control_preparation_only=True)
    require(_sha(inputs.plan_path) == inputs.plan_sha, 'original_plan_bytes_changed')
    selection = inputs.roster['splits']['selection']
    require(len(selection) == 20 and len({row['task_id'] for row in selection}) == 20,
            'original_twenty_selection_required')
    prerequisites = {'train': _trios(inputs, train_controls_path, train_controls_sha256, 'train', 1),
                     'source_reading': _source_reading(inputs, inputs_ref, source_review_path, source_review_sha256)}
    require(prerequisites['train']['task_identities'] == [prerequisites['source_reading']['train_identity']],
            'train_control_and_source_reader_identity_changed')
    contract = {'schema': 'magento-selection20-reference-root-review-v1', 'inputs_ref': inputs_ref,
                'source_binding': source_binding(), 'selection_tasks': selection,
                'selection_identities_sha256': workers.digest(workers.final.canonical(selection)),
                'prerequisites': prerequisites, 'output_root': str(Path(output).resolve()),
                'modes': [mode for mode, _ in MODES], 'task_count': 20,
                'model_calls': 0, 'model_lane_admission_claimed': False,
                'formal_registration_authorized': False, 'automatic_restart_authorized': False}
    return inputs, contract


def review_contract(**kwargs):
    """Metadata and saved re-audit only; opens no selection task body/runtime."""
    return _prepare(**kwargs)[1]


class _ReferenceInputs:
    """Authority applies only to reference controls, never to model admission."""
    def __init__(self, inputs, contract, kwargs): self._inputs, self._contract, self._kwargs = inputs, contract, kwargs
    def __getattr__(self, name): return getattr(self._inputs, name)
    def _current(self):
        require(self._inputs.binding == workers.public_binding() and
                self._contract['source_binding'] == source_binding(), 'current_reference_source_changed')
    def validate_train_admission(self):
        self._current()
        require(_prepare(**self._kwargs)[1] == self._contract, 'reference_prerequisites_changed')
    def load(self, identity, split):
        self._current()
        require(split == 'selection' and identity in self.roster['splits']['selection'], 'reference_selection_only')
        return self._inputs.load(identity, split)
    def runtime(self): self._current(); return self._inputs.runtime()


def run(*, root_review_path, root_review_sha256, execute=False, **kwargs):
    require(execute is True, 'explicit_reviewed_reference_execution_required')
    inputs, expected = _prepare(**kwargs)
    require(private(root_review_path, root_review_sha256) == expected, 'exact_current_reference_review_required')
    output = Path(kwargs['output'])
    require(not output.exists() and not output.is_symlink(), 'fresh_reference_namespace_required')
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    write(output.parent, 'selection-reference-'+root_review_sha256+'-consumed.private.json',
          {'root_review_sha256': root_review_sha256, 'model_calls': 0, 'automatic_restarts': 0})
    try:
        facade.run_controls(inputs=_ReferenceInputs(inputs, expected, kwargs), split='selection', output=output, enable_live=True)
        require(source_binding() == expected['source_binding'], 'current_reference_source_changed')
        checked = _trios(inputs, output/'controls.private.json', _sha(output/'controls.private.json'), 'selection', 20)
        value = {'schema': 'magento-selection20-reference-result-v1', 'source_binding': expected['source_binding'],
                 'root_review_ref': _ref(root_review_path, root_review_sha256), 'saved_audit': checked,
                 'source_visual_qualification_complete': False, 'formal_registration_performed': False,
                 'model_lane_admission_claimed': False, 'model_calls': 0, 'tinker_calls': 0}
        write(output, 'selection-reference-result.private.json', value)
        return value
    except BaseException as error:
        output.mkdir(mode=0o700, exist_ok=True)
        write(output, 'failure.private.json', {'schema': 'magento-selection20-reference-failure-v1',
              'error_type': type(error).__name__, 'automatic_replay_authorized': False,
              'model_calls': 0, 'formal_registration_performed': False})
        raise


def saved_audit(*, root_review_path, root_review_sha256, **kwargs):
    inputs, expected = _prepare(**kwargs)
    require(private(root_review_path, root_review_sha256) == expected, 'exact_current_reference_review_required')
    output = Path(kwargs['output'])
    require(not (output/'failure.private.json').exists(), 'failed_reference_not_complete')
    value = private(output/'selection-reference-result.private.json')
    checked = _trios(inputs, output/'controls.private.json', value['saved_audit']['controls_ref']['sha256'], 'selection', 20)
    require(value == {'schema': 'magento-selection20-reference-result-v1', 'source_binding': expected['source_binding'],
                     'root_review_ref': _ref(root_review_path, root_review_sha256), 'saved_audit': checked,
                     'source_visual_qualification_complete': False, 'formal_registration_performed': False,
                     'model_lane_admission_claimed': False, 'model_calls': 0, 'tinker_calls': 0},
            'saved_reference_summary_changed')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('review', 'run', 'audit'))
    for name in ('inputs-path', 'inputs-sha256', 'train-controls-path', 'train-controls-sha256',
                 'source-review-path', 'source-review-sha256', 'output'):
        parser.add_argument('--'+name, required=True)
    parser.add_argument('--root-review-path'); parser.add_argument('--root-review-sha256')
    parser.add_argument('--review-output'); parser.add_argument('--execute', action='store_true')
    args = vars(parser.parse_args()); command = args.pop('command'); review_output = args.pop('review_output')
    if command == 'review':
        args.pop('root_review_path'); args.pop('root_review_sha256'); args.pop('execute')
        require(review_output is not None, 'private_review_output_required')
        dest = Path(review_output); dest.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        write(dest.parent, dest.name, review_contract(**args)); result = {'task_count': 20}
    else:
        if command == 'audit': args.pop('execute')
        result = (run if command == 'run' else saved_audit)(**args)
    print(json.dumps({'status': 'reference_'+command+'_complete', 'model_calls': 0,
                      'formal_registration_performed': False}))


if __name__ == '__main__': main()
