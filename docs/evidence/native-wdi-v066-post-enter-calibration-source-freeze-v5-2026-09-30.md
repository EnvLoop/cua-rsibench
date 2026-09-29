# Desktop post-Enter calibration: main-checkout source freeze

The [main-checkout freeze](native-wdi-v066-post-enter-calibration-source-freeze-v5-2026-09-30.json) rebinds the reviewed public-train Calc/Writer calibration source to a new private reservation and unused three-guest output root. Its private freeze SHA-256 is `46175db7988cda77a74d83b4cc280758da4317c6b22fffe2852423f063a00796`. The source-file hashes match the earlier isolated [v4 source freeze](native-wdi-v066-post-enter-calibration-source-freeze-v4-2026-09-30.json); the private paths and reservation do not carry over from that checkout.

This is a source-only freeze with no provider create or dispatch authority. The proposed run uses two unchanged public-train saved-file positive demonstrations and one fresh Calc cold-reset guest, with exact independent review and a separate private permit required before execution. It does not touch the quarantined final identity, admit any official task, or establish a model result.
