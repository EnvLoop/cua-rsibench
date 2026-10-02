"""Offline boundaries for the shared guarded Desktop guest factory.

Synthetic raw guests exercise the real constructor and common runtime context;
no provider, native desktop, or model invocation is performed by these tests.
"""
import copy
import json
from pathlib import Path
import shlex
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from native_desktop_factory import common_native_guest_v31 as common
from native_desktop_factory import terminal_owned_runtime as terminal


ACTORS = ("teacher", "control", "shared-base", "astra", "sol56", "sol6", "luna6")
APP_FILES = ("fixture.xlsx", "fixture.docx", "fixture.pptx")


def qualification(manifest):
    return {
        "schema": "cua-native-common-guest-qualification-v31",
        "source_manifest_sha256": common.digest(common.canonical(manifest)),
        "actor_paths": list(ACTORS),
        "native_policy_sha256": common.POLICY_SHA,
        "old_results_reclassified": False,
    }


def independent_proof():
    return {
        "raw_native_evidence_reopened": True,
        "completed_current_control_trios": 120,
        "all_seven_actor_paths_verified": True,
        "app_kinds": ["calc", "impress", "writer"],
        "base_and_supplemental_content_reopened": True,
        "actor_clock_and_distinct_reset_verified": True,
    }


class TerminalOwnedRuntimeTests(unittest.TestCase):
    def test_manifest_is_additive_without_historical_qualification_credit(self):
        parent_manifest = common.source_manifest()
        manifest = terminal.source_manifest()
        self.assertEqual(manifest["schema"], "cua-native-terminal-owned-runtime-source-v38")
        self.assertEqual(manifest["actor_paths"], list(ACTORS))
        self.assertEqual(manifest["native_reader_schema"], terminal.SCHEMA)
        self.assertFalse(manifest["structural_containers_actionable"])
        self.assertIs(manifest["old_results_reclassified"], False)
        self.assertIs(manifest["native_qualification_passed"], False)
        self.assertEqual(manifest["task_policy"], parent_manifest["task_policy"])
        self.assertTrue(manifest["base_and_supplemental_content_attestation_required"])
        self.assertTrue(manifest["offline_bootstrap_before_prepare"])
        for name, source_hash in parent_manifest["source_sha256s"].items():
            with self.subTest(parent_source=name):
                self.assertEqual(manifest["source_sha256s"][name], source_hash)
        for name in terminal.EXTRA:
            with self.subTest(extra_source=name):
                self.assertEqual(
                    manifest["source_sha256s"][name],
                    common.digest((Path(terminal.__file__).resolve().parents[1] / name).read_bytes()),
                )
        self.assertEqual(common.source_manifest(), parent_manifest)

    def test_all_seven_actors_and_three_apps_create_the_same_guarded_class(self):
        manifest = terminal.source_manifest()
        audited = []
        calls = []

        def audit(row):
            audited.append(row)
            return independent_proof()

        def create(**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                sandbox_id=f"offline-owned-{len(calls)}",
                files=SimpleNamespace(),
                commands=SimpleNamespace(),
            )

        factory = terminal.factory(
            manifest=manifest, qualification=qualification(manifest), independent_raw_auditor=audit,
        )
        self.assertIsInstance(factory, common.CommonGuestFactory)
        actors = []
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.dict(sys.modules, {"e2b_desktop": SimpleNamespace(Sandbox=SimpleNamespace(create=create))}), \
                    patch("native_desktop_factory.reconcile_interrupted_sweep.active_hashes", return_value=([], 0)), \
                    common.runtime_context(factory):
                for role in ACTORS:
                    for filename in APP_FILES:
                        with self.subTest(role=role, filename=filename):
                            out = root / role / Path(filename).suffix[1:]
                            out.mkdir(parents=True)
                            actor = common.create_guest(root=root, out=out, filename=filename)
                            actors.append(actor)
                            self.assertEqual(actor.native_manifest, manifest)
                            self.assertFalse(actor.bootstrap_completed)
                            self.assertEqual(actor.filename, filename)
                            self.assertIs(actor.__class__, actors[0].__class__)
                            self.assertIsNot(actor.__class__, common.CommonNativeModelGuest)
                            self.assertEqual(actor.native_probe.__globals__["PROBE_SOURCE"], terminal.SOURCE)
                            self.assertEqual(actor.native_probe.__globals__["PROBE_SCHEMA"], terminal.SCHEMA)
                            self.assertIn("native_terminal_hit_diagnostic_v38.py", actor._bootstrap.__globals__["PEERS"])
                            intent = json.loads((out / "native-create-intent-v31.private.json").read_bytes())
                            self.assertEqual(intent["source_manifest_sha256"], common.digest(common.canonical(manifest)))
                            self.assertEqual(intent["automatic_restarts"], 0)
                            journal = json.loads((out / "native-raw-created-v31.private.json").read_bytes())
                            self.assertEqual(journal["sandbox_id"], actor.sandbox.sandbox_id)
        self.assertEqual(len(actors), 21)
        self.assertEqual(len(calls), 21)
        self.assertEqual(len(audited), 22)  # Context activation plus every create.
        self.assertTrue(all(call == {
            "template": "desktop", "resolution": (1280, 800), "timeout": 1200,
            "allow_internet_access": False, "metadata": {"envloop_purpose": "uniform-native-common-v31"},
        } for call in calls))

    def test_guarded_probe_uses_owned_points_and_keeps_v31_runtime_untouched(self):
        parent_manifest = common.source_manifest()
        originals = {
            name: getattr(common, name)
            for name in ("PROBE_SOURCE", "PROBE_SCHEMA", "PROBE_PATH", "PEERS", "source_manifest", "checked_runtime_manifest")
        }
        original_guest_methods = dict(vars(common.CommonNativeModelGuest))
        original_factory_methods = dict(vars(common.CommonGuestFactory))
        manifest = terminal.source_manifest()
        value = {
            "schema": terminal.SCHEMA, "status": "observed",
            "probe_source_sha256": common.digest(terminal.SOURCE.read_bytes()),
            "native_mutations": 0, "raster_equality_used": False,
            "recursive_collection_query_called": False, "focus_from_selection": False,
        }
        facts = b'{"kind":"bounded_runtime_diagnostic_summary","native_predicates_skipped":0}\n'
        value["private_native_facts_file"] = {
            "path": "/tmp/envloop-native-terminal-v38-facts-000000.private.jsonl",
            "sha256": common.digest(facts), "bytes": len(facts), "mode": 0o600,
            "actor_access_authorized": False,
        }
        calls = []

        def run(command, **bounds):
            calls.append((command, bounds))
            return SimpleNamespace(exit_code=0, stdout=json.dumps(value), stderr="")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "fixture" / "actor"
            out.mkdir(parents=True)
            sandbox = SimpleNamespace(sandbox_id="offline-probe", files=SimpleNamespace(read=lambda path, **kwargs: facts), commands=SimpleNamespace(run=run))
            factory = terminal.factory(manifest=manifest)
            actor = factory.wrap_owned_guest(sandbox, root=root, out=out, filename="fixture.xlsx", lease_started_monotonic=time.monotonic())
            self.assertEqual(calls, [])
            with self.assertRaisesRegex(ValueError, "bootstrap before original prepare"):
                actor.native_probe("before-bootstrap")
            self.assertEqual(calls, [])
            actor.bootstrap_completed = True
            actor.requested_points = [[40, 50], [60, 70]]
            self.assertEqual(actor.native_probe("predispatch-before"), value)
            tokens = shlex.split(calls[0][0])
            self.assertEqual(tokens[:3], [f"GI_TYPELIB_PATH={common.bootstrap.PREFIX}", "python3", common.REMOTE + "/native_terminal_hit_diagnostic_v38.py"])
            self.assertEqual(tokens.count("--guarded"), 1)
            self.assertEqual(tokens[tokens.index("--facts-path") + 1], "/tmp/envloop-native-terminal-v38-facts-000000.private.jsonl")
            self.assertEqual(tokens[tokens.index("--filename") + 1], "fixture.xlsx")
            self.assertEqual(json.loads(tokens[tokens.index("--points-json") + 1]), [[40, 50], [60, 70]])
            self.assertEqual(calls[0][1], {"timeout": 45, "request_timeout": 55})
            receipt = json.loads((out / "native-probe-000.private.json").read_bytes())
            self.assertEqual(receipt["phase"], "predispatch-before")
            self.assertEqual(receipt["native_source_manifest_sha256"], actor.native_manifest_sha256)
            self.assertEqual((out / "native-facts-000.private.jsonl").read_bytes(), facts)
            value["private_native_facts_file"]["path"] = "/tmp/envloop-native-terminal-v38-facts-000001.private.jsonl"
            actor.native_probe("observation-before")
            self.assertEqual((out / "native-facts-001.private.jsonl").read_bytes(), facts)
            self.assertEqual(shlex.split(calls[1][0])[shlex.split(calls[1][0]).index("--facts-path") + 1], value["private_native_facts_file"]["path"])
            value["private_native_facts_file"]["sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "source/sequence"):
                actor.native_probe("stale-journal")
        for name, original in originals.items():
            self.assertIs(getattr(common, name), original)
        self.assertEqual(dict(vars(common.CommonNativeModelGuest)), original_guest_methods)
        self.assertEqual(dict(vars(common.CommonGuestFactory)), original_factory_methods)
        self.assertEqual(common.source_manifest(), parent_manifest)
        self.assertEqual(common.PROBE_SOURCE.name, "native_visible_surface_probe_v31.py")
        self.assertNotIn("native_desktop_factory/native_terminal_hit_diagnostic_v38.py", parent_manifest["source_sha256s"])

    def test_unqualified_and_historical_rows_fail_before_raw_guest_create(self):
        manifest = terminal.source_manifest()
        rows = (None, qualification(common.source_manifest()), qualification(manifest) | {"old_results_reclassified": True})
        creates = []
        audits = []
        for row in rows:
            with self.subTest(qualification=row), patch.dict(sys.modules, {
                "e2b_desktop": SimpleNamespace(Sandbox=SimpleNamespace(create=lambda **kwargs: creates.append(kwargs))),
            }):
                factory = terminal.factory(
                    manifest=manifest, qualification=row,
                    independent_raw_auditor=lambda value: audits.append(value) or independent_proof(),
                )
                with self.assertRaisesRegex(ValueError, "Fresh common native qualification"):
                    factory.create_guest(root=Path("/unused"), out=Path("/unused"), filename="fixture.xlsx")
                with self.assertRaisesRegex(ValueError, "Fresh common native qualification"):
                    with common.runtime_context(factory):
                        self.fail("Unqualified runtime must not enter")
        self.assertEqual(creates, [])
        self.assertEqual(audits, [])

    def test_control_driver_accepts_only_this_factory_exact_owned_class(self):
        factory = terminal.factory(manifest=terminal.source_manifest())
        other_factory = terminal.factory(manifest=terminal.source_manifest())
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary);out=root / 'fixture' / 'actor';out.mkdir(parents=True)
            sandbox = SimpleNamespace(sandbox_id='offline-control')
            actor = factory.wrap_owned_guest(sandbox, root=root, out=out, filename='fixture.xlsx', lease_started_monotonic=time.monotonic())
            driver = terminal.control_driver(factory, actor=actor, identity={'task_id':'fixture'}, instruction='Public synthetic control.', actor_deadline=time.monotonic()+60)
            self.assertIs(driver.actor, actor)
            with self.assertRaisesRegex(ValueError, 'Exact scoped'):
                terminal.control_driver(other_factory, actor=actor, identity={}, instruction='', actor_deadline=0)
            with self.assertRaisesRegex(ValueError, 'Actual common native control actor'):
                from native_desktop_factory.common_native_episode_v31 import CommonNativeControlDriver
                CommonNativeControlDriver(actor=actor, identity={}, instruction='', actor_deadline=0)

    def test_fresh_manifest_still_requires_full_independent_formal_qualification(self):
        manifest = terminal.source_manifest()
        row = qualification(manifest)
        factory = terminal.factory(manifest=manifest, qualification=row)
        with self.assertRaisesRegex(ValueError, "Independent common native raw reopening"):
            factory.require_activation()
        incomplete = {
            "raw_native_evidence_reopened": False,
            "completed_current_control_trios": 119,
            "all_seven_actor_paths_verified": False,
            "app_kinds": ["calc", "writer"],
            "base_and_supplemental_content_reopened": False,
            "actor_clock_and_distinct_reset_verified": False,
        }
        for field, missing in incomplete.items():
            with self.subTest(missing=field):
                proof = independent_proof() | {field: missing}
                factory = terminal.factory(manifest=manifest, qualification=row, independent_raw_auditor=lambda _, proof=proof: proof)
                with self.assertRaisesRegex(ValueError, "Actual common native qualification incomplete"):
                    factory.require_activation()
        factory = terminal.factory(manifest=manifest, qualification=row, independent_raw_auditor=lambda _: independent_proof())
        self.assertIs(factory.require_activation(), row)

    def test_changed_source_manifest_is_rejected_before_guest_construction(self):
        manifest = terminal.source_manifest()
        changed = copy.deepcopy(manifest)
        changed["source_sha256s"]["native_desktop_factory/native_terminal_hit_diagnostic_v38.py"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "Terminal runtime source changed"):
            terminal.factory(manifest=changed)
        factory = terminal.factory(manifest=manifest)
        factory.manifest = changed
        with self.assertRaisesRegex(ValueError, "Terminal runtime source changed"):
            factory.require_activation()


if __name__ == "__main__":
    unittest.main()
