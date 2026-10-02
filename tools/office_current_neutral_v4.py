"""Reviewed TRAIN neutral control for the current Office source epoch.

Same V4 lifecycle, current TTL/absolute deadline/pump; zero model/paid calls.
"""
from pathlib import Path
from types import ModuleType,SimpleNamespace
import hashlib,sys
from tools import office_neutral_lifecycle_pilot_v4 as original
from tools.office_current_native_clock_v4 import CurrentOperationSpool
from tools.office_current_authority_v4 import current_sources
from tools.office_current_package_v4 import Package

EXPECTED_PILOT_SHA='65f0a9fcd058835141fe19e140c8ad71921702267f4356baf56a029de941e471'


def module():
 raw=Path(original.__file__).read_bytes()
 if hashlib.sha256(raw).hexdigest()!=EXPECTED_PILOT_SHA:raise ValueError('historical_v4_neutral_source_changed')
 source=raw.decode()
 before="  with client.open(package,attempt_id='neutral-one-use-v4') as active:\n"
 if source.count(before)!=1:raise ValueError('exact_current_neutral_clock_patch_changed')
 source=source.replace(before,before+'   actor_started=time.monotonic();active.actor.bind_actor_clock(actor_started,actor_started+720)\n')
 for before,after in [('operation-spool.private','native-operations.private'),('native-episode.private','native.private'),('source-admission.private.json','native-source-admission.private.json')]:source=source.replace(before,after)
 name='tools._office_current_neutral_v4';value=ModuleType(name);value.__file__=original.__file__;value.__package__='tools';sys.modules[name]=value
 exec(compile(source,'office-current-neutral-v4','exec'),value.__dict__)
 value.NativeOperationSpool=CurrentOperationSpool;value.V4_FILES=(*original.V4_FILES,'tools/office_current_cua_pump_v4.mjs')
 value.runtime=SimpleNamespace(**vars(original.runtime));value.runtime.Package=Package;value.source_hashes=current_sources
 return value

if __name__=='__main__':module().main()
