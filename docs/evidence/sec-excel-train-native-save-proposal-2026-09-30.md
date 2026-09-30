# Excel native-save normalization: one TRAIN-derived proposal

The separate proposal accepts the frozen saved and reopened positive artifacts
and rejects the unsolved raw seed, pre-edit native baseline and fresh native
reset. It is source-derived TRAIN evidence only. Historical strict scoring
still rejects both positive exports; neither historical scorer was changed.
Model calls, selection runs, final runs and formal admissions are all zero.

For each positive, the proposal checks twelve target formulas against reviewed
financial arithmetic and ten independent source/driver counterfactual replays.
All twelve targets have a dependency witness. It independently evaluates all
29 formula caches and preserves 157 non-target semantic cells across six
sheets. Candidate and native baseline have exactly the same sixteen ZIP parts;
seven parts differ before normalization. The package has zero tables.

The limited save masks cover validated UTC created/modified timestamps, the
validated UUID component of the existing session document ID, bounded
single-cell focus on existing selection nodes, and chain ordering plus observed
boolean l/s flags. Chain membership must exactly and uniquely equal the
29 actual formula cells. All remaining XML metadata, calculation settings,
formula/cell attributes, styles, worksheet structure and ZIP part membership
remain protected. Formula/cache text masks are followed by the independent
arithmetic, counterfactual and cache checks.

The adversarial audit rejects 55 disposable controls. Twelve separately restored
bad target formulas fail current arithmetic after refreshing caches. Twelve
numeric-formula hardcodes retain correct current displays and chain membership
but fail counterfactual dependencies. Further controls cover wrong formulas,
plain hardcodes, stale/missing/nonfinite caches, source edits, collateral
formulas, style changes, table additions, validation changes, external links,
macros, protected metadata, calculation settings, selection fields, chain
membership/shape, QName-only namespace rebinding and removed parts. Four valid
save-equivalence controls pass. Ten synthetic unit tests additionally check existing-table range changes,
binary part changes, duplicate ZIP members, unknown XML nodes, UTF-16 entity
payload refusal, selection count/pane preservation, semantic namespace
resolution and private-error redaction.

The fresh reset preserves all 169 raw semantic cells, including the faulty
formula text and constants. Its normalized package matches the pre-edit native
baseline with no target formula mask. It is correctly rejected as unsolved.
This audit establishes the downloaded reset artifact comparison; it does not
independently establish the GUI reset workflow.

| Frozen artifact | SHA-256 |
| --- | --- |
| Raw seed | `e279e2b24695208282db024210d1c3e46c3bd3cd38f002c7d49b64df96912a40` |
| Pre-edit native baseline | `a7923d89481ec66062da23d31a2dfddea2d328d9827a3a6cf8601363a90af122` |
| Saved positive | `7a27251707fb05e19a650923c3a514521b8f4964af1959c711ceea6dc31313dc` |
| Reopened positive | `a12d49983353e3af48b6e47e5287f9e4e8bc2d0acc264e73724d820f8d0944ad` |
| Fresh native reset | `0109d5e5f747c7837688371a84325b6cfe6f76e0183ef1060eaee438f418ce8d` |
| Private review | `b8eb2d73511ff19f7b68aa2fae67e309e21d51d2ee4e317ad974f48d500fdf72` |
| Reviewed case, canonical JSON | `6eebe0ecef0227538e8e0fa520f99f9c90756671e13a199b4183385bbc6e7888` |
| Raw source case | `142fe847d4e652c1f2c75e2cb41ef0adff8b50d513083c3c184edfa2ca5e3a0d` |
| Reviewed source-plan binding | `d975e9a31259b6a5bf5474b3b2b57b140fc55a5da03e3357bf2cca78de3e13aa` |
| Public audit JSON | `a3c2e078f6654ffbf52e3085b72e9d2ecc46f1bfba0a0d1c952380dc361aedd5` |

The audit directly rehashes the source-case bytes and all five source files.
The reviewed source-plan binding is pinned; the source-plan file itself is
not reread by this audit.

| Frozen source file | SHA-256 |
| --- | --- |
| Filing | `0b8340937190ff224215ead8f7f66ac6df31e949294b98d1607f8f7f0ced7fa5` |
| Company facts | `2ac80ea17fde0111954d3bacddcaf77a5009bd70745952dfc4e56da804df9a8a` |
| Filing index | `edac07c8c3caee1ba9b7f2f1119d3e707158a8e5c78f37a23ad78750eb6be934` |
| Submissions | `eec8a75d8c631dda180750d8fdb13b9e7b56c1c280ce99474231b1bf05550e99` |
| Supporting filing document | `ae8be90dc36f495da242f8b3c1645b4b092640cda20ca406897cebaa54cb38ee` |

Run from a checkout containing this proposal. Set `PRIVATE_INPUT_DIRECTORY` to
the evaluator-private collection directory containing the six frozen inputs;
set `PUBLIC_AUDIT_OUT` to a new output file. These variables are intentionally
not populated in public evidence.

```bash
python3 -m unittest tests.test_sec_excel_train_native_save_proposal_v1 -v
python3 -m tools.audit_sec_excel_train_native_save_proposal_v1 \
  --private-input-directory "$PRIVATE_INPUT_DIRECTORY" \
  --public-out "$PUBLIC_AUDIT_OUT"
```

The machine-readable JSON records individual adversarial artifact hashes,
refusal codes, source-code hashes and unchanged before/after input hashes.
Disposable controls use fixed ZIP timestamps and permissions so the same
source/runtime reproduces their hashes. They are deleted after auditing. Output contains no source
values, formulas, answers, account/file identifiers, session document IDs,
credentials or local collection paths.

Validation passed sixteen tests across the new synthetic package suite and the
existing TRAIN source-dimension/review suites. Two fresh local audit executions
produced byte-identical public JSON at the recorded hash.

The pre-edit baseline's chronology is supplied collection evidence. Raw seed
to native baseline preserves semantic cells, sheet order, tables and selected
sheet structures, but Office's broader package/style/theme rewrite and visual
preservation remain unqualified. Cache consistency does not independently
prove native recalculation provenance. Second-person source review, GUI reset
proof and worker isolation remain outside this proposal. No final/admission
claim is made.
