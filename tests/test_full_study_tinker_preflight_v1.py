"""Train-only provider preflight and checkpoint-boundary regression tests."""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from cursibench import full_study_tinker_preflight_v1 as preflight


ROOT = Path(__file__).resolve().parents[1]
MODEL = preflight.MODEL
MODEL_ROW = {'tinker_id': MODEL, 'type': 'Hybrid + Vision',
             'context': '64K', 'prefill': '$1.86',
             'cached_prefill': '$0.372', 'sample': '$5.595',
             'train': '$4.103'}


class FakeService:
    def __init__(self, *, model=MODEL, trainable=True, sampleable=True,
                 user_metadata=None):
        self.model = model
        self.trainable = trainable
        self.sampleable = sampleable
        self.metadata = user_metadata
        self.calls = []

    def get_server_capabilities(self):
        self.calls.append('get_server_capabilities')
        return SimpleNamespace(supported_models=[SimpleNamespace(
            model_name=self.model, trainable=self.trainable,
            sampleable=self.sampleable, max_context_length=65_536)])

    def close(self, status):
        self.calls.append(('close', status))
        return SimpleNamespace(result=lambda timeout: None)


class FakeSampler:
    def __init__(self, base=MODEL):
        self.base = base

    def get_base_model(self):
        return self.base


class FakeCheckpointService:
    def __init__(self, base=MODEL):
        self.base = base
        self.paths = []

    def create_sampling_client(self, *, model_path):
        self.paths.append(model_path)
        return FakeSampler(self.base)


