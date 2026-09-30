# Neutral GitLab cold-boot execution

This additive runner tests the proposed optional telemetry profile on three fresh COW clones of the retained 33-project baseline. It consumes no task IDs, invokes no GUI or model, grants no control or final credit, and does not authorize the next task batch. A successful source review is not native proof. All three boots, teardown, restoration, and independent saved-evidence replay must succeed before a uniform prospective task amendment can be considered.

The index-9 failure occurred in the optional `gitlab-exporter/log` restart during Omnibus reconfiguration. PID/FIFO corruption has not been established. GitLab documents disabling monitoring on resource-constrained installations. The proposal keeps the existing image, business seed, operators, grader, critical services, concurrency, KAS configuration, memory, `SVWAIT=60`, and readiness deadline of 900 seconds. It appends exactly the nine settings in the existing profile to each new clone's writable upper `gitlab.rb` and generated environment. The generated environment preserves the internal URL and listen port 8018; neutral isolation maps a new loopback host port to internal 8018. Readiness uses the neutral host URL. The immutable base configuration already sets 8018 and takes precedence over Omnibus environment values, so changing only the environment port would produce an unusable mapping. There is no environment or upper-file origin delta beyond the nine telemetry settings. It never edits the original configuration, environment, lower seed, COW state, source freeze, control namespace, or historical prohibited flags.

The three supervisor file locks must already exist and be exclusively acquired. The existing process scanner must prove no concurrent GitLab worker. The preserved successor is checked against the complete saved SQL/Git baseline, gracefully stopped with the existing 300-second stop allowance, then resumed with its exact container, mounts, ports, image identity, business state, and full Git trees. The original instance is restored after a failed stop proof, failed clone boot, failed readback, or failed teardown; restoration failure is terminal and remains visible.

Every clone has a new owned container name and COW upper/work root. A colliding container or VM root is refused and retained. The frozen `_mount`, `wait_cohort`, operator roster, snapshot and Git helpers are called through a temporary local scope; the original `reset.reset` is never called. Each clone is started once with `--restart no`. There is no restart, task setup, mutation through GitLab APIs, or automatic retry. Only a successfully claimed neutral namespace can be stopped, removed, unmounted, and deleted. All owned mounts, the container, and the cycle subtree must be absent before continuing.

The runner retains private raw startup streams, limited Docker state, effective settings, service status, SQL/Git snapshot, complete NUL-delimited Git trees for every branch in all 33 projects, config-delta proof, seed content/metadata hashes, original stop/resume proof, native command streams, and a durable lifecycle chronology. The config edit executes against the actual fresh upper file and checks that its bytes equal the lower file plus only the fixed suffix. `gitlab-ctl show-config` remains inside the container: an exact-path Ruby reader emits only nine typed booleans, with a fixed error on missing/nonboolean values. It uses the official 18.5 `SettingsDSL.sanitized_config` layout, with exporter settings under `monitoring` and application settings under `gitlab`. It does not store or print the unfiltered configuration. All private files use mode 0600.

`audit` reopens every retained evidence byte, validates the one-use plan/permit binding and current source/metadata, compares raw snapshots and every full Git tree, checks actual service/config/state semantics, and verifies three distinct identities and a single boot/teardown per cycle in the chronology. Editing a receipt and updating its file hash cannot bypass these comparisons. A failed run records a terminal failure with its raw refs; a consumed intent cannot be replayed.

## Commands

Run preparation after importing the source commit into the original evaluator. Use an exclusive private output directory and the previously retained official 18.5 source bindings. Keep the same Python interpreter and `PYTHONPATH=.:src` used by the existing evaluator.

```bash
python -m gitlab_world.v066_neutral_telemetry_coldboot_v1 prepare \
  --freeze "$SOURCE_FREEZE" --out "$NEUTRAL_OUT" \
  --upstream-bindings "$UPSTREAM_BINDINGS" --port 8026
python -m gitlab_world.v066_neutral_telemetry_coldboot_v1 review \
  --plan "$NEUTRAL_OUT/plan.private.json" \
  --permit "$NEUTRAL_OUT/permit.private.json" \
  --accept-root-review --note 'Reviewed original bindings, owned paths, exact telemetry delta, and lifecycle restoration.'
python -m gitlab_world.v066_neutral_telemetry_coldboot_v1 run \
  --plan "$NEUTRAL_OUT/plan.private.json" \
  --permit "$NEUTRAL_OUT/permit.private.json" --execute
python -m gitlab_world.v066_neutral_telemetry_coldboot_v1 audit \
  --plan "$NEUTRAL_OUT/plan.private.json" \
  --permit "$NEUTRAL_OUT/permit.private.json"
```

Preparation and review are source-only. Native execution is restricted to the original evaluator checkout. The reviewer must inspect the prepared plan and current retained metadata before issuing the exact permit. Stop on any native failure; do not use a second output directory as an automatic retry.

## Offline validation and limits

Tests exercise the actual lifecycle algorithm with effects replaced, invoke the frozen mount helper and scope restoration, execute the upper-file edit against real fixture bytes, run the Ruby filter locally, and independently reopen retained fixture evidence. They attack failed startup, stop proof, teardown, remaining upper directory, changed SQL/Git/critical service/settings/seed/source, reused identities, namespace collision, ambiguous Docker absence, modified receipts, and one-use intent replay. They make no Docker, Colima, native UI, or provider calls. These tests demonstrate source behavior, not successful native cold boots or a known logger root cause.

The proposal uses [GitLab's documented monitoring option](https://docs.gitlab.com/omnibus/settings/memory_constrained_envs/#disable-monitoring), [Docker configuration precedence](https://docs.gitlab.com/install/docker/configuration/#pre-configure-docker-container), and [rendered configuration readback](https://docs.gitlab.com/omnibus/maintenance/). Profile-group behavior is pinned to [official 18.5 monitoring source](https://gitlab.com/gitlab-org/omnibus-gitlab/-/blob/18.5.0%2Bce.0/files/gitlab-cookbooks/monitoring/libraries/prometheus.rb); output layout follows [official 18.5 settings DSL](https://gitlab.com/gitlab-org/omnibus-gitlab/-/blob/18.5.0%2Bce.0/files/gitlab-cookbooks/package/libraries/settings_dsl.rb) and [show-config recipe](https://gitlab.com/gitlab-org/omnibus-gitlab/-/blob/18.5.0%2Bce.0/files/gitlab-cookbooks/package/recipes/show_config.rb).
