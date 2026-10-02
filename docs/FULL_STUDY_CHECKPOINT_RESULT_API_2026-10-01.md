# Checked private checkpoint results for selected Desktop execution

Selected Desktop execution called `_checkpoint_result(...)["sampler_path"]`,
an accessor present only in its test fixture. The real `CampaignSession`
did not implement that method, and the actual SFT provider result contains
`checkpoint_path`. A qualified selected run would therefore fail before
opening the native task.

`CampaignSession.checkpoint_result(event)` now reopens one registered
checkpoint event and its private paid request/result. It verifies the paid
ledger and journal hashes, ordered intent/result/checkpoint events, exact
cell and researcher ownership, round and dataset lineage, frozen training
source and schedule, result schema, reported Qwen base model, and exact
checkpoint URI hash. The URI remains private. Missing registration, changed
bytes/permissions, extra fields, or wrong lineage fail closed.

Desktop calls this real API and reads `checkpoint_path`. The common base,
four researcher slots, action policy, renderer, reset, verifier, candidate
selection rule, and paid reservation protocol are unchanged. The prospective
Desktop source closure now includes the campaign source and regression test.
No old source freeze or running episode may silently acquire these bytes.

Seven focused tests use the actual `CampaignSession` class with synthetic
six-cell artifacts and fake provider callbacks. They cover the real SFT
result, wrong cell/researcher, changed checkpoint, extra result field, wrong
base model, unregistered events, private-file drift, training-source drift,
and selected Desktop execution reaching the package boundary only after the
checked read. The negative selected test stops before any package, sampler,
or environment callback. Together with campaign/transport regression tests,
**43 tests passed in 69.681 seconds**. No real provider, native task, or hidden
task body was used.

This is an isolated source correction. Import it only after the already
running diagnostic finishes, then prepare a fresh model source binding.
Qualification, shared-base results, billing settlement, full researcher
chains, and final results remain separate gates.
