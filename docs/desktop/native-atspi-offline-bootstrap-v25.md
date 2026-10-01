# Offline AT-SPI typelib prerequisite

The actual v24 Calc probe passed the corrected ownership checks, then returned `Namespace Atspi not available`. The guest closed with acknowledged kill and `is_running=false`. The saved guest manifest contains the native library, bus launcher and registry, but no Atspi typelib. This result is infrastructure evidence; no tree, focus or target was qualified.

The official Ubuntu Jammy package is [gir1.2-atspi-2.0 version 2.44.0-3](https://packages.ubuntu.com/cs/jammy/gir1.2-atspi-2.0). Its amd64 archive SHA-256 is `c471afd53d03216643cb5fb7d3e0587b27a6bda84d44bc67f566beadbd693781`. The included `Atspi-2.0.typelib` is 54164 bytes, SHA-256 `210580f698add0a1607ee01e177d93d3b6bdb0fdcfc908e8c1b5c7ebbb503b62`. The official package's libatspi library matches the existing attested guest bytes exactly; no library upgrade is required. The retained upstream copyright accompanies the pinned asset.

This source adds only that offline typelib under a fresh trusted setup prefix. It performs no apt/network operation, replaces no existing library/service, changes no GUI setting and touches no task document. The installed native dependency hashes and `/usr/lib/os-release` must match the observed guest. Bootstrap must happen before LibreOffice profile/task preparation; a nonfresh profile or setup prefix fails. Only the probe child receives the additional `GI_TYPELIB_PATH`.

A prospective derived template can use the official [E2B custom desktop template API](https://github.com/e2b-dev/desktop/blob/main/template/README.md), but this minimal source packet does not build a cloud template. Fresh source and supplemental native-content attestation are required for all seven actor paths even though the older content projection excludes `/tmp`. No older guest/result is promoted.

## Source-only host preparation

```bash
PYTHONPATH=.:src python -m native_desktop_factory.native_atspi_epoch_v25 \
  prepare-host-bundle --out work/fresh-atspi-bundle.private
PYTHONPATH=.:src python -m unittest tests.test_native_desktop_atspi_bootstrap_v25
```

## Next root-reviewed fresh guest sequence

Copy the pinned asset and bootstrap helper into a trusted incoming directory before opening a task or creating the LibreOffice profile. Then:

```bash
python3 /tmp/atspi-incoming/native_atspi_bootstrap_v25.py check \
  --typelib /tmp/atspi-incoming/Atspi-2.0.typelib
python3 /tmp/atspi-incoming/native_atspi_bootstrap_v25.py apply \
  --typelib /tmp/atspi-incoming/Atspi-2.0.typelib
python3 /tmp/atspi-incoming/native_atspi_bootstrap_v25.py namespace
```

Retain the base content/profile proof and an independently reopened supplemental attestation containing both typelib and bootstrap/source hashes. After the normal owned Calc document preparation, copy the unchanged v23 plus corrected v24 probe beside each other and run:

```bash
GI_TYPELIB_PATH=/tmp/envloop-atspi-v25 python3 \
  /tmp/atspi-incoming/native_accessibility_probe_v24.py \
  --filename ACTUAL_OWNED_FILE.xlsx --width 1280 --height 800
```

Namespace availability alone is insufficient. The next native probe must establish actual bus/service access, owned window/PID/UID, native tree bounds, focus and accessible-at-point target safety. Calc, Writer and Impress require their real native evidence before the common source epoch can qualify. Unknown/partial trees remain infrastructure failures; no static canvas fallback exists.
