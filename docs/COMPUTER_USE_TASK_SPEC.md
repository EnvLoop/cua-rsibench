# Computer-use task and verifier contract

This is the part that must be real before claiming a computer-use result. A JSON fixture is only a
development substitute for a resettable application environment.

## Domain packs

The first release should report six independent domain cells, with no aggregate score:

1. **Browser transactions**: search, filter, edit, submit, and recover from an interrupted page.
2. **Office artifacts**: Word, spreadsheet, and presentation edits with structural and visual checks.
3. **Desktop state**: files, folders, archives, permissions, and application settings.
4. **Cross-application workflows**: move facts between browser, files, mail/calendar, and Office.
5. **Expert digital work**: layout, diagram, CAD-like or media operations with artifact readback.
6. **Environment learning**: unfamiliar app behavior that must be inferred from visible feedback.

Each cell has independent train, acceptance-anchor, and hidden test tasks. Splits are by task template,
application, workflow, and source artifact—not just by a random task ID.

## Task package

```json
{
  "task_id": "office_017",
  "domain": "office_artifacts",
  "app_image": "powerpoint-online@pinned-release",
  "initial_state": "snapshot://office_017/start",
  "instruction": "Update Q3 revenue on the sales slide and preserve the theme",
  "visible_inputs": ["deck.pptx", "q3.csv", "brand-guide.pdf"],
  "limits": {"steps": 40, "wall_seconds": 900},
  "reset": {"kind": "snapshot_restore", "id": "office_017/start"},
  "output_contract": {"path": "/workspace/final/deck.pptx"}
}
```

The agent may see the instruction, visible inputs, screenshots/accessibility tree, and reset behavior.
It must not see the expected state, hidden assets, verifier source, or test trajectories.

## Verifier layers

- **Artifact/state**: parse application state or OOXML/DOM/file metadata independently of the agent.
- **Task semantics**: recompute values from source data and check intended object IDs and relationships.
- **Side effects**: detect wrong-object edits, source mutation, extra files, corrupted output, and hidden
  state changes.
- **Visual/semantic**: render the result and use a rubric/VLM only for soft properties such as layout,
  readability, and visual consistency.
- **Integrity**: validate the verifier on positive, negative, adversarial, and replay fixtures.

Hard requirements gate promotion. Partial credit is allowed for meaningful intermediate progress, but a
successful screenshot alone never proves task completion.

## Real adapter contract

```text
reset(task_id) -> clean environment
observe() -> screenshot + accessibility tree + allowed state
act(action) -> observation + tool result
snapshot() -> saved artifact and environment fingerprint
```

The evaluator calls `reset` itself, reads the final artifact independently, and records every action,
observation, timeout, infrastructure failure, and verifier consequence. Infrastructure failures are kept
separate from model scores.
