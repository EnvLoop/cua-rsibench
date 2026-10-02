"""One neutral metadata-only SSL archive probe; no reference or TLS change."""
import argparse
from contextlib import contextmanager
import importlib.metadata
import json
from pathlib import Path
from unittest.mock import patch

from tools import capture_desktop_guest_attestation_v14 as parent
from native_desktop_factory import ssl_archive_metadata_v15 as inspection
from native_desktop_factory.factory import digest
from native_desktop_factory.v066_storage_budget import reserve_and_write

SCHEMA = 'cua-neutral-ssl-archive-freeze-v15'
PERMIT = 'cua-neutral-ssl-archive-one-create-permit-v15'
PARENT_SOURCES = parent.sources


def sources():
    root = Path(__file__).resolve().parents[1]
    files = ('native_desktop_factory/ssl_archive_metadata_v15.py', 'tools/probe_desktop_ssl_archive_v15.py',
             'tests/test_desktop_ssl_archive_v15.py')
    return {**PARENT_SOURCES(), **{name: digest((root / name).read_bytes()) for name in files}}


@contextmanager
def binding():
    with patch.object(parent, 'SCHEMA', SCHEMA), patch.object(parent, 'PERMIT', PERMIT), patch.object(parent, 'sources', sources):yield


def prepare(control_freeze, output, freeze):
    with binding():return parent.prepare(control_freeze, output, freeze)


def review(freeze, permit):
    with binding():return parent.review(freeze, permit)


def run(freeze, permit, *, enable_paid_probe=False):
    parent.epoch.require(enable_paid_probe is True, 'Paid SSL metadata probe is disabled before private reads')
    with binding():value = parent.validate(freeze)
    authorization = json.loads(parent.epoch.private(permit)); out = Path(value['output_root'])
    parent.epoch.require(authorization == {'schema': PERMIT, 'freeze_sha256': digest(freeze.read_bytes()),
             'source_sha256s': value['source_sha256s'], 'provider_active_zero_at_review': True,
             'maximum_new_creates': 1, 'same_intent_replay_authorized': False} and not out.exists(), 'Fresh SSL probe permit required')
    pins = {'e2b-desktop': '2.2.0', 'e2b': '2.51.0', 'Pillow': '11.3.0'}
    parent.epoch.require({name: importlib.metadata.version(name) for name in pins} == pins, 'Pinned native SDK runtime required')
    from native_desktop_factory.reconcile_interrupted_sweep import active_hashes
    active, count = active_hashes(); parent.epoch.require(not active and count == 0, 'SSL probe create requires active zero')
    expected = json.loads(Path(value['guest_reference']).read_bytes()); out.mkdir(parents=True, mode=0o700)
    parent.epoch.accounting._write_new(out / 'intent.json', {'schema': 'cua-native-ssl-archive-intent-v15',
              'freeze_sha256': digest(freeze.read_bytes()), 'lease_seconds': 600, 'same_intent_replay_authorized': False})
    receipt = {'schema': 'cua-native-ssl-archive-receipt-v15', 'status': 'started', 'lease_seconds': 600,
               'task_files_staged': 0, 'gui_actions': 0, 'model_calls': 0, 'official_final_admissions': 0,
               'tls_configuration_changed': False, 'actual_provider_billed_usd': None}
    sandbox = None
    try:
        from e2b_desktop import Sandbox
        sandbox = Sandbox.create(template=expected['provider_template_id'], resolution=(1280, 800), timeout=600,
                allow_internet_access=False, metadata={'envloop_purpose': 'neutral-v15-ssl-archive-metadata'})
        receipt['sandbox_id_sha256'] = digest(sandbox.sandbox_id.encode()); info = sandbox.get_info(request_timeout=12)
        parent.epoch.require(info.template_id == expected['provider_template_id'] and info.envd_version == expected['provider_envd_version'] and
                    info.cpu_count == expected['provider_shape']['vcpu'] and info.memory_mb == expected['provider_shape']['memory_mb'],
                    'Neutral SSL probe provider shape changed')
        sandbox.files.write('/tmp/native-ssl-archive-probe-v15.py', Path(inspection.__file__).read_bytes())
        try:result = sandbox.commands.run('sudo -n python3 /tmp/native-ssl-archive-probe-v15.py', timeout=60, request_timeout=90)
        except Exception as exc:
            if not all(hasattr(exc, key) for key in ('exit_code', 'stdout', 'stderr')):raise
            result = exc
        command = {'exit_code': result.exit_code, 'stdout': result.stdout, 'stderr': result.stderr}
        ref = reserve_and_write(out, out / 'command-result.private.json', parent.epoch.accounting.encode(command))
        receipt['command_result_sha256'] = ref['sha256']
        if result.exit_code != 0:receipt['status'] = 'ssl_metadata_command_failed_output_retained'
        else:
            metadata = json.loads(result.stdout)
            parent.epoch.require(metadata['schema'] == 'cua-native-ssl-archive-metadata-v15' and
                          metadata['raw_payloads_persisted'] is metadata['archive_extracted'] is metadata['archive_executed'] is metadata['tls_configuration_changed'] is False,
                          'SSL probe metadata contract changed')
            receipt.update(status='ssl_archive_metadata_retained_no_reference_change', archive_sha256=metadata['archive_sha256'],
                          member_count=metadata['member_count'], members_with_private_key_pem=metadata['members_with_private_key_pem'])
    except Exception as exc:receipt['status'] = 'ssl_metadata_probe_failed'; receipt['error_type'] = type(exc).__name__
    finally:
        if sandbox is not None:
            try:receipt['kill_returned'] = bool(sandbox.kill()); receipt['is_running_after_kill'] = bool(sandbox.is_running(request_timeout=12))
            except Exception as exc:receipt['cleanup_error_type'] = type(exc).__name__
        if receipt.get('is_running_after_kill') is not False:receipt['status'] = 'cleanup_unverified'
        parent.epoch.accounting._write_new(out / 'receipt.json', receipt)
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
