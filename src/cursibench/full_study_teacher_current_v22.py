"""Pinned legacy teacher collection with authentic current-budget reset hook.

No fake finish or teacher turn is inserted. A verified expired episode may
create its one distinct reset; it remains ineligible for successful SFT data.
The old collector bytes and previously collected evidence are untouched.
"""
from pathlib import Path
import hashlib
import sys
from types import ModuleType

PIN='b5a6b434a03e1079a7db28982dc482527c0893aa809892d848daaa20cd0952fc'
path=Path(__file__).with_name('full_study_teacher_adapter_v1.py');raw=path.read_bytes()
if hashlib.sha256(raw).hexdigest()!=PIN:raise ValueError('immutable_teacher_collector_source_changed')
source=raw.decode();before="""                       len(e2b_attempt_ids) == 1 and bool(turns) and
                       turns[-1]['action']['type'] == 'finish')) and"""
after="""                       len(e2b_attempt_ids) == 1 and
                       ((bool(turns) and turns[-1]['action']['type'] == 'finish') or
                        (callable(getattr(cell_worker,'authorize_actual_budget_reset',None)) and
                         cell_worker.authorize_actual_budget_reset(task=task,episode_dir=episode_dir) is True)))) and"""
if source.count(before)!=1:raise ValueError('teacher_reset_hook_not_exactly_once')
source=source.replace(before,after)
name='cursibench._current_teacher_collector_v22';module=ModuleType(name);module.__package__='cursibench';module.__file__=str(path);sys.modules[name]=module
try:exec(compile(source,name,'exec'),module.__dict__)
except BaseException:sys.modules.pop(name,None);raise
collect_train_batch=module.collect_train_batch
