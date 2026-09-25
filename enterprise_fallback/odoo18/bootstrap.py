"""One-shot, local-only bootstrap for the Odoo Community development world."""

from __future__ import annotations

import json
import os
import secrets
import socket
import subprocess
import xmlrpc.client

from factory import HERE, PRIVATE, seed
from reset import checkpoint, compose, wait_web
from verify import freeze

ROLE_SQL = """
CREATE ROLE bench_verify LOGIN;
GRANT CONNECT ON DATABASE bench TO bench_verify;
GRANT USAGE ON SCHEMA public TO bench_verify;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO bench_verify;
ALTER DEFAULT PRIVILEGES FOR ROLE odoo IN SCHEMA public
  GRANT SELECT ON TABLES TO bench_verify;
"""


def run(args: list[str]) -> None:
    subprocess.run(args, cwd=HERE, check=True, capture_output=True, text=True)


def bootstrap() -> dict:
    env = HERE / ".env"
    if env.exists() or (PRIVATE / "baseline_snapshot.json").exists():
        raise RuntimeError("This one-shot bootstrap requires a fresh isolated project and no .env")
    admin_password = secrets.token_urlsafe(32)
    port = int(os.environ.get("ODOO_PORT", "8078"))
    if not 1024 <= port <= 65535:
        raise ValueError("ODOO_PORT must be an unprivileged TCP port")
    with socket.socket() as probe:
        probe.settimeout(2)
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            raise RuntimeError(f"Loopback port {port} is already occupied; choose an unused ODOO_PORT")
    project = os.environ.get("ODOO_PROJECT", "envloop-odoo-fallback")
    if not project.startswith("envloop-odoo-") or not project.replace("-", "").isalnum():
        raise ValueError("ODOO_PROJECT must be an isolated envloop-odoo-* name")
    env.write_text(
        "ODOO_DB_PASSWORD=" + secrets.token_urlsafe(32) + "\n"
        "ODOO_ADMIN_PASSWORD=" + admin_password + "\n"
        f"ODOO_PORT={port}\n"
        f"ODOO_PROJECT={project}\n"
    )
    env.chmod(0o600)
    run(compose("up", "-d", "db"))
    run(compose("--profile", "bootstrap", "run", "--rm", "init"))
    run(compose("up", "-d", "web"))
    wait_web()
    common = xmlrpc.client.ServerProxy(f"http://127.0.0.1:{port}/xmlrpc/2/common", allow_none=True)
    models = xmlrpc.client.ServerProxy(f"http://127.0.0.1:{port}/xmlrpc/2/object", allow_none=True)
    uid = common.authenticate("bench", "admin", "admin", {})
    if uid != 2:
        raise RuntimeError("Expected a fresh Odoo Community admin account")
    if not models.execute_kw("bench", uid, "admin", "res.users", "write", [[uid], {"password": admin_password}]):
        raise RuntimeError("Could not rotate the temporary default admin password")
    run(compose("exec", "-T", "db", "psql", "-U", "odoo", "-d", "bench", "-v", "ON_ERROR_STOP=1", "-c", ROLE_SQL))
    fixture = seed()
    counts = freeze()
    saved = checkpoint()
    return {
        "status": "local_development_world_ready",
        "fixture": {key: value for key, value in fixture.items() if key != "candidate_ids"},
        "evaluator_scope_counts": counts,
        "checkpoint": saved,
    }


if __name__ == "__main__":
    print(json.dumps(bootstrap(), indent=2))
