"""Fresh shared source closure for the owned interrupted-reset amendment.

The V6 process-effective wait, strict V5 status decoder and native backend
are unchanged. Earlier neutral/task receipts supply zero current credit.
"""
from hashlib import sha256
from pathlib import Path


def _load_frozen(relative, expected, namespace, substitutions=()):
    """Execute only an exact local ancestor with counted source substitutions."""
    path = Path(__file__).resolve().parents[1] / relative
    if path.is_symlink() or not path.is_file():
        raise ValueError('gitlab_frozen_source_unsafe')
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != expected:
        raise ValueError('gitlab_frozen_source_changed')
    text = raw.decode()
    for before, after, count in substitutions:
        if text.count(before) != count:
            raise ValueError('gitlab_frozen_source_interface_changed')
        text = text.replace(before, after)
    # A wrapper CLI dispatches only after its successor gates are installed.
    guard = "if __name__=='__main__':main()"
    if text.count(guard) not in (1, 2):
        raise ValueError('gitlab_frozen_main_boundary_changed')
    text = text.replace(guard, '')
    exec(compile(text, namespace['__file__'], 'exec'), namespace)


_load_frozen('gitlab_world/v066_neutral_telemetry_coldboot_v6.py',
             '8aa6ed16c6af41f7c22fda4a99acb3bc60f3e9783a3f3aed31668d32f0483608', globals())
SCHEMA = 'envloop-gitlab-neutral-effective-svwait-coldboot-plan-v7'
SUCCESSOR_ROOTS = (
    'gitlab_world/v066_neutral_telemetry_coldboot_v6.py',
    'gitlab_world/v066_neutral_telemetry_coldboot_v7.py',
    'gitlab_world/v066_interrupted_reset_cleanup_v1.py',
    'gitlab_world/v066_uniform_task_runtime_v15.py',
    'gitlab_world/v066_uniform_model_workers_v15.py',
    'gitlab_world/v066_uniform_train_qualification_v15.py',
    'gitlab_world/v066_uniform_reference_controls_v20.py',
    'tests/test_gitlab_interrupted_reset_cleanup_v1.py',
    'tests/test_gitlab_interrupted_uniform_epoch_v15.py',
)
with patch.object(common_source, 'FILES', tuple(dict.fromkeys(common_source.FILES + SUCCESSOR_ROOTS))):
    SOURCE_FILES = tuple(dict.fromkeys(SOURCE_FILES + common_source.closed_source_files()))
_ancestor_audit = audit


def source_hashes():
    root = Path(__file__).resolve().parents[1]
    return {name: source.sha((root / name).read_bytes()) for name in SOURCE_FILES}


def audit(*, plan, permit):
    value = _ancestor_audit(plan=plan, permit=permit)
    doc, _, _ = checked_plan(plan)
    require(doc['source_sha256s'] == source_hashes(), 'Fresh V7 neutral shared closure required')
    return value | {
        'status': 'saved_three_neutral_v7_effective_wait_native_cycles_independently_replayed',
        'neutral_source_epoch': SCHEMA,
        'neutral_source_sha256s': doc['source_sha256s'],
        'old_neutral_v6_credit': 0,
    }


if __name__ == '__main__':
    main()
