"""Offline preparation of a versioned full-suite operational final replay.

This tool never builds a template, creates a sandbox, launches an evaluation,
or edits an original final plan/result. Each of four eligible logical slots
receives two remote-control-plane-v1 payloads of three frozen cases.
"""
import argparse
import io
import json
import os
from pathlib import Path
import re
import tarfile
import tempfile
import time
import uuid

from cursibench.cloud_launch import model_input
from cursibench.factory_campaign import digest, valid_scores
from cursibench.factory_final import make_plan, combine, verify_execution
from cursibench.factory_results import summarize
from run_cloud_chain_remote import source_closure, runtime_origin
from remote_cloud_worker import VERSION, MAX_BYTES, assert_no_credentials, safe_name, sha, write_json, unpack_payload, verify_materialized

ROOT = Path(__file__).resolve().parents[1]
AMENDMENT_VERSION = 'remote-final-full-suite-recovery-v1'
SLOTS = ('astra-base-repeat-1', 'astra-base-repeat-2', 'sol-selected-repeat-1', 'sol-selected-repeat-2')
PRESERVED_VALID = ('astra-selected-repeat-1', 'astra-selected-repeat-2')
ALLOWED_ERRORS = frozenset(('BuildException', 'TimeoutException', 'RemoteProtocolError', 'ConnectError'))
FIXED = {'agent_actions': 90, 'agent_timeout_seconds': 1500, 'temperature': 0, 'seed': 23,
         'output_tokens': 512, 'environment': 'journal', 'concurrency': 3, 'child_job_cap_seconds': 2700}
LEASE = 3600


def read(path):
    return json.loads(Path(path).read_text())


def file_sha(path):
    return sha(Path(path).read_bytes())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def tree_hashes(directory):
    hashes = {}
    for path in sorted(Path(directory).rglob('*')):
        require(not path.is_symlink(), 'evidence/task input contains a symlink')
        if path.is_file():
            hashes[path.relative_to(directory).as_posix()] = file_sha(path)
    return hashes


def eligible_faults(summary, raw_results, expected_tasks):
    """Only recorded infrastructure faults qualify; model/budget failures do not."""
    require(summary.get('status') == 'infrastructure_error' and summary.get('score') is None,
            'a scored or unfinished original slot is never eligible')
    rows = summary.get('tasks', [])
    names = [row.get('task') for row in rows]
    require(len(names) == len(set(names)) and set(names) == set(expected_tasks), 'original final task identities are incomplete')
    require(set(raw_results) == set(expected_tasks), 'raw original task evidence is incomplete')
    faults = []
    for row in rows:
        raw = raw_results[row['task']]
        exception = raw.get('exception_info')
        if row.get('score') is not None:
            require(type(row['score']) in (int, float) and row['score'] in (0, 1) and not row.get('error_type') and not exception,
                    'original scored row is inconsistent')
            require((raw.get('verifier_result') or {}).get('rewards', {}).get('reward') == row['score'] and
                    raw.get('verifier_environment_mode') == 'separate', 'original scored row lacks separate verifier evidence')
            continue
        error = row.get('error_type')
        require(error in ALLOWED_ERRORS and exception and exception.get('exception_type') == error,
                'original error is not an allowed recorded infrastructure fault')
        trace = exception.get('exception_traceback', '')
        require(not re.search(r'AgentTimeout|AgentExecutionTimeout|agent_timeout|model.?budget|action.?budget.{0,30}exceed', trace, re.I),
                'agent timeout or model-budget failure is not eligible')
        require(any(marker in trace.lower() for marker in ('e2b', 'connectrpc', 'httpx', 'httpcore')),
                'infrastructure classification lacks a provider/transport traceback')
        faults.append({'task': row['task'], 'error_type': error,
                       'agent_setup_present': raw.get('agent_setup') is not None,
                       'agent_execution_present': raw.get('agent_execution') is not None})
    require(bool(faults), 'no infrastructure-failed case in original slot')
    return faults


