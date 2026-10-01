# Original Magento absent-object inspection

The first current native TRAIN launch stopped before creating any container.
Its sole Docker command was a read-only inspection. Docker returned exit 1,
stdout `[]` and a lowercase `error: no such object` message for the exact
expected evaluator container. The frozen journal recognized only an uppercase
phrase, so it incorrectly treated the confirmed absence as an infrastructure
failure. The failed namespace and original raw replies are preserved.

The additive native journal loads the exact pinned original `run` method and
changes only this predicate. It requires exit 1, an empty JSON list, an owned
Magento object name and an exact missing-object/network message. Daemon,
transport, permission, wrong-target and nonempty-output failures remain
terminal. Original stdout/stderr bytes and hashes are retained. No Docker
command is replayed.

Teacher, controls, shared base and all four checkpoints use the same new
journal and source binding. The original journal source and previous 52
development controls remain unchanged. Eleven focused original pipeline,
admission and raw-result tests passed. A fresh source-bound TRAIN namespace is
required; no native qualification or formal result is claimed by this repair.

The next actual launch reached the intentional stopped cron service. Its
`supervisorctl status cron` returned code 3 and `cron STOPPED Not started`.
The additive journal accepts only that exact owned-app/status-command reply;
it preserves code 3, records the checked classification and retains original
stdout bytes. Other service failures remain terminal. Two created containers
and the empty network were matched against their creation-result hashes and
removed by an explicit root recovery. The prior failure remains preserved.
