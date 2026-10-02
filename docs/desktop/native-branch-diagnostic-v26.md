# Bounded native branch diagnostic and visible-query plan

The actual offline typelib bootstrap made Atspi available. The next owned Calc read-only probe reached the native tree but returned `native_accessibility_tree_unbounded`. Its full raw result is retained; no targets or focus were qualified. The v23/v24 caps remain unchanged.

The additive v26 helper records actual role, child count, visible/showing/focused states, bounds, PID/UID and hashed ancestor paths before cap rejection. It records no names, values or document text. Table/Collection interfaces add only structural dimensions; an unsupported optional method records its exception class without discarding the branch facts. It never exposes a partial tree as safe metadata.

## Next root-reviewed diagnostic

Use one fresh owned Calc guest, the same pinned SDK/public TRAIN data/guest and profile attestation, and the approved offline v25 typelib bootstrap before preparation. Copy the frozen v23 probe, v24 owner helper and v26 branch helper into one trusted directory. After document preparation:

```bash
GI_TYPELIB_PATH=/tmp/envloop-atspi-v25 python3 \
  /tmp/atspi-incoming/native_accessibility_branch_diagnostic_v26.py \
  --filename ACTUAL_OWNED_FILE.xlsx
```

Retain the exact sources, bounded stdout/stderr/return code, raw handle-before-wrapper and owned kill/status proof. The result remains diagnostic. Source tests prove cap/error retention and no virtual child enumeration; they do not prove native metadata.

## Prospective visible-surface query

The Context7 AT-SPI index did not document the needed GI Collection calls. The official [Collection.get_matches API](https://gnome.pages.gitlab.gnome.org/at-spi2-core/libatspi/method.Collection.get_matches.html) defines a finite maximum result count and subtree traversal. The installed-version 2.44.0 GIR was inspected from the official Ubuntu development package to confirm MatchRule parameter order and state-match types. A future source reader should request native VISIBLE/SHOWING candidates and FOCUSED candidates with explicit finite caps; overflow remains failure.

[Table row count](https://gnome.pages.gitlab.gnome.org/at-spi2-core/libatspi/method.Table.get_n_rows.html) includes cells outside the viewport. It must not be used to enumerate the full virtual grid. Only actual visible Collection candidates may supply observation targets. Each accepted pointer action then uses native component accessible-at-point and its bounded ancestor chain to verify the requested coordinate, PID/window/account and actual enabled/obscured state. Keyboard input requires actual focused/editable metadata after pointer selection. Unknown hit/collection/focus remains unsafe; a large table rectangle never substitutes for cell state.

The official Collection active-descendant method is documented as unimplemented; no reader should infer focus from it. Writer and Impress need their own actual native type/tree/focus evidence. After the visible prototype qualifies, one shared guest factory must apply the exact offline bootstrap before prepare, run probes with the scoped child environment, retain supplemental content attestation and supply teacher/control/base/four-checkpoint actors. The current v23 source is preserved and unqualified until that new runtime/native epoch is independently replayed.