def inspect_slot(study, execution):
    label = execution['label']
    require(label in SLOTS, 'only the four declared infrastructure-invalid original slots are eligible')
    directory = study / 'final-executions' / label
    original_plan = read(directory / 'plan.json')
    state = read(study / (execution['researcher'] + '-campaign.json'))
    require(digest(state['protocol']) == state['protocol_hash'], 'campaign protocol hash mismatch')
    expected_plan = make_plan(ROOT, study, state, execution['role'], execution['repetition'])
    require(original_plan == expected_plan, 'immutable original final plan or selected checkpoint changed')
    require(execution['checkpoint_sha256'] == original_plan['binding']['checkpoint_sha256'], 'comparison checkpoint binding changed')
    require(len(original_plan['chunks']) == 2 and all(len(tasks) == 3 for tasks in original_plan['chunks'].values()),
            'full-suite replay requires the exact two frozen three-task chunks')
    require(original_plan['sampling'] == {'max_tokens': 512, 'temperature': 0, 'seed': 23}, 'frozen sampling settings differ')
    summaries, raw_results, raw_hashes, wrappers = [], {}, {}, {}
    for chunk, tasks in sorted(original_plan['chunks'].items()):
        child = directory / chunk
        verify_execution(child, original_plan)  # validates identity even if the original execution was invalid
        summary = summarize(child, tasks)
        require(summary['status'] in ('scored', 'infrastructure_error'), 'original chunk is still running')
        summaries.append(summary)
        wrappers[chunk] = file_sha(child / 'result.json')
        for path in (child / 'harbor/checkpoint-browser').glob('*/result.json'):
            raw = read(path)
            require(raw['task_name'] not in raw_results, 'duplicate raw original final result')
            raw_results[raw['task_name']] = raw
            raw_hashes[raw['task_name']] = file_sha(path)
    summary = read(directory / 'summary.json')
    require(combine(summaries, state['protocol']['final_tasks']) == summary, 'original summary differs from retained task evidence')
    registered = [row for row in state['final_results'] if row['label'] == label]
    require(len(registered) == 1 and registered[0]['evaluation'] == summary, 'original registry outcome differs from evidence')
    faults = eligible_faults(summary, raw_results, state['protocol']['final_tasks'])
    training = original_plan['binding']['training_manifest']
    selected = model_input(training, base=original_plan['binding']['candidate'] == 'base', model=original_plan['binding']['model'])
    require(digest(selected['checkpoint']) == original_plan['binding']['checkpoint_sha256'], 'selected checkpoint input changed')
    return {'label': label, 'execution': execution, 'plan': original_plan, 'selected': selected,
            'proof': {'logical_comparison_slot': label, 'researcher': execution['researcher'], 'role': execution['role'],
                      'repetition': execution['repetition'], 'original_plan_sha256': file_sha(directory / 'plan.json'),
                      'original_summary_sha256': file_sha(directory / 'summary.json'), 'original_result_hashes': raw_hashes,
                      'original_wrapper_hashes': wrappers, 'original_status': summary['status'], 'original_score': None,
                      'recorded_infrastructure_faults': faults, 'checkpoint_sha256': original_plan['binding']['checkpoint_sha256'],
                      'candidate': original_plan['binding']['candidate'], 'protocol_hash': state['protocol_hash'],
                      'selection_sha256': digest(state['final_selection']), 'task_package_hashes': original_plan['task_package_hashes'],
                      'runtime_hashes': original_plan['runtime_hashes'], 'chunks': original_plan['chunks']}}


def ready_controller(template_directory, runtime):
    plan = read(template_directory / 'plan.json')
    built = read(template_directory / 'build-result.json')
    require(built.get('state') == 'built_ready' and built.get('template') == plan.get('template'),
            'an existing independently READY controller template is required')
    require(plan.get('operational_version') == VERSION and file_sha(template_directory / 'runtime-lock.txt') == plan['requirements_sha256'],
            'controller template version or dependency lock changed')
    for key in ('packages', 'package_sources', 'python_required', 'platform_destination'):
        require(plan['runtime'][key] == runtime[key], 'controller dependency origin differs: ' + key)
    return {'template': plan['template'], 'state': 'built_ready',
            'plan_sha256': file_sha(template_directory / 'plan.json'),
            'build_result_sha256': file_sha(template_directory / 'build-result.json'),
            'requirements_sha256': plan['requirements_sha256']}


