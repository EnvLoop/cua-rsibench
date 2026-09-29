# GitLab CE v0.6.6: source-frozen boot-only infrastructure probe

The fourth GitLab continuation batch ended on an infrastructure failure after 13 completed evaluator controls. Its disposable container exited with code 1 during GitLab Omnibus nginx log-service startup, then the 900-second health wait expired. The supervisor preserved the failure, forbade replay of that task identity, and restored the exact healthy baseline. The proximate service error was observed, but the failed container's raw startup log was removed before it could be independently retained. The earlier original run had stopped at a different runit log service. Neither observation establishes the underlying cause.

This v5 source is a **task-free, prospective infrastructure probe** in the original GitLab evaluator worktree. Its offline freeze reopens the v4 no-dispatch family-recovery plan and the published checkout-scope addendum, hashes the probe source and reset/supervision dependencies, and creates one private random intent nonce with a public SHA-256 commitment. The main checkout's different private world cannot validate this source freeze. The freeze and its read-only audit do not start Docker, open a browser, dispatch a selection or final task, call a model, or issue official admission.

Only a later explicit `run-probe --execute` with the reviewed public freeze SHA-256 can write the one-use private intent. The supervisor launches one process group with a 3,600-second watchdog and at most three boot-only cold clones. The child uses the existing exact reset path, checks the frozen business baseline after each clone, and saves raw `docker logs --timestamps` stdout and stderr plus a State-only `docker inspect` result as mode-0600 files before another clone or any failure cleanup removes the container. Capturing State rather than Config avoids copying container environment variables. Each raw file's SHA-256 and length are bound by a private boot receipt. Docker's [logging documentation](https://docs.docker.com/engine/logging/configure/) explains why log retrieval should use the Docker interface rather than reading the daemon's log files directly.

If any reset, saved-log capture, State inspect, or exact readback fails, the child stops the probe. A watchdog could terminate the child while it waits for GitLab health, before its own log-capture step. In that case, the supervisor first saves the current container's logs and State into a separate private fallback record, then attempts one exact cold reset and health readback after confirming process-group termination. If termination is unconfirmed, it does not reset a world a live child might still mutate. A failed or uncertain intent is terminal and cannot be replayed by the same source. The public outcome, if a probe is run later, contains only status, counts, hashes, and cleanup state; raw logs remain private. The read-only `audit` action reopens saved raw-file hashes without needing Docker.

This source freeze **does not certify infrastructure reliability**. Three clean boots would establish only the observed boot-only result; they cannot rule out intermittent failures under GUI load. A separate source-frozen one-ID diagnostic in a different original source family would still need a new intent and independent GUI/DB/Git/reset audit. The proposed final 100-task cohort separately requires bootstrapping the FIFO reserve family, freezing a new baseline and ACL state, and qualifying every task. The failed original identity is not replayed, and this probe contributes zero final-task or model outcomes.

Offline source commands are:

    PYTHONPATH=src:. python -m gitlab_world.v066_boot_only_probe_v5 freeze \
      --ratification-private /ABS/PATH/TO/v066-caret-amended-control-ratification-20260928.private.json

    PYTHONPATH=src:. python -m gitlab_world.v066_boot_only_probe_v5 audit \
      --ratification-private /ABS/PATH/TO/v066-caret-amended-control-ratification-20260928.private.json

The reviewed live command, only after an operator verifies the source freeze and original evaluator checkout, is:

    PYTHONPATH=src:. python -m gitlab_world.v066_boot_only_probe_v5 run-probe \
      --ratification-private /ABS/PATH/TO/v066-caret-amended-control-ratification-20260928.private.json \
      --reviewed-public-sha256 THE_PUBLISHED_JSON_SHA256 --execute
