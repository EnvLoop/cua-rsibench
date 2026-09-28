# Train-only E2B login bridge for original Office web software

**Status: design, not an executed Office model run.** The current PowerPoint and Excel controls use the original Microsoft web applications in a dedicated personal OneDrive account. The evaluator can operate them with a signed-in local browser, but that path is not a scalable 24-campaign model executor and stops when the host is locked. Transferring the local browser's cookies to a cloud sandbox would create a persistent credential copy and blur the account boundary. A browser-only mock would lose the original-software claim.

The next bounded experiment is one fresh [E2B Desktop sandbox](https://github.com/e2b-dev/desktop/blob/main/README.md) with outbound internet and a password-protected, time-limited desktop stream. Trusted setup launches Chrome at the Microsoft PowerPoint web sign-in page; the user signs in manually in that remote desktop. The script receives **no Microsoft password, session cookie or refresh token**, and the model receives only current screenshots, task instructions and the declared action budget. The stream URL, VNC password and sandbox ID remain under ignored mode-0600 private storage; they never enter Git or a model prompt. One train-only deck then tests whether visible browser actions can save a PPTX that an independent evaluator downloads and verifies. Any final-task URL or gold is rejected in this pilot.

The E2B lease is bounded and its sandbox/template identity, runtime, attempted actions, provider errors and teardown are journaled separately from model scores. On setup failure the sandbox is killed. On success the sandbox is still short-lived, explicitly killed after the train test, and no authenticated image/template is published or snapshotted. This pilot does **not** prove the later per-task reset, concurrent account use, 16-hour researcher campaign, or cost estimate; those need separate observed controls before adoption. The existing local-browser qualification evidence remains authoritative until the cloud path passes the same source-bound saved-state and no-regression checks.

## Bounded train runner and current acceptance boundary

`tools/office_web_e2b_train_runner_v1.py` adds the next stage. It accepts only a mode-0600 bridge `session.private.json`, an existing `packages/train/<ppt-wdi-id>/task.private.json` with the pinned train schema and zero official-final credit, and a mode-0600 `run.private.json`, all under the current checkout's ignored `work/`. It rejects paths containing final or official before opening a task file. The actor receives only `actor_task` and current desktop screenshots; calculation fields and train gold stay out of the model request. The run config contains a human-entered `manual_login_confirmed_at_unix`, a narrowly validated `<private OneDrive train-file edit URL>` train-file edit URL, `max_steps` (1–20), and `wall_seconds` (1–600). The confirmation and train-file name are operator attestations, not automated proof of Microsoft login or cloud-item source identity; a live source-bound download is still required before this runner can qualify any result.

The runner reconnects with `Sandbox.connect(sandbox_id)` without a timeout argument, rechecks the pinned Desktop template, launches the declared train deck, and calls the shared Qwen/Qwen3.8-27B Tinker vision adapter. Each request has a durable proxy journal entry. The runner's private JSONL journal records setup, request intents/results, action intents/results, artifact gate, and teardown, with hashes in place of URLs, typed text, sandbox IDs, and stream credentials. It uses the v0.6.5 action parser on screenshot observations with no invented control refs. Immediately before dispatch it compares a fresh screenshot to the sampled frame and checks the frame, wall, and lease bounds. E2B Desktop 2.2.0 provides `screenshot`, `move_mouse`, `left_click`, `press`, `write`, `scroll`, and `drag`; the runner rejects action forms without an exact desktop mapping. Teardown calls the bridge's class-level kill path even when sampling or action dispatch fails.

The default `UnqualifiedOfficeDownload` gate **always blocks artifact acceptance**. The Office web GUI download path, cloud-item binding, and independent task oracle have not been observed in this E2B session. An injected test retriever can exercise PPTX ZIP/XML readback, but that produces `artifact_readback_unscored` only. It does not establish a saved cloud item or benchmark score. Production must implement and live-test a source-bound download, save/reload confirmation, fresh-copy reset, and task-specific verifier before replacing this gate. No E2B or Tinker call was made while implementing this runner.

After the user manually signs in through the private stream, create `work/.../run.private.json` with this shape and file mode 0600. Keep the real deck URL in that ignored file, never in a shell argument or Git:

```json
{
  "schema": "office-web-e2b-train-run-private-v1",
  "split": "train",
  "manual_login_confirmed_at_unix": 0,
  "deck_url": "<private OneDrive train-file edit URL>",
  "max_steps": 3,
  "wall_seconds": 300
}
```

Replace the timestamp with the actual confirmation time after the bridge lease starts. From the checkout containing the bridge receipt, run the no-provider preflight first:

```sh
PYTHONPATH=src python -m tools.office_web_e2b_train_runner_v1 --dry-run \
  --session work/.../session.private.json \
  --task work/.../packages/train/ppt-wdi-.../task.private.json \
  --config work/.../run.private.json \
  --out work/.../new-run
```

`--run` uses the same arguments and is an explicit paid-provider action; it requires host-side `E2B_API_KEY` and `TINKER_API_KEY` plus pinned `e2b-desktop==2.2.0`. The run result remains private under `work/` and, with the default artifact gate, cannot be reported as a successful Office benchmark attempt. The fake sandbox/model test is `PYTHONPATH=src python -m unittest tests.test_office_web_e2b_train_runner_v1 -v`.

A private Python 3.14 target dependency directory was then assembled without changing the project venv. It resolves E2B Desktop 2.2.0, E2B 2.51.0, Tinker 0.30.0, Transformers 5.5.4, Pillow 11.3.0 and `tml-renderers` 0.1.0; `pip check`, offline Qwen3.8 renderer loading and eleven fake runner/bridge tests pass with that directory first on `PYTHONPATH`. This establishes a locally coherent import/render path, **not** E2B account access, Microsoft login, cloud artifact binding, Tinker sampling, provider billing or a model outcome. The private dependency tree remains outside Git and must be rebuilt and hashed before any live study freeze.
