# GitLab CE train capture amendment, 2026-09-28

The first original-GitLab v0.6.6 train-only GUI pair stopped while collecting
its first frame. The native actor reported a stale physical frame before it
returned any task screenshot. An independent readback found zero provider
request intents, bodies, responses, recorded GUI frames, or actor actions; the
PostgreSQL/Git business snapshot matched the frozen baseline after the
worker's cold reset. The original source plan, private trace, and public
[interruption audit](evidence/gitlab-v066-train-preintent-interruption-2026-09-28.json)
remain preserved. The exception class is durable; the exact subtype appeared
in the live traceback but was not saved in the first failure receipt.

Three narrow responses were considered: stop this train example entirely,
weaken the physical-frame equality check, or resample only before an arm's
first provider intent. The separately frozen amendment chooses resampling.
It keeps the original actor, action parser, teacher worker, saved-state
oracle, and cold reset unchanged. On step zero of each train arm, at most five
complete observe-and-current-frame checks may run. Each rejected attempt is
recorded privately, and the loop asserts that the arm has no provider request
intent or body, model response, accepted frame, or actor action. Other steps
retain the original one-shot behavior. A provider POST, GUI dispatch,
saved-state readback, or later failure is never retried automatically.

The second attempt has a fresh output directory and an immutable supplement
that binds the original plan, interruption audit, amendment code, and
independent auditor. The auditor reopens every accepted raw frame, normalized
action, model request/response, positive and wrong-priority saved result, and
fresh cold reset through the original independent pair auditor. A failed
second attempt is reported as unqualified with request counts and reset
state; a passing pair can only make its positive train episode eligible for
later SFT. Neither outcome admits a selection/final task, runs Tinker, or
supports a model-improvement claim.
