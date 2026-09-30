"""One neutral runtime diagnostic retaining raw probe output before comparison.

No task file, GUI action, model or scorer is available through this entry.
The old failed guest cannot be replayed. Source preparation and root review
precede one fresh, bounded create outside frozen historical accounting roots.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path

from native_desktop_factory import selection_control_accounting_epoch_v13 as epoch
from native_desktop_factory import runtime_fingerprint_probe as probe
from native_desktop_factory.factory import digest
from native_desktop_factory.v066_storage_budget import reserve_and_write

SCHEMA = 'cua-neutral-desktop-attestation-freeze-v14'
PERMIT = 'cua-neutral-desktop-attestation-one-create-permit-v14'


def sources():
    root = Path(__file__).resolve().parents[1]
    names = ('tools/capture_desktop_guest_attestation_v14.py', 'tests/test_desktop_attestation_capture_v14.py')
    return {**epoch.source_hashes(), **{n: digest((root / n).read_bytes()) for n in names}}


def prepare(control_freeze, output, freeze):
    value = epoch.validate(control_freeze)
    epoch.require(not output.exists() and not output.is_symlink() and
                  not any(output.resolve().is_relative_to(Path(p).resolve()) for p in value['accounting_roots']),
                  'Neutral probe needs a fresh root outside all frozen accounting roots')
    reference = Path(value['guest_public'])
    result = {'schema': SCHEMA, 'control_freeze': str(control_freeze.resolve()),
              'control_freeze_sha256': digest(control_freeze.read_bytes()), 'source_sha256s': sources(),
              'guest_reference': str(reference), 'guest_reference_sha256': digest(reference.read_bytes()),
              'output_root': str(output.resolve()), 'lease_seconds': 600,
              'task_files_staged': 0, 'gui_actions': 0, 'model_calls': 0,
              'same_intent_replay_authorized': False}
    epoch.accounting._write_new(freeze, result)
    return {'status': 'neutral_probe_source_frozen_no_create', 'freeze_sha256': digest(freeze.read_bytes())}


def validate(freeze):
    value = json.loads(epoch.private(freeze))
    epoch.require(value['schema'] == SCHEMA and value['source_sha256s'] == sources() and value['lease_seconds'] == 600 and
                  value['same_intent_replay_authorized'] is False, 'Neutral probe source or bounds changed')
    epoch.validate(Path(value['control_freeze']))
    epoch.require(digest(Path(value['control_freeze']).read_bytes()) == value['control_freeze_sha256'] and
                  digest(Path(value['guest_reference']).read_bytes()) == value['guest_reference_sha256'],
                  'Neutral probe reference changed')
    return value


def review(freeze, permit):
    from native_desktop_factory.reconcile_interrupted_sweep import active_hashes
    value = validate(freeze); active, count = active_hashes()
    epoch.require(not active and count == 0 and not Path(value['output_root']).exists(), 'Neutral review requires fresh root and active zero')
    epoch.accounting._write_new(permit, {'schema': PERMIT, 'freeze_sha256': digest(freeze.read_bytes()),
              'source_sha256s': value['source_sha256s'], 'provider_active_zero_at_review': True,
              'maximum_new_creates': 1, 'same_intent_replay_authorized': False})
    return {'status': 'one_neutral_create_reviewed_no_dispatch'}


def compare(observed, expected):
    fields = {'content_tree_sha256': 'static_content_sha256', 'counts': 'static_content_counts',
              'kernel': 'kernel_identity', 'excluded_paths': 'static_content_excluded_paths'}
    return [key for key, reference in fields.items() if observed.get(key) != expected[reference]]


def capture_result(root, result, *, manifest_reader):
    """Always retain exit/stdout/stderr before JSON parsing or gate comparison."""
    value = {'exit_code': result.exit_code, 'stdout': result.stdout, 'stderr': result.stderr,
             'stdout_sha256': digest(result.stdout.encode()), 'stderr_sha256': digest(result.stderr.encode())}
    reserve_and_write(root, root / 'command-result.private.json', epoch.accounting.encode(value))
    try:
        raw = manifest_reader()
        value['manifest_ref'] = reserve_and_write(root, root / 'guest-content-files.jsonl.gz', raw)
    except Exception as exc:
        value['manifest_capture_error_type'] = type(exc).__name__
    epoch.accounting._write_new(root / 'capture-index.private.json', {k: v for k, v in value.items() if k not in ('stdout', 'stderr')})
    return value


def run_command_capture(sandbox, out):
    try:
        result = sandbox.commands.run('sudo -n python3 /tmp/native-guest-content-probe-v066.py', timeout=450, request_timeout=480)
    except Exception as exc:
        if not all(hasattr(exc, field) for field in ('exit_code', 'stdout', 'stderr')):
            raise
        result = exc  # The pinned SDK's CommandExitException retains CommandResult fields.
    return capture_result(out, result, manifest_reader=lambda: bytes(sandbox.files.read(
                          '/tmp/native-guest-content-files.jsonl.gz', format='bytes')))


def run(freeze, permit, *, enable_paid_probe=False):
    epoch.require(enable_paid_probe is True, 'Paid neutral probe is disabled before private reads')
    value = validate(freeze); review_value = json.loads(epoch.private(permit)); out = Path(value['output_root'])
    pins = {'e2b-desktop': '2.2.0', 'e2b': '2.51.0', 'Pillow': '11.3.0'}
    epoch.require({name: importlib.metadata.version(name) for name in pins} == pins, 'Pinned native SDK runtime required')
    epoch.require(review_value == {'schema': PERMIT, 'freeze_sha256': digest(freeze.read_bytes()),
              'source_sha256s': value['source_sha256s'], 'provider_active_zero_at_review': True,
              'maximum_new_creates': 1, 'same_intent_replay_authorized': False} and not out.exists(),
              'Neutral source-reviewed one-use permit required')
    from native_desktop_factory.reconcile_interrupted_sweep import active_hashes
    active, count = active_hashes(); epoch.require(not active and count == 0, 'Neutral create requires active zero')
    expected = json.loads(Path(value['guest_reference']).read_bytes())
    out.mkdir(parents=True, mode=0o700)
    epoch.accounting._write_new(out / 'intent.json', {'schema': 'cua-native-neutral-attestation-intent-v14',
              'freeze_sha256': digest(freeze.read_bytes()), 'lease_seconds': 600,
              'same_intent_replay_authorized': False})
    receipt = {'schema': 'cua-native-neutral-attestation-receipt-v14', 'status': 'started',
               'lease_seconds': 600, 'task_files_staged': 0, 'gui_actions': 0, 'model_calls': 0,
               'actual_provider_billed_usd': None, 'official_final_admissions': 0}
    sandbox = None
    try:
        from e2b_desktop import Sandbox
        sandbox = Sandbox.create(template=expected['provider_template_id'], resolution=(1280, 800), timeout=600,
                                 allow_internet_access=False, metadata={'envloop_purpose': 'neutral-v14-raw-attestation-diagnostic'})
        receipt['sandbox_id_sha256'] = digest(sandbox.sandbox_id.encode())
        info = sandbox.get_info(request_timeout=12)
        receipt['provider_shape_matches'] = (info.template_id == expected['provider_template_id'] and
                    info.envd_version == expected['provider_envd_version'] and info.cpu_count == expected['provider_shape']['vcpu'] and
                    info.memory_mb == expected['provider_shape']['memory_mb'])
        sandbox.files.write('/tmp/native-guest-content-probe-v066.py', probe.GUEST_CONTENT_PROBE.encode())
        captured = run_command_capture(sandbox, out)
        receipt['probe_exit_code'] = captured['exit_code']
        receipt['raw_command_result_sha256'] = digest((out / 'command-result.private.json').read_bytes())
        receipt['raw_manifest_retained'] = 'manifest_ref' in captured
        if captured['exit_code'] != 0:
            receipt['status'] = 'probe_command_failed_raw_output_retained'
        else:
            observed = json.loads(captured['stdout']); differences = compare(observed, expected)
            receipt['differing_attestation_fields'] = differences
            receipt['status'] = 'attestation_summary_matches_frozen_reference' if not differences else 'attestation_mismatch_raw_command_retained'
    except Exception as exc:
        receipt['status'] = 'neutral_probe_failed'; receipt['error_type'] = type(exc).__name__
    finally:
        if sandbox is not None:
            try:
                receipt['kill_returned'] = bool(sandbox.kill()); receipt['is_running_after_kill'] = bool(sandbox.is_running(request_timeout=12))
            except Exception as exc:receipt['cleanup_error_type'] = type(exc).__name__
        if receipt.get('is_running_after_kill') is not False:receipt['status'] = 'cleanup_unverified'
        epoch.accounting._write_new(out / 'receipt.json', receipt)
    return receipt


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('mode', choices=('prepare', 'review', 'run'))
    p.add_argument('--freeze', type=Path, required=True); p.add_argument('--permit', type=Path)
    p.add_argument('--control-freeze', type=Path); p.add_argument('--output', type=Path)
    p.add_argument('--enable-paid-probe', action='store_true'); a = p.parse_args()
    result = prepare(a.control_freeze, a.output, a.freeze) if a.mode == 'prepare' else review(a.freeze, a.permit) if a.mode == 'review' else run(
                          a.freeze, a.permit, enable_paid_probe=a.enable_paid_probe)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':main()
