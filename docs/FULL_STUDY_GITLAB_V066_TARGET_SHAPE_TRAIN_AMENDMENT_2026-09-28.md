# GitLab CE train target-shape amendment, 2026-09-28

The first train pair stopped before a provider request because its physical
frame changed during capture. A separately frozen pre-intent capture
amendment allowed one fresh frame; the subsequent Sol response was retained
but rejected before dispatch. Its `click` action supplied `target` as a bare
string. The unchanged v0.6.6 validator requires a target object containing
either one current visible `ref` or bounded integer `x` and `y` coordinates.
The [private-byte forensic audit](evidence/gitlab-v066-target-shape-failure-2026-09-28.json)
confirmed the bare string was one of 69 current visible refs. This was a
model-output format failure rather than a missing visible control. The source contract
described copying a ref but did not make the outer object shape salient in
the train request. The first task and paid response remain unqualified and
must not be replayed.

The next proposal selects a **different** train task from a different GitLab
project and source family. It preserves the frozen action parser, worker,
PostgreSQL/Git oracle, reset, original six-cell profile, and same Sol 5.6
teacher route. It changes only the model-facing train instruction by
prepending a target-shape rule: `target` must be an object; a visible control
ref goes under its `ref` key, or screenshot coordinates go under integer `x`
and `y` keys. A bare string is explicitly invalid. No dummy ref or concrete
coordinate is shown for the model to copy. The exact request body and current
frame are still saved before a provider POST.

The fresh attempt is source frozen separately and limited to one positive
and one wrong-priority negative arm, at most 45 GUI actions and 20 minutes
per arm. No provider call, response, GUI dispatch, or failed task is retried.
The independent auditor reopens all accepted frames, prompts, requests,
responses, actions, saved-state results, and cold resets. A passing pair
would make only the positive train episode eligible for SFT. It would not
admit a final task or show a trained-model effect. Actual provider billing
remains unknown until a bill or usage accounting is available; every call
and returned token count is retained privately.
