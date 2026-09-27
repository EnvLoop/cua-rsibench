"""A changed application file cannot be hidden as personalized E2B state."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from native_desktop_factory.publish_guest_content_identity import aggregate


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class GuestContentIdentityTests(unittest.TestCase):
    def test_only_the_two_e2b_ca_paths_may_differ(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ("batch-001", "batch-002"):
                path = root / "final-v2-normalization" / name / "batch-receipt.json"
                path.parent.mkdir(parents=True)
                path.write_text(json.dumps({
                    "schema": "cua-native-impress-batch-normalization-v1",
                    "status": "finished", "lease_seconds": 120,
                    "sandbox_id_sha256": name,
                }))
            dynamic = ["/etc/ssl/certs/ca-certificates.crt",
                       "/usr/local/share/ca-certificates/e2b-ca.crt"]
            fixed_exclusions = ["/etc/hostname", "/etc/hosts", "/etc/machine-id",
                                "/etc/mtab", "/etc/resolv.conf"]
            paths = []

            def write_probe(index: int, *, static: bool, changed_app: bool = False):
                path = root / "gui-diagnostics" / f"runtime-fingerprint-{index}"
                path.mkdir(parents=True, exist_ok=True)
                application_hash = "changed" if changed_app else "same"
                entries = [["/usr/bin/libreoffice", "regular_file", 493, 0, 0,
                            [10, application_hash]]]
                if not static:
                    entries += [[name, "regular_file", 420, 0, 0,
                                 [10, f"ca-{index}-{position}"]]
                                for position, name in enumerate(dynamic)]
                entries.sort(key=lambda item: item[0])
                raw = b"".join(json.dumps(item, sort_keys=True,
                                          separators=(",", ":")).encode() + b"\n"
                               for item in entries)
                packed = gzip.compress(raw, mtime=0)
                (path / "guest-content-files.jsonl.gz").write_bytes(packed)
                receipt = {
                    "schema": "cua-native-wdi-runtime-fingerprint-v1",
                    "status": "fingerprinted_and_terminated", "lease_seconds": 120,
                    "sandbox_id_sha256": f"sandbox-{index}",
                    "is_running_after_kill": False,
                    "provider_sandbox_info": {"template_id": "same", "envd_version": "0.9.0",
                                              "vcpu": 8, "memory_mb": 8192},
                    "fixture_sha256": "fixture",
                    "guest_content_probe_script_sha256": "static-script" if static else "raw-script",
                    "private_guest_content_files_gzip_sha256": sha(packed),
                    "fresh_guest": {"libreoffice_profile_tree": {"exists": False}},
                    "fresh_guest_content_manifest": {
                        "content_tree_sha256": sha(raw),
                        "counts": {"regular_file": len(entries)},
                        "kernel": {"release": "same"},
                        "excluded_paths": fixed_exclusions + (dynamic if static else []),
                        "regular_file_bytes": 10 * len(entries),
                        "personalized_ca_files": ([{"path": name, "bytes": 10,
                                                   "sha256": f"ca-{index}-{position}"}
                                                  for position, name in enumerate(dynamic)]
                                                 if static else []),
                    },
                }
                (path / "receipt.json").write_text(json.dumps(receipt))
                return path

            for index in range(4):
                paths.append(write_probe(index, static=index >= 2))
            report = aggregate(paths[:2], paths[2:], root)
            self.assertTrue(report["scoped_guest_content_identity_passed"])
            self.assertEqual(report["unexcluded_changed_entry_count"], 2)
            write_probe(1, static=False, changed_app=True)
            with self.assertRaisesRegex(ValueError, "drift exceeds"):
                aggregate(paths[:2], paths[2:], root)


if __name__ == "__main__":
    unittest.main()