class PreflightTests(unittest.TestCase):
    def test_exact_official_catalog_and_rate_distinctions(self):
        raw = json.dumps([MODEL_ROW]).encode()
        retained, pricing = preflight.official_catalog(lambda url: raw)
        self.assertEqual(retained, raw)
        self.assertEqual(pricing['published_models_json_sha256'],
                         preflight.sha256(raw))
        self.assertEqual(pricing['usd_per_million_tokens']['train'], '4.103')
        self.assertEqual(preflight.nominal_token_cost(
            pricing, training_tokens=1_000_000,
            prefill_tokens=1_000_000, sample_tokens=1_000_000)[
                'published_rate_nominal_usd'], '11.558')
        for corrupted in (
            [{**MODEL_ROW, 'tinker_id': MODEL + ':peft:262144'}],
            [MODEL_ROW, MODEL_ROW],
            [{**MODEL_ROW, 'type': 'Hybrid'}],
            [{**MODEL_ROW, 'train': '$NaN'}],
        ):
            with self.assertRaises(preflight.PreflightError):
                preflight.official_catalog(
                    lambda url, corrupted=corrupted: json.dumps(corrupted).encode())

    def test_authenticated_capability_is_read_only_and_closed(self):
        created = []

        def factory(**kwargs):
            created.append(FakeService(**kwargs))
            return created[-1]

        result = preflight.provider_capabilities(factory)
        self.assertTrue(result['exact_model_trainable'])
        self.assertEqual(result['training_or_sampling_provider_calls'], 0)
        self.assertEqual(created[0].calls,
                         ['get_server_capabilities', ('close', 'success')])
        self.assertEqual(created[0].metadata['split'], 'none')

        rejected = []

        def bad_factory(**kwargs):
            rejected.append(FakeService(model='different', **kwargs))
            return rejected[-1]

        with self.assertRaisesRegex(preflight.PreflightError,
                                    'exact_model_not_in_account_capabilities'):
            preflight.provider_capabilities(bad_factory)
        self.assertEqual(rejected[0].calls[-1], ('close', 'errored'))

    def test_private_preflight_retains_source_bytes_and_no_dispatch(self):
        with tempfile.TemporaryDirectory() as scratch:
            repo = Path(scratch)
            for relative in preflight.ACTION_FILES:
                target = repo / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / relative).read_bytes())
            receipts = {
                'native-wdi-guest-content-identity-2026-09-27.json': {
                    'scoped_guest_content_identity_passed': True,
                    'provider_image_digest_available': False},
                'native-wdi-profile-drift-2026-09-27.json': {
                    'canonical_profile_stable_across_two_probes': True,
                    'raw_profile_stable_across_two_probes': False,
                    'full_image_profile_freeze_gate_passed': False},
            }
            for name, data in receipts.items():
                path = repo / 'docs/evidence' / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(data))
            raw = json.dumps([MODEL_ROW]).encode()
            service = FakeService()
            out = repo / 'work' / 'preflight'
            receipt = preflight.run_read_only(
                repo, out, fetcher=lambda url: raw,
                service_factory=lambda **kwargs: service)
            self.assertEqual(receipt['provider']['training_or_sampling_provider_calls'], 0)
            self.assertFalse(receipt['six_cell_pre_campaign_plan_verified'])
            self.assertFalse(receipt['cross_cell_v065_hash_freeze_verified'])
            self.assertFalse(receipt['campaign_dispatch_authorized'])
            self.assertFalse(receipt['desktop_attestation_snapshot'][
                'full_image_profile_freeze_passed'])
            self.assertEqual((out / 'published-models.private.json').read_bytes(), raw)
            self.assertEqual(os.stat(out / 'receipt.private.json').st_mode & 0o777,
                             0o600)
            with self.assertRaises(preflight.PreflightError):
                preflight.run_read_only(
                    repo, out, fetcher=lambda url: raw,
                    service_factory=lambda **kwargs: self.fail(
                        'duplicate output must block before provider access'))

    def test_sampler_binding_requires_exact_private_path_and_base(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            work = root / 'work'
            work.mkdir()
            path = work / 'sampler.private.json'
            hashes = dict(plan_sha256='a' * 64,
                          campaign_intent_sha256='b' * 64,
                          train_data_sha256='c' * 64,
                          action_bundle_sha256='d' * 64,
                          usage_receipt_sha256='e' * 64)
            sampler_path = 'tinker://run:train:0/sampler_weights/step-0001'
            wrong_service = FakeCheckpointService('other')
            with self.assertRaisesRegex(preflight.PreflightError,
                                        'sampler_base_model_mismatch'):
                preflight.bind_sampler_checkpoint(
                    root, path, sampler_path=sampler_path,
                    service_client=wrong_service, optimizer_steps=1,
                    **hashes)
            self.assertFalse(path.exists())
            self.assertEqual(wrong_service.paths, [sampler_path])
            service = FakeCheckpointService()
            public = preflight.bind_sampler_checkpoint(
                root, path, sampler_path=sampler_path,
                service_client=service, optimizer_steps=1, **hashes)
            self.assertEqual(service.paths, [sampler_path])
            self.assertNotIn('tinker://', json.dumps(public))
            self.assertEqual(public['checkpoint_path_sha256'],
                             preflight.sha256(sampler_path.encode()))
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(path.read_text())['sampler_path'],
                             sampler_path)
            outside_service = FakeCheckpointService()
            with self.assertRaisesRegex(preflight.PreflightError,
                                        'private_checkpoint_path_required'):
                preflight.bind_sampler_checkpoint(
                    root, root / 'public.json', sampler_path=sampler_path,
                    service_client=outside_service, optimizer_steps=1,
                    **hashes)
            self.assertEqual(outside_service.paths, [])

    def test_training_telemetry_is_private_sequential_and_tamper_evident(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            work = root / 'work'
            work.mkdir()
            path = work / 'training-events.private.jsonl'
            journal = preflight.TrainingTelemetry(
                root, path, plan_sha256='a' * 64,
                campaign_intent_sha256='b' * 64,
                train_data_sha256='c' * 64,
                action_bundle_sha256='d' * 64,
                catalog_sha256='e' * 64)
            pricing = preflight.official_catalog(
                lambda url: json.dumps([MODEL_ROW]).encode())[1]
            event = journal.append_step(
                step=1, work_sha256='f' * 64, training_tokens=1000,
                prefill_tokens=0, sample_tokens=0,
                elapsed_seconds=2.5, pricing=pricing)
            self.assertEqual(event['usage']['published_rate_nominal_usd'],
                             '0.004103')
            self.assertIsNone(event['usage']['provider_billed_usd'])
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
            with self.assertRaisesRegex(preflight.PreflightError,
                                        'training_step_not_sequential'):
                journal.append_step(
                    step=1, work_sha256='f' * 64, training_tokens=1000,
                    prefill_tokens=0, sample_tokens=0,
                    elapsed_seconds=2.5, pricing=pricing)
            content = path.read_text().replace('0.004103', '0.004104')
            path.write_text(content)
            with self.assertRaisesRegex(preflight.PreflightError,
                                        'telemetry_hash_chain_broken'):
                journal.append_step(
                    step=2, work_sha256='f' * 64, training_tokens=1000,
                    prefill_tokens=0, sample_tokens=0,
                    elapsed_seconds=2.5, pricing=pricing)


if __name__ == '__main__':
    unittest.main()
