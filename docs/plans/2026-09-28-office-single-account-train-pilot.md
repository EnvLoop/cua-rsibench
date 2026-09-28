# Single-account original Office train pilot

Goal: accept one bounded, manually operated PowerPoint-for-the-web or
Excel-for-the-web **train** source without requiring a second Microsoft
account or Entra application registration. The local evaluator retains
the source, task specification, reference answer and independent verifier.
The existing signed-in test account opens only the current cloud task item
in a dedicated folder, saves through the original Office GUI, and manually
downloads the exact item twice. A distinct neutral copy provides a fresh
reset; the folder is cleared afterward.

The auditor checks source/task hashes, strict train URLs and distinct cloud
document IDs, private operator-reviewed folder inventories (one actor item,
then one reset item, then empty), screenshot hashes, six downloaded files,
pair equality, source-equivalent initial state, independently scored saved
positive with no-regression, and semantically neutral reset. It emits only
a private development-control receipt plus a field-limited public status
with zero official final and selection credit. It never calls a provider,
Graph, browser, E2B, Tinker or model API.

The dedicated-folder inventory is operator-attested by screenshots, not an
independent account ACL. The signed-in account may have access to other
files outside the folder; no result from this pilot can satisfy the stricter
two-account hidden-set isolation or full 20/20/100 admission. Use the
two-account Graph lease only as an optional higher-assurance track.
