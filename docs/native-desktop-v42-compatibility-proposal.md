# V42 compatibility proposal — unadopted

V41 remains frozen and unqualified. Its source binding is
`2022b3d8c64713875dd2592841b9b2697a8c451b64db2f81c9ae62e5b7f2c1d7`.
No V42 native guard or eligibility path is implemented by this proposal.
The latest Calc reference applied a Review-tab click and wait, then stopped
before a business edit. Its saved verifier, business positive and fresh-reset
credits remain zero. All owned sandboxes were confirmed stopped.

## Actual deployed evidence

The retained read-only runtime receipt records LibreOffice core/GTK3
`1:7.3.7-0ubuntu0.22.04.11`, GTK3
`3.24.33-1ubuntu2.2`, AT-SPI2 `2.44.0-3`, ATK `2.36.0-3build1` and the ATK bridge
`2.38.0-3`. The actual process mapped `libvclplug_gtk3lo.so`, SHA256
`6c86e9d5c6cbcde4f6556f4c646ebf196e9cf3407758918afa8f8ea33bf6f823`.
Its current typed class was `libreoffice-calc`; process and probe UID were 1000.
The staged public TRAIN document was owned by UID/GID1000, mode0644, writable
by the actor UID, and independently reread equal to its original bytes.
The filtered bridge environment contained only `DISPLAY=:0`; GTK3 was already
loaded. The attested executable remains
`/usr/lib/libreoffice/program/soffice.bin`, SHA256
`65bab645455ca7fe2f38e61f5d36b84dc02c229594d6c0598b5078a819d4f43a`.

Actual native tables reported ENABLED=true, EDITABLE=true and a focused table,
while SENSITIVE=false was retained verbatim. V41 therefore admitted no editable
keyboard target. Cache.NONE was already active and did not change this state.
The coordinate repair is separately proved: `xwininfo` client origin(0,51),
size1280×749, maps the original Review-tab pixel to its actual native page-tab
leaf in WINDOW coordinates. Name Box still lacks a terminal leaf proof.

## Primary source explanation

LibreOffice7.3's [Calc spreadsheet state provider](https://github.com/LibreOffice/core/blob/libreoffice-7-3/sc/source/ui/Accessibility/AccessibleSpreadsheet.cxx)
adds EDITABLE, ENABLED, FOCUSED and other states, but omits SENSITIVE.
The [document](https://github.com/LibreOffice/core/blob/libreoffice-7-3/sc/source/ui/Accessibility/AccessibleDocument.cxx)
and [cell](https://github.com/LibreOffice/core/blob/libreoffice-7-3/sc/source/ui/Accessibility/AccessibleCell.cxx)
providers likewise omit it. The [GTK3 ATK wrapper](https://github.com/LibreOffice/core/blob/libreoffice-7-3/vcl/unx/gtk3/a11y/atkwrapper.cxx)
maps ENABLED and SENSITIVE independently and emits only supplied UNO states.
Thus switching an already GTK3 process to GTK3 again does not supply the absent
state. No environment-only repair is demonstrated.

Spreadsheet `IsEditable()` checks formula mode and sheet protection. It does
not check document UI read-only mode. EDITABLE plus file permissions alone is
therefore insufficient to prove permission to edit this current document.
The [EditDoc command state](https://github.com/LibreOffice/core/blob/libreoffice-7-3/sfx2/source/view/viewfrm.cxx)
provides a native GUI read-only check: SID_EDITDOC's bool state reflects the
inverse of `SfxObjectShell::IsReadOnly()`. The associated native Edit Mode
checkmark must be reopened in the current owned document before using it.
Medium/file writability and sheet/cell editability remain separate checks.
The [native menu accessibility provider](https://github.com/LibreOffice/core/blob/libreoffice-7-3/accessibility/source/standard/vclxaccessiblemenuitem.cxx)
reports CHECKED directly from the current menu item's checked state, and the
GTK3 wrapper maps that state directly. A unique current enabled Edit Mode item
with CHECKED=true is positive evidence; absence of a state is not evidence.
The retained base content lists only the gen and GTK3 VCL plugins, so a Qt/KF5
environment switch is not established on this deployed image.

## Proposed eligibility contract

An additive V42 scope may accept a source-backed sensitivity capability only
after every condition below is demonstrated. It must preserve raw SENSITIVE=false
and place capability evidence in a separate receipt. It must never report that
the missing native flag was true.

1. Pin the exact installed LibreOffice/GTK/ATK build and mapped plugin/executable
   hashes. Limit the exception to the source-proved Calc document/spreadsheet/
   cell roles; unsupported roles/builds keep the ordinary native predicate.
2. Reopen the same owned current document with exact UID, PID, native bus/object
   identity, typed class, executable, ACTIVE title, lease and verified X11 client
   projection. Reuse the strict current physical zero-child-leaf hit proof.
3. Require native ENABLED and EDITABLE, safe visible/showing non-stale ancestors,
   and the actual currently focused editable editor. Reject a false ENABLED,
   protected/noneditable cell, unrelated editor, foreign principal or unknown
   current focus. Ordinary non-VCL controls still require actual SENSITIVE.
4. Require current native Edit Mode CHECKED with source-bound command identity,
   plus medium/file writable evidence and the exact target's native editability.
   Missing, unchecked, disabled or ambiguous read-only evidence rejects.
5. Use one new class/source binding for every actor role. Preserve V38–V41
   observations and failed controls without promotion. Require fresh positive,
   near-miss and distinct-reset qualification before any model/training credit.

Before adoption, test genuine disabled and read-only documents, a protected
cell, unsupported build/role, wrong editor/focus, foreign/stale identity and
uncertain input. If a trusted reversible selection-only diagnostic is used,
record it as responsiveness evidence with zero business/model/qualification
credit. It must not silently replay a failed or uncertain actor action.
# Historical proposal

This document records the pre-implementation V42 proposal. Its statements about an unadopted path or missing implementation describe that earlier point in time. See [current Native Desktop build status](native-desktop-build-status.md) for tested source, actual evidence, and remaining gates.
