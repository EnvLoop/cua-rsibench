"""Concrete guarded Desktop runtime using the existing common guest launcher.

One fresh class/source manifest serves Calc, Writer and Impress and all actor
roles. V31–V37 sources remain immutable; old diagnostics provide no credit.
"""
from __future__ import annotations
import inspect
from pathlib import Path
import textwrap
from types import FunctionType,SimpleNamespace
from . import common_native_guest_v31 as parent
from . import native_terminal_hit_diagnostic_v38 as terminal
from . import common_native_episode_v31 as episode

SCHEMA='cua-native-visible-surface-probe-v38'
SOURCE=Path(terminal.__file__)
EXTRA=('native_desktop_factory/native_terminal_hit_diagnostic_v38.py',
 'native_desktop_factory/terminal_owned_runtime.py','native_desktop_factory/native_hit_identity_diagnostic_v33.py',
 'native_desktop_factory/native_forward_owned_probe_v37.py','tests/test_native_desktop_terminal_hit_diagnostic_v38.py',
 'tests/test_native_desktop_terminal_owned_runtime.py')

def persist_native_facts(actor,value):
 ref=value.get('private_native_facts_file');expected=f'/tmp/envloop-native-terminal-v38-facts-{actor.native_sequence-1:06d}.private.jsonl'
 parent.require(type(ref) is dict and ref.get('path')==expected and ref.get('mode')==0o600 and ref.get('actor_access_authorized') is False,'Native facts source/sequence binding missing')
 raw=bytes(actor.sandbox.files.read(expected,format='bytes'))
 parent.require(len(raw)<=131072 and len(raw)==ref['bytes'] and parent.digest(raw)==ref['sha256'],'Native facts private readback differs')
 parent.put(actor.root,actor.out/f'native-facts-{actor.native_sequence-1:03d}.private.jsonl',raw)

def control_driver(factory,*,actor,identity,instruction,actor_deadline):
 parent.require(type(actor) is factory.actor_class and actor.native_manifest==factory.manifest,'Exact scoped terminal control actor required')
 original=episode.CommonNativeControlDriver.__init__
 bound=FunctionType(original.__code__,{**original.__globals__,'native':SimpleNamespace(CommonNativeModelGuest=factory.actor_class)},original.__name__,original.__defaults__,original.__closure__)
 driver=type('TerminalOwnedControlDriver',(episode.CommonNativeControlDriver,),{'__init__':bound})
 return driver(actor=actor,identity=identity,instruction=instruction,actor_deadline=actor_deadline)


def source_manifest(root=None):
 root=Path(root or Path(__file__).resolve().parents[1]);value=parent.source_manifest(root)
 hashes={**value['source_sha256s'],**{name:parent.digest((root/name).read_bytes()) for name in EXTRA}}
 return {**value,'schema':'cua-native-terminal-owned-runtime-source-v38','source_sha256s':hashes,
  'native_reader_schema':SCHEMA,'structural_containers_actionable':False,'old_results_reclassified':False}


def factory(*,manifest,source_root=None,qualification=None,independent_raw_auditor=None):
 def checked(value,root):
  parent.require(value==source_manifest(root),'Terminal runtime source changed');return value
 ns={**vars(parent),'PROBE_SOURCE':SOURCE,'PROBE_SCHEMA':SCHEMA,
  'PROBE_PATH':parent.REMOTE+'/native_terminal_hit_diagnostic_v38.py',
  'PEERS':(*parent.PEERS,'native_hit_identity_diagnostic_v33.py','native_forward_owned_probe_v37.py','native_terminal_hit_diagnostic_v38.py'),
  'checked_runtime_manifest':checked,'source_manifest':source_manifest,
  'reader':SimpleNamespace(PRIVATE_ERROR_PATH=terminal.PRIVATE_PATH)}
 def clone(fn):
  value=FunctionType(fn.__code__,ns,fn.__name__,fn.__defaults__,fn.__closure__);value.__kwdefaults__=fn.__kwdefaults__;return value
 source=textwrap.dedent(inspect.getsource(parent.CommonNativeModelGuest.native_probe))
 needle="+' --filename '+";parent.require(source.count(needle)==1,'Common probe command interface changed')
 source=source.replace(needle,"+' --guarded --facts-path '+shlex.quote(f'/tmp/envloop-native-terminal-v38-facts-{self.native_sequence:06d}.private.jsonl')+' --filename '+")
 audit=' # Preserve full raw stderr above.'
 parent.require(source.count(audit)==1,'Common raw evidence interface changed')
 ns['persist_native_facts']=persist_native_facts
 exec(compile(source.replace(audit," if value.get('status')=='observed':persist_native_facts(self,value)\n"+audit),__file__,'exec'),ns)
 guest=type('TerminalOwnedModelGuest',(parent.CommonNativeModelGuest,),{
  '__init__':clone(parent.CommonNativeModelGuest.__init__),'_bootstrap':clone(parent.CommonNativeModelGuest._bootstrap),
  'prepare':clone(parent.CommonNativeModelGuest.prepare),'native_probe':ns['native_probe']})
 ns['CommonNativeModelGuest']=guest
 constructor=type('TerminalOwnedGuestFactory',(parent.CommonGuestFactory,),{
  '__init__':clone(parent.CommonGuestFactory.__init__),'wrap_owned_guest':clone(parent.CommonGuestFactory.wrap_owned_guest),
  'create_guest':clone(parent.CommonGuestFactory.create_guest),'require_activation':clone(parent.CommonGuestFactory.require_activation),
  'actor_class':guest})
 return constructor(manifest=manifest,source_root=source_root,qualification=qualification,independent_raw_auditor=independent_raw_auditor)
