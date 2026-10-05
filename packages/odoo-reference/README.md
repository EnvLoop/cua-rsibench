# Public Odoo reference controls, additive v5

This package prepares one public synthetic purchase-order demo in a **new, owned local Docker Compose project**. The reference uses the Odoo GUI to repair one RFQ, and then changes a different RFQ as a negative control. A SELECT-only PostgreSQL verifier independently expects the score sequence `0 / 1 / 0`. Each control starts from the same cold checkpoint. The public demo is known-answer, nontraining reference validation; it grants no hidden-set qualification or formal benchmark admission.

The package contains two explicit synthetic RFQs and generated supplier PDFs. It contains no hidden evaluation tasks, credentials, historical results, private authority files or private-loader imports. A new package source binding covers its vendored native guard, reviewed read-only diagnostic observer, saved audit, and Compose configuration. Historical private control results do not transfer to this source binding.

## Requirements

Python 3.11 or newer, Docker with Compose, and a local Playwright Chromium installation are required. The Compose file pins PostgreSQL and Odoo 18 image digests and binds Odoo only to `127.0.0.1`. A local built-in administrator is used for this isolated demo; no additional Odoo user account is created. Random local passwords are generated after execution approval and stored only in a mode-0600 file in the fresh workspace. No external model or Tinker dependency is present.

From a clean checkout of this directory:

```sh
python -m pip install .
python -m playwright install chromium
python -m unittest discover -s tests -v
```

The tests use synthetic pages, screenshots and local files. They trap native browser, RPC and Docker constructors. They test actual diagnostic probe execution with real exclusive file creation, both original visibility predicates, repeated conflicts, conditional-final samples and saved audit3 selector-prefix reconstruction. Tests also reject absent target rows, duplicate identities, invalid numeric comparators, protected source changes and incomplete cleanup.

## Prepare and review

Choose a new workspace directory, a separate new preparation directory, a free unprivileged port and your local Docker context. Preparation writes source hashes, the exact plan, a review template and argv; it does not start Docker or a browser.

```sh
odoo-reference prepare \
  --stage "$PWD/review-demo" \
  --workspace "$PWD/run-demo" \
  --port 18098 \
  --docker-context default
```

Review `review-demo/plan.json`, `root-review-template.json`, source-lock contents and the source code. After review, write the **exact reviewed template bytes** to `review-demo/root-approval.json` with mode 0600. Calculate its SHA256 and replace the approval-hash placeholder in `argv.json`. Execute that exact argv once. The CLI consumes the approval before any native construction. Existing workspace, project containers, volumes or networks cause refusal. The namespace must start with `odoo-ref-demo-`; there is no resume or automatic retry.

The CLI config records paths at preparation time. No personal absolute path is embedded in the distributed package.

## Control and evidence lifecycle

Trusted fixture bootstrap creates the two public RFQs, PDFs, read-only SQL role and full database/filestore checkpoint. Login and initial purchase-route setup precede each actor. Every actor mutation then goes through the vendored native guard with the original 90-action, 720-second limits, current frame, owned application, principal, lease, focus and hit checks. Selection uses explicit guarded focus, platform select-all and insert actions.

Positive and wrong-object phases each restore the original checkpoint before construction of a fresh actor. The reference opens the original public PDF through the GUI in the positive phase, edits the price and uses the original Save helper. After the original Save, v5 performs exactly one normal guarded click on the uniquely visible existing active form tab. It proves the same current DOM control, native reference and eligible owned focus before continuing. It requires the original native window identity both before and after the click. The original native metadata capture may register its focus reference; v5 retains the preceding sample and reopens the same DOM element after that capture to verify its current reference. BODY/HTML focus is refused; no focus setter, additional Save, alternate-control fallback or action retry exists. The strict observer is unchanged. The additive observer records current indicators, both visibility predicates, full ancestor style chains, native identity, URL, focus and raw frames. It requires positive Saved state and zero controls visible under the original Playwright predicate for `.25` seconds, within the fixed `30` seconds and `.1` second polling interval. Unknown scope or ownership is a hard stop. It performs no UI input or action retry. Different times are recorded separately; URL/page/context continuity is checked without claiming an immutable document-generation token.

The actor writes its end proof before evaluator reload and persisted SQL readback. The final reset saves the persisted business snapshot and complete filestore manifest while the owned web service is stopped, then restores the original services. Scoring protects selected business fields, global record identities, attachment store paths and source bytes. The full database archive is restored; snapshot equality covers the explicit SQL projection. The saved audit reopens guard dispatch evidence, raw diagnostic frames, selector prefixes, checkpoints, persisted scores and full cold reset evidence. Success requires exact `[0,1,0]` and every cleanup gate to be boolean `true`. The negative phase must additionally satisfy the wrong RFQ's expected persisted change, so a zero target score alone cannot pass. Initial failure and cleanup failure remain separate.

```sh
odoo-reference audit --workspace "$PWD/run-demo"
```

CLI output contains only scores, counts, booleans, hashes and fixed failure codes. Runtime artifacts remain private under `run-demo/private/`. Keep credentials, raw frames, SQL snapshots and run directories out of source control. Failed resources and evidence are retained for inspection. This package never prunes Docker or cleans up an existing project.

This package was reproduced from its clean installed wheel on 2026-10-05 in one fresh local Odoo 18 project. The persisted score trio was **0 / 1 / 0**, with 28 actual guarded actions and all seven reset gates independently verified. A separate process and independent reviewer reopened the saved evidence and obtained the same audit. The public [scalar validation receipt](validation/native-train-v5.json) records counts and hashes. This is one public synthetic reference demo; model calls, training and official model admissions remain zero.
