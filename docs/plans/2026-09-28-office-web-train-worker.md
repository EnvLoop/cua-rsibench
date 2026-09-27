# PowerPoint Web train-only teacher worker plan

**Goal:** Feed the frozen Qwen v0.6.6 teacher collector one original PowerPoint-for-the-web training episode with independent saved-file and fresh-copy reset evidence.

**Architecture:** A private task binding selects one authorized PowerPoint training deck and a distinct neutral reset copy. The shared teacher adapter owns the model calls and E2B dollar ledger. This worker owns the two bounded E2B desktop leases, manual actor login/single-file ACL gates, screenshot/action loop, owner-side double downloads, independent WDI PPTX scorer, and exact private receipts consumed by `collect_train_batch`. No selection or final package is opened.

**Provider boundary:** The actor moves only through v0.6.6 screenshot-grounded E2B GUI primitives. A separate evaluator uses a delegated Microsoft Graph owner token for read-only download of the exact drive/item identity, verifies stable metadata plus identical bytes across two downloads, and runs the frozen OOXML verifier. The owner token and all cloud locators remain in ignored private `work/`. A missing login, permission snapshot, Graph token, rate cap, readback, or reset proof stops the episode.

**Steps**

1. Parse and hash-check the private task binding and normalized baseline before an E2B lease.
2. Reserve an actor E2B lease through `dispatch_e2b`; create a secure desktop through the existing manual-login bridge, then require an operator-reviewed one-file ACL receipt bound to that sandbox and exact deck URL.
3. Recheck the owner-side cloud item against the normalized baseline, open the assigned deck in Chrome, and run at most the frozen action count through current screenshot observations and the v0.6.6 dispatcher. Persist frames and the exact teacher trace with fsync.
4. Stop the actor desktop, double-download the assigned cloud item from the independent owner account, and require target success plus no unrelated PPTX changes.
5. Reserve a *new* reset E2B desktop, require a distinct one-file ACL receipt for a distinct neutral copy, open that copy in the native Office GUI, and double-download it from the owner. Require zero target changes, no unrelated changes, and task-equivalent baseline state.
6. Write only the exact private episode, saved-state, and reset receipts accepted by the shared teacher adapter. Fake desktop/Graph tests cover source mismatch, ACL denial, changed frame, partial save, duplicate download mismatch, reused sandbox, and reset drift. No paid or cloud call runs during these tests.

The current environment lacks a signed-in E2B Office actor session, a verified owner Graph token, and a six-cell ratification. A passing offline test is not an admitted real training episode or a campaign result.
