"""Offline checks for collected remote runs and full-suite final replays."""
import json
from pathlib import Path

from cursibench.factory_campaign import digest
from remote_cloud_worker import read_archive, sha
from run_cloud_chain_remote import checked_inputs, verified_evidence


def read(path):
    return json.loads(Path(path).read_text())


def file_sha(path):
    return sha(Path(path).read_bytes())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit_remote(directory, names, checkpoint_sha256, final_plan=None):
    """Recompute hashes from payload/archive and extracted evidence; no cloud calls."""
    directory = Path(directory)
    plan = checked_inputs(directory)
    payload = read_archive((directory / 'payload.tar.gz').read_bytes())
    encoded = payload['manifest.json']
    require(sha(encoded) == plan['manifest_sha256'], 'remote payload manifest changed')
    manifest = json.loads(encoded)
    require(manifest == read(directory / 'manifest.json'), 'local remote manifest changed')
    require(manifest['job_id'] == plan['job_id'], 'remote job identity mismatch')
    require(set(manifest['task_names']) == set(names) and len(manifest['task_names']) == len(names), 'remote task identities differ')
    require(manifest['model']['checkpoint_sha256'] == checkpoint_sha256, 'remote checkpoint binding differs')
    expected_files = {'manifest.json'} | {'blobs/' + row['sha256'] for row in manifest['files'].values()}
    require(set(payload) == expected_files, 'remote payload file set differs')
    for row in manifest['files'].values():
        blob = payload['blobs/' + row['sha256']]
        require(sha(blob) == row['sha256'] and len(blob) == row['bytes'], 'remote input blob changed')
    if final_plan:
        for name in names:
            prefix = 'tasks/' + name + '/'
            hashes = {key[len(prefix):]: row['sha256'] for key, row in manifest['files'].items() if key.startswith(prefix)}
            require(digest(hashes) == final_plan['task_package_hashes'][name], 'remote sealed task package differs')
        for name, expected in final_plan['runtime_hashes'].items():
            if name in manifest['files']:
                require(manifest['files'][name]['sha256'] == expected, 'remote frozen runtime differs')
    completion = read(directory / 'remote-completion.json')
    lifecycle = read(directory / 'lifecycle.json')
    require(completion.get('complete') is True and completion.get('evaluation_dispatched') is True, 'remote evaluation incomplete')
    require(all(completion[key] == plan[key] for key in ('payload_sha256', 'manifest_sha256')), 'remote completion belongs to another payload')
    require(lifecycle.get('collected') is True and lifecycle.get('orchestrator_destroyed') is True, 'remote collection or cleanup incomplete')
    require(lifecycle['job_id'] == plan['job_id'] and lifecycle['archive_sha256'] == completion['archive_sha256'], 'remote lifecycle differs')
    runtime = completion['runtime']
    require(runtime['platform'] == 'linux' and runtime['python'].startswith('3.12.'), 'unexpected remote platform')
    require(runtime['packages'] == manifest['runtime']['packages'], 'remote package versions differ')
    require(runtime['package_source_hashes'] == {key: row['sha256'] for key, row in manifest['runtime']['package_sources'].items()}, 'remote installed source hashes differ')
    _, index = verified_evidence((directory / 'evidence.tar.gz').read_bytes(), completion)
    evidence = directory / 'evaluation'
    actual_files = {str(p.relative_to(evidence)) for p in evidence.rglob('*') if p.is_file()}
    extras = actual_files - set(index['files'])
    require(set(index['files']) <= actual_files and extras <= {'summary.json'}, 'extracted remote evidence file set differs')
    if extras:
        from cursibench.factory_results import summarize
        require(read(evidence / 'summary.json') == summarize(evidence, names), 'derived remote summary differs from archived results')
    for name, row in index['files'].items():
        path = evidence / name
        require(not path.is_symlink() and file_sha(path) == row['sha256'], 'extracted remote evidence changed')
    wrapper = read(evidence / 'result.json')
    require(digest(wrapper.get('training_checkpoint')) == checkpoint_sha256, 'executed remote checkpoint differs')
    require(wrapper.get('training_model') == manifest['model']['name'], 'executed remote student differs')
    require(wrapper.get('proxy_destroyed') is True, 'remote proxy cleanup incomplete')
    admission = manifest.get('admission_kind')
    if admission is None and manifest['model'].get('prior_execution_wrapper_sha256'):
        admission = 'selection_recovery'
    require(admission is not None, 'remote admission kind missing')
    return {'operational_version': plan['operational_version'], 'admission_kind': admission,
            'plan_sha256': file_sha(directory / 'plan.json'), 'payload_sha256': plan['payload_sha256'],
            'archive_sha256': completion['archive_sha256'], 'evidence_files': len(index['files']),
            'started_at': completion['started_at'], 'controller_platform': runtime['platform'],
            'controller_python': runtime['python'].split()[0], 'runtime_and_member_hashes_verified': True,
            'proxy_destroyed': True, 'orchestrator_destroyed': True}


