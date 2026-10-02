# Evaluator-owned Graph one-file lease plan

**Goal:** Automate a bounded single-file Office actor grant and exact-ID revocation for PowerPoint/Excel without giving the actor model a Graph API or credential.

**Architecture:** A private lease specification pins owner, actor, drive, item, parent and sentinel identities, source/task/action hashes, and a separately witnessed train-only account-capability receipt. An evaluator-only client verifies distinct delegated owner/actor identities and scope evidence, then commits a hash-chained intent before a single `invite` POST. It stores the one returned permission ID privately, probes actor target access and parent/sentinel denial, and later commits an exact-ID DELETE intent. Owner-side effective-permission readback proves actor and broad-link absence while preserving owner/inherited permissions. Ambiguous writes are never replayed automatically; read-only reconciliation may adopt a uniquely observed grant or confirm a completed deletion.

**Implementation steps**

1. Validate private input/source references and a real capability receipt. No writable endpoint is reachable when owner/actor tokens or the verified personal-account scope receipt are missing.
2. Add no-retry Graph v1.0 transport with allowlisted drive/item endpoints and separate owner/actor bearer tokens; never log them or send them to a model.
3. Add mode-0600 fsynced hash-chain journal, private exact request/response files, one-writer lock and terminal state reducer. Persist invite/delete intent before sending; preserve uncertain status after timeout, crash or ambiguous response.
4. Verify the `invite` response is exactly one direct specific-person write permission with `signInRequired=true`, `sendInvitation=false` in the recorded request, no link, exact actor email and new permission ID. Verify actor GET target 200 and parent/sentinel 403/404; preserve receipt hashes.
5. DELETE only that permission ID; inspect owner effective permissions by exact drive/item. Reject the old ID, actor identity, anonymous/organization/unidentified links and unexpected direct grants. Keep owner/inherited entries.
6. Test fake success, wrong owner/actor, existing broad link, 207/multiple invite responses, uncertain invite and delete, crash/restart, tampered journal, duplicate dispatch, owner/inherited retention, and missing capability receipt. Run full suite and publish an English boundary note. No live Graph/browser/E2B call in this task.

**Personal OneDrive caveat:** Microsoft Graph v1.0 documents delegated personal `Files.ReadWrite` for invite and permission DELETE on non-root driveItems. The documented request permits `sendInvitation=false`, but this account's actual silent-invite, permission response and actor redemption have not been verified. The controller stays disabled until a bounded original-software train pilot provides that evidence and valid delegated scopes.
