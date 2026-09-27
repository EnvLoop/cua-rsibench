"""Read-only Tinker campaign preflight and private checkpoint evidence helpers.

This module cannot train, sample, inspect a final task, or authorize dispatch.
The six-cell pre-campaign gate and dollar ledger remain separate prerequisites.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import fcntl
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import time
import urllib.request


MODEL = 'Qwen/Qwen3.8-27B'
CATALOG_URL = 'https://tinker-docs.thinkingmachines.ai/tinker/models.json'
ACTION_FILES = (
    'src/cursibench/scale_action_contract.py',
    'src/cursibench/scale_action_output_v062.py',
    'src/cursibench/scale_action_output_v064.py',
    'src/cursibench/scale_action_output_v065.py',
    'src/cursibench/scale_vision_proxy.py',
)
HASH = re.compile(r'[0-9a-f]{64}\Z')
SAMPLER_PATH = re.compile(r'tinker://[^\s/]+/sampler_weights/[^\s/]+\Z')


class PreflightError(ValueError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=False, allow_nan=False) + '\n').encode()


def require(condition: bool, code: str) -> None:
    if not condition:
        raise PreflightError(code)


def exact_hash(value: object, label: str) -> str:
    require(isinstance(value, str) and HASH.fullmatch(value) is not None,
            f'{label}_sha256_invalid')
    return value


def private_write_new(path: Path, data: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def private_output_dir(repo_root: Path, output_dir: Path) -> Path:
    root = repo_root.resolve()
    work = root / 'work'
    require(not work.is_symlink(), 'private_work_symlink')
    target = output_dir.absolute().parent.resolve() / output_dir.name
    require(target.is_relative_to(work) and not target.exists() and
            not target.is_symlink(), 'private_output_required')
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    target.mkdir(mode=0o700)
    target.chmod(0o700)
    return target


def official_catalog(fetcher=None) -> tuple[bytes, dict]:
    if fetcher is None:
        def fetcher(url):
            request = urllib.request.Request(url, headers={
                'User-Agent': 'EnvLoop-read-only-model-preflight/1.0'})
            with urllib.request.urlopen(request, timeout=20) as response:
                require(response.url == CATALOG_URL, 'catalog_redirected')
                return response.read(1_000_001)
    raw = fetcher(CATALOG_URL)
    require(isinstance(raw, bytes) and 0 < len(raw) <= 1_000_000,
            'catalog_size_invalid')
    try:
        rows = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise PreflightError('catalog_json_invalid') from None
    require(isinstance(rows, list), 'catalog_shape_invalid')
    matches = [row for row in rows if isinstance(row, dict) and
               row.get('tinker_id') == MODEL]
    require(len(matches) == 1 and 'Vision' in str(matches[0].get('type', '')),
            'exact_vision_model_not_priced')
    row = matches[0]
    rates = {}
    for kind in ('prefill', 'cached_prefill', 'sample', 'train'):
        value = row.get(kind)
        require(isinstance(value, str) and value.startswith('$'),
                f'{kind}_rate_invalid')
        try:
            amount = Decimal(value[1:])
        except InvalidOperation:
            raise PreflightError(f'{kind}_rate_invalid') from None
        require(amount.is_finite() and amount > 0, f'{kind}_rate_invalid')
        rates[kind] = str(amount)
    return raw, {'model': MODEL, 'type': row['type'],
                 'context': row.get('context'),
                 'usd_per_million_tokens': rates,
                 'published_models_json_sha256': sha256(raw),
                 'billing_basis': 'published_rate_not_invoice'}


def action_bundle(repo_root: Path) -> dict:
    root = repo_root.resolve()
    files = {}
    for relative in ACTION_FILES:
        path = root / relative
        require(path.is_file() and not path.is_symlink(),
                'action_bundle_file_missing')
        files[relative] = sha256(path.read_bytes())
    from .scale_action_output_v065 import MODEL_ACTION_CONTRACT, OUTPUT_VERSION
    from .scale_vision_proxy import MODEL as PROXY_MODEL
    from .scale_vision_proxy import PROCESSOR, RENDERER
    require(OUTPUT_VERSION == 'scale-action-output-v0.6.5' and
            PROXY_MODEL == MODEL and
            'visible-ref' not in MODEL_ACTION_CONTRACT,
            'action_prompt_contract_mismatch')
    bundle = {'files': files, 'output_version': OUTPUT_VERSION,
              'model_prompt_sha256': sha256(MODEL_ACTION_CONTRACT.encode()),
              'model': MODEL, 'renderer': RENDERER,
              'image_processor': PROCESSOR}
    return {**bundle, 'bundle_sha256': sha256(canonical(bundle))}


def desktop_boundary(repo_root: Path) -> dict:
    root = repo_root.resolve()
    sources = {
        'guest': root / 'docs/evidence/native-wdi-guest-content-identity-2026-09-27.json',
        'profile': root / 'docs/evidence/native-wdi-profile-drift-2026-09-27.json',
    }
    values = {}
    digests = {}
    for name, path in sources.items():
        require(path.is_file() and not path.is_symlink(),
                'desktop_attestation_receipt_missing')
        raw = path.read_bytes()
        digests[name] = sha256(raw)
        values[name] = json.loads(raw)
    guest, profile = values['guest'], values['profile']
    return {'receipt_sha256': digests,
            'scoped_guest_content_passed':
                guest.get('scoped_guest_content_identity_passed') is True,
            'provider_image_digest_available':
                guest.get('provider_image_digest_available') is True,
            'canonical_profile_stable':
                profile.get('canonical_profile_stable_across_two_probes') is True,
            'raw_profile_stable':
                profile.get('raw_profile_stable_across_two_probes') is True,
            'full_image_profile_freeze_passed':
                profile.get('full_image_profile_freeze_gate_passed') is True,
            'historical_controls_use_new_attestation': False}


def provider_capabilities(service_factory=None) -> dict:
    """Authenticate via the SDK and make only one read-only capabilities call."""
    if service_factory is None:
        import tinker
        service_factory = tinker.ServiceClient
    started = time.monotonic()
    service = service_factory(user_metadata={
        'purpose': 'envloop-full-study-read-only-tinker-preflight',
        'split': 'none'})
    status = 'errored'
    try:
        capabilities = service.get_server_capabilities()
        rows = [row for row in capabilities.supported_models
                if getattr(row, 'model_name', None) == MODEL]
        require(len(rows) == 1, 'exact_model_not_in_account_capabilities')
        model = rows[0]
        require(model.trainable is True and model.sampleable is True and
                type(model.max_context_length) is int and
                model.max_context_length >= 32_768,
                'exact_model_not_trainable_and_sampleable')
        status = 'success'
        result = {'authenticated_capabilities': True,
                  'exact_model_trainable': True,
                  'exact_model_sampleable': True,
                  'max_context_length': model.max_context_length,
                  'read_only_provider_call_count': 1,
                  'training_or_sampling_provider_calls': 0}
    finally:
        service.close(status).result(timeout=30)
    result['provider_session_closed'] = True
    result['elapsed_seconds'] = round(time.monotonic() - started, 3)
    return result


def run_read_only(repo_root: Path, output_dir: Path, *, fetcher=None,
                  service_factory=None) -> dict:
    """Capture private reproducible evidence; never attempt campaign dispatch."""
    root = repo_root.resolve()
    catalog_raw, pricing = official_catalog(fetcher)
    bundle = action_bundle(root)
    desktop = desktop_boundary(root)
    output = private_output_dir(root, output_dir)
    provider = provider_capabilities(service_factory)
    receipt = {
        'schema': 'cua-full-study-tinker-preflight-v1',
        'scope': 'read_only_train_candidate_preflight',
        'model': MODEL,
        'tinker_sdk_version': importlib.metadata.version('tinker'),
        'catalog': pricing, 'action_bundle': bundle,
        'desktop_attestation_snapshot': desktop,
        'provider': provider,
        'six_cell_pre_campaign_plan_verified': False,
        'cross_cell_v065_hash_freeze_verified': False,
        'provider_model_weight_snapshot_known': False,
        'provider_available_balance_usd': None,
        'provider_billed_usd': None,
        'campaign_dispatch_authorized': False,
        'researcher_campaigns_started': 0,
        'official_final_results': 0,
    }
    private_write_new(output / 'published-models.private.json', catalog_raw)
    private_write_new(output / 'receipt.private.json', canonical(receipt))
    return receipt


def nominal_token_cost(pricing: dict, *, training_tokens: int,
                       prefill_tokens: int, sample_tokens: int) -> dict:
    """A published-rate estimate, explicitly separate from provider billing."""
    counts = {'training_tokens': training_tokens,
              'prefill_tokens': prefill_tokens,
              'sample_tokens': sample_tokens}
    require(all(type(value) is int and value >= 0 for value in counts.values()),
            'invalid_local_token_count')
    rates = pricing['usd_per_million_tokens']
    amount = sum((Decimal(counts[kind + '_tokens']) * Decimal(rates[rate])
                  for kind, rate in (('training', 'train'),
                                     ('prefill', 'prefill'),
                                     ('sample', 'sample'))), Decimal(0)) / Decimal(1_000_000)
    return {**counts, 'published_rate_nominal_usd': str(amount),
            'provider_billed_tokens': None, 'provider_billed_usd': None,
            'invoice_usd': None}


class TrainingTelemetry:
    """Private hash-chained local token/time events for a future admitted run.

    This cannot authorize a provider call or settle the dollar ledger. It
    records measured local counts and published-rate nominal cost only.
    """

    def __init__(self, repo_root: Path, path: Path, *, plan_sha256: str,
                 campaign_intent_sha256: str, train_data_sha256: str,
                 action_bundle_sha256: str, catalog_sha256: str):
        root = repo_root.resolve()
        target = path.absolute().parent.resolve() / path.name
        require(target.is_relative_to(root / 'work') and
                not target.is_symlink(), 'private_telemetry_path_required')
        self.path = target
        self.lock_path = target.parent / ('.' + target.name + '.lock')
        self.bindings = {
            'plan_sha256': exact_hash(plan_sha256, 'plan'),
            'campaign_intent_sha256': exact_hash(
                campaign_intent_sha256, 'campaign_intent'),
            'train_data_sha256': exact_hash(train_data_sha256, 'train_data'),
            'action_bundle_sha256': exact_hash(action_bundle_sha256, 'action_bundle'),
            'catalog_sha256': exact_hash(catalog_sha256, 'catalog'),
        }
        header = {'schema': 'cua-full-study-tinker-telemetry-v1',
                  'kind': 'header', 'model': MODEL, **self.bindings,
                  'cost_basis': 'published_nominal_only',
                  'provider_invoice_usd': None, 'previous': None}
        private_write_new(self.path, canonical({
            **header, 'hash': sha256(canonical(header))}))

    def _rows(self) -> list[dict]:
        rows = [json.loads(line) for line in self.path.read_bytes().splitlines()]
        require(rows and rows[0].get('kind') == 'header' and
                all(rows[0].get(key) == value for key, value in self.bindings.items()),
                'telemetry_header_changed')
        previous = None
        for row in rows:
            core = {key: value for key, value in row.items() if key != 'hash'}
            require(row.get('previous') == previous and
                    row.get('hash') == sha256(canonical(core)),
                    'telemetry_hash_chain_broken')
            previous = row['hash']
        return rows

    def append_step(self, *, step: int, work_sha256: str,
                    training_tokens: int, prefill_tokens: int,
                    sample_tokens: int, elapsed_seconds: float,
                    pricing: dict) -> dict:
        require(type(step) is int and step > 0 and
                type(elapsed_seconds) in (int, float) and
                0 <= elapsed_seconds <= 57_600,
                'training_step_runtime_invalid')
        exact_hash(work_sha256, 'step_work')
        usage = nominal_token_cost(pricing, training_tokens=training_tokens,
                                   prefill_tokens=prefill_tokens,
                                   sample_tokens=sample_tokens)
        require(training_tokens > 0, 'training_step_tokens_missing')
        require(not self.lock_path.is_symlink(), 'telemetry_lock_symlink')
        lock_descriptor = os.open(self.lock_path,
                                  os.O_WRONLY | os.O_CREAT, 0o600)
        with os.fdopen(lock_descriptor, 'w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            rows = self._rows()
            last_step = sum(row['kind'] == 'optimizer_step' for row in rows)
            require(step == last_step + 1, 'training_step_not_sequential')
            core = {'schema': 'cua-full-study-tinker-telemetry-v1',
                    'kind': 'optimizer_step', 'step': step,
                    'work_sha256': work_sha256,
                    'elapsed_seconds': elapsed_seconds,
                    'usage': usage, 'previous': rows[-1]['hash']}
            row = {**core, 'hash': sha256(canonical(core))}
            descriptor = os.open(self.path, os.O_WRONLY | os.O_APPEND)
            with os.fdopen(descriptor, 'ab') as stream:
                stream.write(canonical(row))
                stream.flush()
                os.fsync(stream.fileno())
            return row


def bind_sampler_checkpoint(repo_root: Path, private_path: Path, *,
                            sampler_path: str, sampler_client,
                            plan_sha256: str,
                            campaign_intent_sha256: str, train_data_sha256: str,
                            action_bundle_sha256: str, optimizer_steps: int,
                            usage_receipt_sha256: str) -> dict:
    """Bind an actual sampler checkpoint after a future frozen training run.

    The account-specific path is only written to a private mode-0600 file.
    The caller supplies the provider's SamplingClient created from this exact
    path. We read its base model; no caller-provided model claim is accepted.
    """
    require(isinstance(sampler_path, str) and
            SAMPLER_PATH.fullmatch(sampler_path) is not None,
            'sampler_checkpoint_path_invalid')
    observed_base_model = sampler_client.get_base_model()
    require(observed_base_model == MODEL, 'sampler_base_model_mismatch')
    for label, value in (('plan', plan_sha256),
                         ('campaign_intent', campaign_intent_sha256),
                         ('train_data', train_data_sha256),
                         ('action_bundle', action_bundle_sha256),
                         ('usage_receipt', usage_receipt_sha256)):
        exact_hash(value, label)
    require(type(optimizer_steps) is int and optimizer_steps > 0,
            'optimizer_steps_missing')
    private = {'schema': 'cua-full-study-sampler-checkpoint-binding-v1',
               'model': MODEL, 'sampler_path': sampler_path,
               'observed_base_model': observed_base_model,
               'plan_sha256': plan_sha256,
               'campaign_intent_sha256': campaign_intent_sha256,
               'train_data_sha256': train_data_sha256,
               'action_bundle_sha256': action_bundle_sha256,
               'optimizer_steps': optimizer_steps,
               'usage_receipt_sha256': usage_receipt_sha256}
    root = repo_root.resolve()
    target = private_path.absolute().parent.resolve() / private_path.name
    require(target.is_relative_to(root / 'work') and
            not target.is_symlink(),
            'private_checkpoint_path_required')
    require(not target.exists() and not target.is_symlink(),
            'checkpoint_binding_already_exists')
    private_write_new(target, canonical(private))
    return {'schema': 'cua-full-study-sampler-checkpoint-public-binding-v1',
            'model': MODEL,
            'checkpoint_path_sha256': sha256(sampler_path.encode()),
            'private_binding_sha256': sha256(canonical(private)),
            'plan_sha256': plan_sha256,
            'campaign_intent_sha256': campaign_intent_sha256,
            'train_data_sha256': train_data_sha256,
            'action_bundle_sha256': action_bundle_sha256,
            'optimizer_steps': optimizer_steps,
            'provider_weight_bytes_sha256': None,
            'checkpoint_sampled_and_scored': False}
