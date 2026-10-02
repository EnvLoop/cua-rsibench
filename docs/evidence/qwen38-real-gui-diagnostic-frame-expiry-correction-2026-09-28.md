# Qwen3.8 real-GUI diagnostic: frame-expiry incident and read-only correction

The one-shot `Qwen/Qwen3.8-27B` LoRA diagnostic completed 64 optimizer steps and
all 154 journaled provider operations, including four optimizer-state saves,
final sampler-weights save, both sampler opens, 16 matched samples, and service
close. The exact private plan and journal are bound to the [pre-dispatch Git
freeze](qwen38-real-gui-diagnostic-freeze.json) at commit
`4b0ec2ce78344bdd1cfa77d1d93818fdff84fe5a`. The freeze was also
independently fetched from that commit's public GitHub raw URL and matched the
local bytes (SHA-256 `79d20dafc6430b14a8ab5fc08ee865db1c2c314ca49a294139398108926e67e0`).
The [field-limited independent audit](qwen38-real-gui-diagnostic-frame-expiry-correction-2026-09-28.json)
reopens the three original Desktop public-train GUI source episodes, source
receipts, exact task-disjoint plan, every request/result file and hash-chain
entry, final checkpoint binding, saved samples, and private result. It makes no
provider call and publishes no task IDs, instructions, screenshots, sample
texts, checkpoint paths, or credentials.

The saved v1 result's **0/8 format-valid counts for both base and LoRA are
invalid as model measurements**. The held-out `Observation` objects were built
before training. Their live-dispatch frame lifetime is 270 seconds, while the
first matched sample was requested 625 seconds after the first provider intent.
The v1 scorer called the strict live-frame validator on those expired objects
and converted each `ContractError` into a model format failure. Repeating that
expired-frame condition reproduces all 16 saved invalid verdicts. Reopening
the exact held-out source frames and refreshing **only** their issuance and
expiry times makes all 16 saved outputs parse under the same strict action
parser; task, package, instruction, screenshot, step, frame ID, action and
sample text remain unchanged. This is a post-run correction from saved bytes,
not a second model run or a retroactive claim that the original preregistered
scoring implementation was sound.

| Teacher-forced metric on one held-out Writer train task | Saved v1 base | Saved v1 LoRA | Corrected base | Corrected LoRA |
| --- | ---: | ---: | ---: | ---: |
| Strict action format, 8 turns | 0 | 0 | 8 | 8 |
| Reference action type, 8 turns | 0 | 0 | 2 | 4 |
| Exact reference payload, 8 turns | 0 | 0 | 0 | 1 |
| Non-wait reference action type, 6 turns | 0 | 0 | 2 | 3 |
| Non-wait exact payload, 6 turns | 0 | 0 | 0 | 0 |

The corrected action-type comparison has four paired gains and two paired
losses. Exact payload has one gain and no loss. The 16 outputs comprise eight
direct JSON objects and eight fenced JSON objects; all are 11–26 output tokens,
none reached the 128-token ceiling, and none fails the refreshed strict
parser. These counts describe **one eight-turn, task-disjoint, public-train
holdout**. They do not establish a reliable training effect, interactive
application success, an official selection result, or any of the 24 researcher
campaigns or 3,000 final slot-task outcomes.

The journal records 212,895 scheduled training tokens, 26,368 rendered
sampling-prompt tokens and 295 observed output tokens. Those are not
provider-billed totals. The pre-run `$1.868022450` figure is a nominal planning
quote, not a dispatch limit or invoice. Provider billing attribution, discounts
and final dollars remain pending; the independent audit leaves billed tokens
and invoice fields null.

The frozen v1 scorer and runner files remain unchanged. A separate
[prospective v2 scoring module](../../src/cursibench/qwen38_real_gui_diagnostic_scoring_v2.py)
raises a fixed error on an expired live frame and reissues timestamps only for
offline archived-frame scoring. Its regression tests reproduce the v1 artifact
and validate the corrected boundary. Any future paid diagnostic must bind a
new runner, exact plan, and immutable public freeze before dispatch. No paid
replay was performed for this correction.
