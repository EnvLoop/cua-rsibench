"""Fake Docker/process proofs for the disjoint Magento training clone lane."""

from __future__ import annotations

import asyncio
import copy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from magento_catalog_factory import seed, verify
from tests.test_magento_catalog_saved_state import CASE, baseline
from tools import magento_dedicated_train_lane_v066 as lane


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


class FakeDocker:
    def __init__(self):
        self.network_id = "a" * 64
        self.network = False
        self.containers = {}
        self.commands = []
        self.fail_stop_app = False
        self.stop_app_calls = 0
        self.documents = {str(index): {"sku": f"SKU-{index:03d}"}
                          for index in range(1, 182)}
        self.source_sha = verify.canonical_sha(self.documents)

    def _result(self, value="", *, code=0, error=""):
        return SimpleNamespace(returncode=code, stdout=value, stderr=error)

    def __call__(self, args, *, input_text, timeout):
        assert args[:3] == ["docker", "--context", lane.CONTEXT]
        command = args[3:]
        self.commands.append(tuple(command))
        head = command[0]
        if head == "image":
            return self._result(json.dumps([
                {"Id": seed.IMAGE}, {"Id": verify.NATIVE_SEARCH_IMAGE}]))
        if head == "network":
            kind = command[1]
            if kind == "inspect":
                if not self.network:
                    return self._result(code=1,
                        error="Error: network not found")
                members = {row["Id"]: {"Name": name} for name, row in
                           self.containers.items()}
                return self._result(json.dumps([{
                    "Id": self.network_id, "Name": lane.NETWORK,
                    "Driver": "bridge", "Containers": members}]))
            if kind == "create":
                assert not self.network
                self.network = True
                return self._result(self.network_id + "\n")
            if kind == "rm":
                assert not self.containers
                self.network = False
                return self._result(lane.NETWORK + "\n")
        if head == "inspect":
            record = self.containers.get(command[1])
            return (self._result(json.dumps([record])) if record is not None
                    else self._result(code=1,
                                     error="Error: No such object"))
        if head == "run":
            name = command[command.index("--name") + 1]
            is_search = "search" in name
            image = verify.NATIVE_SEARCH_IMAGE if is_search else seed.IMAGE
            record = {"Id": digest(name.encode()), "Name": "/" + name,
                      "Image": image, "Mounts": [],
                      "State": {"Running": True},
                      "NetworkSettings": {
                          "Networks": {lane.NETWORK: {}},
                          "Ports": ({"80/tcp": [{"HostIp": "127.0.0.1",
                                       "HostPort": command[
                                           command.index("-p") + 1]
                                           .split(":")[1]}],
                                     "8877/tcp": [{"HostIp": "127.0.0.1",
                                       "HostPort": [item for item in command
                                           if item.endswith(":8877")][0]
                                           .split(":")[1]}]}
                                    if not is_search else {})}}
            self.containers[name] = record
            return self._result(record["Id"] + "\n")
        if head == "stop":
            if command[1] == lane.PAIRS[0][0]:
                self.stop_app_calls += 1
                if self.fail_stop_app:
                    raise subprocess.TimeoutExpired(args, timeout)
            self.containers[command[1]]["State"]["Running"] = False
            return self._result(command[1] + "\n")
        if head == "rm":
            del self.containers[command[1]]
            return self._result(command[1] + "\n")
        if head == "exec":
            offset = 2 if command[1] == "-i" else 1
            program = command[offset + 1:]
            if program[:2] == ["supervisorctl", "status"]:
                return self._result("cron STOPPED\n")
            if program[:2] == ["supervisorctl", "stop"]:
                return self._result("elasticsearch: stopped\n")
            if program[:2] == ["cat", "/etc/supervisor.d/cron.ini"]:
                return self._result("autostart=false\n")
            if program and program[0] == "curl":
                url = program[-1]
                if url.endswith("/_cluster/health"):
                    return self._result(json.dumps({
                        "status": "yellow", "number_of_nodes": 1,
                        "timed_out": False}))
                if url.endswith("/admin"):
                    return self._result("302")
                if "_search?size=1000" in url:
                    rows = [{"_id": key, "_source": value} for key, value
                            in self.documents.items()]
                    return self._result(json.dumps({"hits": {
                        "total": {"value": 181}, "hits": rows}}))
            if program[:2] == ["php", "-r"]:
                if input_text is not None:
                    assert "START TRANSACTION READ ONLY" in program[2]
                    return self._result(json.dumps(baseline()["database"]))
                return self._result(json.dumps({
                    "price_rows": 8156,
                    "price_key_sets_equal": True,
                    "price_changed_rows": 0}))
            return self._result("completed\n")
        raise AssertionError("Unexpected fake Docker command: " + repr(command))


class DedicatedLaneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="magento-lane-fake-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)
        self.process = FakeDocker()
        self.journal = lane.CommandJournal(self.root, runner=self.process)
        self.manager = lane.DedicatedCloneManager(
            self.journal,
            seeder=lambda case, app, http, control: {
                "task_id": case["task_id"], "page_id": 8,
                "package_sha256": case["package_sha256"],
                "status": "trusted_fixture_seeded_not_gui_admitted"})
        self.ports = patch.object(self.manager, "_ports_free")
        self.ports.start()
        self.addCleanup(self.ports.stop)

    def test_disjoint_names_ports_and_cron_before_supervisor(self):
        for spec in (lane.pair(0), lane.pair(1)):
            self.assertNotEqual(spec.app, lane.evaluator.APP)
            self.assertNotEqual(spec.search, lane.evaluator.SEARCH)
            self.assertTrue(seed.CONTAINER_NAME.fullmatch(spec.app))
            self.assertFalse({spec.http_port, spec.control_port} &
                             {7794, 7795})
        first = self.manager.prepare(lane.pair(0),
                                     source_search_sha256=self.process.source_sha)
        self.assertTrue(first["cron_autostart_disabled_before_supervisor"])
        app_run = next(command for command in self.process.commands
                       if command[:1] == ("run",) and
                       lane.pair(0).app in command)
        script = app_run[-1]
        self.assertLess(script.index("autostart=false"),
                        script.index("exec /custom-entrypoint.sh"))
        self.assertEqual(first["search_document_count"], 181)
        self.assertEqual(first["loopback_ports"], [7820, 7821])

    def test_scoped_read_only_sql_and_fresh_pair_reset(self):
        first = self.manager.prepare(lane.pair(0),
                                     source_search_sha256=self.process.source_sha)
        self.manager.seed_case(lane.pair(0), CASE)
        before = lane.read_snapshot_scoped(CASE, lane.pair(0), 8,
                                           self.manager)
        verify.check_baseline(CASE, before)
        runtime = lane.DedicatedMagentoTrainRuntime(
            {"source_search_sha256": self.process.source_sha},
            self.root / "synthetic-lane.private.json",
            runner=self.process, seeder=self.manager.seeder)
        # The real reset method drives the fake process manager. No Docker.
        proof = asyncio.run(runtime._prove_fresh_reset(
            self.manager, CASE, self.process.source_sha, first, before))
        self.assertTrue(proof["fresh_clone_reset_passed"])
        self.assertTrue(proof["different_app_container_ids"])
        self.assertTrue(proof["different_search_container_ids"])
        self.assertEqual(proof["restored_snapshot"], before)
        self.assertEqual(self.process.containers, {})
        self.assertFalse(self.process.network)
        db_reads = [command for command in self.process.commands
                    if command[:1] == ("exec",) and
                    "START TRANSACTION READ ONLY" in repr(command)]
        self.assertGreaterEqual(len(db_reads), 2)

    def test_cleanup_timeout_is_terminal_and_not_replayed(self):
        self.manager.prepare(lane.pair(0),
                             source_search_sha256=self.process.source_sha)
        self.process.fail_stop_app = True
        with self.assertRaisesRegex(lane.DedicatedLaneError,
                                    "uncertain_no_replay"):
            self.manager.cleanup(lane.pair(0))
        self.assertEqual(self.process.stop_app_calls, 1)
        with self.assertRaises(lane.DedicatedLaneError):
            self.manager.cleanup(lane.pair(0))
        self.assertEqual(self.process.stop_app_calls, 1)
        with self.assertRaisesRegex(lane.DedicatedLaneError,
                                    "attempt_already_exists"):
            lane.CommandJournal(self.root, runner=self.process)
        events = [json.loads(line) for line in
                  self.journal.path.read_bytes().splitlines()]
        self.assertTrue(any(row.get("event") == "uncertain" and
                            row.get("label") == "p0_app_stop"
                            for row in events))

    def test_changed_container_identity_blocks_cleanup_before_stop(self):
        self.manager.prepare(lane.pair(0),
                             source_search_sha256=self.process.source_sha)
        self.process.containers[lane.pair(0).app]["Id"] = "b" * 64
        with self.assertRaisesRegex(lane.DedicatedLaneError,
                                    "cleanup_identity_changed"):
            self.manager.cleanup(lane.pair(0))
        self.assertEqual(self.process.stop_app_calls, 0)
        self.assertTrue(self.process.network)

    def test_unexpected_exited_app_blocks_cleanup_without_replay(self):
        self.manager.prepare(lane.pair(0),
                             source_search_sha256=self.process.source_sha)
        self.process.containers[lane.pair(0).app]["State"]["Running"] = False
        with self.assertRaisesRegex(lane.DedicatedLaneError,
                                    "cleanup_identity_changed"):
            self.manager.cleanup(lane.pair(0))
        self.assertEqual(self.process.stop_app_calls, 0)

    def test_preexisting_network_refuses_before_container_create(self):
        self.process.network = True
        with self.assertRaisesRegex(lane.DedicatedLaneError,
                                    "dedicated_network_already_exists"):
            self.manager.prepare(lane.pair(0),
                                 source_search_sha256=self.process.source_sha)
        self.assertFalse(any(command[:1] == ("run",)
                             for command in self.process.commands))

    def test_existing_evaluator_container_prevents_any_train_mutation(self):
        self.process.containers[lane.evaluator.APP] = {
            "Id": "e" * 64, "Name": "/" + lane.evaluator.APP,
            "Image": seed.IMAGE, "Mounts": [],
            "State": {"Running": True},
            "NetworkSettings": {"Networks": {}, "Ports": {}},
        }
        with self.assertRaisesRegex(lane.DedicatedLaneError,
                                    "evaluator_container_overlap"):
            self.manager.prepare(lane.pair(0),
                                 source_search_sha256=self.process.source_sha)
        self.assertFalse(any(command[:1] == ("run",)
                             for command in self.process.commands))
        self.assertFalse(self.process.network)

    def test_failed_process_keeps_private_diagnostic_without_retry(self):
        self.journal.runner = lambda *_args, **_kwargs: SimpleNamespace(
            returncode=1, stdout="", stderr="synthetic process failure")
        with self.assertRaisesRegex(lane.DedicatedLaneError,
                                    "docker_step_failed_no_replay"):
            self.journal.run("failed_probe", ("version",),
                             mutating=False, timeout=5)
        diagnostic = (self.root / "process-diagnostics" /
                      "failed_probe.stderr.private.bin")
        self.assertEqual(diagnostic.read_bytes(),
                         b"synthetic process failure")
        self.assertEqual(diagnostic.stat().st_mode & 0o077, 0)
        with self.assertRaisesRegex(lane.DedicatedLaneError,
                                    "duplicate_or_unbounded"):
            self.journal.run("failed_probe", ("version",),
                             mutating=False, timeout=5)

    def test_actor_exception_still_runs_fresh_pair_reset_with_fake_playwright(self):
        credentials = self.root / "actor.private.json"
        credentials.write_text(json.dumps({"username": "synthetic",
                                           "password": "synthetic"}))
        credentials.chmod(0o600)
        configuration = {
            "source_search_sha256": self.process.source_sha,
            "actor_credentials_ref": {
                "path": str(credentials),
                "sha256": digest(credentials.read_bytes())},
        }

        class Control:
            async def fill(self, _value): return None
            async def click(self): return None
            async def wait_for(self, **_kwargs): return None

        class Page:
            async def goto(self, *_args, **_kwargs): return None
            def get_by_label(self, *_args, **_kwargs): return Control()
            def get_by_role(self, *_args, **_kwargs): return Control()
            def locator(self, _selector): return Control()

        class Context:
            async def route(self, *_args): return None
            async def new_page(self): return Page()
            async def close(self): return None

        class Browser:
            async def new_context(self, **_kwargs): return Context()
            async def close(self): return None

        class Playwright:
            def __init__(self):
                self.chromium = SimpleNamespace(
                    launch=self._launch)
            async def _launch(self, **_kwargs): return Browser()
            async def __aenter__(self): return self
            async def __aexit__(self, *_args): return False

        async def quote(_page, case, _out):
            return {"quote_visible_in_native_cms": True,
                    "quote_body_sha256": case["quote_page_body_sha256"]}

        runtime = lane.DedicatedMagentoTrainRuntime(
            configuration, self.root / "synthetic-lane.private.json",
            runner=self.process, seeder=self.manager.seeder,
            lock_path=self.root / "exclusive.lock")
        observed = []

        async def exercise():
            try:
                async with runtime.open_case(CASE, self.root) as session:
                    observed.append(session)
                    raise RuntimeError("synthetic actor interruption")
            except RuntimeError as exc:
                self.assertEqual(str(exc),
                                 "synthetic actor interruption")

        with patch("playwright.async_api.async_playwright",
                   return_value=Playwright()), \
             patch.object(lane.original_gui, "read_quote_in_gui",
                          side_effect=quote), \
             patch.object(lane, "read_snapshot_scoped",
                          return_value=baseline()):
            asyncio.run(exercise())
        self.assertEqual(len(observed), 1)
        self.assertTrue(observed[0].reset_proof[
            "fresh_clone_reset_passed"])
        self.assertTrue(observed[0].reset_proof[
            "both_pairs_removed"])
        self.assertEqual(self.process.containers, {})
        self.assertFalse(self.process.network)


if __name__ == "__main__":
    unittest.main()
