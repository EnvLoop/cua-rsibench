# Native hit identity diagnostic

The actual common V31 Calc development prepare completed the offline bootstrap, current source/profile attestation and independent owned-window lookup. The prepared native read then refused a point object because its parent chain did not reach the owned window under the preserved reader's comparison. Its first failed stage was `physical_hit`; target/focus availability remains unknown. Owned cleanup was verified, with no models, actor actions or qualification credit. The actual probe command SHA is `746216d57f78e8ee0c0abd2113712501be72298eddcacee125199abd5cca1999`; the saved independent audit SHA is `f54b41d378b1c3704e67d1f76ce92a4818cae130dd8f4c7d551b6b28622dbad0`.

V33 is a separate read-only diagnostic. It reuses the exact pinned V31 physical-hit implementation and the unchanged independent ownership lookup. It samples the same center of the actual owned window geometry, captures native identity and parent facts at the first ancestry refusal, and preserves that original refusal. The structural diagnostic does not read node names, text, values or children. The existing owned-window lookup retains its original title comparison; only its title hash is returned. No GUI mutation, ownership relaxation, focus/canvas fallback or qualification promotion is present.

The diagnostic reads the documented AT-SPI object path and application bus name where GI exposes them. It hashes the real bus/object pair and compares it with the independently owned window. Missing fields remain unknown; wrapper addresses and matching PIDs never substitute for native ownership. Each bounded parent record contains its native PID, role, identity hashes, geometry and proxy comparison, with per-field error classes. A matching native bus/object pair with different proxy equality can be diagnosed; a different native window identity can be reported; neither authorizes an action. The existing 32-ancestor cap is unchanged. Mandatory structural facts are streamed to an exclusive mode-0600 trusted guest journal before optional geometry or the next parent query.

Primary references are [GNOME Object](https://gnome.pages.gitlab.gnome.org/at-spi2-core/libatspi/class.Object.html) and [GNOME Application](https://gnome.pages.gitlab.gnome.org/at-spi2-core/libatspi/class.Application.html). Context7 was checked first for native object-reference semantics. The exact 2.44 package headers and GIR confirm `Object.app`, `Object.path` and `Application.bus_name`: [official Ubuntu development package](https://archive.ubuntu.com/ubuntu/pool/main/a/at-spi2-core/libatspi2.0-dev_2.44.0-3_amd64.deb), archive SHA `d95ce746f15480b971bf860d0a8156de00202fee08ce6707a297e90ce68ad1e6`, GIR SHA `f6145d5f54d3b4cec15f66b0e1f2005455177e8e0a9b1c85c1605dd96b94dc99`. This source evidence does not assert that the live guest exposes those fields successfully.

Source check:

```bash
PYTHONPATH=.:src python -m unittest discover -s tests -p 'test_native_desktop_hit_identity_diagnostic_v33.py' -v
```

A separately reviewed one-guest diagnostic would copy the exact V23/V24/V27/V30/V31/V33 peers, use the reviewed V25 offline bootstrap and original public TRAIN setup, then run one command with child `GI_TYPELIB_PATH`, the existing 45/55 bounds and no user-supplied point:

```bash
GI_TYPELIB_PATH=/tmp/envloop-atspi-v25 python3 /tmp/envloop-native-common-v31/native_hit_identity_diagnostic_v33.py --filename ACTUAL_OWNED_TRAIN.xlsx --width 1280 --height 800
```

Its fixed private journal is `/tmp/envloop-native-hit-v33-facts.private.jsonl`; root readback must verify the declared SHA/bytes/mode. No guest is authorized by this document. V31 runtime sources and all terminal evidence remain unchanged, and the common runtime is still unqualified.
