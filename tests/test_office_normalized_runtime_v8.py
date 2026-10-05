import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from tools import office_web_normalized_runtime_v8 as adapter
from tests import test_office_owned_folder_runtime_v2 as fixture


class NormalizedBaselineTests(unittest.TestCase):
    def test_freeze_precedes_actor_and_uses_owned_copy(self):
        setup = fixture.RuntimeTests(methodName='test_double_saved_readback_and_fresh_reset')
        setup.setUp()
        try:
            calls = []
            def bind(baseline, receipt):
                calls.append('freeze')
                self.assertEqual(baseline.parent, setup.root / 'attempt')
                self.assertEqual(baseline.read_bytes(), b'neutral source')
                record = json.loads(receipt.read_bytes())
                self.assertEqual(record['native_before_sha256'], fixture.rt.sha(b'neutral source'))
            setup.package.bind_native_baseline = bind
            previous = setup.host.actor_open
            def actor_open(*args, **kwargs):
                calls.append('actor')
                self.assertEqual(calls, ['freeze', 'actor'])
                return previous(*args, **kwargs)
            setup.host.actor_open = actor_open
            runtime = adapter.Runtime(setup.host, binding_path=setup.bp,
                permit_path=setup.pp, artifact_root=setup.root/'attempt', mode='offline_fixture')
            with runtime.open(setup.package, attempt_id='normalized-fixture'):
                setup.host.saved = True
            self.assertEqual(calls, ['freeze', 'actor'])
            self.assertEqual(setup.host.items, [])
            self.assertFalse(runtime.account_lease.path.exists())
        finally:
            setup.tearDown()

    def test_baseline_binding_is_one_use_and_hash_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); root.chmod(0o700)
            baseline, receipt = root/'baseline.pptx', root/'native-before.private.json'
            fixture.put(baseline, b'neutral source')
            fixture.put(receipt, fixture.rt.canonical({
                'task_id': 'fixture', 'package_sha256': 'a'*64,
                'native_before_sha256': fixture.rt.sha(b'neutral source'),
                'item_identity_sha256': 'b'*64}))
            package = object.__new__(adapter.Package)
            package.actor = SimpleNamespace(cell_id='powerpoint-web', task_id='fixture')
            package.binding_sha256 = 'a'*64
            package.task = {'fixture': True}
            package.revalidate = lambda: None
            package.neutral = lambda _: {'equivalent': True}
            with patch.object(adapter.ppt, 'freeze', return_value={'fixture': 'oracle'}) as freeze:
                package.bind_native_baseline(baseline, receipt)
                self.assertEqual(freeze.call_count, 1)
                with self.assertRaises(ValueError): package.bind_native_baseline(baseline, receipt)
            baseline.write_bytes(b'tampered source')
            with self.assertRaises(ValueError): package.strict_score(baseline)

    def test_scoring_before_baseline_freeze_rejects_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, candidate = root/'source.pptx', root/'candidate.pptx'
            package = object.__new__(adapter.Package)
            package.actor = SimpleNamespace(cell_id='powerpoint-web')
            package.paths = {'baseline': source}
            package.revalidate = lambda: None
            with self.assertRaises(ValueError): package.strict_score(candidate)


if __name__ == '__main__': unittest.main()
