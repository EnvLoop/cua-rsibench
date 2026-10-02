# TRAIN-only Excel native-save normalization proposal

This is a separate source-derived proposal for one frozen bank TRAIN case. It
does not change a historical scorer, admit an Excel task, or assess a model.
The raw seed, pre-edit native export, saved candidate, reopened export and
private source review remain immutable inputs. Their exact SHA-256 bindings
are part of the proposal; replacements require a new proposal version.

The trusted comparison package is the native export captured before the twelve
formula edits. Candidate and baseline must contain exactly the same ZIP part
names, with no duplicate names, unsafe paths, XML entities, macros or external
links. Every protected XML node, attribute, text value and child order is
compared after namespace-aware parsing; binary parts must match byte for byte.
QName-valued and markup-compatibility attributes resolve their prefix bindings,
so a namespace referenced only by an attribute cannot be silently rebound.
The limited masks are two valid UTC core timestamps, a valid session UUID in
the existing revision-pointer document ID, existing selection nodes' bounded
single-cell focus attributes, target formula text, and formula numeric cache
text. Formula caches are subsequently required and independently recomputed.
The selection node count, pane and all other view attributes remain protected.

Calculation-chain ordering and the observed l/s flags are ignored only after
each package independently proves unique, exact (sheet ID, cell address)
membership equal to every actual formula cell. Unknown chain attributes or
children, malformed flags, dropped members and duplicate members are refused.
Calculation settings and all other workbook nodes remain protected.

The existing independent TRAIN arithmetic and counterfactual implementation
is reused without importing a workbook builder or a teacher action plan. All
twelve targets must remain formulas, satisfy the reviewed financial arithmetic,
pass all ten source/driver replays and have current numeric saved caches. Every
non-target constant and formula remains unchanged. Source facts and lineage
must match the hash-pinned private review.

Raw seed to native baseline is separately checked for unchanged semantic cells,
formula text, constants, sheet order, tables and selected sheet structures.
Office's broader package, style and theme rewrite on that first native save is
not qualified by that check. Independent source review, raw-to-native visual
and package qualification, native recalculation provenance, GUI reset evidence,
worker isolation, model effects and any admission remain open.

The audit creates disposable private copies for formula, hardcoding, one-target
short, cache, source, collateral, style, table, validation, link, metadata,
selection and chain attacks. It exports only hashes, counts, reason codes and
explicit limitations. It never exports source values, formulas, answers,
account IDs, file IDs, session document IDs, credentials or local paths.
