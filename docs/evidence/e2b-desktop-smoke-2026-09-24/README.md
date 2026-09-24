# E2B Desktop / Calc one-sandbox smoke receipt

On 2026-09-24, one disposable E2B Desktop sandbox ran for **159.625 seconds of local test elapsed time**, below its configured **540-second** cloud timeout. The sandbox identifier is omitted; its SHA-256 is `0f743fe9f0c20348dbd47ac67ec8ef090d76b805f9810a03d137cddda48af933`. No API key or user document was placed in the evidence.

The cloud desktop reported **LibreOffice 7.3.7.2**, and the GUI screenshot shows **LibreOffice Calc** editing a new workbook. After entering synthetic A1 text and B1 number through desktop keyboard actions, the GUI saved `e2b_calc_smoke_20260924.xlsx` in Excel 2007–365 format. The [saved screenshot](calc-saved.png) has SHA-256 `6534265960111ea670a6c61dcfdfca7db28607591af01f8d308be19a4edf2e94`. The [downloaded XLSX](calc-smoke.xlsx) has SHA-256 `155ebc1e2d8aa977def8e21c85f54842295d9a6d104d9d41af698aebe5d52cdb` and is 4,787 bytes. A separate local Python `zipfile`/`ElementTree` parser read **A1 = `E2B Desktop smoke`** and **B1 = `1729`** from its worksheet XML; both matched the expected values. This readback did not use Calc's displayed cell values.

The SDK `kill()` call returned `true`; the subsequent `is_running()` check returned `false`. These results, timing, file hashes, and GUI stage evidence are recorded in [receipt.json](receipt.json). The [script](../../../tools/e2b_desktop_calc_smoke_20260924.py) made one `Sandbox.create()` call, used a server-side timeout, and killed the sandbox in `finally`.

The trace includes one `CommandExitException` from an optional pre-save status probe that ended with a test for the XLSX before it existed. It did not affect the GUI operation or final readback. The script's status probe was corrected after this run; no second sandbox was started.

**Cost estimate, separate from observed billing.** [E2B's official pricing](https://e2b.dev/pricing) lists default 2-vCPU compute at **$0.000028/s** and default 4-GiB RAM at **$0.000018/s**, billed by running second. Assuming that default resource size and conservatively charging the full 159.625 seconds of local elapsed time, estimated usage is **$0.00734**. The 540-second timeout would cap that same resource assumption at **$0.02484**. This is a rate-based estimate; the account's actual invoice or credit use was not checked.

This verifies a Linux LibreOffice Calc desktop action and saved-file readback. It does not establish Microsoft Excel, OneDrive, an OSWorld task result, reset behavior, or a benchmark score.
