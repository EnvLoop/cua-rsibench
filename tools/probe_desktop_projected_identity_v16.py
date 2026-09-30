"""Fresh neutral validation of an explicit projected runtime reference."""
import argparse
import importlib.metadata
import json
from pathlib import Path

from native_desktop_factory import selection_control_accounting_epoch_v13 as old_controls
from native_desktop_factory import structural_guest_attestation_v16 as common
from native_desktop_factory.factory import digest

SCHEMA = 'cua-neutral-projected-runtime-freeze-v16'
PERMIT = 'cua-neutral-projected-runtime-one-create-permit-v16'
SOURCE_FILES = (*old_controls.SOURCE_FILES, 'native_desktop_factory/ssl_archive_metadata_v15.py',
                'native_desktop_factory/structural_guest_attestation_v16.py',
                'tools/audit_desktop_neutral_manifest_diff_v14.py', 'tools/audit_desktop_ssl_archive_evidence_v16.py',
                'tools/probe_desktop_projected_identity_v16.py', 'tests/test_structural_guest_attestation_v16.py')


def sources():
    root = Path(__file__).resolve().parents[1]
    return {name: digest((root / name).read_bytes()) for name in SOURCE_FILES}


def prepare(control_freeze, reference, output, freeze):
    value = old_controls.validate(control_freeze); ref = json.loads(reference.read_bytes())
    old_controls.require(ref['schema'] == 'cua-native-desktop-structural-runtime-reference-v16' and
                         ref['guest_content_probe_script_sha256'] == digest(common.script().encode()), 'Projected reference source changed')
    old_controls.require(not output.exists() and not output.is_symlink() and
                         not any(output.resolve().is_relative_to(Path(p).resolve()) for p in value['accounting_roots']),
                         'Projected probe requires fresh root outside historical accounting')
    record = {'schema': SCHEMA, 'control_freeze': str(control_freeze.resolve()), 'control_freeze_sha256': digest(control_freeze.read_bytes()),
              'reference': str(reference.resolve()), 'reference_sha256': digest(reference.read_bytes()),
              'source_sha256s': sources(), 'output_root': str(output.resolve()), 'lease_seconds': 600,
              'maximum_new_creates': 1, 'same_intent_replay_authorized': False}
    old_controls.accounting._write_new(freeze, record)
    return {'status': 'projected_runtime_neutral_source_frozen_no_create', 'freeze_sha256': digest(freeze.read_bytes())}


def validate(freeze):
    value = json.loads(old_controls.private(freeze))
    old_controls.require(value['schema'] == SCHEMA and value['source_sha256s'] == sources() and value['lease_seconds'] == 600 and
                         value['maximum_new_creates'] == 1 and value['same_intent_replay_authorized'] is False, 'Projected probe source/bounds changed')
    old_controls.validate(Path(value['control_freeze']))
    old_controls.require(digest(Path(value['control_freeze']).read_bytes()) == value['control_freeze_sha256'] and
                         digest(Path(value['reference']).read_bytes()) == value['reference_sha256'], 'Projected probe reference changed')
    return value


def review(freeze, permit):
    from native_desktop_factory.reconcile_interrupted_sweep import active_hashes
    value = validate(freeze); active, count = active_hashes()
    old_controls.require(not active and count == 0 and not Path(value['output_root']).exists(), 'Projected review needs active zero/fresh root')
    old_controls.accounting._write_new(permit, {'schema': PERMIT, 'freeze_sha256': digest(freeze.read_bytes()),
           'source_sha256s': value['source_sha256s'], 'provider_active_zero_at_review': True, 'same_intent_replay_authorized': False})
    return {'status': 'one_projected_runtime_probe_reviewed_no_create'}


