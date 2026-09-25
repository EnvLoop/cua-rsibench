"""Offline-render a quarantined GUI episode; optional one-step checkpoint smoke.

The default path makes no Tinker service call. Paid mode is explicitly opt-in,
one-shot, and trains only on quarantined public task 777. It never evaluates
the checkpoint on that source task or claims a held-out improvement.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import sys
import time

from cursibench.gui_sft_data_v1 import (
    MODEL, build_tinker_datums, train_exclusion_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
PINNED_ACTION_ONLY_EPISODE_SHA256 = '8ae9143ab98ea96572a19c3e5cd4a8a529f5dc320cb61044a57acddc2c5b22f0'
PINNED_PROCESSOR_SHA256 = 'f30d048e3fda7839c8b3e0e9b8559e5f4581ce7d4f9b15ccd893b9bf5c6ac45b'
PINNED_TOKENIZER_SHA256 = '420ab4b96193b4325156f56cd7c3876a8a0d46f515fe4f711a7a6bf5553bf8fa'
PUBLISHED_TRAIN_USD_PER_M = Decimal('4.103')
PUBLISHED_PREFILL_USD_PER_M = Decimal('1.86')
PUBLISHED_SAMPLE_USD_PER_M = Decimal('5.595')
PUBLISHED_RATE_CAP_USD = Decimal('0.25')
MAX_SAMPLE_TOKENS = 96


def nominal_usd(train_tokens: int, prefill_tokens: int,
                output_tokens: int) -> str:
    return str((Decimal(train_tokens) * PUBLISHED_TRAIN_USD_PER_M +
                Decimal(prefill_tokens) * PUBLISHED_PREFILL_USD_PER_M +
                Decimal(output_tokens) * PUBLISHED_SAMPLE_USD_PER_M) /
               Decimal(1_000_000))


def paid_preflight(receipt: dict) -> dict:
    identity = receipt.get('renderer_identity') or {}
    if (receipt.get('episode_sha256') != PINNED_ACTION_ONLY_EPISODE_SHA256 or
            receipt.get('train_only') is not True or
            receipt.get('train_task_id') != 777 or
            receipt.get('train_template_id') != 742 or
            receipt.get('datum_count') != 36 or
            receipt.get('paid_provider_calls') != 0 or
            identity.get('processor_config_sha256') != PINNED_PROCESSOR_SHA256 or
            identity.get('tokenizer_vocabulary_sha256') != PINNED_TOKENIZER_SHA256 or
            receipt.get('tinker_sdk_version') != '0.30.1'):
        raise ValueError('paid_dataset_or_renderer_contract_mismatch')
    supervised = receipt.get('first_supervised_tokens')
    prompt = receipt.get('first_prompt_tokens')
    if (type(supervised) is not int or type(prompt) is not int or
            not 0 < prompt < supervised <= 32_768):
        raise ValueError('paid_token_length_contract_mismatch')
    reservation = Decimal(nominal_usd(supervised, prompt, MAX_SAMPLE_TOKENS))
    if reservation > PUBLISHED_RATE_CAP_USD:
        raise ValueError('published_rate_reservation_exceeds_cap')
    return {'first_supervised_tokens': supervised,
            'first_prompt_tokens': prompt,
            'max_sample_tokens': MAX_SAMPLE_TOKENS,
            'max_published_rate_reservation_usd': str(reservation),
            'published_rate_cap_usd': str(PUBLISHED_RATE_CAP_USD),
            'provider_invoice_usd': None}


def write_new(path: Path, value) -> None:
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    path.chmod(0o600)


def run(episode: Path, out: Path, *, paid_one_step: bool = False) -> dict:
    episode, out = Path(episode).resolve(), Path(out).resolve()
    if not out.is_relative_to(ROOT / 'work') or out.exists():
        raise ValueError('output_requires_fresh_ignored_work_path')
    out.mkdir(mode=0o700, parents=True)
    out.chmod(0o700)
    rendered = build_tinker_datums(episode)
    receipt = {**rendered.receipt,
               'train_exclusion_manifest_sha256': hashlib.sha256(
                   json.dumps(train_exclusion_manifest(), sort_keys=True).encode()).hexdigest(),
               'paid_one_step_requested': bool(paid_one_step),
               'optimizer_steps_completed': 0, 'checkpoint_saved': False,
               'checkpoint_sampled': False, 'provider_invoice_usd': None}
    write_new(out / 'receipt.json', receipt)
    if not paid_one_step:
        return receipt
    receipt['paid_preflight'] = paid_preflight(receipt)
    if not os.environ.get('TINKER_API_KEY'):
        raise ValueError('tinker_key_missing_no_paid_dispatch')
    write_new(out / 'paid-intent.private.json', {
        'model': MODEL, 'source_task_id': 777, 'datum_count': 1,
        'episode_sha256': PINNED_ACTION_ONLY_EPISODE_SHA256,
        'published_rate_reservation_usd':
            receipt['paid_preflight']['max_published_rate_reservation_usd'],
        'optimizer_steps_limit': 1, 'created_at': time.time(),
        'single_dispatch_only': True,
    })
    import tinker
    from tinker import types
    service = tinker.ServiceClient(user_metadata={
        'purpose': 'magento-price777-gui-sft-checkpoint-smoke-v1',
        'split': 'train', 'source_task_id': '777'})
    status = 'errored'
    try:
        trainer = service.create_lora_training_client(base_model=MODEL, rank=8, seed=23)
        receipt['paid_provider_calls'] = 1
        write_new(out / 'forward-backward-intent.private.json', {
            'source_task_id': 777, 'datum_count': 1,
            'provider_dispatch_attempts': 1,
            'state': 'may_have_started_do_not_retry_automatically',
        })
        backward = trainer.forward_backward([rendered.datums[0]], 'cross_entropy').result(timeout=300)
        trainer.optim_step(types.AdamParams(learning_rate=1e-4)).result(timeout=300)
        receipt['optimizer_steps_completed'] = 1
        receipt['loss_metrics_available'] = bool(getattr(backward, 'metrics', {}))
        write_new(out / 'after-step.private.json', receipt)
        checkpoint = trainer.save_weights_for_sampler('price777-gui-sft-smoke').result(timeout=300)
        write_new(out / 'checkpoint.private.json', {'path': checkpoint.path})
        receipt['checkpoint_saved'] = True
        sampler = service.create_sampling_client(model_path=checkpoint.path)
        if sampler.get_base_model() != MODEL:
            raise RuntimeError('checkpoint_base_model_mismatch')
        sample = sampler.sample(prompt=rendered.prompts[0], num_samples=1,
            sampling_params=types.SamplingParams(max_tokens=MAX_SAMPLE_TOKENS, temperature=0,
                seed=23, stop=rendered.stop_sequences)).result(timeout=300)
        tokens = sample.sequences[0].tokens
        receipt.update(checkpoint_sampled=True, paid_provider_calls=2,
                       sample_token_count=len(tokens),
                       sample_token_sha256=hashlib.sha256(str(tokens).encode()).hexdigest(),
                       measured_rendered_usage={
                           'training_input_tokens': rendered.supervised_token_lengths[0],
                           'sampling_prompt_tokens': rendered.prompt_token_lengths[0],
                           'sampling_output_tokens': len(tokens),
                           'provider_billed_tokens_known': False,
                       },
                       nominal_published_rate_subtotal_usd=nominal_usd(
                           rendered.supervised_token_lengths[0],
                           rendered.prompt_token_lengths[0], len(tokens)),
                       checkpoint_path_published=False,
                       trained_improvement_measured=False)
        status = 'success'
        return receipt
    finally:
        write_new(out / 'final.private.json', receipt)
        service.close(status).result(timeout=30)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--episode', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--paid-one-step', action='store_true')
    args = parser.parse_args()
    try:
        result = run(args.episode, args.out, paid_one_step=args.paid_one_step)
        print(json.dumps({key: result.get(key) for key in (
            'model', 'datum_count', 'max_supervised_tokens', 'min_assistant_loss_weight_sum',
            'paid_provider_calls', 'optimizer_steps_completed', 'checkpoint_sampled')}))
    except Exception as exc:
        print(json.dumps({'status': 'failed', 'failure_type': type(exc).__name__}),
              file=sys.stderr)
        raise SystemExit(1)