def audit_full_suite_recoveries(study, executions, evaluation):
    from cursibench.factory_final import combine, verify_execution
    from prepare_remote_final_recovery import inspect_slot

    study = Path(study)
    root = study / 'final-remote-recovery-v1'
    if not root.exists():
        return set(), True
    amendment = read(root / 'amendment.json')
    master = read(root / 'plan.json')
    amendment_sha = file_sha(root / 'amendment.json')
    require(master['amendment_sha256'] == amendment_sha, 'final amendment changed')
    require(amendment['policy_kind'] == 'full_suite_replay' and amendment['original_rows_reused'] is False, 'invalid full-suite policy')
    lookup = {row['label']: row for row in executions}
    comparison = {row['label']: row for row in read(study / 'final-comparison.json')['executions']}
    declarations = {row['logical_comparison_slot']: row for row in amendment['slots']}
    require(set(declarations) == set(master['slot_plan_sha256']), 'declared recovery slot set differs')
    for label, preserved in amendment['scored_original_slots_never_replayed'].items():
        require(file_sha(study / 'final-executions' / label / 'summary.json') == preserved['summary_sha256'], 'valid original final changed')
        require(not (root / label).exists(), 'scored original slot was replayed')
    superseded = set()
    for old in amendment['supersedes_build_only_recoveries']:
        path = study / 'final-recoveries' / old['label']
        marker = read(path / 'SUPERSEDED.json')
        require(marker['amendment_sha256'] == amendment_sha and marker['further_build_only_execution_permitted'] is False, 'invalid recovery supersession')
        require(marker['unattempted_cases_canceled'] == old['unattempted_cases_canceled'], 'superseded retry scope changed')
        current = {str(p.relative_to(path)): file_sha(p) for p in path.rglob('*') if p.is_file() and p.name != 'SUPERSEDED.json'}
        require(current == old['preserved_file_hashes'], 'superseded original bootstrap evidence changed')
        superseded.add(old['label'])
    finished = True
    for label, expected_sha in master['slot_plan_sha256'].items():
        directory = root / label
        require(file_sha(directory / 'plan.json') == expected_sha, 'full-suite slot plan changed')
        declaration = read(directory / 'plan.json')
        slot = inspect_slot(study, comparison[label])
        require(slot['proof'] == declarations[label], 'recovery original evidence changed')
        require(declaration['amendment_sha256'] == amendment_sha, 'slot binds another amendment')
        for chunk, expected in declaration['child_plan_sha256'].items():
            require(file_sha(directory / chunk / 'plan.json') == expected, 'recovery child plan changed')
        if not (directory / 'summary.json').exists():
            finished = False
            continue
        require((directory / 'recovery-receipt.json').exists(), 'completed replay lacks receipt')
        receipt = read(directory / 'recovery-receipt.json')
        for key in ('amendment_sha256', 'original_plan_sha256', 'original_summary_sha256', 'checkpoint_sha256', 'child_plan_sha256'):
            require(receipt[key] == declaration[key], 'recovery receipt binding differs')
        require(receipt['summary_sha256'] == file_sha(directory / 'summary.json') and receipt['slot_plan_sha256'] == expected_sha, 'recovery receipt hash differs')
        require(receipt['started_at'] >= lookup[label]['started_at'], 'replay predates original')
        pieces, proofs = [], {}
        for chunk, names in slot['plan']['chunks'].items():
            child = directory / chunk
            proof = audit_remote(child, names, declaration['checkpoint_sha256'], slot['plan'])
            manifest = read(child / 'manifest.json')
            binding = manifest['final_recovery']
            require(binding['amendment_sha256'] == amendment_sha and binding['logical_comparison_slot'] == label and binding['chunk'] == chunk, 'remote replay scope differs')
            require(proof['started_at'] >= receipt['started_at'], 'remote replay predates declaration')
            ev = evaluation(child / 'evaluation', names)
            if not verify_execution(child / 'evaluation', slot['plan']):
                ev.update(status='infrastructure_error', score=None)
            pieces.append(ev)
            proofs[chunk] = proof
        combined = combine(pieces, lookup[label]['evaluation']['expected_tasks'])
        require(combined == read(directory / 'summary.json'), 'fresh final summary differs from six fresh results')
        lookup[label]['recovered_evaluation'] = combined
        lookup[label]['recovery'] = {'policy_kind': 'full_suite_replay', 'original_rows_reused': False,
            'new_independent_repetition': False, 'new_research_seed': False, 'logical_comparison_slot': label,
            'retried_tasks': combined['expected_tasks'], 'amendment_sha256': amendment_sha,
            'chunk_plan_sha256': declaration['child_plan_sha256'], 'runtime_platform_change': amendment['runtime_platform_change'],
            'started_at': receipt['started_at'], 'proof': proofs}
    return superseded, finished
