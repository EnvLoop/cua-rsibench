# Atomic readonly editor matching

A reference workflow queried the number of `.monaco-editor` nodes, then evaluated matching-node metadata in a separate browser round trip. During editor hydration, the first call observed one node and the second observed two. One was the valid focused code editor; the other was an unpainted wrapper with no textarea. The existing guard correctly refused the inconsistent count, leaving the positive control incomplete.

`cursibench.atomic_editor_matching` collects the matching array, its length, the role-code count, document readiness and all eligible or excluded facts in one synchronous readonly `Locator.evaluate_all` callback. The callback performs no UI input, DOM writes, focus change or editor-model access. It retains the original eight-match limit. Overlimit snapshots contain their actual count and fail the known-facts check; they are never accepted by suppressing the unknown flag.

The portable fact contract still requires exactly one painted DIV with role `code`, one enabled writable TEXTAREA with the caller's exact expected label, and actual textarea focus inside that editor. All excluded matches remain in the returned evidence. Multiple eligible editors, role/focus drift, inconsistent metadata and incomplete snapshots refuse. Zero matches are known but remain not ready.

The helper grants no input permission and does not establish task ownership, native qualification or saved success. Integration must retain the caller's existing URI, native target, two-second stability, thirty-second readiness, physical input, actor/lifecycle budget, complete-content, independent saved verification and exact reset rules. It is intentionally independent of local reference-epoch files and private task data.

Tests exercise a one-to-two hydration race without any separate count call, the excluded wrapper, incomplete and overlimit facts, ambiguous focus, wrong labels and protected or invisible fields. The actual JavaScript callback is also executed against a small constructor-free DOM fixture. A fresh original control trio has scalar runtime evidence in the accompanying JSON; a complete twenty-task successor run remains separate and pending.

The Python API uses `Locator.evaluate_all`, which receives the matched element array and returns a serializable result. [Playwright documentation](https://playwright.dev/python/docs/api/class-locator#locator-evaluate-all)
