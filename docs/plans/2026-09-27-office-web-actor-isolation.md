# Office-web actor and evaluator isolation

**Status: implementation proposal with an offline pre-model evidence gate; no
live ACL proof, model result, saved-file qualification, or final admission.**
The existing PowerPoint and Excel E2B runners are train-only. Their OneDrive
URL filters prevent many mistaken routes, but a valid URL cannot establish
which Microsoft account is signed in or what else that account can open. The
evaluator account already holds sealed final items. Signing that account into
the model's browser would expose those items through normal OneDrive UI even
if the runner initially navigates to a train URL.

## Choice and threat boundary

| Route | Benefit | Publication problem |
| --- | --- | --- |
| Evaluator account in the actor desktop | No second login | Reject: actor can browse evaluator-owned sealed items. |
| One fresh, anonymous file-edit link in a signed-out desktop | Lowest login overhead | Link is a transferable bearer capability. Microsoft documents that anyone holding it can access the item; anonymous editing and app behavior need a real-account pilot. Keep this as a separate, lower-assurance train experiment. |
| **Dedicated actor Microsoft personal account, one specific-person edit grant on one file** | Identity-bound file access with owner-side permission inventory | Requires one separate account and an authenticated desktop per isolated attempt. Use this route for the first qualifying pilot; scale-out authentication is still unproven. |

Microsoft says OneDrive files are private until shared, that a **Specific
people** link is limited to named recipients, and that sharing a folder with
Edit grants access to its contents. Its personal-account sharing guidance
limits specified recipients to other Microsoft personal accounts. Therefore
the evaluator owns a *fresh copy* of the assigned deck or workbook in a
private folder and grants `Can edit` to a distinct actor account **on that
file only**. No folder grant, `Anyone` edit link, owner login, evaluator
Graph token, source gold, or final item URL enters the E2B desktop. The
actor receives one assigned editor URL and the actor task through the
existing screenshot/action contract. [OneDrive sharing](https://support.microsoft.com/en-us/onedrive/share-files-and-folders-in-microsoft-onedrive),
[external sharing](https://support.microsoft.com/en-us/sharepoint/lists/sharepoint-sharing-and-permissions/external-or-guest-sharing-in-onedrive-sharepoint-and-lists).

## Trusted setup and per-attempt lifecycle

1. The evaluator seals the train/selection/final source manifests and
   baseline bytes outside the actor browser. For a candidate attempt it
   uploads only a fresh actor input copy, resolves its **owner-side item ID**,
   and reads its original-format bytes back to bind the cloud item to the
   intended seed. PowerPoint uses the already stabilized Office-native
   baseline, rather than the pre-normalization OOXML, as the comparison base.
2. In the owner account, grant one specific-person `write` permission to a
   separate actor account. An optional Microsoft Graph implementation can
   use delegated personal `Files.ReadWrite` and `POST
   /me/drive/items/{item-id}/invite` with `requireSignIn: true`,
   `sendInvitation: false`, and a single recipient; Microsoft documents
   that `sendInvitation: false` grants access without notifying that person.
   This is an evaluator operation, never a student action. The owner then
   reads `GET /me/drive/items/{item-id}/permissions` for the file and its
   parent. Require exactly that named file grant and no broad, inherited, or
   folder grant. These API calls are a **design**, not an observed live run.
   [Invite](https://learn.microsoft.com/en-us/graph/api/driveitem-invite?view=graph-rest-1.0),
   [list permissions](https://learn.microsoft.com/en-us/graph/api/driveitem-list-permissions?view=graph-rest-1.0).
3. In a fresh E2B desktop, a trusted operator signs in **only** as the actor.
   Before starting model sampling, capture private evidence that the actor
   identity differs from the owner, the one assigned item is editable, an
   unrelated non-final sentinel in the owner account is denied, and no other
   benchmark item is visible. The sentinel contains no hidden-final task
   material. Keep URLs, account names, screenshots, permission IDs and raw
   Graph responses in mode-0600 evaluator-private files under ignored `work/`.
4. `tools/office_web_actor_scope_gate_v1.py` checks a five-minute, one-session
   receipt against the E2B session hash, sandbox ID, exact assigned URL,
   actor seed hash (Excel), file/parent owner permission snapshots, and four
   private screenshot hashes. It rejects an extra file link, parent share,
   wrong recipient, same owner/actor, stale or missing evidence before an
   E2B connection or model call. Both train-only runners now invoke it at
   admission. **The code validates evidence integrity and asserted operator
   review; it cannot authenticate the Graph server or interpret screenshots.**
   Synthetic unit tests exercise rejection logic and never count as a live
   ACL qualification.
5. After the model stops and its sandbox is killed, the **owner/evaluator**
   downloads the same item twice through an independently authenticated
   owner session, compares bytes and source-bound item identity, then runs
   the task-specific OOXML oracle. Microsoft documents owner-side
   `GET /me/drive/items/{item-id}/content`; its preauthenticated redirect
   must remain private. The actor's own downloaded copy is not the primary
   scoring artifact. [Download content](https://learn.microsoft.com/en-us/graph/api/driveitem-get-content?view=graph-rest-1.0).
6. The owner revokes the exact, non-inherited permission, confirms the file
   permissions no longer include that actor, and repeats the actor denial
   probe. Microsoft documents both Manage access removal and Graph
   `DELETE /me/drive/items/{item-id}/permissions/{permission-id}`. A failed
   revoke or readback is an infrastructure failure, never a zero task score.
   [Manage access](https://support.microsoft.com/en-us/onedrive/sharepoint/manage-sharing-and-permissions-in-onedrive-and-sharepoint),
   [delete permission](https://learn.microsoft.com/en-us/graph/api/permission-delete?view=graph-rest-1.0).

For an official run, repeat this lifecycle on fresh task copies and fresh
actor browser state. No earlier final item may remain accessible in the actor
account; a single sentinel denial is a useful probe but does **not** prove
that all sealed final items are unshared. The evaluator must audit the sealed
final inventory and its parent-folder permissions separately before freezing
the hidden set. One reused actor login can retain recent item names even
after revocation, so its use across official final attempts requires a
measured contamination audit or a clean identity/session strategy. The
current manual-login E2B bridge has neither 3,000-attempt authentication
automation nor a qualified owner readback/revocation implementation.

## Admission meaning

The new pre-model gate is a guard against accidental owner-session use, not
an official ACL proof or scorer. It admits only a train-only pilot after a
trusted operator supplies evidence; it leaves `official_final_admitted = 0`.
The live personal-account share shape, Office editor URL under shared access,
Graph permission response, actor edit ability, owner item/URL binding,
post-run independent readback, revocation, sealed-final ACL sweep, and clean
large-scale authentication all remain **unknown**. Freeze the observed
account and application behavior before deriving an official final runner.
Neither this plan nor its unit tests change the full-study state of **0/600
official final identities and 0/24 researcher campaigns**.
