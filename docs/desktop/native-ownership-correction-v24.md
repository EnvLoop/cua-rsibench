# Observed native ownership correction

The authorized diagnostic ran in one actual original Desktop guest after the current public TRAIN source, guest content and profile attestations. It made no model request and no actor GUI step. The diagnostic result hash is recorded in the public facts receipt.

The process and probe both used UID 1000; all four process UID fields matched. The actual X11 pair was `libreoffice` / `libreoffice-calc`. The executable was `/usr/lib/libreoffice/program/soffice.bin`, 14488 bytes, SHA-256 `65bab645455ca7fe2f38e61f5d36b84dc02c229594d6c0598b5078a819d4f43a`. That exact file/size/hash also matched the reopened current guest-content manifest. The frozen v23 predicate rejected the class because it required a `soffice` substring. Its rejection is preserved.

The additive v24 helper requires the exact observed LibreOffice instance/class pair, the document's application type, equal process/probe UID, the expected executable path and attested executable hash. It leaves the original PID/window/title/document and native GI/AT-SPI checks in place. It rejects arbitrary class strings, wrong UID, wrong executable/image and unobserved application types. Impress and Writer remain source candidates until actual native evidence is available.

The owned guest's automatic cleanup returned a transport `WriteError`, so this attempt does not claim confirmed cleanup. Its raw handle and receipts were preserved and handed to the root controller for recovery. No kill or create was replayed. A pre-provider interpreter import failure was separately preserved; the successful diagnostic used the pinned native SDK interpreter rather than the unit-test interpreter.

A next root-reviewed probe must copy these two exact files together:

```plaintext
/tmp/envloop-native-ownership-v24/native_accessibility_probe_v23.py
/tmp/envloop-native-ownership-v24/native_accessibility_probe_v24.py
```

Then, after the same guest/profile attestation and actual owned Calc document open:

```bash
python3 /tmp/envloop-native-ownership-v24/native_accessibility_probe_v24.py \
  --filename ACTUAL_OWNED_FILE.xlsx --width 1280 --height 800
```

The new source proposal is `native_accessibility_ownership_epoch_v24.proposal()`. This is a prospective source correction, not a native qualification or model result. GI/AT-SPI availability, target/focus/hit semantics and the common seven-path guard still require actual native proof. The older probe, failed attempts and source epochs remain unchanged.
