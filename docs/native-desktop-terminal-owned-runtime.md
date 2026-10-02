# Scoped owned Desktop runtime

`native_desktop_factory.terminal_owned_runtime` provides one generated guest
class for Calc, Writer, Impress and all seven existing actor roles. It reuses
the common V31 bootstrap, original document/profile setup, semantic guard,
episode/scorer/reset and owned cleanup. V31–V37 sources remain unchanged.

The scoped V38 reader addresses actual retained failures. Native structural
nodes with children are nonactionable inventory. An actor's physical hit still
requires the original owned, current, safe zero-child leaf proof. Every accepted
ownership path reopens exact native bus/object identities from the owned root.
If native `get_index_in_parent()` disagrees and its reverse parent is a different
owned-process native identity, the current forward slot must reopen the same
child twice. An unchanged parent with a wrong index, changed slot, foreign
process or stale state remains a rejection. Repeated inventory identities and
node-budget cutoffs are separately recorded after ownership is reopened.

Production diagnostics retain bounded samples, exact counts and a hash chain;
sampling does not skip native predicates or authorize actions. Each repeated
probe uses a new exclusive sequence-bound private journal. The host independently
reads it and checks path, byte count, mode and SHA before retaining it. Full raw
native command outputs and screenshots remain private. The control driver binds
the factory's exact generated class and dispatches through the unchanged semantic
observation/guard/native-input body.

The installed isolated runtime is `work/native-desktop-terminal-runtime/.venv`
with `e2b==2.51.0`, `e2b-desktop==2.2.0` and `Pillow==11.3.0`. The shared environment
is unchanged. Actual E2B costs remain unknown. No model or Tinker invocation is
part of this development path.

Offline checks:

```bash
PYTHONPATH=.:src:tests:enterprise_fallback/odoo18 \
  /Users/xiaoyong/Documents/Codex/2026-09-22/ya/.venv/bin/python -m unittest -q \
  tests.test_native_desktop_terminal_hit_diagnostic_v38 \
  tests.test_native_desktop_forward_owned_probe_v37 \
  tests.test_native_desktop_terminal_owned_runtime
```

Construction and owned development wrapping use the existing launcher:

```python
from native_desktop_factory import terminal_owned_runtime as runtime

manifest = runtime.source_manifest(repository_root)
factory = runtime.factory(manifest=manifest, source_root=repository_root)
# raw_guest has already been created once and journaled by the owned launcher.
guest = factory.wrap_owned_guest(
    bounded_raw_guest, root=private_gui_root, out=private_actor_directory,
    filename=public_train_filename, lease_started_monotonic=lease_started,
)
guest.prepare(source=public_train_bytes, guest_reference=guest_reference,
              profile_reference=scoped_profile_reference)
driver = runtime.control_driver(
    factory, actor=guest, identity=public_train_identity,
    instruction=public_train_instruction, actor_deadline=actor_deadline,
)
driver.dispatch(action_json)
```

The inherited current teacher and model episode workers accept this factory.
Native source registration must use `runtime.source_manifest(...)["source_sha256s"]`
and the fresh runtime content epoch; the old V31 registration helper emits V31
sources. The 90-action, 720-second actor and 1200-second formal lease settings are
unchanged. Construction and development wrapping grant no qualification credit.
Formal `create_guest` and current worker activation still require independently
reopened fresh evidence for all seven actor paths, all three apps, 120 control
trios, and distinct actor/reset base plus supplemental content. Historical V31–V37
controls are not relabelled.

Actual development evidence is retained under
`work/full-study/desktop-terminal-runtime-control-20261002-11.private`.
The one-use launcher records create intent, raw handle, source manifest,
observation/predispatch/decision/nonce/native receipts, saved-file readback,
development byte restoration and owned kill/readback. Its no-change wait control
does not satisfy a business-edit positive or the formal distinct-reset trio.
