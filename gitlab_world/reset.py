"""Cold-reset a disposable GitLab CE world with immutable-volume lowerdirs.

The named seed volumes are never mounted writable by an evaluation container.
Each attempt starts a new container on fresh overlayfs upper/work directories,
and is checked against the same independent PostgreSQL/Git business baseline.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

from . import factory, runtime, verify


PRIVATE = runtime.PRIVATE
STATE_FILE = PRIVATE / "cow-reset-state.json"
VM_ROOT = "/var/lib/envloop-gitlab-cow-" + runtime.ACTIVE_VERSION
LEGACY_VM_ROOT = "/var/lib/envloop-gitlab-cow-v1"


def vm_shell(script: str, *, timeout: int = 120) -> str:
    result = subprocess.run(["colima", "ssh", "--profile", "cua-gitlab", "--",
                             "sudo", "sh", "-lc", script], capture_output=True,
                            text=True, check=True, timeout=timeout)
    return result.stdout.strip()


def _baseline() -> dict:
    path = PRIVATE / "baseline-persisted-state.json"
    result = json.loads(path.read_text())
    verify.verify_bootstrap(result)
    return result


def _volume_lowerdirs() -> dict[str, str]:
    mounts = runtime.inspect(runtime.WORLD)["Mounts"]
    by_destination = {mount["Destination"]: mount for mount in mounts}
    result = {}
    for role, destination in runtime.DESTS.items():
        mount = by_destination.get(destination)
        if not mount or mount.get("Type") != "volume" or mount.get("Name") != runtime.VOLUMES[role]:
            raise RuntimeError("world is not mounted on expected dedicated seed volumes")
        source = mount["Source"]
        if not source.startswith("/var/lib/docker/volumes/") or not source.endswith("/_data"):
            raise RuntimeError("unexpected Docker volume source")
        result[role] = source
    return result


def _state() -> dict:
    result = json.loads(STATE_FILE.read_text())
    if result.get("schema") != "envloop-gitlab-overlay-cold-reset-v1":
        raise RuntimeError("cold reset state schema changed")
    return result


def _mount(role: str, lower: str) -> None:
    if role not in runtime.DESTS:
        raise ValueError("unknown GitLab volume role")
    base = VM_ROOT + "/" + role
    # All path components are fixed or validated from Docker inspect.
    script = ("set -eu; "
              f"mkdir -p {base}/upper {base}/work {base}/merged; "
              f"mount -t overlay overlay -o lowerdir={lower},upperdir={base}/upper,"
              f"workdir={base}/work {base}/merged; "
              f"mountpoint -q {base}/merged")
    vm_shell(script)


def _unmount_and_clear(role: str) -> None:
    if role not in runtime.DESTS:
        raise ValueError("unknown GitLab volume role")
    base = VM_ROOT + "/" + role
    vm_shell("set -eu; "
             f"if mountpoint -q {base}/merged; then umount {base}/merged; fi; "
             f"rm -rf {base}/upper {base}/work; "
             f"mkdir -p {base}/upper {base}/work {base}/merged")


def _create_case() -> dict:
    args = ["run", "-d", "--name", runtime.WORLD,
            "--hostname", "gitlab-world.local", "--restart", "no",
            "--env-file", str(runtime._env_file()),
            "-p", "127.0.0.1:8014:8014"]
    for role, destination in runtime.DESTS.items():
        args.extend(["-v", f"{VM_ROOT}/{role}/merged:{destination}"])
    args.append(runtime.IMAGE)
    runtime.docker(*args)
    row = runtime.wait_world()
    if row["image_id"] != runtime.IMAGE_ID:
        raise RuntimeError("cold clone image drift")
    return row


def _stop_remove_case() -> None:
    try:
        runtime.docker("stop", runtime.WORLD, timeout=120)
    except subprocess.CalledProcessError:
        pass
    runtime.docker("rm", runtime.WORLD, timeout=120)


def freeze() -> dict:
    if STATE_FILE.exists():
        raise RuntimeError("baseline already frozen; use reset")
    baseline = _baseline()
    current = verify.state_snapshot()
    if current["business_sha256"] != baseline["business_sha256"]:
        raise RuntimeError("world changed after independent baseline capture")
    lowerdirs = _volume_lowerdirs()
    runtime.docker("stop", runtime.WORLD, timeout=120)
    runtime.docker("rm", runtime.WORLD, timeout=120)
    try:
        for role, source in lowerdirs.items():
            _mount(role, source)
        row = _create_case()
        after = verify.state_snapshot()
        if after["business_sha256"] != baseline["business_sha256"]:
            raise RuntimeError("first cold clone differs from frozen business baseline")
        state = {"schema": "envloop-gitlab-overlay-cold-reset-v1",
                 "baseline_business_sha256": baseline["business_sha256"],
                 "seed_volume_lowerdirs": lowerdirs,
                 "clone_generation": 1,
                 "first_clone_container_id_sha256": row["container_id_sha256"],
                 "first_clone_readback_equal": True}
        factory.write_private(STATE_FILE, state)
        return {"baseline_frozen": True, "generation": 1,
                "same_business_sha256": True,
                "seed_named_volumes_unmodified_by_clone": True}
    except Exception:
        # Retain lowerdirs and upperdirs for inspection. The preserved demo is
        # still stopped; recovery can be performed with runtime.restore_demo.
        raise


def promote_replacement_baseline() -> dict:
    """Freeze 31-project state on new named volumes after reserve refill.

    This one-time migration copies a stopped, verified v1 overlay merge into
    new v2 seed volumes. The 30-project seed, first overlay, and its receipts
    remain private for forensic replay; no final outcome is promoted.
    """
    from . import bootstrap, quarantine, sweep

    if not STATE_FILE.exists():
        # STATE_FILE is the v1 path name shared by the migration; its contents
        # record the actual old lowerdirs and must be preserved before replace.
        raise RuntimeError("v1 cold clone state is missing")
    global VM_ROOT
    old_state = _state()
    if runtime.ACTIVE_VERSION != "v1":
        raise RuntimeError("reserve baseline is already promoted")
    if len(bootstrap.all_projects(bootstrap.world())) != 31:
        raise RuntimeError("replacement project was not generated")
    if len(sweep.candidates()) != 100 or not quarantine.public_counts()[
            "refill_complete_as_inventory_only"]:
        raise RuntimeError("five exposed candidates not fully refilled")
    current = verify.state_snapshot()
    if len(current["project_ids"]) != 31:
        raise RuntimeError("replacement project is not persisted")
    verify.verify_bootstrap(current)
    old_baseline = json.loads((PRIVATE / "baseline-persisted-state.json").read_text())
    if len(old_baseline["project_ids"]) != 30:
        raise RuntimeError("original 30-project baseline was not preserved")
    _stop_remove_case()
    next_volumes = runtime.volume_names("v2")
    for role, volume in next_volumes.items():
        runtime.docker("volume", "create", volume, timeout=30)
        source = f"{LEGACY_VM_ROOT}/{role}/merged/."
        target = f"/var/lib/docker/volumes/{volume}/_data/"
        vm_shell(f"set -eu; cp -a {source} {target}", timeout=600)
    for role in runtime.DESTS:
        base = f"{LEGACY_VM_ROOT}/{role}"
        vm_shell("set -eu; "
                 f"if mountpoint -q {base}/merged; then umount {base}/merged; fi")
    args = ["run", "-d", "--name", runtime.WORLD, "--hostname", "gitlab-world.local",
            "--restart", "no", "--env-file", str(runtime._env_file()),
            "-p", "127.0.0.1:8014:8014"]
    for role, destination in runtime.DESTS.items():
        args.extend(["-v", next_volumes[role] + ":" + destination])
    args.append(runtime.IMAGE)
    runtime.docker(*args)
    runtime.wait_world()
    copied = verify.state_snapshot()
    if copied["business_sha256"] != current["business_sha256"]:
        raise RuntimeError("new seed volumes differ from verified 31-project state")
    (PRIVATE / "baseline-persisted-state.json").rename(
        PRIVATE / "baseline-persisted-state-v1.json")
    STATE_FILE.rename(PRIVATE / "cow-reset-state-v1.json")
    verify.save_baseline(copied)
    runtime.private_write(runtime.ACTIVE_VERSION_FILE, "v2\n")
    runtime.ACTIVE_VERSION = "v2"
    runtime.VOLUMES = next_volumes
    VM_ROOT = "/var/lib/envloop-gitlab-cow-v2"
    result = freeze()
    return {"replacement_source_refilled": True, "final_unexposed_candidate_count": 100,
            "new_project_count": 31,
            "new_business_sha256": copied["business_sha256"],
            "new_cold_clone_equal": result["same_business_sha256"],
            "official_final_admitted": 0}


def reset() -> dict:
    state = _state()
    baseline = _baseline()
    if state["baseline_business_sha256"] != baseline["business_sha256"]:
        raise RuntimeError("reset state and independent business baseline differ")
    _stop_remove_case()
    for role in runtime.DESTS:
        _unmount_and_clear(role)
        _mount(role, state["seed_volume_lowerdirs"][role])
    row = _create_case()
    after = verify.state_snapshot()
    if after["business_sha256"] != baseline["business_sha256"]:
        raise RuntimeError("cold reset did not restore exact monitored business state")
    state["clone_generation"] += 1
    state["last_clone_container_id_sha256"] = row["container_id_sha256"]
    state["last_readback_equal"] = True
    temporary = STATE_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    temporary.chmod(0o600)
    temporary.replace(STATE_FILE)
    return {"cold_reset": True, "generation": state["clone_generation"],
            "same_business_sha256": True,
            "container_identity_changed": row["container_id_sha256"] !=
                state["first_clone_container_id_sha256"]}


def resume_after_demo() -> dict:
    """Resume a preserved frozen world after the original demo was restored."""
    state = _state()
    demo = runtime.proof(runtime.DEMO)
    pre = json.loads((PRIVATE / "demo-prestop.json").read_text())
    if runtime.stable_identity(demo) != runtime.stable_identity(pre) or not demo["running"]:
        raise RuntimeError("preserved demo identity or running state changed")
    try:
        runtime.inspect(runtime.WORLD)
    except subprocess.CalledProcessError:
        pass
    else:
        raise RuntimeError("disposable world already exists; reset it instead")
    runtime.docker("stop", runtime.DEMO, timeout=120)
    try:
        for role in runtime.DESTS:
            _mount(role, state["seed_volume_lowerdirs"][role])
        row = _create_case()
        after = verify.state_snapshot()
        if after["business_sha256"] != state["baseline_business_sha256"]:
            raise RuntimeError("resumed cold clone differs from frozen baseline")
        return {"resumed": True, "same_business_sha256": True,
                "new_case_container_id_sha256": row["container_id_sha256"]}
    except Exception:
        runtime.docker("start", runtime.DEMO, timeout=120)
        raise


def restore_preserved_demo(*, remove_seed_volumes: bool = False) -> dict:
    if STATE_FILE.exists():
        try:
            _stop_remove_case()
        except subprocess.CalledProcessError:
            pass
        for role in runtime.DESTS:
            _unmount_and_clear(role)
        vm_shell(f"rm -rf {VM_ROOT}")
        if remove_seed_volumes:
            for volume in runtime.VOLUMES.values():
                runtime.docker("volume", "rm", volume, timeout=120)
    restored = runtime.restore_demo(remove_world=False)
    restored["world_removed"] = True
    restored["seed_volumes_retained_for_replay"] = not remove_seed_volumes
    return restored


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["freeze", "reset", "restore-demo",
                                           "resume", "promote-reserve"])
    args = parser.parse_args()
    if args.action == "freeze":
        result = freeze()
    elif args.action == "reset":
        result = reset()
    elif args.action == "resume":
        result = resume_after_demo()
    elif args.action == "promote-reserve":
        result = promote_replacement_baseline()
    else:
        result = restore_preserved_demo()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
