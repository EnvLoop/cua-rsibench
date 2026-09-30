"""Readonly comparison of source-bound guest manifests; no API or extraction."""
import argparse
import gzip
import json
from pathlib import Path
from native_desktop_factory.factory import digest


def manifest(path):
    raw = path.read_bytes()
    if len(raw) > 16_000_000:raise ValueError('Compressed manifest exceeds bound')
    decoded = gzip.decompress(raw)
    if len(decoded) > 128_000_000:raise ValueError('Decoded manifest exceeds bound')
    rows = [json.loads(line) for line in decoded.splitlines()]
    if len(rows) > 120_000 or len({r[0] for r in rows}) != len(rows):raise ValueError('Manifest row count or uniqueness changed')
    return {r[0]: r for r in rows}, digest(decoded), digest(raw)


def audit(reference, original, current_root):
    expected = json.loads(reference.read_bytes())
    baseline, base_tree, base_compressed = manifest(original)
    current, current_tree, current_compressed = manifest(current_root / 'guest-content-files.jsonl.gz')
    receipt = json.loads((current_root / 'receipt.json').read_bytes())
    index = json.loads((current_root / 'capture-index.private.json').read_bytes())
    command = json.loads((current_root / 'command-result.private.json').read_bytes())
    observed = json.loads(command['stdout'])
    if not (base_compressed in expected['private_compressed_manifest_sha256s'] and base_tree == expected['static_content_sha256'] and
            current_compressed == index['manifest_ref']['sha256'] and current_tree == observed['content_tree_sha256'] and
            command['exit_code'] == 0 and receipt['kill_returned'] is True and receipt['is_running_after_kill'] is False):
        raise ValueError('Frozen reference, raw command, manifest or cleanup binding changed')
    changed = [name for name in sorted(set(baseline) | set(current)) if baseline.get(name) != current.get(name)]
    differences = [{'path': name, 'baseline': baseline.get(name), 'current': current.get(name)} for name in changed]
    return {'schema': 'cua-native-neutral-v14-manifest-diff-public',
            'status': 'one_exact_archive_entry_changed' if len(changed) == 1 else 'manifest_difference_audited',
            'guest_reference_sha256': digest(reference.read_bytes()), 'original_manifest_sha256': base_compressed,
            'current_manifest_sha256': current_compressed, 'original_tree_sha256': base_tree,
            'current_tree_sha256': current_tree, 'original_rows': len(baseline), 'current_rows': len(current),
            'added_paths': len(set(current) - set(baseline)), 'removed_paths': len(set(baseline) - set(current)),
            'changed_entries': len(changed), 'unchanged_rows': len(set(baseline) & set(current)) - len(changed),
            'differences': differences, 'kernel_counts_exclusions_equal': all(observed[k] == expected[v] for k, v in
                {'kernel': 'kernel_identity', 'counts': 'static_content_counts', 'excluded_paths': 'static_content_excluded_paths'}.items()),
            'archive_payload_bytes_available': False, 'template_change_established': False,
            'old_failed_v13_guest_exact_cause_recovered': False, 'api_calls': 0,
            'official_final_admissions': 0, 'official_model_results': 0}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('reference', 'original', 'current-root', 'public-out'):p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args(); value = audit(a.reference, a.original, a.current_root)
    with a.public_out.open('x') as stream:stream.write(json.dumps(value, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'changed_entries': value['changed_entries'], 'public_sha256': digest(a.public_out.read_bytes())}))


if __name__ == '__main__':main()
