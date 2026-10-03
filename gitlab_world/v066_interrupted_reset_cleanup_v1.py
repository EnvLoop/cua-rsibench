"""Clean an explicitly owned partial boot when a reset is interrupted.

This component is not a ratified task runtime or a model qualification. Its
integration requires a fresh shared source binding for every actor role.
"""
import hashlib
import inspect
import textwrap
from pathlib import Path
from . import v066_uniform_task_runtime_v14 as original

PARENT_SHA = '7bb7eea6732b060b3022eda7ebdb8c7063241526e2f31fcaf57049abdb0d239a'


def interruption_safe_reset():
    raw = Path(original.__file__).read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError('Frozen V14 task runtime changed')
    source = textwrap.dedent(inspect.getsource(original.TaskWorld.reset))
    before = ' except Exception:\n'
    if source.count(before) != 1:
        raise ValueError('Original partial-boot cleanup boundary changed')
    namespace = dict(original.TaskWorld.reset.__globals__)
    exec(compile(source.replace(before, ' except BaseException:\n'),
                 __file__, 'exec'), namespace)
    return namespace['reset']


class InterruptionSafeTaskWorld(original.TaskWorld):
    reset = interruption_safe_reset()
