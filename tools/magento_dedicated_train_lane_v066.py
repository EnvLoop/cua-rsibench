"""Dedicated, journaled Magento train clone lane; no evaluator-lane fallback.

This module defines a separate cron-free original-Magento app/search pair and
a second fresh pair for material reset. It never adopts the running 100-case
evaluator's names, ports or network. Every mutating Docker command has one
durable intent and outcome; an uncertain outcome is terminal until a separate
operator audit. The module has no CLI and does no work on import.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import time
from typing import Callable

from magento_catalog_factory import seed, verify
from magento_catalog_factory.plan import require
from tools import qualify_magento_original_catalog_v1 as original_gui
from tools import sweep_magento_original_gui_controls_v1 as evaluator
from tools.reconcile_magento_unseeded_search_drift_v1 import SQL_READ


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "envloop-magento-v066-dedicated-train-lane-v1"
CONTEXT = "colima-cua-scale"
NETWORK = "envloop-magento-v066-teacher-network"
PAIRS = (
    ("envloop-magento-original-v066-teacher-app-a",
     "envloop-magento-v066-teacher-search-a", 7820, 7821),
    ("envloop-magento-original-v066-teacher-app-b",
     "envloop-magento-v066-teacher-search-b", 7822, 7823),
)
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
MAX_PROCESS_OUTPUT = 2_000_000
WAIT_SECONDS = 900


class DedicatedLaneError(RuntimeError):
    """Fixed safe subtype; no raw Docker/credential/source text."""


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":"), allow_nan=False) + "\n").encode()


def private_file(path: Path) -> bool:
    return (path.is_file() and not path.is_symlink() and
            path.stat().st_mode & 0o077 == 0)


def private_new(path: Path, value: object) -> str:
    if (path.exists() or path.is_symlink() or
            path.parent.is_symlink() or
            path.parent.stat().st_mode & 0o077):
        raise DedicatedLaneError("private_lane_receipt_path_unsafe")
    raw = canonical(value)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return digest(raw)


@dataclass(frozen=True)
class Pair:
    index: int
    app: str
    search: str
    http_port: int
    control_port: int

    def __post_init__(self):
        if (self.index not in (0, 1) or
                (self.app, self.search, self.http_port,
                 self.control_port) != PAIRS[self.index] or
                self.app == evaluator.APP or
                self.search == evaluator.SEARCH or
                {self.http_port, self.control_port} & {7794, 7795}):
            raise DedicatedLaneError("dedicated_pair_overlaps_evaluator")


def pair(index: int) -> Pair:
    return Pair(index, *PAIRS[index])


def _default_process(args: list[str], *, input_text: str | None,
                     timeout: int):
    return subprocess.run(args, input=input_text, capture_output=True,
                          text=True, timeout=timeout, check=False)


class CommandJournal:
    """Append-only, one-shot Docker process intents for one private episode."""

    def __init__(self, directory: Path, *, runner: Callable = _default_process):
        self.directory = Path(directory).resolve()
        if (not self.directory.is_dir() or self.directory.is_symlink() or
                self.directory.stat().st_mode & 0o077):
            raise DedicatedLaneError("private_lane_directory_unsafe")
        self.path = self.directory / "docker-steps.private.jsonl"
        if self.path.exists() or self.path.is_symlink():
            raise DedicatedLaneError("dedicated_lane_attempt_already_exists")
        self.runner = runner
        self.used = set()
        self.previous = "0" * 64

    def _append(self, row: dict) -> None:
        value = {"schema": "envloop-magento-v066-docker-step-v1",
                 "previous_sha256": self.previous, **row}
        raw = canonical(value)
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        self.previous = digest(raw)

    def _diagnostic(self, label: str, stream: str,
                    value: str | bytes | None) -> None:
        if value is None:
            return
        raw = value.encode() if type(value) is str else value
        if type(raw) is not bytes or not raw or len(raw) > MAX_PROCESS_OUTPUT:
            return
        directory = self.directory / "process-diagnostics"
        directory.mkdir(mode=0o700, exist_ok=True)
        path = directory / f"{label}.{stream}.private.bin"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as output:
            output.write(raw)
            output.flush()
            os.fsync(output.fileno())

    def run(self, label: str, docker_args: tuple[str, ...], *,
            mutating: bool, input_text: str | None = None,
            timeout: int = 120, allow_absent: bool = False) -> str | None:
        if (not re.fullmatch(r"[a-z][a-z0-9_-]{1,80}", label) or
                label in self.used or not docker_args or
                type(timeout) is not int or not 1 <= timeout <= 900):
            raise DedicatedLaneError("docker_step_duplicate_or_unbounded")
        self.used.add(label)
        command = ["docker", "--context", CONTEXT, *docker_args]
        self._append({"event": "intent", "label": label,
                      "mutating": mutating,
                      "command_sha256": digest(canonical(command)),
                      "input_sha256": digest(input_text.encode())
                      if input_text is not None else None,
                      "timeout_seconds": timeout})
        try:
            result = self.runner(command, input_text=input_text,
                                 timeout=timeout)
        except Exception as exc:
            try:
                self._diagnostic(label, "stdout", getattr(exc, "stdout", None))
                self._diagnostic(label, "stderr", getattr(exc, "stderr", None))
            except OSError:
                pass
            self._append({"event": "uncertain", "label": label,
                          "reason": "process_transport_or_timeout",
                          "exception_type": type(exc).__name__})
            raise DedicatedLaneError("docker_step_uncertain_no_replay") from None
        stdout = result.stdout
        stderr = result.stderr
        if (type(stdout) is not str or type(stderr) is not str or
                len(stdout.encode()) > MAX_PROCESS_OUTPUT or
                len(stderr.encode()) > MAX_PROCESS_OUTPUT):
            self._append({"event": "uncertain", "label": label,
                          "reason": "process_output_ambiguous"})
            raise DedicatedLaneError("docker_step_uncertain_no_replay")
        absent = (allow_absent and result.returncode != 0 and
                  ("No such object" in stderr or
                   "not found" in stderr.lower()))
        self._append({"event": "result", "label": label,
                      "returncode": result.returncode,
                      "stdout_sha256": digest(stdout.encode()),
                      "stderr_sha256": digest(stderr.encode()),
                      "absent": absent})
        if absent:
            return None
        if result.returncode != 0:
            try:
                self._diagnostic(label, "stdout", stdout)
                self._diagnostic(label, "stderr", stderr)
            except OSError:
                pass
            raise DedicatedLaneError("docker_step_failed_no_replay")
        return stdout


class DedicatedCloneManager:
    """Pinned original images, isolated network, cron-off-before-start pairs."""

    def __init__(self, journal: CommandJournal,
                 *, seeder: Callable = seed.seed):
        self.journal = journal
        self.seeder = seeder
        self.network_created = False
        self.network_id = None
        self.prepared: dict[int, dict] = {}
        self.cleaned: set[int] = set()

    def _ports_free(self, spec: Pair) -> None:
        for port in (spec.http_port, spec.control_port):
            with socket.socket() as sock:
                try:
                    sock.bind(("127.0.0.1", port))
                except OSError:
                    raise DedicatedLaneError(
                        "dedicated_loopback_port_unavailable") from None

    def _inspect(self, label: str, name: str) -> dict | None:
        raw = self.journal.run(label, ("inspect", name),
                               mutating=False, timeout=30,
                               allow_absent=True)
        if raw is None:
            return None
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            raise DedicatedLaneError("docker_inspect_invalid_json") from None
        if type(result) is not list or len(result) != 1:
            raise DedicatedLaneError("docker_inspect_identity_ambiguous")
        return result[0]

    def _network_absent(self) -> None:
        raw = self.journal.run("network_absent", ("network", "inspect", NETWORK),
                               mutating=False, timeout=30, allow_absent=True)
        if raw is not None:
            raise DedicatedLaneError("dedicated_network_already_exists")

    def _images_pinned(self) -> None:
        raw = self.journal.run(
            "pinned_images", ("image", "inspect", seed.IMAGE,
                               verify.NATIVE_SEARCH_IMAGE),
            mutating=False, timeout=30)
        try:
            images = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            raise DedicatedLaneError("pinned_clone_images_missing") from None
        if (type(images) is not list or len(images) != 2 or
                {row.get("Id") for row in images} !=
                {seed.IMAGE, verify.NATIVE_SEARCH_IMAGE}):
            raise DedicatedLaneError("pinned_clone_images_missing")

    def _ensure_isolated_start(self, spec: Pair) -> None:
        if spec.index == 0:
            for kind, name in (("app", evaluator.APP),
                               ("search", evaluator.SEARCH)):
                if self._inspect(f"evaluator_{kind}_absent", name) is not None:
                    raise DedicatedLaneError(
                        "running_evaluator_container_overlap")
            self._network_absent()
            self._images_pinned()
        self._ports_free(spec)
        for kind, name in (("app", spec.app), ("search", spec.search)):
            if self._inspect(f"p{spec.index}_{kind}_absent", name) is not None:
                raise DedicatedLaneError("dedicated_name_already_exists")
        if not self.network_created:
            created = self.journal.run(
                "network_create", ("network", "create", "--driver",
                                   "bridge", NETWORK), mutating=True,
                timeout=30)
            self.network_id = (created or "").strip()
            if not re.fullmatch(r"[0-9a-f]{12,64}", self.network_id):
                raise DedicatedLaneError(
                    "dedicated_network_create_result_ambiguous")
            raw = self.journal.run(
                "network_created_identity",
                ("network", "inspect", NETWORK),
                mutating=False, timeout=30)
            info = json.loads(raw)
            if (type(info) is not list or len(info) != 1 or
                    info[0].get("Id") != self.network_id or
                    info[0].get("Name") != NETWORK or
                    info[0].get("Driver") != "bridge"):
                raise DedicatedLaneError("dedicated_network_identity_changed")
            self.network_created = True

    def _ready(self, spec: Pair) -> dict:
        app = search = None
        for attempt in range(30):
            app = self._inspect(f"p{spec.index}_app_running_{attempt:02d}",
                                spec.app)
            search = self._inspect(
                f"p{spec.index}_search_running_{attempt:02d}", spec.search)
            if (app is not None and search is not None and
                    app.get("State", {}).get("Running") is True and
                    search.get("State", {}).get("Running") is True):
                break
            time.sleep(2)
        else:
            raise DedicatedLaneError("dedicated_pair_missing_after_start")
        for record, name, image in (
                (app, spec.app, seed.IMAGE),
                (search, spec.search, verify.NATIVE_SEARCH_IMAGE)):
            if (record.get("Name", "").lstrip("/") != name or
                    record.get("Image") != image or
                    record.get("Mounts") != [] or
                    record.get("State", {}).get("Running") is not True or
                    NETWORK not in record.get("NetworkSettings", {})
                    .get("Networks", {})):
                raise DedicatedLaneError("dedicated_pair_identity_changed")
        ports = app["NetworkSettings"]["Ports"]
        if (ports.get("80/tcp") != [{"HostIp": "127.0.0.1",
                                    "HostPort": str(spec.http_port)}] or
                ports.get("8877/tcp") != [{"HostIp": "127.0.0.1",
                                      "HostPort": str(spec.control_port)}]):
            raise DedicatedLaneError("dedicated_pair_port_changed")
        return {"app_id_sha256": digest(app["Id"].encode()),
                "search_id_sha256": digest(search["Id"].encode()),
                "app_id": app["Id"], "search_id": search["Id"],
                "app_image_sha256": app["Image"],
                "search_image_sha256": search["Image"],
                "no_host_mounts": True,
                "loopback_ports": [spec.http_port, spec.control_port],
                "network": NETWORK}

    def _wait_services(self, spec: Pair) -> None:
        for attempt in range(45):
            try:
                health_raw = self._exec(
                    f"p{spec.index}_search_health_{attempt:02d}",
                    spec.search, "curl", "-fsS", "--max-time", "5",
                    "http://127.0.0.1:9200/_cluster/health", timeout=10)
                health = json.loads(health_raw)
                admin = self._exec(
                    f"p{spec.index}_app_http_{attempt:02d}", spec.app,
                    "curl", "-sS", "-o", "/dev/null", "-w",
                    "%{http_code}", "--max-time", "5",
                    "http://127.0.0.1/admin", timeout=10)
                if (health.get("status") in ("yellow", "green") and
                        health.get("number_of_nodes") == 1 and
                        not health.get("timed_out") and
                        admin.strip() in ("200", "301", "302")):
                    return
            except (DedicatedLaneError, ValueError, KeyError,
                    json.JSONDecodeError):
                pass  # A read-only readiness probe may be repeated.
            time.sleep(2)
        raise DedicatedLaneError("dedicated_app_or_search_readiness_failed")

    def _exec(self, label: str, container: str, *command: str,
              timeout: int = 120, input_text: str | None = None) -> str:
        args = ("exec", *(["-i"] if input_text is not None else []),
                container, *command)
        read_only = (bool(command) and
                     (command[0] in ("curl", "cat", "ps") or
                      command[:2] == ("supervisorctl", "status")))
        return self.journal.run(label, args, mutating=not read_only,
            timeout=timeout, input_text=input_text) or ""

    def prepare(self, spec: Pair, *, source_search_sha256: str) -> dict:
        if spec.index in self.prepared or spec.index in self.cleaned:
            raise DedicatedLaneError("dedicated_pair_reuse_forbidden")
        self._ensure_isolated_start(spec)
        self.journal.run(
            f"p{spec.index}_search_run",
            ("run", "-d", "--name", spec.search, "--network", NETWORK,
             "--memory", "1536m", "-e", "discovery.type=single-node",
             "-e", "ES_JAVA_OPTS=-Xms512m -Xmx512m",
             verify.NATIVE_SEARCH_IMAGE), mutating=True, timeout=120)
        self.journal.run(
            f"p{spec.index}_app_run",
            ("run", "-d", "--name", spec.app, "--network", NETWORK,
             "-p", f"127.0.0.1:{spec.http_port}:80",
             "-p", f"127.0.0.1:{spec.control_port}:8877",
             "--entrypoint", "/bin/sh", seed.IMAGE, "-c",
             "sed -i 's/^autostart=true$/autostart=false/' "
             "/etc/supervisor.d/cron.ini && "
             "grep -q '^autostart=false$' /etc/supervisor.d/cron.ini && "
             "exec /custom-entrypoint.sh supervisord -n -j /supervisord.pid"),
            mutating=True, timeout=120)
        proof = self._ready(spec)
        self._wait_services(spec)
        self._exec(f"p{spec.index}_embedded_search_stop", spec.app,
                   "supervisorctl", "stop", "elasticsearch", timeout=30)
        cron = self._exec(f"p{spec.index}_cron_status", spec.app,
                          "supervisorctl", "status", "cron", timeout=30)
        config = self._exec(f"p{spec.index}_cron_config", spec.app,
                            "cat", "/etc/supervisor.d/cron.ini", timeout=30)
        if ("STOPPED" not in cron or "autostart=false" not in config or
                "autostart=true" in config):
            raise DedicatedLaneError("dedicated_cron_autostart_not_disabled")
        settings = (
            ("catalog/search/engine", "elasticsearch7"),
            ("catalog/search/elasticsearch7_server_hostname", spec.search),
            ("catalog/search/elasticsearch7_server_port", "9200"),
            ("catalog/search/elasticsearch7_index_prefix", "magento2"),
            ("web/unsecure/base_url",
             f"http://127.0.0.1:{spec.http_port}/"),
            ("web/secure/base_url",
             f"http://127.0.0.1:{spec.http_port}/"),
        )
        for index, (key, value) in enumerate(settings):
            self._exec(f"p{spec.index}_setting_{index}", spec.app,
                       "php", "/var/www/magento2/bin/magento",
                       "config:set", key, value, timeout=180)
        self._exec(f"p{spec.index}_config_cache", spec.app, "php",
                   "/var/www/magento2/bin/magento", "cache:clean",
                   "config", timeout=180)
        self._exec(f"p{spec.index}_search_reindex", spec.app, "php",
                   "/var/www/magento2/bin/magento", "indexer:reindex",
                   "catalogsearch_fulltext", timeout=240)
        # Search and price indices must agree with the original frozen source
        # before any task fixture is seeded. This is read-only verification.
        for attempt in range(15):
            try:
                raw = self._exec(
                    f"p{spec.index}_source_search_{attempt:02d}",
                    spec.app, "curl", "-fsS", "--max-time", "30",
                    f"http://{spec.search}:9200/"
                    "magento2_product_1/_search?size=1000", timeout=45)
                result = json.loads(raw)
                hits = result["hits"]["hits"]
                documents = {row["_id"]: row["_source"] for row in hits}
                if (len(hits) == result["hits"]["total"]["value"] == 181
                        and verify.canonical_sha(documents) ==
                        source_search_sha256):
                    break
            except (DedicatedLaneError, ValueError, KeyError,
                    json.JSONDecodeError):
                pass  # Re-read search only; never rerun the indexer.
            time.sleep(2)
        else:
            raise DedicatedLaneError("dedicated_source_search_index_changed")
        price_raw = self._exec(f"p{spec.index}_price_index", spec.app,
                               "php", "-r", SQL_READ, timeout=90)
        price = json.loads(price_raw)
        if (price.get("price_rows") != 8156 or
                price.get("price_key_sets_equal") is not True or
                price.get("price_changed_rows") != 0):
            raise DedicatedLaneError("dedicated_price_index_drift")
        self.prepared[spec.index] = proof
        return {"schema": "envloop-magento-v066-pair-prepared-v1",
                "index": spec.index, "source_search_sha256":
                    source_search_sha256,
                "cron_autostart_disabled_before_supervisor": True,
                "search_document_count": 181,
                **proof}

    def seed_case(self, spec: Pair, case: dict) -> dict:
        if spec.index not in self.prepared:
            raise DedicatedLaneError("dedicated_pair_not_prepared")
        label = f"p{spec.index}_seed_intent"
        if label in self.journal.used:
            raise DedicatedLaneError("dedicated_seed_replay_forbidden")
        self.journal.used.add(label)
        self.journal._append({"event": "intent", "label": label,
                              "mutating": True,
                              "task_package_sha256": case["package_sha256"]})
        try:
            result = self.seeder(case, spec.app, spec.http_port,
                                 spec.control_port)
        except Exception:
            self.journal._append({"event": "uncertain", "label": label,
                                  "reason": "task_seed_may_have_mutated"})
            raise DedicatedLaneError("dedicated_seed_uncertain_no_replay") from None
        self.journal._append({"event": "result", "label": label,
                              "receipt_sha256": digest(canonical(result))})
        return result

    def cleanup(self, spec: Pair) -> dict:
        if spec.index not in self.prepared or spec.index in self.cleaned:
            raise DedicatedLaneError("dedicated_cleanup_unowned_or_repeated")
        expected = self.prepared[spec.index]
        for kind, name, key in (("app", spec.app, "app_id"),
                                ("search", spec.search, "search_id")):
            observed = self._inspect(f"p{spec.index}_{kind}_precleanup", name)
            if (observed is None or observed.get("Id") != expected[key] or
                    observed.get("Mounts") != [] or
                    observed.get("State", {}).get("Running") is not True):
                raise DedicatedLaneError("dedicated_cleanup_identity_changed")
            self.journal.run(f"p{spec.index}_{kind}_stop",
                             ("stop", name), mutating=True, timeout=90)
            stopped = self._inspect(f"p{spec.index}_{kind}_stopped", name)
            if (stopped is None or stopped.get("Id") != expected[key] or
                    stopped.get("State", {}).get("Running") is not False):
                raise DedicatedLaneError("dedicated_stop_uncertain_no_replay")
            self.journal.run(f"p{spec.index}_{kind}_remove",
                             ("rm", name), mutating=True, timeout=90)
            if self._inspect(f"p{spec.index}_{kind}_removed", name) is not None:
                raise DedicatedLaneError("dedicated_remove_uncertain_no_replay")
        self.cleaned.add(spec.index)
        return {"index": spec.index, "app_id_sha256":
                expected["app_id_sha256"],
                "search_id_sha256": expected["search_id_sha256"],
                "both_containers_absent": True,
                "cleanup_journal_sha256": digest(self.journal.path.read_bytes())}

    def cleanup_network(self) -> dict:
        if not self.network_created or self.cleaned != {0, 1}:
            raise DedicatedLaneError("dedicated_network_cleanup_too_early")
        raw = self.journal.run("network_precleanup_identity",
                               ("network", "inspect", NETWORK),
                               mutating=False, timeout=30)
        info = json.loads(raw)
        if (type(info) is not list or len(info) != 1 or
                info[0].get("Id") != self.network_id or
                info[0].get("Name") != NETWORK or
                info[0].get("Containers", {}) != {}):
            raise DedicatedLaneError("dedicated_network_cleanup_identity_changed")
        self.journal.run("network_remove", ("network", "rm", NETWORK),
                         mutating=True, timeout=30)
        if self.journal.run("network_removed", ("network", "inspect", NETWORK),
                            mutating=False, timeout=30,
                            allow_absent=True) is not None:
            raise DedicatedLaneError("dedicated_network_remove_uncertain")
        return {"network": NETWORK, "removed": True,
                "journal_sha256": digest(self.journal.path.read_bytes())}


def read_snapshot_scoped(case: dict, spec: Pair, page_id: int,
                         manager: DedicatedCloneManager) -> dict:
    """Independent original-Magento SQL/search readback for this pair only."""
    if spec.index not in manager.prepared or page_id <= 0:
        raise DedicatedLaneError("scoped_snapshot_pair_or_page_unbound")
    target_ids = [int(row["entity_id"]) for row in case["target_variants"]]
    other_ids = [int(row["entity_id"]) for row in
                 case["untouched_comparators"]]
    if (not target_ids or len(set(target_ids + other_ids)) !=
            len(target_ids) + len(other_ids)):
        raise DedicatedLaneError("scoped_snapshot_variants_unbound")
    request = {"target_ids": target_ids,
               "variant_ids": target_ids + other_ids,
               "parent_id": case["parent_id"], "page_id": page_id}
    db = json.loads(manager._exec(
        f"p{spec.index}_snapshot_db_{len(manager.journal.used)}", spec.app,
        "php", "-r", verify.PHP_READ.removeprefix("<?php\n"),
        timeout=180, input_text=json.dumps(request, sort_keys=True)))
    search = json.loads(manager._exec(
        f"p{spec.index}_snapshot_search_{len(manager.journal.used)}",
        spec.app, "curl", "-fsS", "--max-time", "30",
        f"http://{spec.search}:9200/"
        "magento2_product_1/_search?size=1000", timeout=45))
    hits = search["hits"]["hits"]
    if len(hits) != search["hits"]["total"]["value"] or len(hits) <= 100:
        raise DedicatedLaneError("scoped_search_snapshot_truncated")
    documents = {row["_id"]: row["_source"] for row in hits}
    parent = str(case["parent_id"])
    if parent not in documents or len(documents) != len(hits):
        raise DedicatedLaneError("scoped_parent_search_document_missing")
    return {"schema": "envloop-magento-catalog-saved-state-v1",
            "task_id": case["task_id"], "page_id": page_id,
            "database": db,
            "search": {
                "document_count": len(documents),
                "full_sha256": verify.canonical_sha(documents),
                "other_documents_sha256": verify.canonical_sha({
                    key: value for key, value in documents.items()
                    if key != parent}),
                "parent_document_sha256": verify.canonical_sha(
                    documents[parent])}}


class DedicatedMagentoTrainRuntime:
    """Physical app/search pair lifecycle and original-admin Playwright page."""

    qualified = True

    def __init__(self, lane: dict, lane_path: Path,
                 *, runner: Callable = _default_process,
                 seeder: Callable = seed.seed,
                 lock_path: Path | None = None):
        self.lane = lane
        self.lane_path = Path(lane_path)
        self.runner = runner
        self.seeder = seeder
        self.lock_path = (Path(lock_path) if lock_path is not None else
                          ROOT / "work/magento-v066-dedicated-train.lock")

    def reserve_capacity(self, request: dict) -> dict:
        if (request.get("dedicated_lane_sha256") !=
                digest(self.lane_path.read_bytes()) or
                request.get("worker_runtime_sha256") !=
                self.lane.get("runtime_sha256")):
            raise DedicatedLaneError("dedicated_capacity_source_changed")
        return {"schema": "envloop-magento-v066-local-capacity-v1",
                "status": "reserved_before_original_gui_start",
                "provider_invoice_usd": None}

    async def _prove_fresh_reset(self, manager: DedicatedCloneManager,
                                 case: dict, source_sha: str,
                                 first_prepared: dict,
                                 baseline: dict) -> dict:
        first_clean = await asyncio.to_thread(manager.cleanup, pair(0))
        second = pair(1)
        second_prepared = await asyncio.to_thread(
            manager.prepare, second, source_search_sha256=source_sha)
        second_seed = await asyncio.to_thread(manager.seed_case,
                                              second, case)
        restored = await asyncio.to_thread(
            read_snapshot_scoped, case, second,
            second_seed["page_id"], manager)
        allowed = verify.check_material_reset(baseline, restored)
        second_clean = await asyncio.to_thread(manager.cleanup, second)
        network_clean = await asyncio.to_thread(manager.cleanup_network)
        if (first_prepared["app_id_sha256"] ==
                second_prepared["app_id_sha256"] or
                first_prepared["search_id_sha256"] ==
                second_prepared["search_id_sha256"]):
            raise DedicatedLaneError("fresh_clone_identity_not_distinct")
        return {"fresh_clone_reset_passed": True,
                "different_app_container_ids": True,
                "different_search_container_ids": True,
                "no_host_mounts": True,
                "both_pairs_removed": True,
                "allowed_volatile_fields": allowed,
                "restored_snapshot": restored,
                "positive_cleanup": first_clean,
                "reset_cleanup": second_clean,
                "network_cleanup": network_clean,
                "journal_sha256": digest(manager.journal.path.read_bytes())}

    @asynccontextmanager
    async def open_case(self, case: dict, out_dir: Path):
        from playwright.async_api import async_playwright

        directory = Path(out_dir).resolve()
        journal = CommandJournal(directory, runner=self.runner)
        manager = DedicatedCloneManager(journal, seeder=self.seeder)
        self.lock_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(self.lock_path,
                     os.O_RDWR | os.O_CREAT, 0o600)
        browser = None
        session = None
        first_prepared = None
        baseline = None
        source_sha = None
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise DedicatedLaneError("dedicated_train_lane_busy") from None
            source_sha = self.lane["source_search_sha256"]
            first = pair(0)
            first_prepared = await asyncio.to_thread(
                manager.prepare, first,
                source_search_sha256=source_sha)
            seeded = await asyncio.to_thread(manager.seed_case, first, case)
            baseline = await asyncio.to_thread(
                read_snapshot_scoped, case, first, seeded["page_id"],
                manager)
            verify.check_baseline(case, baseline)
            credentials_ref = self.lane["actor_credentials_ref"]
            credentials_path = Path(credentials_ref["path"])
            if (not private_file(credentials_path) or
                    digest(credentials_path.read_bytes()) !=
                    credentials_ref["sha256"]):
                raise DedicatedLaneError("dedicated_actor_credentials_changed")
            credentials = json.loads(credentials_path.read_bytes())
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                context = await browser.new_context(
                    viewport={"width": 1440, "height": 1000},
                    service_workers="block")
                async def restrict(route):
                    from urllib.parse import urlsplit
                    url = urlsplit(route.request.url)
                    if (url.scheme in ("data", "blob", "about") or
                            (url.scheme == "http" and
                             url.hostname in ("localhost", "127.0.0.1") and
                             url.port == first.http_port and
                             url.username is None and url.password is None)):
                        await route.continue_()
                    else:
                        blocked_requests.append(digest(
                            route.request.url.encode()))
                        await route.abort()
                blocked_requests = []
                await context.route("**/*", restrict)
                page = await context.new_page()
                await page.goto(
                    f"http://127.0.0.1:{first.http_port}/admin",
                    wait_until="domcontentloaded", timeout=90000)
                await page.get_by_label("Username", exact=True).fill(
                    credentials["username"])
                await page.get_by_label("Password", exact=True).fill(
                    credentials["password"])
                await page.get_by_role("button", name="Sign in",
                                       exact=True).click()
                await page.get_by_role("heading", name="Dashboard",
                                       exact=True).wait_for(timeout=90000)
                quote = await original_gui.read_quote_in_gui(
                    page, case, directory)
                quote_image = directory / "private-quote-page.png"
                if quote_image.is_file():
                    quote_image.chmod(0o600)
                if (quote.get("quote_visible_in_native_cms") is not True or
                        quote.get("quote_body_sha256") !=
                        case["quote_page_body_sha256"]):
                    raise DedicatedLaneError(
                        "dedicated_quote_not_visible_in_original_gui")
                if blocked_requests:
                    raise DedicatedLaneError(
                        "dedicated_browser_cross_origin_request_blocked")
                session = _TrainSession(case, first, manager,
                                        seeded["page_id"], page, baseline,
                                        first_prepared, quote,
                                        blocked_requests)
                try:
                    yield session
                finally:
                    await context.close()
                    await browser.close()
                    browser = None
        finally:
            try:
                if browser is not None:
                    try:
                        await browser.close()
                    except Exception:
                        pass
                if (session is not None and first_prepared is not None and
                        baseline is not None and source_sha is not None and
                        session.reset_proof is None):
                    # Even a model/GUI failure gets a physical fresh-pair
                    # reset. A partial prepare or uncertain cleanup is never
                    # replayed.
                    session.reset_proof = await self._prove_fresh_reset(
                        manager, case, source_sha, first_prepared, baseline)
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)
            # No catch-up cleanup or Docker retry here. The private journal
            # and exact live identities must be audited by an operator first.


class _TrainSession:
    def __init__(self, case: dict, spec: Pair,
                 manager: DedicatedCloneManager, page_id: int, page,
                 baseline_state: dict, prepared: dict, quote: dict,
                 blocked_requests: list[str]):
        self.case = case
        self.spec = spec
        self.manager = manager
        self.page_id = page_id
        self.page = page
        self.baseline_state = baseline_state
        self.fresh_clone_prepared = bool(
            prepared["cron_autostart_disabled_before_supervisor"] and
            prepared["no_host_mounts"])
        self.native_quote_visible = (
            quote.get("quote_visible_in_native_cms") is True and
            quote.get("quote_body_sha256") ==
            case["quote_page_body_sha256"])
        self.blocked_requests = blocked_requests
        self.reset_proof = None

    async def saved_state(self) -> dict:
        if self.blocked_requests:
            raise DedicatedLaneError(
                "dedicated_browser_cross_origin_request_blocked")
        await self.page.reload(wait_until="domcontentloaded")
        await self.page.locator("body").wait_for(timeout=90000)
        state = await asyncio.to_thread(read_snapshot_scoped, self.case,
                                        self.spec, self.page_id, self.manager)
        image = await self.page.screenshot(type="png", full_page=False,
                                           animations="disabled",
                                           mask=[self.page.locator(".admin-user")])
        return {"snapshot": state,
                "native_save_observed": True,
                "gui_reload_frame_sha256": digest(image)}


__all__ = ["DedicatedMagentoTrainRuntime", "DedicatedCloneManager",
           "CommandJournal", "DedicatedLaneError", "Pair", "pair",
           "read_snapshot_scoped", "NETWORK", "PAIRS"]
