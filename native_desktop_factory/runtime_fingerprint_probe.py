"""Bounded neutral E2B Desktop guest-runtime fingerprint probe.

This uses a public training fixture only and never samples a model or opens a
private final package. A provider template ID is recorded, but E2B's current
SandboxInfo does not expose a container-image digest; guest fingerprints are
measured evidence, not a substitute for that missing provider image digest.
"""

from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import time

if __package__:
    from .budget_ledger import audit as audit_budget
    from .gui_control_shell import wait_for_document_ready
else:
    from budget_ledger import audit as audit_budget
    from gui_control_shell import wait_for_document_ready


GUEST_PROBE = r'''import hashlib,json,pathlib,subprocess
def sha(raw): return hashlib.sha256(raw).hexdigest()
def filehash(path):
 h=hashlib.sha256()
 with path.open('rb') as stream:
  for chunk in iter(lambda:stream.read(1024*1024),b''): h.update(chunk)
 return h.hexdigest()
def tree(path):
 root=pathlib.Path(path)
 rows=[(str(p.relative_to(root)),filehash(p)) for p in sorted(root.rglob('*')) if p.is_file()] if root.exists() else []
 return {'exists':root.exists(),'files':len(rows),'sha256':sha(json.dumps(rows,sort_keys=True,separators=(',',':')).encode())}
def run(args):
 r=subprocess.run(args,capture_output=True,text=True,check=True)
 return r.stdout
font=tree('/usr/share/fonts')
profile=tree('/home/user/.config/libreoffice/4/user')
packages='\n'.join(sorted(run(['dpkg-query','-W','-f=${binary:Package}\t${Version}\n']).splitlines()))
fontconfig='\n'.join(sorted(run(['fc-list','-f','%{family}|%{style}|%{file}\n']).splitlines()))
print(json.dumps({'font_tree':font,'libreoffice_profile_tree':profile,
 'os_release_sha256':filehash(pathlib.Path('/etc/os-release')),
 'libreoffice_executable_sha256':filehash(pathlib.Path('/usr/bin/libreoffice')),
 'libreoffice_version':run(['libreoffice','--version']).strip(),
 'package_manifest_sha256':sha(packages.encode()),'package_count':len(packages.splitlines()),
 'fontconfig_catalog_sha256':sha(fontconfig.encode()),'fontconfig_entry_count':len(fontconfig.splitlines())},sort_keys=True))
'''


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--train-fixture", type=Path, required=True)
    parser.add_argument("--lease-seconds", type=int, default=180)
    parser.add_argument("--max-lane-reserved-usd", type=Decimal, default=Decimal("40"))
    parser.add_argument("--expected-template-id", default="k0wmnzir0zuzye6dndlw")
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("Refusing to overwrite runtime fingerprint probe")
    if (args.out.name != "receipt.json" or not args.out.parent.name.startswith("runtime-fingerprint-")
            or args.out.parent.parent.resolve() != (args.work_root / "gui-diagnostics").resolve()):
        raise ValueError("Probe receipt must be in ledger-visible runtime-fingerprint directory")
    if not 120 <= args.lease_seconds <= 600:
        raise ValueError("Runtime fingerprint lease outside bounded range")
    if not args.train_fixture.is_file() or not args.train_fixture.resolve().is_relative_to(
            Path(__file__).parent.resolve() / "dev-fixtures"):
        raise ValueError("Only a committed public training fixture may be opened")
    baseline = args.train_fixture.read_bytes()
    if not baseline or args.train_fixture.suffix not in (".xlsx", ".pptx", ".docx"):
        raise ValueError("Invalid public training fixture")
    budget = audit_budget(args.work_root, proposed_new_sandboxes=1,
                          proposed_lease_seconds=args.lease_seconds,
                          max_lane_reserved_usd=args.max_lane_reserved_usd)
    if not budget["within_cap"]:
        raise ValueError("Lane-wide E2B lease reservation exceeds cap")
    if not os.environ.get("E2B_API_KEY"):
        raise ValueError("E2B credential missing")
    args.out.parent.mkdir(parents=True)
    receipt = {
        "schema": "cua-native-wdi-runtime-fingerprint-v1",
        "status": "started", "lease_seconds": args.lease_seconds,
        "fixture_sha256": digest(baseline),
        "guest_probe_script_sha256": digest(GUEST_PROBE.encode()),
        "sdk_version": importlib.metadata.version("e2b-desktop"),
        "budget_before": {k: budget[k] for k in (
            "past_conservative_reserved_usd", "proposed_reserved_usd",
            "combined_reserved_usd", "lane_usd_cap")},
        "actual_billed_usd": None,
    }

    def persist():
        args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")

    persist()
    sandbox = None
    try:
        from e2b_desktop import Sandbox
        sandbox = Sandbox.create(template="desktop", resolution=(1280, 800),
                                 timeout=args.lease_seconds, allow_internet_access=False)
        receipt["sandbox_id_sha256"] = digest(sandbox.sandbox_id.encode())
        info = sandbox.get_info(request_timeout=12)
        receipt["provider_sandbox_info"] = {
            "template_id": info.template_id, "vcpu": info.cpu_count,
            "memory_mb": info.memory_mb, "envd_version": info.envd_version,
        }
        if (info.template_id != args.expected_template_id
                or info.cpu_count > 8 or info.memory_mb > 8192):
            raise ValueError("E2B provider template or resource shape drifted")
        sandbox.files.write("/tmp/native-runtime-probe.py", GUEST_PROBE.encode())

        def guest_probe() -> dict:
            result = sandbox.commands.run("python3 /tmp/native-runtime-probe.py")
            if result.exit_code != 0:
                raise ValueError("Guest runtime probe failed")
            return json.loads(result.stdout)

        receipt["fresh_guest"] = guest_probe()
        remote = "/home/user/" + args.train_fixture.name
        sandbox.files.write(remote, baseline)
        if bytes(sandbox.files.read(remote, format="bytes")) != baseline:
            raise ValueError("Public training fixture staging changed bytes")
        sandbox.open(remote)
        receipt["trusted_setup_ready"] = wait_for_document_ready(sandbox,
                                                                  args.train_fixture.name)
        time.sleep(7)
        sandbox.press("esc")
        time.sleep(1)
        receipt["after_neutral_open"] = guest_probe()
        if (receipt["fresh_guest"]["font_tree"] != receipt["after_neutral_open"]["font_tree"]
                or receipt["fresh_guest"]["libreoffice_executable_sha256"] !=
                receipt["after_neutral_open"]["libreoffice_executable_sha256"]):
            raise ValueError("Installed fonts or LibreOffice binary changed during neutral open")
        receipt["status"] = "fingerprinted"
    except Exception as exc:
        receipt["status"] = "probe_failed"
        receipt["error_type"] = type(exc).__name__
    finally:
        if sandbox is not None:
            try:
                receipt["kill_returned"] = bool(sandbox.kill())
                receipt["is_running_after_kill"] = bool(sandbox.is_running(request_timeout=8))
            except Exception as exc:
                receipt["kill_error_type"] = type(exc).__name__
        if receipt["status"] == "fingerprinted" and receipt.get("is_running_after_kill") is False:
            receipt["status"] = "fingerprinted_and_terminated"
        persist()
    print(json.dumps({"status": receipt["status"],
                      "sandbox_terminated": receipt.get("is_running_after_kill") is False,
                      "font_files": receipt.get("fresh_guest", {}).get("font_tree", {}).get("files")},
                     sort_keys=True))
    return 0 if receipt["status"] == "fingerprinted_and_terminated" else 2


if __name__ == "__main__":
    raise SystemExit(main())
