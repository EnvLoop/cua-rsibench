"""Lifecycle of a disposable GitLab CE 18.5 world, preserving the demo.

No benchmark credential is printed. The demo is stopped, never mutated or
removed. Its exact identity/mounts/ports/health are checked on restoration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import time
from urllib.request import urlopen


CONTEXT = "colima-cua-gitlab"
DEMO = "cua-v06-gitlab-demo"
WORLD = "envloop-gitlab-world-v1"
IMAGE = "gitlab/gitlab-ce:18.5.0-ce.0"
IMAGE_ID = "sha256:f7e992491db0c80a9a3f066c2c26e69b444307b5a8834e1bdde7929c4a74e97e"
BASE = "http://127.0.0.1:8014"
PRIVATE = Path(__file__).resolve().parents[1] / "work/gitlab-full-world"
VOLUMES = {"config": WORLD + "-config", "logs": WORLD + "-logs",
           "data": WORLD + "-data"}
DESTS = {"config": "/etc/gitlab", "logs": "/var/log/gitlab",
         "data": "/var/opt/gitlab"}


def docker(*args: str, timeout: int = 120, input_text: str | None = None) -> str:
    result = subprocess.run(["docker", "--context", CONTEXT, *args],
                            text=True, input=input_text, capture_output=True,
                            timeout=timeout, check=True)
    return result.stdout.strip()


def inspect(name: str) -> dict:
    rows = json.loads(docker("inspect", name, timeout=30))
    if len(rows) != 1:
        raise RuntimeError("ambiguous GitLab container")
    return rows[0]


def proof(name: str) -> dict:
    row = inspect(name)
    mounts = {mount["Destination"]: {"type": mount["Type"],
                                    "name": mount.get("Name", ""),
                                    "source_sha256": hashlib.sha256(mount["Source"].encode()).hexdigest()}
              for mount in row["Mounts"]}
    return {"container_id_sha256": hashlib.sha256(row["Id"].encode()).hexdigest(),
            "image_ref": row["Config"]["Image"], "image_id": row["Image"],
            "mounts": mounts,
            "ports": row["HostConfig"]["PortBindings"],
            "running": row["State"]["Running"],
            "health": row["State"].get("Health", {}).get("Status")}


def stable_identity(row: dict) -> dict:
    return {key: row[key] for key in
            ("container_id_sha256", "image_ref", "image_id", "mounts", "ports")}


def private_write(path: Path, text: str) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with path.open("x") as stream:
        stream.write(text)
    path.chmod(0o600)


def _env_file() -> Path:
    path = PRIVATE / "runtime.env"
    if not path.exists():
        password = secrets.token_urlsafe(40)
        # One-line Omnibus configuration is accepted by Docker's --env-file.
        config = ("external_url 'http://127.0.0.1:8014'; "
                  "nginx['listen_port'] = 8014; "
                  "letsencrypt['enable'] = false; "
                  "gitlab_rails['gitlab_email_enabled'] = false; "
                  "gitlab_rails['gitlab_default_projects_features_builds'] = false")
        private_write(path, f"GITLAB_ROOT_PASSWORD={password}\n"
                            f"GITLAB_OMNIBUS_CONFIG={config}\n")
    if path.stat().st_mode & 0o077:
        raise RuntimeError("private GitLab credential file is not restrictive")
    return path


def credential() -> str:
    line = [entry for entry in _env_file().read_text().splitlines()
            if entry.startswith("GITLAB_ROOT_PASSWORD=")]
    if len(line) != 1 or not line[0].split("=", 1)[1]:
        raise RuntimeError("isolated GitLab credential missing")
    return line[0].split("=", 1)[1]


def _http_ready() -> bool:
    try:
        with urlopen(BASE + "/users/sign_in", timeout=5) as response:
            return response.status == 200
    except Exception:
        return False


def wait_world(timeout_seconds: int = 900) -> dict:
    end = time.monotonic() + timeout_seconds
    while time.monotonic() < end:
        state = proof(WORLD)
        if (state["running"] and state["health"] == "healthy"
                and _http_ready()):
            return state
        time.sleep(10)
    raise TimeoutError("disposable GitLab world did not become healthy")


def start() -> dict:
    PRIVATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    pre_path = PRIVATE / "demo-prestop.json"
    demo = proof(DEMO)
    if demo["image_id"] != IMAGE_ID or not demo["running"] or demo["health"] != "healthy":
        raise RuntimeError("preserved demo was not the expected healthy GitLab image")
    if pre_path.exists():
        if json.loads(pre_path.read_text()) != demo:
            raise RuntimeError("demo identity differs from saved pre-stop proof")
    else:
        private_write(pre_path, json.dumps(demo, indent=2, sort_keys=True) + "\n")
    docker("stop", DEMO, timeout=120)
    try:
        for volume in VOLUMES.values():
            docker("volume", "create", volume, timeout=30)
        args = ["run", "-d", "--name", WORLD, "--hostname", "gitlab-world.local",
                "--restart", "no", "--env-file", str(_env_file()),
                "-p", "127.0.0.1:8014:8014"]
        for role, name in VOLUMES.items():
            args.extend(["-v", name + ":" + DESTS[role]])
        args.append(IMAGE)
        docker(*args, timeout=120)
        world = wait_world()
        if world["image_id"] != IMAGE_ID or world["health"] != "healthy":
            raise RuntimeError("disposable GitLab image/health mismatch")
        return {"demo_pre_stop_identity_sha256": hashlib.sha256(
                    json.dumps(stable_identity(demo), sort_keys=True).encode()).hexdigest(),
                "world": world, "demo_stopped": True}
    except Exception:
        # Leave any created world and volumes for forensic inspection, but
        # restore the original demo whenever its port is free.
        try:
            docker("stop", WORLD, timeout=120)
        except subprocess.CalledProcessError:
            pass
        docker("start", DEMO, timeout=120)
        raise


def restore_demo(*, remove_world: bool = False) -> dict:
    pre_path = PRIVATE / "demo-prestop.json"
    if not pre_path.exists():
        raise RuntimeError("missing demo pre-stop proof")
    pre = json.loads(pre_path.read_text())
    try:
        docker("stop", WORLD, timeout=120)
    except subprocess.CalledProcessError:
        pass
    if remove_world:
        docker("rm", WORLD, timeout=120)
        for name in VOLUMES.values():
            docker("volume", "rm", name, timeout=120)
    if not proof(DEMO)["running"]:
        docker("start", DEMO, timeout=120)
    end = time.monotonic() + 900
    while time.monotonic() < end:
        after = proof(DEMO)
        if after["health"] == "healthy":
            break
        time.sleep(10)
    else:
        raise TimeoutError("preserved GitLab demo did not return healthy")
    if stable_identity(pre) != stable_identity(after):
        raise RuntimeError("preserved GitLab demo identity/mounts/ports changed")
    return {"demo_identity_preserved": True, "demo_healthy": True,
            "same_container_id": pre["container_id_sha256"] == after["container_id_sha256"],
            "world_removed": remove_world}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "status", "restore", "remove"])
    args = parser.parse_args()
    if args.action == "start":
        result = start()
    elif args.action == "status":
        result = {"demo": proof(DEMO), "world": proof(WORLD)}
    else:
        result = restore_demo(remove_world=args.action == "remove")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
