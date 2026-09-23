"""Read-only provenance guards for selection packages and factory identities.

These checks are separate from the pinned execution runtime so an audit can be
strengthened without changing a running final evaluation's execution plan.
"""
from pathlib import Path

from .factory_final import package_hash, read, sha, validate_exported_runtime
from .gui_contract import VERSION


def validate_selection_packages(root, study, state):
    """Validate the exact selection task set against its frozen manifest.

    ``state`` is a CampaignRegistry snapshot. This function requires no frozen
    final selection and performs no writes. It returns package and case hashes
    keyed by the task identities used in the campaign protocol.
    """
    root, study = Path(root), Path(study)
    protocol = state['protocol']
    manifest_path = study / 'manifest.json'
    manifest_hash = sha(manifest_path)
    if manifest_hash != protocol['selection_manifest_sha256']:
        raise ValueError('selection manifest changed')
    manifest = read(manifest_path)
    tasks = protocol.get('selection_tasks')
    if (not isinstance(tasks, list) or not tasks
            or any(not isinstance(task, str) or not task or task in ('.', '..')
                   or '/' in task or '\\' in task for task in tasks)
            or len(tasks) != len(set(tasks))):
        raise ValueError('invalid selection task identities')

    expected_ids = {'factory-' + task: task for task in tasks}
    cases = manifest.get('cases', [])
    if (not isinstance(cases, list)
            or any(not isinstance(row, dict) or not isinstance(row.get('id'), str)
                   for row in cases)):
        raise ValueError('invalid selection manifest cases')
    case_ids = [row['id'] for row in cases]
    if len(case_ids) != len(set(case_ids)) or set(case_ids) != set(expected_ids):
        raise ValueError('selection manifest task identities differ from protocol')
    if manifest.get('evaluation', {}).get('task_count') != len(tasks):
        raise ValueError('selection manifest task count differs from protocol')

    selection = study / 'selection'
    if not selection.is_dir():
        raise ValueError('selection packages are missing')
    directories = {path.name for path in selection.iterdir() if path.is_dir()}
    package_configs = {str(path.relative_to(selection)) for path in selection.rglob('task.toml')}
    if directories != set(tasks) or package_configs != {task + '/task.toml' for task in tasks}:
        raise ValueError('selection package task identities differ from protocol')

    packages, hashes = {}, {}
    for row in cases:
        task = expected_ids[row['id']]
        path = selection / task
        scenario = read(path / 'environment/scenario.json')
        targets = read(path / 'tests/targets.json')
        contract = read(path / 'contract.json')
        if 'targets' in scenario or contract.get('contract') != VERSION:
            raise ValueError('selection package actor/verifier contract changed: ' + task)
        if (scenario.get('id') != row['id']
                or scenario.get('kind') != 'factory-' + row.get('family', '')
                or row.get('target_count') != len(targets)):
            raise ValueError('selection package identity differs from manifest: ' + task)
        # package_hash validates the reconstructed case (including hidden targets),
        # instruction, contract hash, and both selection-partition declarations.
        packages[task] = package_hash(path, row['hash'], 'selection')
        validate_exported_runtime(path, root)
        hashes[task] = row['hash']
    return {'selection_manifest_sha256': manifest_hash,
            'task_package_hashes': packages, 'case_hashes': hashes}


def verify_factory_identity(factory, expected_researcher, expected_teacher='gpt-5.6-sol'):
    """Check a completed factory's requested models and its saved spec copy.

    The returned values attest to recorded request identifiers only; they do
    not independently establish which weights the provider actually served.
    """
    if not all(isinstance(model, str) and model for model in (expected_researcher, expected_teacher)):
        raise ValueError('explicit researcher and teacher identities required')
    factory = Path(factory)
    spec_path = factory / 'spec.json'
    spec = read(spec_path)
    if not isinstance(spec, dict):
        raise ValueError('factory specification must be an object')
    if spec.get('researcher') != expected_researcher or spec.get('teacher') != expected_teacher:
        raise ValueError('factory researcher or fixed teacher identity mismatch')
    result = read(factory / 'result.json')
    if not isinstance(result, dict) or result.get('spec') != spec:
        raise ValueError('factory result specification differs from saved specification')
    return {'researcher': expected_researcher, 'teacher': expected_teacher,
            'spec_sha256': sha(spec_path)}
