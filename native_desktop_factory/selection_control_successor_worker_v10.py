"""Additive selection-aware executor on the unchanged v9 transport/runtime.

Both execution and read-only attempt auditing use the same newly frozen
constructor. Patched function references are process-local and restored; no
historical source file, intent, receipt or root is rewritten.
"""
from __future__ import annotations
import argparse
from contextlib import ExitStack,contextmanager
import json
from pathlib import Path
from unittest.mock import patch

from . import v066_post_enter_control_attempt_v9 as worker
from . import v066_post_enter_control_audit_v9 as audit
from . import selection_control_successor_epoch_v10 as epoch
from . import selection_control_scripts_v10 as scripts


@contextmanager
def context():
 with ExitStack() as stack:
  for module in [worker,audit]:
   stack.enter_context(patch.object(module,'epoch',epoch))
   stack.enter_context(patch.object(module,'actor_script',scripts.actor_script))
  yield


def run_trio(*,freeze_path:Path,permit_path:Path,enable_paid_controls:bool=False):
 if enable_paid_controls is not True:raise ValueError('Paid selection successor is disabled')
 # Metadata/input-layout preflight and exact current constructor happen before
 # inherited v9 run_trio can create its first consumed task/attempt intent.
 value=epoch.validate(freeze_path);row=epoch.next_row(value)
 epoch.require(row is not None,'All120 successor trios already consumed')
 epoch.checked_permit(freeze_path,permit_path,value,row)
 if row['split']=='selection':
  from . import admit
  inventory=json.loads(epoch.private(Path(value['candidate_root'])/'candidate-inventory.json'))
  full=next(r for r in inventory['tasks'] if r['task_id']==row['task_id'])
  directory,_baseline,oracle=admit._package(Path(value['candidate_root']),full)
  for attempt in ['positive','near-miss','cold-reset']:scripts.actor_script(directory,oracle,attempt)
 with context():return worker.run_trio(freeze_path=freeze_path,permit_path=permit_path,enable_paid_controls=True)


def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--freeze',type=Path,required=True);parser.add_argument('--permit',type=Path,required=True)
 parser.add_argument('--enable-paid-controls',action='store_true');args=parser.parse_args()
 print(json.dumps(run_trio(freeze_path=args.freeze,permit_path=args.permit,enable_paid_controls=args.enable_paid_controls),sort_keys=True))


if __name__=='__main__':main()