def prior_build_recoveries(study):
    records = []
    for label in ('astra-base-repeat-1', 'sol-selected-repeat-1'):
        directory = study / 'final-recoveries' / label
        require(directory.is_dir() and not (directory / 'summary.json').exists(), 'build-only recovery no longer matches the incomplete supersession scope')
        require(not (directory / 'SUPERSEDED.json').exists(), 'build-only recovery already has a supersession declaration')
        old_plan = read(directory / 'plan.json')
        intended = {case['task'] for case in old_plan['cases']}
        attempted = []
        for task in sorted(path for path in directory.iterdir() if path.is_dir()):
            require(task.name in intended, 'unexpected prior recovery case')
            wrapper = read(task / 'result.json')
            require(wrapper.get('error_type') == 'TimeoutException' and wrapper.get('proxy_destroyed') is True and
                    not wrapper.get('proxy_ready') and not (task / 'harbor/checkpoint-browser/result.json').exists(),
                    'prior build-only attempt was not the recorded pre-Harbor bootstrap failure')
            require(not list(task.glob('harbor/checkpoint-browser/*/agent/trace.json')), 'prior bootstrap recovery contains actor work')
            process = read(directory / (task.name + '-execution-process.json'))
            require(process.get('finished_at') and process.get('return_code') == 0, 'prior recovery child is not finished')
            attempted.append(task.name)
        require(bool(attempted), 'expected prior bootstrap failure is absent')
        records.append({'label': label, 'path': str(directory.relative_to(ROOT)),
                        'preserved_file_hashes': tree_hashes(directory), 'attempted_cases': attempted,
                        'attempted_outcome': 'unscored pre-Harbor TimeoutException',
                        'unattempted_cases_canceled': sorted(intended - set(attempted)),
                        'replacement_policy_kind': 'full_suite_replay'})
    return records


def prepare_chunk(study, slot, chunk, out, runtime, controller, amendment_sha):
    names = slot['plan']['chunks'][chunk]
    require(len(names) == 3, 'remote child must contain all three tasks in its original chunk')
    mapping = {path.relative_to(ROOT).as_posix(): path for path in source_closure(ROOT)}
    mapping['tools/run_cloud_chain.py'] = ROOT / 'tools/run_cloud_chain.py'
    for name in names:
        package = study / 'sealed-final' / chunk / name
        for path in sorted(package.rglob('*')):
            require(not path.is_symlink(), 'frozen final package contains a symlink')
            if path.is_file():
                mapping['tasks/' + name + '/' + path.relative_to(package).as_posix()] = path
    training = slot['plan']['binding']['training_manifest']
    if training:
        mapping['inputs/training.json'] = Path(training)
    blobs, files = {}, {}
    for name, path in mapping.items():
        safe_name(name)
        data = path.read_bytes()
        assert_no_credentials(data, [os.environ.get(name) for name in ('E2B_API_KEY', 'TINKER_API_KEY', 'OPENAI_API_KEY')])
        key = sha(data)
        blobs[key] = data
        files[name] = {'sha256': key, 'bytes': len(data), 'mode': path.stat().st_mode & 0o777,
                       'origin': path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else 'selected-training-manifest'}
    worker = (ROOT / 'tools/remote_cloud_worker.py').read_bytes()
    manifest = {'operational_version': VERSION, 'job_id': uuid.uuid4().hex,
                'campaign': slot['execution']['researcher'], 'attempt_id': slot['plan']['binding']['candidate'],
                'purpose': 'one entire fresh final suite for an infrastructure-invalid original logical comparison slot',
                'execution_kind': 'frozen-final-full-suite-replay', 'admission_kind': 'frozen_final_full_suite_replay',
                'protocol_hash': slot['proof']['protocol_hash'], 'task_names': names, 'files': files, 'runtime': runtime,
                'model': {'name': slot['selected']['model'], 'kind': slot['selected']['inference_kind'],
                          'checkpoint_sha256': slot['proof']['checkpoint_sha256'],
                          'prior_execution_wrapper_sha256': slot['proof']['original_wrapper_hashes'][chunk]},
                'worker_sha256': sha(worker), 'fixed': FIXED, 'orchestrator_lease_seconds': LEASE,
                'final_recovery': {'amendment_version': AMENDMENT_VERSION, 'amendment_sha256': amendment_sha,
                                   'logical_comparison_slot': slot['label'], 'chunk': chunk,
                                   'policy_kind': 'full_suite_replay', 'original_rows_reused': False,
                                   'new_independent_repetition': False, 'new_research_seed': False,
                                   'original_plan_sha256': slot['proof']['original_plan_sha256'],
                                   'original_summary_sha256': slot['proof']['original_summary_sha256'],
                                   'task_package_hashes': {name: slot['proof']['task_package_hashes'][name] for name in names}},
                'controller_template': controller,
                'credentials': {'orchestrator': ['E2B_API_KEY', 'TINKER_API_KEY'],
                                'proxy': ['TINKER_API_KEY', 'ephemeral proxy bearer'],
                                'actor': [], 'verifier': [], 'research_workspace': []}}
    encoded = json.dumps(manifest, sort_keys=True).encode()
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:gz') as archive:
        for name, data in [('manifest.json', encoded), *[('blobs/' + key, value) for key, value in sorted(blobs.items())]]:
            entry = tarfile.TarInfo(name)
            entry.mode, entry.size = 0o600, len(data)
            archive.addfile(entry, io.BytesIO(data))
    payload = stream.getvalue()
    require(len(payload) <= MAX_BYTES and sum(map(len, blobs.values())) <= MAX_BYTES, 'bounded remote payload size exceeded')
    with tempfile.TemporaryDirectory(prefix='cua-final-verify-') as temporary:
        materialized = Path(temporary)
        restored = unpack_payload(payload, materialized, sha(encoded))
        verify_materialized(materialized, restored)
        require(restored == manifest, 'payload manifest differs after round-trip')
    out.mkdir(parents=True, exist_ok=False)
    out.chmod(0o700)
    (out / 'payload.tar.gz').write_bytes(payload)
    (out / 'payload.tar.gz').chmod(0o600)
    (out / 'worker.py').write_bytes(worker)
    write_json(out / 'manifest.json', manifest)
    plan = {'operational_version': VERSION, 'job_id': manifest['job_id'],
            'admission_kind': manifest['admission_kind'], 'prepared_at': time.time(),
            'payload_sha256': sha(payload), 'manifest_sha256': sha(encoded), 'worker_sha256': sha(worker),
            'payload_bytes': len(payload), 'unique_blobs': len(blobs), 'materialized_files': len(files),
            'task_names': names, 'credential_values_present': False, 'orchestrator_lease_seconds': LEASE,
            'runtime_platform_change': 'Mac control plane to separate trusted Linux E2B control plane',
            'final_recovery': manifest['final_recovery'], 'controller_template': controller['template'],
            'cloud_execution_authorized_by_this_preparation': False}
    write_json(out / 'plan.json', plan)
    return plan