def run(freeze, permit, *, enable_paid_probe=False):
    old_controls.require(enable_paid_probe is True, 'Paid projected probe disabled before private reads')
    value = validate(freeze); out = Path(value['output_root']); authorization = json.loads(old_controls.private(permit))
    old_controls.require(authorization == {'schema': PERMIT, 'freeze_sha256': digest(freeze.read_bytes()),
          'source_sha256s': value['source_sha256s'], 'provider_active_zero_at_review': True, 'same_intent_replay_authorized': False} and not out.exists(),
          'Fresh exact projected probe permit required')
    pins = {'e2b-desktop': '2.2.0', 'e2b': '2.51.0', 'Pillow': '11.3.0'}
    old_controls.require({name: importlib.metadata.version(name) for name in pins} == pins, 'Pinned native runtime required')
    from native_desktop_factory.reconcile_interrupted_sweep import active_hashes
    active, count = active_hashes(); old_controls.require(not active and count == 0, 'Projected create requires active zero')
    reference = json.loads(Path(value['reference']).read_bytes()); out.mkdir(parents=True, mode=0o700)
    old_controls.accounting._write_new(out / 'intent.json', {'schema': 'cua-native-projected-runtime-neutral-intent-v16',
        'freeze_sha256': digest(freeze.read_bytes()), 'lease_seconds': 600, 'same_intent_replay_authorized': False})
    receipt = {'schema': 'cua-native-projected-runtime-neutral-receipt-v16', 'status': 'started', 'lease_seconds': 600,
        'reference_sha256': value['reference_sha256'], 'task_files_staged': 0, 'gui_actions': 0, 'model_calls': 0,
        'official_final_admissions': 0, 'actual_provider_billed_usd': None}
    sandbox = None
    try:
        from e2b_desktop import Sandbox
        sandbox = Sandbox.create(template=reference['provider_template_id'], resolution=(1280, 800), timeout=600,
                allow_internet_access=False, metadata={'envloop_purpose': 'neutral-v16-projected-runtime-identity'})
        receipt['sandbox_id_sha256'] = digest(sandbox.sandbox_id.encode()); info = sandbox.get_info(request_timeout=12)
        old_controls.require(info.template_id == reference['provider_template_id'] and info.envd_version == reference['provider_envd_version'] and
                 info.cpu_count == reference['provider_shape']['vcpu'] and info.memory_mb == reference['provider_shape']['memory_mb'], 'Projected probe provider shape changed')
        _result, _observed, attestation = common.execute_probe(sandbox, root=out, out=out, reference=reference)
        receipt.update(status='projected_runtime_identity_verified_before_teardown', identity_kind=attestation['identity_kind'],
                       projected_tree_sha256=attestation['projected_tree_sha256'], raw_tree_sha256=attestation['raw_tree_sha256'],
                       raw_archive_sha256=attestation['raw_archive_sha256'], raw_tree_equals_legacy_reference=attestation['raw_tree_equals_legacy_reference'])
    except Exception as exc:receipt['status'] = 'projected_runtime_probe_failed'; receipt['error_type'] = type(exc).__name__
    finally:
        if sandbox is not None:
            try:receipt['kill_returned'] = bool(sandbox.kill()); receipt['is_running_after_kill'] = bool(sandbox.is_running(request_timeout=12))
            except Exception as exc:receipt['cleanup_error_type'] = type(exc).__name__
        if receipt.get('is_running_after_kill') is not False:receipt['status'] = 'cleanup_unverified'
        elif receipt['status'] == 'projected_runtime_identity_verified_before_teardown':receipt['status'] = 'projected_runtime_identity_verified'
        old_controls.accounting._write_new(out / 'receipt.json', receipt)
    return receipt


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('mode', choices=('reference', 'prepare', 'review', 'run'))
    for name in ('control-freeze', 'reference', 'output', 'freeze', 'permit', 'old-reference', 'old-manifest', 'archive-evidence'):
        p.add_argument('--' + name, type=Path)
    p.add_argument('--enable-paid-probe', action='store_true'); a = p.parse_args()
    if a.mode == 'reference':
        result = common.build_reference(a.old_reference, a.old_manifest, a.archive_evidence)
        old_controls.accounting._write_new(a.reference, result, public=True)
        result = {'status': 'explicit_projected_reference_proposed_no_live_verification', 'reference_sha256': digest(a.reference.read_bytes())}
    elif a.mode == 'prepare':result = prepare(a.control_freeze, a.reference, a.output, a.freeze)
    elif a.mode == 'review':result = review(a.freeze, a.permit)
    else:result = run(a.freeze, a.permit, enable_paid_probe=a.enable_paid_probe)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':main()
