# Native ownership failure diagnostic

The first native result rejected the original v23 ownership predicate before GI/AT-SPI inspection. Its stored result did not retain the X11 class or UID values. This additive diagnostic records those facts and then invokes the exact unchanged frozen probe. It does not assume that a class or UID mismatch is benign.

The private output contains the active window ID, PID, real/effective/saved/filesystem process UIDs, probe UID, raw bounded `WM_CLASS`, process executable path/hash/size, and a title hash. It retains completed query stages when a later query fails. It does not read environment, process command line or document text, and it performs no GUI mutation. All facts remain diagnostic; the original ownership failure is retained unchanged.

Copy the two exact source files into the same trusted setup directory in one root-reviewed fresh owned guest:

```plaintext
/tmp/envloop-native-diagnostic-v23b/native_accessibility_probe_v23.py
/tmp/envloop-native-diagnostic-v23b/native_accessibility_diagnostic_v23b.py
```

Then execute the bounded read-only command against the actual already opened owned document:

```bash
python3 /tmp/envloop-native-diagnostic-v23b/native_accessibility_diagnostic_v23b.py \
  --filename ACTUAL_OWNED_FILE.xlsx --width 1280 --height 800
```

Retain stdout, stderr, return code, source hashes and owned guest cleanup proof. The output must contain both `x11_details` and `frozen_probe_result`; it grants no native qualification or model dispatch. Inspect the observed class/executable/UID values before implementing any generic ownership correction. `native_accessibility_diagnostic_epoch_v23b.proposal()` binds the frozen and additive sources explicitly. The original v23 source, raw failures and prior source epoch stay preserved.
