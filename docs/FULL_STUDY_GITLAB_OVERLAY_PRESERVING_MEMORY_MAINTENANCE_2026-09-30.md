# GitLab overlay-preserving 6-to-12 GiB maintenance

Read-only inspection confirmed three active overlay mounts under the preserved
v3 COW root. Each uses its exact v3 named-volume lowerdir and existing upper/work
directories. Neither `/etc/fstab` nor a systemd mount unit registers those
mounts. The original container has restart policy `no`. Memory resizing requires
a VM stop/start; the tool treats manual mount loss as possible and never starts
the container against an unverified underlying `merged` directory.

The [official Colima resource procedure](https://github.com/abiosoft/colima#customization)
uses stop/start to change memory. Installed Colima 0.10.3 help was also checked:
the current flags are `--cpus`, `--memory`, `--disk`, `--profile`, and
`--activate=false`. The reviewed operation keeps the same profile, disk, CPU
count, architecture and Docker context, changing only 6 to 12 GiB memory. No
new account, VM, disk, seed volume or container is created.

The [maintenance tool](../gitlab_world/v066_overlay_memory_maintenance_v1.py)
first prepares a read-only owner-only plan. It rejects live/concurrent GitLab
workers; captures the exact 31-project SQL/Git snapshot, all sealed original metadata
hashes, original core source hashes, container/image/mount identity, three seed
volume identities, and lower/upper/work directory inode/mode/owner identities.
Only a healthy original container with no automatic restart is eligible.

Reviewed execution consumes a fresh maintenance directory. It gracefully stops
the exact captured container ID before stopping the VM, saves the stopped
overlay identities, and restarts the same VM with 12 GiB, 3 CPUs and 24 GiB disk.
The container must still be stopped. The tool reuses the existing directories
and mounts the exact preserved lower/upper/work paths; it never calls
`reset.reset`, clears a layer, creates a replacement directory, removes a
container, rewrites COW state or changes the active-volume marker. Only after
all three overlay mounts and existing directory identities pass does it start
the exact original container ID. Independent verification requires the full
31-project snapshot, all original metadata and core source hashes, original container and seed
identities, exact overlay topology and 12 GiB/3 CPU resource readback.

The receipt explicitly records the original container's transient stop/restart
as pre-result maintenance. It never claims the original application stayed
running throughout. A failed or interrupted operation is not replayed; keep
the container stopped until its recorded mount topology is re-opened and any
separate remaining-only recovery is reviewed. No controller task or old intent
is replayed by this operation.

Install the committed tool into the original evaluator checkout. Prepare and
review the concrete owner-only plan before executing:

```bash
cd "$GITLAB_EVALUATOR_ROOT"
PYTHONPATH=src:. "$GITLAB_PYTHON" \
  -m gitlab_world.v066_overlay_memory_maintenance_v1 prepare \
  --evaluator-root "$GITLAB_EVALUATOR_ROOT" --plan "$NEW_MAINTENANCE_PLAN"

PYTHONPATH=src:. "$GITLAB_PYTHON" \
  -m gitlab_world.v066_overlay_memory_maintenance_v1 execute \
  --plan "$NEW_MAINTENANCE_PLAN" --output-root "$NEW_MAINTENANCE_RECEIPT_ROOT" \
  --execute-reviewed-maintenance

PYTHONPATH=src:. "$GITLAB_PYTHON" \
  -m gitlab_world.v066_overlay_memory_maintenance_v1 verify \
  --plan "$NEW_MAINTENANCE_PLAN" --output-root "$MAINTENANCE_RECEIPT_ROOT"
```

After successful maintenance, rebind the amended prospective cohort source
freeze and run its separate read-only resource preflight. Maintenance itself
does not bootstrap the new project or authorize task controls. Native bootstrap,
new controls, model calls and official final admissions remain zero here.

The maintenance command retains owner-only stdout and stderr from VM stop/start, including partial bytes on timeout or failure. The post-run receipt reports the actual number of original metadata files checked; it does not substitute a fixed count.
