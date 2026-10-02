"""Offline all-app ownership and isolated probe resource-bound checks."""
import hashlib
import json
from pathlib import Path
import shlex
import tempfile
import time
from types import SimpleNamespace
import unittest

from native_desktop_factory import business_native_runtime as business
from native_desktop_factory import native_business_reader as reader
from native_desktop_factory import current_inventory_runtime as previous
from native_desktop_factory import native_current_inventory as inventory
from native_desktop_factory import native_accessibility_probe_v24 as owner
from native_desktop_factory import native_terminal_hit_diagnostic_v38 as frozen
from native_desktop_factory import terminal_owned_runtime as terminal
from native_desktop_factory import common_native_guest_v31 as common


CLASSES = {
    "fixture.xlsx": "libreoffice-calc",
    "fixture.docx": "libreoffice-writer",
    "fixture.pptx": "libreoffice-impress",
}


def principal(typed_class="libreoffice-calc"):
    return {
        "pid": 123, "uid": 1000, "probe_uid": 1000,
        "wm_class": f'WM_CLASS(STRING) = "libreoffice", "{typed_class}"',
    }


class BusinessRuntimeTests(unittest.TestCase):
    def test_all_three_exact_typed_classes_require_same_principal_and_attested_exe(self):
        self.assertEqual(reader.EXE_SHA, owner.ATTESTED_EXE_SHA)
        for filename, typed_class in CLASSES.items():
            with self.subTest(filename=filename):
                calls = []

                def executable(pid):
                    calls.append(pid)
                    return reader.EXE_PATH, reader.EXE_SHA

                self.assertTrue(reader.ownership(principal(typed_class), filename, executable_reader=executable))
                self.assertEqual(calls, [123])

    def test_wrong_uid_pid_instance_extension_and_typed_class_reject_before_exe_read(self):
        cases = [
            (principal() | {"uid": 2000}, "fixture.xlsx"),
            (principal() | {"uid": "1000"}, "fixture.xlsx"),
            (principal() | {"pid": "123"}, "fixture.xlsx"),
            (principal() | {"pid": True}, "fixture.xlsx"),
            (principal() | {"pid": 0}, "fixture.xlsx"),
            (principal() | {"pid": -1}, "fixture.xlsx"),
            (principal() | {"wm_class": 'WM_CLASS(STRING) = "foreign", "libreoffice-calc"'}, "fixture.xlsx"),
            (principal("libreoffice-writer"), "fixture.xlsx"),
            (principal("libreoffice-calc"), "fixture.docx"),
            (principal("libreoffice-writer"), "fixture.pptx"),
            (principal() | {"wm_class": "libreoffice-calc"}, "fixture.xlsx"),
            (principal() | {"wm_class": 'WM_CLASS(STRING) = "libreoffice", "libreoffice-calc" extra'}, "fixture.xlsx"),
            (principal(), "fixture.txt"),
        ]
        for first, filename in cases:
            with self.subTest(first=first, filename=filename):
                calls = []
                self.assertFalse(reader.ownership(first, filename, executable_reader=lambda pid: calls.append(pid)))
                self.assertEqual(calls, [])

    def test_unattested_executable_path_hash_and_unavailable_proc_are_rejected(self):
        for executable in [
            ("/tmp/soffice.bin", reader.EXE_SHA),
            ("/usr/bin/libreoffice", reader.EXE_SHA),
            (reader.EXE_PATH, "0" * 64),
        ]:
            with self.subTest(executable=executable):
                self.assertFalse(reader.ownership(principal(), "fixture.xlsx", executable_reader=lambda pid, result=executable: result))

        def unavailable(pid):
            raise OSError("Synthetic process exited")

        self.assertFalse(reader.ownership(principal(), "fixture.xlsx", executable_reader=unavailable))

    def test_new_manifest_keeps_prior_sources_and_requires_fresh_formal_qualification(self):
        old = previous.source_manifest()
        manifest = business.source_manifest()
        self.assertEqual(manifest["native_reader_schema"], reader.SCHEMA)
        self.assertEqual(manifest["maximum_typed_probe_bytes"], 524288)
        self.assertTrue(manifest["typed_all_app_principal_checked_each_probe"])
        self.assertIs(manifest["old_results_reclassified"], False)
        self.assertIs(manifest["native_qualification_passed"], False)
        self.assertEqual(manifest["actor_paths"], list(common.ACTOR_PATHS))
        for name, source_hash in old["source_sha256s"].items():
            self.assertEqual(manifest["source_sha256s"][name], source_hash)
        self.assertEqual(set(manifest["source_sha256s"]) - set(old["source_sha256s"]), set(business.EXTRA))
        factory = business.factory(manifest=manifest)
        with self.assertRaisesRegex(ValueError, "Fresh common native qualification"):
            factory.require_activation()

    def test_only_fresh_generated_probe_constant_changes_existing_classes_and_globals_stay_identical(self):
        modules = (owner, frozen, terminal, previous, inventory, common)
        globals_before = {module: dict(vars(module)) for module in modules}
        sources_before = {module: Path(module.__file__).read_bytes() for module in modules}
        class_before = dict(vars(common.CommonNativeModelGuest))
        factory_before = dict(vars(common.CommonGuestFactory))
        old_factory = previous.factory(manifest=previous.source_manifest())
        old_function = old_factory.actor_class.native_probe
        new_factory = business.factory(manifest=business.source_manifest())
        new_function = new_factory.actor_class.native_probe
        self.assertIsNot(old_factory.actor_class, new_factory.actor_class)
        self.assertEqual(old_function.__code__.co_consts.count(262144), 1)
        self.assertNotIn(524288, old_function.__code__.co_consts)
        self.assertEqual(new_function.__code__.co_consts, tuple(
            524288 if value == 262144 else value for value in old_function.__code__.co_consts
        ))
        self.assertEqual(new_function.__code__.co_code, old_function.__code__.co_code)
        self.assertEqual(new_function.__code__.co_names, old_function.__code__.co_names)
        self.assertEqual(new_function.__code__.co_varnames, old_function.__code__.co_varnames)
        self.assertIs(old_factory.actor_class.native_probe, old_function)
        self.assertIn("native_business_reader.py", new_factory.actor_class._bootstrap.__globals__["PEERS"])
        run, main = reader.scoped_reader()
        self.assertTrue(callable(run))
        self.assertTrue(callable(main))
        for module in modules:
            self.assertEqual(dict(vars(module)), globals_before[module])
            self.assertEqual(Path(module.__file__).read_bytes(), sources_before[module])
        self.assertEqual(dict(vars(common.CommonNativeModelGuest)), class_before)
        self.assertEqual(dict(vars(common.CommonGuestFactory)), factory_before)
        self.assertEqual(hashlib.sha256(Path(frozen.__file__).read_bytes()).hexdigest(), inventory.V38_SHA)
        self.assertEqual(hashlib.sha256(Path(inventory.__file__).read_bytes()).hexdigest(), reader.V39_SHA)

    def probe_fixture(self, runtime, *, padding, invalid=None):
        manifest = runtime.source_manifest()
        factory = runtime.factory(manifest=manifest)
        source = factory.actor_class.native_probe.__globals__["PROBE_SOURCE"]
        schema = factory.actor_class.native_probe.__globals__["PROBE_SCHEMA"]
        facts = b'{"kind":"bounded_runtime_diagnostic_summary","native_predicates_skipped":0}\n'
        value = {
            "schema": schema, "status": "observed",
            "probe_source_sha256": common.digest(source.read_bytes()),
            "native_mutations": 0, "raster_equality_used": False,
            "recursive_collection_query_called": False, "focus_from_selection": False,
            "private_native_facts_file": {
                "path": "/tmp/envloop-native-terminal-v38-facts-000000.private.jsonl",
                "sha256": common.digest(facts), "bytes": len(facts),
                "mode": 0o600, "actor_access_authorized": False,
            },
            "offline_padding": "x" * padding,
        }
        if invalid == "schema":
            value["schema"] = "synthetic-unbound-schema"
        elif invalid == "source":
            value["probe_source_sha256"] = "0" * 64
        stdout = json.dumps(value, separators=(",", ":"))
        commands, reads = [], []

        def command(command, **bounds):
            commands.append((command, bounds))
            return SimpleNamespace(exit_code=0, stdout=stdout, stderr="")

        def read(path, **kwargs):
            reads.append((path, kwargs))
            self.assertEqual(path, value["private_native_facts_file"]["path"])
            return facts

        return factory, value, stdout, facts, commands, reads, SimpleNamespace(
            sandbox_id="offline-business", commands=SimpleNamespace(run=command), files=SimpleNamespace(read=read),
        )

    def test_source_bound_300k_probe_passes_new_bound_while_old_runtime_still_refuses(self):
        for runtime, accepted in ((previous, False), (business, True)):
            with self.subTest(runtime=runtime.__name__), tempfile.TemporaryDirectory() as temporary:
                factory, value, stdout, facts, commands, reads, sandbox = self.probe_fixture(runtime, padding=300000)
                self.assertGreater(len(stdout.encode()), 262144)
                self.assertLess(len(stdout.encode()), 524288)
                root = Path(temporary)
                out = root / "fixture" / "actor"
                out.mkdir(parents=True)
                actor = factory.wrap_owned_guest(sandbox, root=root, out=out, filename="fixture.xlsx", lease_started_monotonic=time.monotonic())
                actor.bootstrap_completed = True
                if accepted:
                    self.assertEqual(actor.native_probe("offline-resource-bound"), value)
                    self.assertEqual((out / "native-facts-000.private.jsonl").read_bytes(), facts)
                    self.assertEqual(len(reads), 1)
                    tokens = shlex.split(commands[0][0])
                    self.assertEqual(tokens[2], common.REMOTE + "/native_business_reader.py")
                    self.assertIn("--guarded", tokens)
                else:
                    with self.assertRaisesRegex(ValueError, "failed or exceeded bound"):
                        actor.native_probe("offline-resource-bound")
                    self.assertEqual(reads, [])
                receipt = json.loads((out / "native-probe-000.private.json").read_bytes())
                self.assertEqual(receipt["stdout"], stdout)
                self.assertEqual(commands[0][1], {"timeout": 45, "request_timeout": 55})

    def test_larger_bound_keeps_oversize_schema_and_source_hash_refusals(self):
        for invalid, padding, message in (
            (None, 525000, "failed or exceeded bound"),
            ("schema", 300000, "metadata unavailable"),
            ("source", 300000, "metadata unavailable"),
        ):
            with self.subTest(invalid=invalid, padding=padding), tempfile.TemporaryDirectory() as temporary:
                factory, value, stdout, facts, commands, reads, sandbox = self.probe_fixture(business, padding=padding, invalid=invalid)
                root = Path(temporary)
                out = root / "fixture" / "actor"
                out.mkdir(parents=True)
                actor = factory.wrap_owned_guest(sandbox, root=root, out=out, filename="fixture.xlsx", lease_started_monotonic=time.monotonic())
                actor.bootstrap_completed = True
                with self.assertRaisesRegex(ValueError, message):
                    actor.native_probe("offline-refusal")
                self.assertEqual(len(commands), 1)
                if padding > 524288:
                    self.assertEqual(reads, [])


if __name__ == "__main__":
    unittest.main()
