# GitLab CE all-step capture guard, source-only review

The third train-only attempt used a new project and a model-facing target
shape rule. Its first paid `click` response had a valid object containing a
current visible link ref. The [independent failure audit](evidence/gitlab-v066-target-shape-train-result-2026-09-28.json)
retained one provider response and a precisely restored PostgreSQL/Git
baseline, but no complete train episode. The [read-only forensic](evidence/gitlab-v066-next-frame-failure-2026-09-28.json)
found no second-step request or saved second-step frame. The observed runtime
traceback pointed to second-step `stale_frame` capture; because neither of
the failed capture's two screenshots was saved, a page transition and a
dynamic page element cannot be separated independently. The first target
was a link, which makes navigation plausible but does not prove it.

The proposed guard repeats **only capture and current-frame equality** at
each step, at most five times. Before every repetition it checks that this
same step has no provider intent, request, response, accepted frame, or GUI
dispatch intent. The step can be entered once per browser session. Each
rejected capture receives a private numbered receipt. The first stable
observation is still produced by the unchanged native actor, which compares
two physical screenshots and exposes only current controls. A failure after
five captures terminates the attempt. Paid calls and GUI actions are never
retried.

The wrapper also writes a private, hash-bound dispatch intent with the full
validated action **before** invoking the original GUI dispatcher. It writes
an applied acknowledgment only after the original dispatcher returns with
the session step advanced; an exception or missing acknowledgment is kept as
an uncertain outcome. This closes the evidence gap in the third failure,
where the training sampler recorded a normalized turn but no durable action
trace survived the later capture exception. The common v0.6.6 parser,
GitLab actor, independent verifier, and cold-reset implementation remain
unchanged.

Four simulated tests cover first- and second-step dynamic frames, a provider
intent blocking resampling, an uncertain dispatch blocking replay, and a
five-capture terminal failure. The guard is **source-only**: no fourth paid
train attempt, Tinker batch, final GUI control, or official admission has
used it. The separately frozen [100-ID prospective control plan](evidence/gitlab-v066-prospective-final-control-plan-2026-09-28.json)
uses a different evaluator GUI controller; this training guard does not
alter that controller or credit its historical 100 trios.
