# Pre-model structural runtime identity v16

The completed v15 probe classifies the 246 archive members as two directories,
123 regular files and 121 hardlinks. Of the regular files, 121 are individual
PEM certificates whose exact sizes and hashes match frozen Mozilla certificate
files under `/usr/share/ca-certificates/mozilla`. The 32-byte `./java/cacerts`
matches the frozen `/etc/ssl/certs/java/cacerts`. All 121 hardlinks target
recorded regular archive members.

The only unmatched regular member is `./ca-certificates.crt`: 182,140 bytes,
121 certificate PEM blocks, mode 0644, UID/GID 0 and payload hash
`9481fcd95f41b221f02f14d896535fe500bec539bc563c4cdca1acee483a8bdd`.
Its timestamp is 1790766686. It has no PAX header and no private-key marker.
Its size equals the total size of the 121 individual certificates. This is
consistent with an aggregate certificate bundle; exact concatenation and the
old archive's payload/header differences have not been proven. No archive
member matches either known per-guest CA file. The evidence establishes
certificate packaging, not generic per-guest archive variation.

The explicit new reference preserves every original reference file. It fixes
all 100,660 other filesystem rows and projects only the content-hash field of
`/usr/local/share/e2b/ssl-certs.tar` to an exact canonical member descriptor.
Member names, types, modes, owners, sizes, payload hashes, hardlink targets,
PAX header names and PEM classifications must match the frozen v15 descriptor.
Only archive member timestamps are omitted from that descriptor. The fixed
aggregate payload hash remains part of it. Raw archive hashes and timestamps
are still captured as observations. No certificate configuration, TLS
verification, task, scorer, GUI action or current-frame check changes.

The generated common trusted probe retains the complete raw manifest and raw
tree hash, and reports a separately labelled projected tree hash. Verification
binds the archive metadata to its actual raw filesystem row, reopens the whole
manifest, checks the exact canonical member descriptor and verifies every
other row through the projected tree identity. It never fabricates equality
with the legacy raw reference. Controls, shared-base sampling and all four
checkpoint workers use the same probe and verifier.

The new projected reference is source-only until one fresh neutral 600-second
probe confirms it. That result and its exact teardown must be independently
reopened before the new 120-task control epoch can be prepared. The fresh
control root has its own ordered one-use intents and 1,200-second leases.
Ancestor checks project out only the fresh descendant metadata; the current
history separately retains and hashes the closed v13 failure and includes its
conservative lease. Completed neutral diagnostics are included in the new
history. No old control credit or old failed root is replayed.

Focused checks cover raw-versus-projected truthfulness, timestamp observation,
rejection of payload/structure/owner changes, mutation of another application
file, generated probe syntax, paid-entry refusal and nested ancestor
manifest/accounting behavior after a new intent. Related model-wire fixture
tests also passed under the pinned native host. These are offline code checks;
actual v16 neutral and control execution remain root-side work.

First create the explicit projected reference:

```sh
python -m tools.probe_desktop_projected_identity_v16 reference \
  --old-reference <preserved-original-guest-reference> \
  --old-manifest <preserved-scoped-original-manifest> \
  --archive-evidence <v15-member-evidence-and-structural-proposal> \
  --reference <new-projected-reference>
python -m tools.probe_desktop_projected_identity_v16 prepare \
  --control-freeze <closed-v13-source-freeze> --reference <new-projected-reference> \
  --output <fresh-work/full-study/neutral-v16-root> --freeze <private-neutral-freeze>
```

After exact source review, `review` creates one permit and `run` requires
`--enable-paid-probe`. Following a verified neutral result, prepare the control
epoch using `native_desktop_factory.selection_control_structural_epoch_v16`,
including the neutral v14/v15 roots as `--diagnostic-root` and v16 as
`--neutral-root`. Its `review` writes one fresh trio permit. The corresponding
worker is `native_desktop_factory.selection_control_structural_worker_v16`.
Official model results and final admissions remain zero.
