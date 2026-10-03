"""Uniform owned partial-boot interruption cleanup; old V14 remains frozen."""
from . import v066_neutral_telemetry_coldboot_v7 as _loader

_loader._load_frozen('gitlab_world/v066_uniform_task_runtime_v14.py',
                    '7bb7eea6732b060b3022eda7ebdb8c7063241526e2f31fcaf57049abdb0d239a', globals(), (
                        ('v14', 'v15', 8),
                        ('tests/test_gitlab_uniform_effective_wait_v15.py',
                         'tests/test_gitlab_uniform_effective_wait_v14.py', 1),
                        ('v066_uniform_reference_controls_v19', 'v066_uniform_reference_controls_v20', 1),
                        ('v066_neutral_telemetry_coldboot_v6', 'v066_neutral_telemetry_coldboot_v7', 1),
                    ))
from types import FunctionType
from . import v066_interrupted_reset_cleanup_v1 as _repair

# Rebind the repaired method into this epoch's globals. Keeping its ancestor
# globals would silently retain the old plan/source/neutral prerequisite.
_safe_reset = _repair.interruption_safe_reset()
TaskWorld.reset = FunctionType(_safe_reset.__code__, globals(), _safe_reset.__name__,
                              _safe_reset.__defaults__, _safe_reset.__closure__)
TaskWorld.reset.__kwdefaults__ = _safe_reset.__kwdefaults__
_ancestor_prepare = prepare
_ancestor_checked_plan = checked_plan


def _fresh_neutral(proof):
    require(proof.get('neutral_source_epoch') == cold.SCHEMA and
            proof.get('neutral_source_sha256s') == cold.source_hashes() and
            proof.get('neutral_cycles_verified') == 3 and
            proof.get('native_effective_wait_verified') is True and
            proof.get('effective_wait_seconds') == 60 and
            proof.get('old_neutral_v6_credit') == 0,
            'Fresh V7 three-cycle shared source neutral proof required')


def prepare(*, neutral_plan, neutral_permit, out):
    _fresh_neutral(cold.audit(plan=neutral_plan, permit=neutral_permit))
    return _ancestor_prepare(neutral_plan=neutral_plan, neutral_permit=neutral_permit, out=out)


def checked_plan(path):
    # The original checker refuses old schema/map before invoking any auditor.
    result = _ancestor_checked_plan(path)
    _fresh_neutral(cold.audit(plan=Path(result[0]['parent_neutral_plan']),
                             permit=Path(result[0]['parent_neutral_permit'])))
    return result


if __name__ == '__main__':
    main()
