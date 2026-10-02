# Explicit window relation and frame witnesses

The actual V34 read observed one managed Calc client and two native frame identities, with matching document-title/process/bus but different geometries. No coordinate tolerance or ownership shortcut was applied. V35 is an additive read-only diagnostic for an explicit native relationship and actual X11 frame/tree evidence. All previous sources and refusals stay unchanged.

The preserved coordinate path is internally consistent: V30 requests `Component.get_extents(SCREEN)`, derives a physical point from those screen coordinates, and V31 requests `get_accessible_at_point(..., SCREEN)`. [GNOME CoordType](https://gnome.pages.gitlab.gnome.org/at-spi2-core/libatspi/enum.CoordType.html) defines SCREEN relative to the screen and WINDOW relative to a top-level window. The primary [LibreOffice 7.3 reference bridge](https://github.com/LibreOffice/core/blob/libreoffice-7.3.7.2/vcl/unx/gtk3/a11y/atkcomponent.cxx) subtracts `getLocationOnScreen` for SCREEN before the UNO point lookup, and uses a different origin for WINDOW. No reader coordinate-mode bug is established by these sources; no 24- or 25-pixel correction is introduced. The reference tag is not asserted to identify the live guest's exact build.

The actual 2.44 GIR confirms `Accessible.get_relation_set`, `Relation.get_relation_type`, `get_n_targets` and `get_target`. V35 captures each actual relation type and each target's native bus/object identity, PID, role and geometry, with bounded errors/counts. It does not read target names, cells, text or values. [GNOME relation semantics](https://gnome.pages.gitlab.gnome.org/at-spi2-core/libatspi/enum.RelationType.html) distinguish grouping, logical child relations, subwindows, cross-process embedding and popups. The [LibreOffice relation interface](https://api.libreoffice.org/docs/idl/ref/AccessibleRelationType_8idl_source.html) and [primary GTK bridge relation mapping](https://github.com/LibreOffice/core/blob/libreoffice-7.3.7.2/vcl/unx/gtk3/a11y/atkwrapper.cxx) also distinguish MEMBER_OF, SUB_WINDOW_OF and NODE_CHILD_OF. None of those relations alone grants actor ownership or bypasses the original parent refusal. Context7 was checked before the primary references.

The physical witness reads the actual `_NET_FRAME_EXTENTS`, `WM_TRANSIENT_FOR` and window-type property output. Missing extents remain unknown, not zero. When the actual four borders are available, the decorated box is calculated by the [EWMH frame-extents definition](https://specifications.freedesktop.org/wm/latest/ar01s05.html). This is measured arithmetic, not a geometry tolerance. Direct X11 root/parent/child IDs are read using `xwininfo -children`; recursive tree enumeration is unused. Actual parent-frame and immediate-child geometries are retained. Transient status and a matching box remain diagnostic facts, not ownership authority.

Relations are limited to 16 per source node, eight targets per relation and 64 targets per node. Actual relation counts are recorded before cap refusal. The unchanged native parent cap is 32. Direct X11 children are capped at 64. The private journal remains exclusive mode0600 and bounded; the full guest command remains 45 seconds with a 55-second request. No cache clearing, environment change, GUI input, actor/model call or native ownership amendment is made.

Source check:

```bash
PYTHONPATH=.:src python -m unittest discover -s tests -p 'test_native_desktop_window_relation_diagnostic_v35.py' -v
```

Six offline tests cover measured extents, unknown extents, actual transient/direct-tree parsing, tree and relation count refusal, actual relation-target identity without ownership promotion, and the preserved SCREEN request call path. They do not qualify a native runtime.

After a separate root review, copy the exact V23/V24/V27/V30/V31/V33/V34/V35 peers into the reviewed fresh guest namespace and run one bounded command after the unchanged bootstrap/public TRAIN setup:

```bash
GI_TYPELIB_PATH=/tmp/envloop-atspi-v25 python3 /tmp/envloop-native-common-v31/native_window_relation_diagnostic_v35.py --filename ACTUAL_OWNED_TRAIN.xlsx --width 1280 --height 800
```

The fixed private journal is `/tmp/envloop-native-window-v35-facts.private.jsonl`; root readback must verify its declared hash/bytes and actual mode, including partial failure evidence. No guest is authorized by this document. All original forty-source bytes remain unchanged, and native qualification remains false.
