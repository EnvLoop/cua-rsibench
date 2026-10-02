# Neutral runtime SSL archive difference

The v14 neutral diagnostic completed its content probe and retained the
command output and gzip manifest. Provider shape, kernel, entry counts and
exclusion list match the frozen reference. Against both scoped original
manifests, the current manifest has the same 100,661 paths and exactly one
changed row: `/usr/local/share/e2b/ssl-certs.tar`. Its regular-file type, mode
0644, UID/GID 0 and 522,240-byte size are unchanged. Its content hash changed
from `d8d08ce53f4fb98b1d501fb79a1809f6482bd1371b868a897ea1d55afb2d4ab4`
to `92ce293b421143471ef31b39064b8cb35c2e0ea7cb194f2f255bf87fa52dc28f`.
All other 100,660 rows are identical. There are no added or removed paths.

The independent readonly auditor binds the compressed and decoded manifests
to the original reference and captured probe result. Its result replayed
identically. These records contain hashes rather than tar payload bytes;
neither the old tar contents nor their headers are available. This single-file
change does not establish a template, application or kernel change, and it
cannot recover the missing output of the earlier failed v13 guest.

The additive v15 tool prepares and reviews one fresh neutral 600-second probe
outside all frozen accounting roots. It inspects the fixed SSL archive in
memory, records member names/types/modes/UID/GID/sizes/timestamps and payload
hashes, and compares payload hashes with actual files under the bounded live
certificate directories. Matches to the two previously identified per-guest
CA paths are reported separately. Private-key PEM markers are detected as
booleans; raw member payloads and key bytes are never printed or persisted.

The archive limit is 4 MiB, 2,048 members, 2 MiB per member and 8 MiB total
payload. The live certificate scan is limited to 5,000 files and 32 MiB.
Sparse or oversized members are refused. No archive extraction, command
execution from archive content, task staging, GUI input, model sampling, TLS
configuration change or reference update is provided by this tool.

Eleven focused offline checks passed in the pinned native runtime, covering
the new inspector and existing raw-command capture. The actual v15 probe has
not been run by this author. Its metadata is needed before interpreting the
changed archive as a dynamic provider bootstrap bundle or amending runtime
identity. All 68 control source files remain unchanged.

```sh
python -m tools.probe_desktop_ssl_archive_v15 prepare \
  --control-freeze <current-v13-private-freeze> \
  --output <fresh-work/full-study/ssl-probe-root> --freeze <private-probe-freeze>
python -m tools.probe_desktop_ssl_archive_v15 review \
  --freeze <private-probe-freeze> --permit <new-private-permit>
python -m tools.probe_desktop_ssl_archive_v15 run \
  --freeze <private-probe-freeze> --permit <new-private-permit> --enable-paid-probe
```