def prepare(study, out, template_directory, check_only=False):
    study, out, template_directory = map(lambda path: Path(path).resolve(), (study, out, template_directory))
    require(study == (ROOT / 'work/factory-study-02').resolve(), 'this amendment is restricted to the original study')
    require(not out.exists() and ROOT in out.parents, 'new output directory inside this checkout is required')
    comparison = read(study / 'final-comparison.json')
    by_label = {row['label']: row for row in comparison['executions']}
    require(set(by_label) == set(SLOTS) | set(PRESERVED_VALID), 'original comparison slot set changed')
    slots = [inspect_slot(study, by_label[label]) for label in SLOTS]
    preserved = {}
    for label in PRESERVED_VALID:
        summary = read(study / 'final-executions' / label / 'summary.json')
        require(valid_scores(summary, slots[0]['plan']['task_package_hashes']) is not None,
                'Astra original slot is not the expected complete scored execution')
        preserved[label] = {'summary_sha256': file_sha(study / 'final-executions' / label / 'summary.json'),
                            'status': 'scored', 'replay_permitted': False}
    runtime = runtime_origin()
    controller = ready_controller(template_directory, runtime)
    prior = prior_build_recoveries(study)
    declaration = {'amendment_version': AMENDMENT_VERSION, 'operational_version': VERSION,
                   'prepared_at': time.time(), 'policy_kind': 'full_suite_replay', 'original_rows_reused': False,
                   'new_independent_repetition': False, 'new_research_seed': False, 'original_outcomes_preserved': True,
                   'one_fresh_suite_per_logical_slot': True, 'scored_original_slots_never_replayed': preserved,
                   'eligible_original_error_types': sorted(ALLOWED_ERRORS),
                   'excluded_failures': ['scored model/task failure', 'AgentTimeout', 'model budget failure', 'unfinished execution'],
                   'runtime_platform_change': 'Mac control plane to separate trusted Linux E2B control plane',
                   'controller_template': controller, 'fixed': FIXED,
                   'reason': 'Recorded original environment/transport failures and failed Mac-side build-only proxy bootstrap; move orchestration to the READY remote controller without modifying the frozen actor, tasks, verifier, checkpoint, or sampling.',
                   'slots': [slot['proof'] for slot in slots], 'supersedes_build_only_recoveries': prior,
                   'execution_admission': 'Offline preparation only; root must authorize one pilot final slot before broader execution.',
                   'schema_proposal': {'evaluation': 'retain original six-task summary unchanged',
                                       'recovered_evaluation': 'independently audited summary of all six fresh tasks in both replay chunks; never mix original rows',
                                       'recovery': {'policy_kind': 'full_suite_replay', 'original_rows_reused': False,
                                                    'new_independent_repetition': False, 'new_research_seed': False,
                                                    'amendment_sha256': 'SHA256 of this declaration',
                                                    'chunk_plan_sha256': 'map of both frozen remote-v1 chunk plans',
                                                    'runtime_platform_change': 'Mac to trusted Linux E2B controller'}}}
    if check_only:
        return {'state': 'offline_checks_passed', 'eligible_slots': list(SLOTS),
                'preserved_scored_slots': list(PRESERVED_VALID), 'controller_template': controller['template'],
                'fresh_tasks_per_slot': 6, 'chunks_per_slot': 2, 'cloud_calls': 0}
    out.mkdir(parents=True, exist_ok=False)
    out.chmod(0o700)
    write_json(out / 'amendment.json', declaration)
    amendment_sha = file_sha(out / 'amendment.json')
    plans = {}
    for slot in slots:
        children = {}
        for chunk in sorted(slot['plan']['chunks']):
            prepare_chunk(study, slot, chunk, out / slot['label'] / chunk, runtime, controller, amendment_sha)
            children[chunk] = file_sha(out / slot['label'] / chunk / 'plan.json')
        plan = dict(slot['proof'], amendment_version=AMENDMENT_VERSION, amendment_sha256=amendment_sha,
                    policy_kind='full_suite_replay', original_rows_reused=False, new_independent_repetition=False,
                    new_research_seed=False, child_plan_sha256=children, complete_summary_requires_all_six_fresh_tasks=True,
                    checkpoint_changed=False, tasks_changed=False, sampling_changed=False)
        write_json(out / slot['label'] / 'plan.json', plan)
        plans[slot['label']] = file_sha(out / slot['label'] / 'plan.json')
    # No original file is edited. The new marker explicitly closes the old path.
    for old in prior:
        directory = ROOT / old['path']
        require(tree_hashes(directory) == old['preserved_file_hashes'], 'old recovery evidence changed during preparation')
        write_json(directory / 'SUPERSEDED.json', {'superseded_at': time.time(), 'superseded_by': str(out.relative_to(ROOT)),
                   'amendment_sha256': amendment_sha, 'replacement_policy_kind': 'full_suite_replay',
                   'original_artifacts_preserved': True, 'further_build_only_execution_permitted': False,
                   'unattempted_cases_canceled': old['unattempted_cases_canceled'],
                   'reason': 'A separate frozen full-suite remote amendment replaces this incomplete build-only path; original bootstrap failures remain unscored.'})
    write_json(out / 'plan.json', {'amendment_version': AMENDMENT_VERSION, 'amendment_sha256': amendment_sha,
               'slot_plan_sha256': plans, 'prepared_at': time.time(), 'offline_only': True, 'cloud_calls': 0,
               'prior_recoveries_explicitly_superseded': True, 'controller_template': controller['template']})
    return {'state': 'prepared_offline', 'amendment_version': AMENDMENT_VERSION,
            'eligible_slots': list(SLOTS), 'remote_payloads': 8, 'fresh_tasks_per_slot': 6,
            'scored_original_slots_replayed': 0, 'cloud_calls': 0, 'amendment_sha256': amendment_sha,
            'controller_template': controller['template']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study', default=str(ROOT / 'work/factory-study-02'))
    parser.add_argument('--out', default=str(ROOT / 'work/factory-study-02/final-remote-recovery-v1'))
    parser.add_argument('--controller-template-dir', default=str(ROOT / 'work/remote-controller-template-01'))
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    print(json.dumps(prepare(args.study, args.out, args.controller_template_dir, args.check_only), indent=2))
