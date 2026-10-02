# Odoo private-evidence permission repair

The [aggregate repair receipt](odoo-private-evidence-hardening-2026-09-28.json) records a mode-only repair of the three historical Odoo Community 18.0 private task worlds. Before any change, the worker leases were idle and their event logs were balanced. The pinned Compose file used named database and filestore volumes; none of the private task directories was a mount point. While holding all three exclusive worker locks, the repair wrote a mode-0600 private journal containing each affected path's prior mode, size, inode, and SHA-256 (file bytes or a directory-entry listing), then changed only permissions. It rechecked each path before and after its change and wrote a separate private completion journal.

| Partition | Directories changed to 0700 | Files changed to 0600 | Permissive paths remaining |
| --- | ---: | ---: | ---: |
| Train | 8 | 23 | 0 |
| Selection | 3 | 8 | 0 |
| Hidden candidate | 4 | 8 | 0 |
| **Total** | **15** | **39** | **0** |

All 54 affected paths retained their size, inode and content digest. A separate owner-read preflight read every private file and used each partition's worker configuration and v0.6 task-set validator without starting Docker or calling a provider. The [post-repair offline audit](odoo-offline-candidate-evidence-hardened-2026-09-28.json) again rebuilt all 140 historical source assets and task packages and rechecked their per-ID GUI positive, wrong-object negative, lease and reset receipts. It now reports owner-only private permissions with no violations. The public receipts bind the private journals and the evaluator-only per-ID report by SHA-256; private paths, IDs, prompts, gold and credentials are not published.

This repair does not rerun Odoo live, recheck the current actor ACL or SQL privileges, test a v0.6.6 model action, or supply the six-cell pre-campaign witness. It does not admit hidden final tasks or create a model result. **Official Odoo final tasks: 0/100; campaigns: 0; model attempts: 0.**
