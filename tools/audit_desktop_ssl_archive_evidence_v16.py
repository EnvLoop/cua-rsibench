"""Readonly certificate archive evidence and source-only structural proposal."""
import argparse
from collections import Counter
import json
from pathlib import Path

from native_desktop_factory.factory import digest
from tools.audit_desktop_neutral_manifest_diff_v14 import manifest

CANONICAL_FIELDS = ('name', 'type', 'mode', 'uid', 'gid', 'size', 'linkname', 'pax_header_names',
                    'is_regular_file', 'payload_sha256', 'contains_private_key_pem', 'certificate_pem_blocks')


def canonical_members(metadata):
    members = metadata['members']
    if len({m['name'] for m in members}) != len(members):raise ValueError('Duplicate archive member name')
    return [{key: row[key] for key in CANONICAL_FIELDS} for row in sorted(members, key=lambda r: r['name'])]


def audit(original_manifest, current_root):
    baseline, baseline_tree, baseline_compressed = manifest(original_manifest)
    command_path = current_root / 'command-result.private.json'
    command = json.loads(command_path.read_bytes()); metadata = json.loads(command['stdout'])
    receipt = json.loads((current_root / 'receipt.json').read_bytes())
    if not (command['exit_code'] == 0 and digest(command_path.read_bytes()) == receipt['command_result_sha256'] and
            receipt['archive_sha256'] == metadata['archive_sha256'] and receipt['kill_returned'] is True and
            receipt['is_running_after_kill'] is False and metadata['members_with_private_key_pem'] == 0 and
            metadata['raw_payloads_persisted'] is metadata['archive_extracted'] is metadata['archive_executed'] is metadata['tls_configuration_changed'] is False):
        raise ValueError('Raw archive evidence, privacy or teardown binding changed')
    regular = [m for m in metadata['members'] if m['is_regular_file']]
    proven = []; unmatched = []
    for member in regular:
        matches = [path for path in member['matching_live_certificate_paths'] if path in baseline and
                   baseline[path][1] == 'regular_file' and baseline[path][5] == [member['size'], member['payload_sha256']]]
        if matches:
            proven.append({'member': member['name'], 'size': member['size'], 'payload_sha256': member['payload_sha256'],
                           'frozen_regular_file_matches': matches})
        else:
            unmatched.append({key: member[key] for key in (*CANONICAL_FIELDS, 'mtime')})
    names = {m['name']: m for m in metadata['members']}
    links = [m for m in metadata['members'] if m['type'] == '1']
    if any(m['linkname'] not in names or not names[m['linkname']]['is_regular_file'] for m in links):
        raise ValueError('Archive hardlink is not a recorded regular member')
    certs = [m for m in regular if m['certificate_pem_blocks'] == 1]
    if len(unmatched) != 1 or unmatched[0]['name'] != './ca-certificates.crt':
        raise ValueError('Observed unmatched member classification changed')
    canonical = canonical_members(metadata)
    normalized_hash = digest(json.dumps(canonical, sort_keys=True, separators=(',', ':')).encode())
    immutable_rows = [row for row in baseline.values() if row[0] != '/usr/local/share/e2b/ssl-certs.tar']
    immutable_hash = digest(b''.join((json.dumps(row, sort_keys=True, separators=(',', ':')) + '\n').encode() for row in immutable_rows))
    return {'schema': 'cua-native-v15-ssl-archive-evidence-and-v16-source-proposal',
            'status': 'observed_certificate_packaging_structural_reference_proposed_no_dispatch',
            'command_result_sha256': digest(command_path.read_bytes()), 'receipt_sha256': digest((current_root / 'receipt.json').read_bytes()),
            'original_manifest_sha256': baseline_compressed, 'original_full_tree_sha256': baseline_tree,
            'archive_sha256_observed': metadata['archive_sha256'], 'archive_bytes': metadata['archive_bytes'],
            'member_type_counts': dict(Counter(m['type'] for m in metadata['members'])),
            'regular_members': len(regular), 'individual_certificate_members': len(certs),
            'individual_certificate_total_bytes': sum(m['size'] for m in certs),
            'frozen_regular_file_hash_matches': proven, 'matched_members': len(proven), 'unmatched_members': unmatched,
            'hardlinks_to_recorded_regular_members': len(links), 'known_per_guest_ca_matches': 0,
            'private_key_pem_members': 0, 'archive_mtime_counts': dict(Counter(str(m['mtime']) for m in metadata['members'])),
            'old_tar_payload_or_headers_available': False, 'aggregate_concatenation_proven': False,
            'generic_per_guest_archive_variation_proven': False,
            'structural_proposal': {'path': '/usr/local/share/e2b/ssl-certs.tar',
                'canonical_member_fields': list(CANONICAL_FIELDS), 'exact_canonical_members': canonical,
                'canonical_members_sha256': normalized_hash, 'immutable_other_rows': len(immutable_rows),
                'immutable_other_tree_sha256': immutable_hash, 'ignored_archive_metadata_fields': ['mtime'],
                'raw_archive_sha256_retained_as_observation': True, 'all_member_payload_hashes_fixed': True,
                'all_other_filesystem_metadata_and_content_fixed': True, 'original_reference_rewritten': False,
                'tls_configuration_changed': False, 'task_or_scorer_exception': False, 'dispatch_authorized': False},
            'api_calls_by_audit': 0, 'official_final_admissions': 0, 'official_model_results': 0}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--original-manifest', type=Path, required=True); p.add_argument('--current-root', type=Path, required=True)
    p.add_argument('--public-out', type=Path, required=True); a = p.parse_args()
    value = audit(a.original_manifest, a.current_root)
    with a.public_out.open('x') as stream:stream.write(json.dumps(value, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'matched_members': value['matched_members'], 'unmatched_members': len(value['unmatched_members']),
                      'public_sha256': digest(a.public_out.read_bytes())}))


if __name__ == '__main__':main()
